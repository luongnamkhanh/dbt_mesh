"""
DAMA Reconciliation Scanner - DEV_CUR vs DEV_KM

This DAG reconciles data between:
- Source: dev_cur (Delta Lake - curated tables)
- Target: dev_km (Oracle - KM DWH tables)

Table Mappings:
- arr_turnover_smy (dev_cur) → FT_CUR_ARR_TURNOVER_SMY (dev_km)
- asset_arr_interest_smy (dev_cur) → FT_CUR_ASSET_ARR_INTEREST_SMY (dev_km)
- ft_t24_cust_info (dev_cur) → ft_t24_cust_info (dev_km)
- ft_t24_deposit_ca (dev_cur) → ft_t24_deposit_ca (dev_km)
- ft_t24_deposit_td (dev_cur) → ft_t24_deposit_td (dev_km)
- ft_t24_ld_contract (dev_cur) → ft_t24_ld_contract (dev_km)
- ft_t24_ld_disbursement (dev_cur) → ft_t24_ld_disbursement (dev_km)

DAMA Dimensions Covered:
- Completeness: Row counts, NULL counts on primary keys
- Uniqueness: Primary key duplicate detection
- Consistency: MINUS comparison (dev_cur EXCEPT dev_km)

Output: reconcile_dev_cur_km_{YYYYMMDD_HHMMSS}.csv
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
import io
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import boto3

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.models.param import Param

logger = logging.getLogger(__name__)


def install_pyhive_dependencies(verbose: bool = False):
    """Install PyHive and dependencies from MWAA S3 bucket at runtime."""
    import subprocess

    s3_deps_path = "s3://aws-sg-nedp-uat-mwaa/dependencies/"
    local_wheels_dir = "/tmp/dbt_wheels_operator"

    if verbose:
        logger.info("Installing PyHive and dependencies from S3...")

    try:
        subprocess.run(["mkdir", "-p", local_wheels_dir], check=True)
        subprocess.run(
            ["aws", "s3", "sync", s3_deps_path, local_wheels_dir],
            capture_output=True, text=True, check=True
        )
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--find-links", local_wheels_dir,
            "--no-index", "--upgrade", "--quiet",
            "PyHive", "thrift", "thrift_sasl", "pure-sasl", "six", "future"
        ])
        if verbose:
            logger.info("PyHive dependencies installed")

    except subprocess.CalledProcessError as e:
        if verbose:
            logger.warning(f"S3 install failed: {e}, trying PyPI fallback...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--quiet",
            "PyHive", "thrift", "thrift_sasl", "pure-sasl", "six", "future"
        ])


# ========================================
# Table Mapping Configuration
# ========================================

# Target table prefix for dev_km (Oracle) - only for non-ft_ tables
TARGET_TABLE_PREFIX = 'FT_CUR_'

# Table-specific WHERE condition configuration
# Maps source table names to their partition column patterns
TABLE_WHERE_CONDITIONS = {
    # Fact Snapshot tables: DS_SNAPSHOT_DT for both
    'arr_turnover_smy': {'source_col': 'DS_SNAPSHOT_DT', 'target_col': 'DS_SNAPSHOT_DT', 'type': 'Fact Snapshot'},
    'asset_arr_interest_smy': {'source_col': 'DS_SNAPSHOT_DT', 'target_col': 'DS_SNAPSHOT_DT', 'type': 'Fact Snapshot'},

    # Fact Append tables: DS_DT for source, SYM_RUN_DATE for target
    'ft_t24_cust_info': {'source_col': 'DS_DT', 'target_col': 'SYM_RUN_DATE', 'type': 'Fact Append'},

    # SCD2 tables: Full table for source, SYM_RUN_DATE for target
    'ft_t24_deposit_ca': {'source_col': None, 'target_col': 'SYM_RUN_DATE', 'type': 'SCD2'},

    # SCD4A tables: DS_SNAPSHOT_DT for both
    'ft_t24_deposit_td': {'source_col': 'DS_SNAPSHOT_DT', 'target_col': 'DS_SNAPSHOT_DT', 'type': 'SCD4A'},
    'ft_t24_ld_contract': {'source_col': 'DS_SNAPSHOT_DT', 'target_col': 'DS_SNAPSHOT_DT', 'type': 'SCD4A'},
    'ft_t24_ld_disbursement': {'source_col': 'DS_SNAPSHOT_DT', 'target_col': 'DS_SNAPSHOT_DT', 'type': 'SCD4A'},
}


# ========================================
# WHERE Clause Builder Functions
# ========================================

def build_fact_append_where_clauses(partition_value: str) -> tuple:
    """Build WHERE clauses for Fact Append tables

    Source: ds_dt (lowercase with backticks)
    Target: SYM_RUN_DATE (technical date field in KM)

    Args:
        partition_value: Date in YYYY-MM-DD format

    Returns:
        (source_where, target_where) tuple
    """
    source_where = f"`ds_dt` = '{partition_value}'" if partition_value else ""
    target_where = f"date_trunc('day', SYM_RUN_DATE) = '{partition_value}'" if partition_value else ""
    return source_where, target_where


def build_fact_snapshot_where_clauses(partition_value: str) -> tuple:
    """Build WHERE clauses for Fact Snapshot tables

    Both source and target use ds_snapshot_dt/DS_SNAPSHOT_DT

    Args:
        partition_value: Date in YYYY-MM-DD format

    Returns:
        (source_where, target_where) tuple
    """
    # Source (Spark/Delta): lowercase with backticks
    source_where = f"`ds_snapshot_dt` = '{partition_value}'" if partition_value else ""
    # Target (Oracle via Spark JDBC): uppercase with date_trunc
    target_where = f"date_trunc('day', DS_SNAPSHOT_DT) = '{partition_value}'" if partition_value else ""
    return source_where, target_where


def build_scd1_where_clauses(partition_value: str) -> tuple:
    """Build WHERE clauses for SCD1 tables

    Source: Full table (no filter)
    Target: SYM_RUN_DATE (technical date field in KM)

    Args:
        partition_value: Date in YYYY-MM-DD format

    Returns:
        (source_where, target_where) tuple
    """
    source_where = ""  # Full table scan
    target_where = f"date_trunc('day', SYM_RUN_DATE) = '{partition_value}'" if partition_value else ""
    return source_where, target_where


def build_scd2_where_clauses(partition_value: str) -> tuple:
    """Build WHERE clauses for SCD2 tables

    Source: Full table (no filter)
    Target: SYM_RUN_DATE (technical date field in KM)

    Args:
        partition_value: Date in YYYY-MM-DD format

    Returns:
        (source_where, target_where) tuple
    """
    source_where = ""  # Full table scan
    target_where = f"date_trunc('day', SYM_RUN_DATE) = '{partition_value}'" if partition_value else ""
    return source_where, target_where


def build_scd4a_where_clauses(partition_value: str) -> tuple:
    """Build WHERE clauses for SCD4A tables

    Both source and target use ds_snapshot_dt/DS_SNAPSHOT_DT

    Args:
        partition_value: Date in YYYY-MM-DD format

    Returns:
        (source_where, target_where) tuple
    """
    # Source (Spark/Delta): lowercase with backticks
    source_where = f"`ds_snapshot_dt` = '{partition_value}'" if partition_value else ""
    # Target (Oracle via Spark JDBC): uppercase with date_trunc
    target_where = f"date_trunc('day', DS_SNAPSHOT_DT) = '{partition_value}'" if partition_value else ""
    return source_where, target_where


def get_where_clauses_for_table(table_name: str, partition_value: str) -> tuple:
    """Get WHERE clauses for a specific table based on its configuration

    Args:
        table_name: Source table name (lowercase)
        partition_value: Date in YYYY-MM-DD format

    Returns:
        (source_where, target_where) tuple

    Raises:
        Warning if table not found in configuration (returns empty WHERE clauses)
    """
    if table_name not in TABLE_WHERE_CONDITIONS:
        logger.warning(f"Table '{table_name}' not found in WHERE condition configuration. Using empty WHERE clauses.")
        return "", ""

    config = TABLE_WHERE_CONDITIONS[table_name]
    table_type = config['type']

    # Route to appropriate builder function based on table type
    if table_type == 'Fact Append':
        return build_fact_append_where_clauses(partition_value)
    elif table_type == 'Fact Snapshot':
        return build_fact_snapshot_where_clauses(partition_value)
    elif table_type == 'SCD1':
        return build_scd1_where_clauses(partition_value)
    elif table_type == 'SCD2':
        return build_scd2_where_clauses(partition_value)
    elif table_type == 'SCD4A':
        return build_scd4a_where_clauses(partition_value)
    else:
        logger.warning(f"Unknown table type '{table_type}' for table '{table_name}'. Using empty WHERE clauses.")
        return "", ""


# ========================================
# Reconciliation Scanner Class
# ========================================

class ReconciliationScannerDevCurKm:
    """
    DAMA-aligned reconciliation scanner for dev_cur vs dev_km.

    Compares Delta Lake tables (dev_cur) against Oracle tables (dev_km).
    """

    def __init__(
        self,
        source_catalog_name: str = 'dev_cur',
        target_catalog_name: str = 'dev_km',
        target_schema_name: str = 'KMDW',
        thrift_host: str = 'localhost',
        thrift_port: int = 10001,
        thrift_user: str = 'hadoop',
        output_bucket: str = 'aws-sg-nedp-uat-mwaa',
        output_prefix: str = 'artifacts/reconciliation',
        num_threads: int = 5,
        batch_size: int = 5,
        socket_timeout_seconds: int = 300,
        thread_timeout_seconds: int = 600,
        partition_value: Optional[str] = None,
        table_limit: Optional[int] = None,
        table_patterns: List[str] = None,
        fallback_pk_column: str = 'id',
        # Metric toggles
        enable_completeness: bool = True,
        enable_uniqueness: bool = True,
        enable_minus: bool = True,
        enable_schema: bool = True,
        verbose: bool = False,
        # Large table optimization
        large_table_threshold: int = 1_000_000,
        skip_minus_large_tables: bool = True,
    ):
        # Source: dev_cur (Delta Lake - 2-level namespace: catalog.table)
        self.source_catalog_name = source_catalog_name
        # Target: dev_km (Oracle JDBC - 3-level namespace: catalog.schema.table)
        self.target_catalog_name = target_catalog_name
        self.target_schema_name = target_schema_name
        self.thrift_host = thrift_host
        self.thrift_port = thrift_port
        self.thrift_user = thrift_user
        self.output_bucket = output_bucket
        self.output_prefix = output_prefix.rstrip('/')
        self.num_threads = num_threads
        self.batch_size = batch_size
        self.socket_timeout_seconds = socket_timeout_seconds
        self.thread_timeout_seconds = thread_timeout_seconds
        self.partition_value = partition_value
        self.table_limit = table_limit
        self.table_patterns = table_patterns or []  # Empty = scan all tables from source catalog
        self.fallback_pk_column = fallback_pk_column
        self.enable_completeness = enable_completeness
        self.enable_uniqueness = enable_uniqueness
        self.enable_minus = enable_minus
        self.enable_schema = enable_schema
        self.verbose = verbose
        self.large_table_threshold = large_table_threshold
        self.skip_minus_large_tables = skip_minus_large_tables
        self.extraction_timestamp = datetime.now().isoformat()
        self.run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_filename = f'reconcile_dev_cur_km_{self.run_timestamp}.csv'

        logger.info(f"ReconciliationScanner: {self.source_catalog_name} vs {self.target_catalog_name}")
        logger.info(f"Output: s3://{self.output_bucket}/{self.output_prefix}/{self.output_filename}")

        if self.verbose:
            logger.info(f"Source Catalog: {self.source_catalog_name} (Delta Lake, 2-level: catalog.table)")
            logger.info(f"Target Catalog: {self.target_catalog_name}.{self.target_schema_name} (Oracle, 3-level: catalog.schema.table)")
            logger.info(f"Thrift: {self.thrift_host}:{self.thrift_port}")
            logger.info(f"Partition Value: {self.partition_value or 'None (full table scan)'}")
            logger.info(f"Tables to reconcile: {self.table_patterns}")

    def get_connection(self):
        """Get Spark Thrift server connection"""
        from pyhive import hive

        start = time.time()
        if self.verbose:
            logger.info(f"Connecting to Thrift server: {self.thrift_host}:{self.thrift_port}")
        conn = hive.Connection(
            host=self.thrift_host,
            port=self.thrift_port,
            username=self.thrift_user,
            auth='NONE',
            database='default'
        )
        if self.verbose:
            logger.info(f"Connected in {time.time() - start:.2f}s")
        return conn

    def get_tables_from_source_catalog(self, cursor) -> List[str]:
        """Discover all tables from source catalog (dev_cur).

        Returns list of table names from the source catalog.
        """
        query = f"SHOW TABLES IN {self.source_catalog_name}"
        if self.verbose:
            logger.info(f"Discovering tables: {query}")

        rows = self.run_query_fetchall(cursor, query)
        if not rows:
            return []

        # SHOW TABLES returns: (namespace, tableName, isTemporary)
        tables = [row[1] for row in rows]
        logger.info(f"Found {len(tables)} tables in {self.source_catalog_name}")
        return tables

    def get_tables_to_reconcile(self, cursor) -> List[str]:
        """Get list of tables to reconcile based on table_patterns.

        If table_patterns is empty, discovers all tables from source catalog.
        Returns source table names (dev_cur format: lowercase).
        """
        # Get all tables from source catalog
        all_tables = self.get_tables_from_source_catalog(cursor)

        if not all_tables:
            logger.warning(f"No tables found in source catalog {self.source_catalog_name}")
            return []

        if not self.table_patterns:
            # No patterns specified: use all tables from source catalog
            tables = all_tables
        else:
            # Filter by patterns (exact match or full regex match)
            matched = set()
            for pattern in self.table_patterns:
                for table in all_tables:
                    # Exact match first
                    if table.lower() == pattern.lower():
                        matched.add(table)
                    # Full regex match (use fullmatch, not match)
                    elif re.fullmatch(pattern, table, re.IGNORECASE):
                        matched.add(table)
            tables = [t for t in all_tables if t in matched]
            logger.info(f"Matched {len(tables)} tables from {len(self.table_patterns)} patterns")

        if self.table_limit and self.table_limit > 0:
            tables = tables[:self.table_limit]

        logger.info(f"Tables to reconcile: {len(tables)}")
        if self.verbose:
            for t in tables:
                logger.info(f"  - {t}")
        return tables

    def map_source_to_target_table(self, source_table_name: str) -> str:
        """
        Map source table name (dev_cur) to target table name (dev_km).

        Mapping rules:
        - If table starts with 'ft_': keep the same name (e.g., ft_t24_cust_info → ft_t24_cust_info)
        - Otherwise: add FT_CUR_ prefix and uppercase (e.g., arr_turnover_smy → FT_CUR_ARR_TURNOVER_SMY)
        """
        if source_table_name.lower().startswith('ft_'):
            # Keep the same name for ft_* tables
            return source_table_name.lower()
        else:
            # Add FT_CUR_ prefix and uppercase
            return f"{TARGET_TABLE_PREFIX}{source_table_name.upper()}"

    def run_single_query(self, cursor, query: str, max_retries: int = 2):
        """Execute a single query with retry logic"""
        for attempt in range(max_retries + 1):
            try:
                cursor.execute(query)
                return cursor.fetchone()
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries:
                    logger.warning(f"Query attempt {attempt + 1} failed, retrying: {error_msg}")
                    time.sleep(2 ** attempt)
                else:
                    logger.warning(f"Query failed after {max_retries + 1} attempts: {error_msg}")
                    return None
        return None

    def run_query_fetchall(self, cursor, query: str, max_retries: int = 2):
        """Execute a query and fetch all results"""
        for attempt in range(max_retries + 1):
            try:
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries:
                    logger.warning(f"Query attempt {attempt + 1} failed, retrying: {error_msg}")
                    time.sleep(2 ** attempt)
                else:
                    logger.warning(f"Query failed after {max_retries + 1} attempts: {error_msg}")
                    return None
        return None

    def get_table_columns(self, cursor, full_table_name: str, exclude_cols: set = None) -> List[str]:
        """Get column names from a table using DESCRIBE TABLE"""
        exclude_cols = exclude_cols or set()
        try:
            query = f"DESCRIBE TABLE {full_table_name}"
            rows = self.run_query_fetchall(cursor, query)
            if not rows:
                return []

            columns = []
            for row in rows:
                col_name = row[0]
                if col_name.startswith('#') or col_name == '':
                    break
                if col_name.lower() not in exclude_cols:
                    columns.append(col_name)

            return columns
        except Exception as e:
            logger.warning(f"Failed to get columns for {full_table_name}: {e}")
            return []

    def detect_pk_columns(self, cursor, full_table_name: str) -> List[str]:
        """
        Detect primary key columns from source table schema.

        CUR tables typically have columns ending with '_id' or '_cd' as identifiers.
        Returns a list of likely PK columns, or empty list if none found.
        """
        try:
            # Get table columns
            cols = self.get_table_columns(cursor, full_table_name, set())
            if not cols:
                return []

            # Common PK patterns for CUR tables (prioritized)
            pk_candidates = []

            # First priority: columns ending with '_id' (excluding ds_* columns)
            for col in cols:
                col_lower = col.lower()
                if col_lower.endswith('_id') and not col_lower.startswith('ds_'):
                    pk_candidates.append(col)

            # If we found _id columns, use the first one (usually the main PK)
            if pk_candidates:
                return [pk_candidates[0]]

            # Second priority: columns ending with '_cd'
            for col in cols:
                col_lower = col.lower()
                if col_lower.endswith('_cd') and not col_lower.startswith('ds_'):
                    return [col]

            # Fallback: use first non-technical column
            technical_cols = {'ds_dt', 'ds_etl_processing_ts', 'ds_sym_run_dt',
                              'ds_record_status', 'ds_record_insert_dt', 'ds_record_update_dt',
                              'ds_source_system_cd', 'ds_snapshot_dt'}
            for col in cols:
                if col.lower() not in technical_cols:
                    return [col]

            return []

        except Exception as e:
            logger.warning(f"Failed to detect PK columns for {full_table_name}: {e}")
            return []

    def get_source_row_count(self, cursor, source_table: str, source_where: str = "") -> Dict:
        """Get row count from source (dev_cur) table

        Args:
            cursor: Database cursor
            source_table: Source table name
            source_where: WHERE clause condition (without 'WHERE' keyword)
        """
        full_table_name = f"{self.source_catalog_name}.{source_table}"

        try:
            where_clause = f"WHERE {source_where}" if source_where else ""
            query = f"SELECT COUNT(*) FROM {full_table_name} {where_clause}"
            result = self.run_single_query(cursor, query)

            return {
                'source_row_count': result[0] if result else 0
            }
        except Exception as e:
            logger.error(f"{source_table}: Source row count failed: {e}")
            return {'source_row_count': -1}

    def get_target_row_count(self, cursor, target_table: str, target_where: str = "") -> Dict:
        """Get row count from target (dev_km) table

        Args:
            cursor: Database cursor
            target_table: Target table name
            target_where: WHERE clause condition (without 'WHERE' keyword)
        """
        full_table_name = f"{self.target_catalog_name}.{self.target_schema_name}.{target_table}"

        try:
            where_clause = f"WHERE {target_where}" if target_where else ""
            query = f"SELECT COUNT(*) FROM {full_table_name} {where_clause}"
            result = self.run_single_query(cursor, query)

            return {
                'target_row_count': result[0] if result else 0
            }
        except Exception as e:
            # Try without filter if condition fails
            try:
                query = f"SELECT COUNT(*) FROM {full_table_name}"
                result = self.run_single_query(cursor, query)
                return {
                    'target_row_count': result[0] if result else 0
                }
            except Exception as e2:
                logger.error(f"{target_table}: Target row count failed: {e2}")
                return {'target_row_count': -1}

    def get_completeness_metrics(self, cursor, source_table: str, pk_cols: List[str], source_where: str = "") -> Dict:
        """Get completeness metrics (row count, NULL count) for source table

        Args:
            cursor: Database cursor
            source_table: Source table name
            pk_cols: Primary key columns
            source_where: WHERE clause condition (without 'WHERE' keyword)
        """
        full_table_name = f"{self.source_catalog_name}.{source_table}"

        try:
            where_clause = f"WHERE {source_where}" if source_where else ""

            # If no PK columns detected, just count rows
            if not pk_cols:
                query = f"SELECT COUNT(*) as row_count, 0 as null_count_pk FROM {full_table_name} {where_clause}"
            else:
                pk_null_conditions = " OR ".join([f"`{col}` IS NULL" for col in pk_cols])
                query = f"""
                    SELECT
                        COUNT(*) as row_count,
                        SUM(CASE WHEN {pk_null_conditions} THEN 1 ELSE 0 END) as null_count_pk
                    FROM {full_table_name}
                    {where_clause}
                """

            result = self.run_single_query(cursor, query)

            if result:
                return {
                    'source_row_count': result[0],
                    'null_count_pk': result[1] or 0
                }
            else:
                return {'source_row_count': 0, 'null_count_pk': 0}

        except Exception as e:
            logger.error(f"{source_table}: Completeness query failed: {e}")
            return {'source_row_count': 0, 'null_count_pk': 0}

    def get_uniqueness_metrics(self, cursor, source_table: str, pk_cols: List[str], source_where: str = "") -> Dict:
        """Get uniqueness metrics (PK duplicates) for source table

        Args:
            cursor: Database cursor
            source_table: Source table name
            pk_cols: Primary key columns
            source_where: WHERE clause condition (without 'WHERE' keyword)
        """
        # If no PK columns detected, skip uniqueness check
        if not pk_cols:
            return {'distinct_pk_count': 0, 'duplicate_pk_count': 0, 'duplicate_row_count': 0}

        full_table_name = f"{self.source_catalog_name}.{source_table}"

        try:
            where_clause = f"WHERE {source_where}" if source_where else ""

            if len(pk_cols) == 1:
                pk_expression = f"`{pk_cols[0]}`"
            else:
                pk_columns = ", ".join([f"`{col}`" for col in pk_cols])
                pk_expression = f"CONCAT_WS('||', {pk_columns})"

            query = f"""
                WITH pk_counts AS (
                    SELECT
                        {pk_expression} as pk_value,
                        COUNT(*) as pk_count
                    FROM {full_table_name}
                    {where_clause}
                    GROUP BY {pk_expression}
                )
                SELECT
                    COUNT(DISTINCT pk_value) as distinct_pk_count,
                    SUM(CASE WHEN pk_count > 1 THEN 1 ELSE 0 END) as duplicate_pk_count,
                    SUM(CASE WHEN pk_count > 1 THEN pk_count ELSE 0 END) as duplicate_row_count
                FROM pk_counts
            """

            result = self.run_single_query(cursor, query)

            if result:
                return {
                    'distinct_pk_count': result[0] or 0,
                    'duplicate_pk_count': result[1] or 0,
                    'duplicate_row_count': result[2] or 0
                }
            else:
                return {'distinct_pk_count': 0, 'duplicate_pk_count': 0, 'duplicate_row_count': 0}

        except Exception as e:
            logger.error(f"{source_table}: Uniqueness query failed: {e}")
            return {'distinct_pk_count': 0, 'duplicate_pk_count': 0, 'duplicate_row_count': 0}

    def get_minus_metrics(self, cursor, source_table: str, target_table: str,
                          source_where: str = "", target_where: str = "", execute: bool = True) -> Dict:
        """
        MINUS metrics: Source (dev_cur) EXCEPT Target (dev_km)

        Finds rows in source that don't exist in target.
        Compares all columns except technical columns.

        Args:
            cursor: Database cursor
            source_table: Source table name
            target_table: Target table name
            source_where: WHERE clause for source (without 'WHERE' keyword)
            target_where: WHERE clause for target (without 'WHERE' keyword)
            execute: If False, only build SQL without executing (for large tables)
        """
        source_full_name = f"{self.source_catalog_name}.{source_table}"
        target_full_name = f"{self.target_catalog_name}.{self.target_schema_name}.{target_table}"

        # Technical columns to exclude (lowercase for case-insensitive matching)
        # Source technical: ds_dt, ds_etl_processing_ts, ds_sym_run_dt, ds_snapshot_dt
        # Target KM technical: sym_run_date
        technical_cols = {'ds_dt', 'ds_etl_processing_ts', 'ds_sym_run_dt', 'ds_snapshot_dt', 'sym_run_date'}

        result = {
            'source_minus_target_count': -1,
            'minus_sql': ''
        }

        try:
            # Get columns from source table (lowercase)
            source_cols = self.get_table_columns(cursor, source_full_name, technical_cols)
            if not source_cols:
                logger.warning(f"{source_table}: No columns found for MINUS comparison")
                return result

            # Get columns from target table (get_table_columns lowercases before comparison)
            target_cols = self.get_table_columns(cursor, target_full_name, technical_cols)
            if not target_cols:
                logger.warning(f"{target_table}: No columns found in target for MINUS comparison")
                return result

            # Find common columns (case-insensitive match)
            source_cols_lower = {c.lower(): c for c in source_cols}
            target_cols_upper = {c.upper(): c for c in target_cols}

            common_cols = []
            for col_lower, col_source in source_cols_lower.items():
                col_upper = col_lower.upper()
                if col_upper in target_cols_upper:
                    common_cols.append((col_source, target_cols_upper[col_upper]))

            if not common_cols:
                logger.warning(f"{source_table}: No common columns found between source and target")
                return result

            # Sort columns alphabetically for consistency
            common_cols.sort(key=lambda x: x[0].lower())

            # Source (Delta Lake/Spark): use backticks for column names
            source_select = ", ".join([f"`{col[0]}`" for col in common_cols])
            # Target (Oracle via JDBC): use backticks (Spark SQL syntax, Spark handles JDBC dialect)
            target_select = ", ".join([f"`{col[1]}`" for col in common_cols])

            # Build WHERE clauses
            source_where_clause = f"WHERE {source_where}" if source_where else ""
            target_where_clause = f"WHERE {target_where}" if target_where else ""

            # Query: Source EXCEPT Target
            query = f"""
                SELECT COUNT(*) FROM (
                    SELECT {source_select}
                    FROM {source_full_name}
                    {source_where_clause}

                    EXCEPT

                    SELECT {target_select}
                    FROM {target_full_name}
                    {target_where_clause}
                ) t
            """

            result['minus_sql'] = query.strip()

            # Execute query only if requested
            if execute:
                r = self.run_single_query(cursor, query)
                result['source_minus_target_count'] = r[0] if r else 0
            else:
                # SQL generated but not executed (for large tables)
                result['source_minus_target_count'] = -2  # -2 = skipped

            return result

        except Exception as e:
            logger.warning(f"{source_table}: MINUS query failed: {e}")
            return result

    def get_table_schema(self, cursor, full_table_name: str) -> str:
        """Get table schema as JSON string"""
        try:
            rows = self.run_query_fetchall(cursor, f"DESCRIBE TABLE {full_table_name}")
            if not rows:
                return json.dumps([])

            schema_list = []
            for row in rows:
                col_name = row[0]
                if col_name.startswith('#') or col_name == '':
                    break
                schema_list.append({
                    'name': col_name,
                    'type': row[1] if len(row) > 1 else 'unknown',
                    'comment': row[2] if len(row) > 2 and row[2] else ''
                })

            return json.dumps(schema_list, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"Schema retrieval failed for {full_table_name}: {e}")
            return json.dumps([])

    def process_single_table(self, source_table: str) -> Dict:
        """Process a single table and return reconciliation metrics"""
        thread_id = threading.current_thread().name
        logger.info(f"▶ [{thread_id}] Starting: {source_table}")
        conn = None
        cursor = None
        start_time = time.time()

        target_table = self.map_source_to_target_table(source_table)
        source_full_name = f"{self.source_catalog_name}.{source_table}"
        target_full_name = f"{self.target_catalog_name}.{self.target_schema_name}.{target_table}"

        # Get WHERE clauses based on table configuration
        source_where, target_where = get_where_clauses_for_table(source_table, self.partition_value)

        # Get table type from configuration
        table_config = TABLE_WHERE_CONDITIONS.get(source_table, {})
        table_type = table_config.get('type', 'Unknown')

        result = {
            'source_catalog': self.source_catalog_name,
            'target_catalog': self.target_catalog_name,
            'source_table': source_table,
            'target_table': target_table,
            'table_type': table_type,
            'partition_value': self.partition_value or '',
            'source_where_condition': source_where,
            'target_where_condition': target_where,
            'source_row_count': 0,
            'target_row_count': 0,
            'row_count_diff': 0,
            'null_count_pk': 0,
            'pk_column_name': '',
            'distinct_pk_count': 0,
            'duplicate_pk_count': 0,
            'duplicate_row_count': 0,
            'source_minus_target_count': -1,
            'minus_sql': '',
            'source_schema': '',
            'target_schema': '',
            'source_col_count': 0,
            'target_col_count': 0,
            'extraction_timestamp': self.extraction_timestamp,
            'scan_duration_seconds': 0,
            'error_flag': 'SUCCESS',
            'error_message': ''
        }

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Detect PK columns from source table schema
            pk_cols = self.detect_pk_columns(cursor, source_full_name)
            result['pk_column_name'] = ','.join(pk_cols) if pk_cols else 'N/A'

            # Completeness metrics (source)
            if self.enable_completeness:
                completeness = self.get_completeness_metrics(cursor, source_table, pk_cols, source_where)
                result['source_row_count'] = completeness.get('source_row_count', 0)
                result['null_count_pk'] = completeness.get('null_count_pk', 0)

            # Target row count
            if self.enable_completeness:
                target_count = self.get_target_row_count(cursor, target_table, target_where)
                result['target_row_count'] = target_count.get('target_row_count', 0)
                result['row_count_diff'] = result['source_row_count'] - result['target_row_count']

            # Uniqueness metrics (source)
            if self.enable_uniqueness:
                uniqueness = self.get_uniqueness_metrics(cursor, source_table, pk_cols, source_where)
                result.update(uniqueness)

            # MINUS metrics - build query for all tables, but skip execution for large tables
            if self.enable_minus:
                source_rows = result.get('source_row_count', 0)
                is_large_table = self.skip_minus_large_tables and source_rows >= self.large_table_threshold

                if is_large_table:
                    logger.info(f"  ⏭ Skipping MINUS execution for {source_table} ({source_rows:,} rows >= {self.large_table_threshold:,} threshold)")
                    # Build SQL but don't execute
                    minus_metrics = self.get_minus_metrics(cursor, source_table, target_table,
                                                          source_where, target_where, execute=False)
                else:
                    if self.verbose:
                        logger.info(f"  Running MINUS for: {source_table}")
                    # Build and execute SQL
                    minus_metrics = self.get_minus_metrics(cursor, source_table, target_table,
                                                          source_where, target_where, execute=True)

                result['source_minus_target_count'] = minus_metrics.get('source_minus_target_count', -1)
                result['minus_sql'] = minus_metrics.get('minus_sql', '')

            # Schema collection
            if self.enable_schema:
                source_schema = self.get_table_schema(cursor, source_full_name)
                target_schema = self.get_table_schema(cursor, target_full_name)
                result['source_schema'] = source_schema
                result['target_schema'] = target_schema
                try:
                    result['source_col_count'] = len(json.loads(source_schema)) if source_schema else 0
                    result['target_col_count'] = len(json.loads(target_schema)) if target_schema else 0
                except (json.JSONDecodeError, TypeError):
                    pass

            result['scan_duration_seconds'] = round(time.time() - start_time, 2)

            if self.verbose:
                logger.info(
                    f"✓ {source_table} → {target_table}: "
                    f"SrcRows={result['source_row_count']:,}, TgtRows={result['target_row_count']:,}, "
                    f"Diff={result['row_count_diff']:,}, "
                    f"Minus={result['source_minus_target_count']}, "
                    f"Duration={result['scan_duration_seconds']}s"
                )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"✗ {source_table}: {error_msg}")
            result['error_flag'] = 'ERROR'
            result['error_message'] = error_msg[:500]
            result['scan_duration_seconds'] = round(time.time() - start_time, 2)

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        return result

    def append_to_s3(self, metrics: List[Dict], is_first_batch: bool = False) -> str:
        """Append metrics to S3 CSV file"""
        s3_key = f"{self.output_prefix}/{self.output_filename}" if self.output_prefix else self.output_filename
        s3_path = f"s3://{self.output_bucket}/{s3_key}"
        s3_client = boto3.client('s3')

        fieldnames = [
            'source_catalog', 'target_catalog', 'source_table', 'target_table',
            'table_type', 'partition_value', 'source_where_condition', 'target_where_condition',
            'source_row_count', 'target_row_count', 'row_count_diff',
            'null_count_pk', 'pk_column_name', 'distinct_pk_count', 'duplicate_pk_count', 'duplicate_row_count',
            'source_minus_target_count', 'minus_sql',
            'source_schema', 'target_schema', 'source_col_count', 'target_col_count',
            'extraction_timestamp', 'scan_duration_seconds', 'error_flag', 'error_message'
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        if is_first_batch:
            writer.writeheader()

        writer.writerows(metrics)
        csv_content = output.getvalue()
        output.close()

        if is_first_batch:
            s3_client.put_object(
                Bucket=self.output_bucket,
                Key=s3_key,
                Body=csv_content.encode('utf-8'),
                ContentType='text/csv'
            )
        else:
            try:
                existing_obj = s3_client.get_object(Bucket=self.output_bucket, Key=s3_key)
                existing_content = existing_obj['Body'].read().decode('utf-8')
                new_content = existing_content + csv_content
                s3_client.put_object(
                    Bucket=self.output_bucket,
                    Key=s3_key,
                    Body=new_content.encode('utf-8'),
                    ContentType='text/csv'
                )
            except s3_client.exceptions.NoSuchKey:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(metrics)
                csv_content = output.getvalue()
                output.close()
                s3_client.put_object(
                    Bucket=self.output_bucket,
                    Key=s3_key,
                    Body=csv_content.encode('utf-8'),
                    ContentType='text/csv'
                )

        return s3_path

    def scan_tables(self) -> List[Dict]:
        """Scan all tables using parallel processing"""
        # Get connection to discover tables
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            tables = self.get_tables_to_reconcile(cursor)
        finally:
            cursor.close()
            conn.close()

        if not tables:
            logger.warning("No tables found to process")
            return []

        total_tables = len(tables)
        logger.info(f"Processing {total_tables} tables with {self.num_threads} threads...")

        all_metrics = []
        overall_timeout = self.thread_timeout_seconds * (total_tables / max(self.num_threads, 1)) + 300

        executor = ThreadPoolExecutor(max_workers=self.num_threads)
        try:
            future_to_table = {
                executor.submit(self.process_single_table, table): table
                for table in tables
            }

            # Log that all tasks are submitted
            logger.info(f"✓ Submitted {len(future_to_table)} tasks to executor")

            pending_metrics = []
            completed = 0
            batch_num = 0

            try:
                for future in as_completed(future_to_table, timeout=overall_timeout):
                    table = future_to_table[future]

                    try:
                        table_metrics = future.result(timeout=0)
                        if table_metrics:
                            pending_metrics.append(table_metrics)
                        completed += 1
                        logger.info(f"[{completed}/{total_tables}] Completed: {table}")

                    except Exception as e:
                        logger.error(f"✗ Task failed for {table}: {e}")
                        completed += 1

                    if len(pending_metrics) >= self.batch_size:
                        batch_num += 1
                        self.append_to_s3(pending_metrics, is_first_batch=(batch_num == 1))
                        all_metrics.extend(pending_metrics)
                        pending_metrics = []

            except FuturesTimeoutError:
                logger.error(f"Overall timeout reached after {overall_timeout}s")

            if pending_metrics:
                batch_num += 1
                self.append_to_s3(pending_metrics, is_first_batch=(batch_num == 1))
                all_metrics.extend(pending_metrics)

        finally:
            executor.shutdown(wait=False)

        logger.info(f"Scan complete: {len(all_metrics)} tables")
        return all_metrics

    def run(self) -> Dict:
        """Run the full reconciliation scan"""
        logger.info("=" * 80)
        logger.info("Starting dev_cur vs dev_km reconciliation scan")
        logger.info("=" * 80)

        metrics = self.scan_tables()

        s3_key = f"{self.output_prefix}/{self.output_filename}" if self.output_prefix else self.output_filename
        s3_path = f"s3://{self.output_bucket}/{s3_key}"

        logger.info(f"Done: {len(metrics)} tables → {s3_path}")

        return {
            'status': 'success',
            's3_path': s3_path,
            'total_tables': len(metrics),
            'output_filename': self.output_filename
        }


# ========================================
# Airflow Task Function
# ========================================

def scan_dev_cur_km(**context):
    """Airflow task to run reconciliation"""
    params = context['params']
    verbose = params.get('verbose', False)

    install_pyhive_dependencies(verbose=verbose)

    scanner = ReconciliationScannerDevCurKm(
        source_catalog_name=params['source_catalog_name'],
        target_catalog_name=params['target_catalog_name'],
        target_schema_name=params['target_schema_name'],
        thrift_host=params['thrift_host'],
        thrift_port=params['thrift_port'],
        thrift_user=params['thrift_user'],
        output_bucket=params['output_bucket'],
        output_prefix=params['output_prefix'],
        num_threads=params['num_threads'],
        batch_size=params['batch_size'],
        socket_timeout_seconds=params['socket_timeout_seconds'],
        thread_timeout_seconds=params['thread_timeout_seconds'],
        partition_value=params.get('partition_value'),
        table_limit=params.get('table_limit'),
        table_patterns=params.get('table_patterns', []),
        fallback_pk_column=params.get('fallback_pk_column', 'id'),
        enable_completeness=params.get('enable_completeness', True),
        enable_uniqueness=params.get('enable_uniqueness', True),
        enable_minus=params.get('enable_minus', True),
        enable_schema=params.get('enable_schema', True),
        verbose=verbose,
        large_table_threshold=params.get('large_table_threshold', 1000000),
        skip_minus_large_tables=params.get('skip_minus_large_tables', True),
    )

    result = scanner.run()
    logger.info(f"Result: {result}")
    return result


# ========================================
# DAG Configuration
# ========================================

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

dag = DAG(
    dag_id='reconciliation_dev_cur_km',
    default_args=default_args,
    description='DAMA Reconciliation Scanner - dev_cur vs dev_km',
    schedule=None,
    start_date=datetime(2024, 10, 23),
    catchup=False,
    max_active_runs=1,
    tags=['type::reconciliation', 'layer::cur', 'tool::spark', 'catalog::dev_cur', 'catalog::dev_km', 'dama'],
    params={
        'source_catalog_name': Param(
            default='dev_cur',
            type='string',
            description='Source catalog name (Delta Lake, default: dev_cur)'
        ),
        'target_catalog_name': Param(
            default='dev_km',
            type='string',
            description='Target catalog name (Oracle, default: dev_km)'
        ),
        'target_schema_name': Param(
            default='KMDW',
            type='string',
            description='Target schema name (Oracle schema, default: KMDW). Full path: catalog.schema.table'
        ),
        'thrift_host': Param(
            default='aws-sg-nedp-uat-emr-nlb-5d8b52862943b794.elb.ap-southeast-1.amazonaws.com',
            type='string',
            description='Spark Thrift server host'
        ),
        'thrift_port': Param(
            default=10001,
            type='integer',
            description='Spark Thrift server port'
        ),
        'thrift_user': Param(
            default='hadoop',
            type='string',
            description='Thrift server username'
        ),
        'output_bucket': Param(
            default='aws-sg-nedp-uat-mwaa',
            type='string',
            description='S3 bucket for output CSV'
        ),
        'output_prefix': Param(
            default='artifacts/reconciliation',
            type='string',
            description='S3 prefix for output CSV'
        ),
        'num_threads': Param(
            default=5,
            type='integer',
            description='Number of parallel threads'
        ),
        'batch_size': Param(
            default=5,
            type='integer',
            description='Tables per batch before S3 commit'
        ),
        'socket_timeout_seconds': Param(
            default=300,
            type='integer',
            description='Socket timeout per query (seconds)'
        ),
        'thread_timeout_seconds': Param(
            default=600,
            type='integer',
            description='Thread timeout per table (seconds)'
        ),
        'partition_value': Param(
            default=None,
            type=['null', 'string'],
            description='Partition value (date format: YYYY-MM-DD, e.g., "2025-09-03"). WHERE clauses are auto-generated based on table type. Set to null for full scan.'
        ),
        'table_limit': Param(
            default=None,
            type=['null', 'integer'],
            description='Limit number of tables to process'
        ),
        'table_patterns': Param(
            default=[],
            type='array',
            description='Array of table names or regex patterns to reconcile (source/dev_cur names). Empty = scan all tables from source catalog.'
        ),
        'fallback_pk_column': Param(
            default='id',
            type='string',
            description='Fallback primary key column'
        ),
        'enable_completeness': Param(
            default=True,
            type='boolean',
            description='Enable completeness metrics (row counts)'
        ),
        'enable_uniqueness': Param(
            default=True,
            type='boolean',
            description='Enable uniqueness metrics (duplicates)'
        ),
        'enable_minus': Param(
            default=True,
            type='boolean',
            description='Enable MINUS SQL comparison'
        ),
        'enable_schema': Param(
            default=True,
            type='boolean',
            description='Enable schema collection'
        ),
        'verbose': Param(
            default=True,
            type='boolean',
            description='Enable verbose logging'
        ),
        'large_table_threshold': Param(
            default=1000000,
            type='integer',
            description='Row count threshold for large tables (default: 1M). Tables >= this threshold will skip MINUS query.'
        ),
        'skip_minus_large_tables': Param(
            default=True,
            type='boolean',
            description='Skip MINUS query for tables >= large_table_threshold (default: true)'
        ),
    }
)

# ========================================
# Task Definitions
# ========================================

start = EmptyOperator(
    task_id='start',
    dag=dag,
)

scan_task = PythonOperator(
    task_id='scan_dev_cur_km',
    python_callable=scan_dev_cur_km,
    dag=dag,
)

end = EmptyOperator(
    task_id='end',
    dag=dag,
)

# ========================================
# Task Dependencies
# ========================================
start >> scan_task >> end
