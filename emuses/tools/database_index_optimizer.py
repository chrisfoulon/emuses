"""Database index optimization for improved query performance.

This module provides strategic database index creation and management
for the EMUSES model registry to optimize common query patterns.
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import (
    text, inspect, MetaData
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DatabaseIndexOptimizer:
    """Database index optimization and management.

    Provides strategic index creation for common query patterns
    in the EMUSES model registry system.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy database engine

    Attributes
    ----------
    engine : Engine
        Database engine instance
    metadata : MetaData
        SQLAlchemy metadata for table reflection
    """

    def __init__(self, engine: Engine):
        """Initialize database index optimizer.

        Parameters
        ----------
        engine : Engine
            SQLAlchemy database engine
        """
        self.engine = engine
        self.metadata = MetaData()

    def get_existing_indexes(self, table_name: str) -> Dict[str, Dict]:
        """Get existing indexes for a table.

        Parameters
        ----------
        table_name : str
            Name of the table to inspect

        Returns
        -------
        Dict[str, Dict]
            Dictionary of existing indexes with details
        """
        inspector = inspect(self.engine)
        indexes = inspector.get_indexes(table_name)

        index_info = {}
        for idx in indexes:
            index_info[idx['name']] = {
                'columns': idx['column_names'],
                'unique': idx['unique']
            }

        return index_info

    def create_strategic_indexes(self) -> Dict[str, str]:
        """Create strategic indexes for common query patterns.

        Creates composite indexes optimized for the most frequent
        query patterns in DatabaseModelRegistry.

        Returns
        -------
        Dict[str, str]
            Dictionary of created indexes and their status
        """
        results = {}

        try:
            with self.engine.connect() as conn:
                # Start transaction for index creation
                trans = conn.begin()

                try:
                    # 1. Composite index for access control with ordering
                    # Optimizes: list_models() with ORDER BY created_at
                    results['idx_model_access_ordering'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_model_access_ordering "
                        "ON model_registry (owner_id, created_at DESC)"
                    )

                    # 2. Public models with ordering
                    # Optimizes: public model queries with ORDER BY
                    results['idx_public_models_ordering'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_public_models_ordering "
                        "ON model_registry (is_public, created_at)"
                    )

                    # 3. Workspace models with ordering
                    # Optimizes: workspace-specific queries
                    results['idx_workspace_models_ordering'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_workspace_models_ordering "
                        "ON model_registry (workspace_id, created_at)"
                    )

                    # 4. Composite permission check index
                    # Optimizes: model_access permission lookups
                    results['idx_model_permission_composite'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_model_permission_composite "
                        "ON model_access (model_id, user_id, expires_at)"
                    )

                    # 5. Search optimization indexes
                    # Case-insensitive name search
                    results['idx_model_name_ci'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_model_name_ci "
                        "ON model_registry (LOWER(name))"
                    )

                    # Model type with case-insensitive search
                    results['idx_model_type_ci'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_model_type_ci "
                        "ON model_registry (LOWER(model_type))"
                    )

                    # 6. Analytics and usage tracking indexes
                    # Download tracking by date
                    results['idx_downloads_date'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_downloads_date "
                        "ON model_downloads (model_id, downloaded_at DESC)"
                    )

                    # Popular models (for ranking/recommendations)
                    results['idx_model_popularity'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_model_popularity "
                        "ON model_registry (popularity_score, download_count)"
                    )

                    # 7. Cloud storage optimization
                    # Storage tier queries
                    results['idx_storage_tier'] = self._create_index_safe(
                        conn,
                        "CREATE INDEX IF NOT EXISTS idx_storage_tier "
                        "ON model_registry (storage_tier, is_cached)"
                    )

                    trans.commit()
                    logger.info("Successfully created strategic database indexes")

                except Exception as e:
                    trans.rollback()
                    logger.error(f"Failed to create indexes, rolling back: {e}")
                    raise

        except Exception as e:
            logger.error(f"Database index creation failed: {e}")
            results['error'] = str(e)

        return results

    def _create_index_safe(self, conn, sql: str) -> str:
        """Safely create an index with error handling.

        Parameters
        ----------
        conn : Connection
            Database connection
        sql : str
            SQL statement for index creation

        Returns
        -------
        str
            Status message for index creation
        """
        try:
            # Extract index name from SQL for logging
            if 'IF NOT EXISTS ' in sql:
                index_name = sql.split('IF NOT EXISTS ')[1].split(' ON')[0].strip()
            else:
                # Fallback extraction
                parts = sql.split()
                for i, part in enumerate(parts):
                    if part.upper() == 'INDEX':
                        index_name = parts[i + 1] if i + 1 < len(parts) else 'unknown'
                        break
                else:
                    index_name = 'unknown'

            conn.execute(text(sql))
            logger.info(f"Created index: {index_name}")
            return "created"

        except Exception as e:
            error_msg = str(e).lower()
            # Check if error is due to existing index
            if ("already exists" in error_msg or
                    "duplicate" in error_msg or
                    "index" in error_msg and "exists" in error_msg):
                logger.debug(f"Index already exists (expected): {e}")
                return "already_exists"
            else:
                logger.warning(f"Failed to create index: {e}")
                return f"failed: {str(e)}"

    def analyze_query_performance(
        self,
        session: Session,
        test_queries: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """Analyze query performance with current indexes.

        Parameters
        ----------
        session : Session
            Database session for query execution
        test_queries : List[str], optional
            Custom queries to test. Uses defaults if None.

        Returns
        -------
        Dict[str, Dict]
            Query performance analysis results
        """
        if test_queries is None:
            test_queries = self._get_default_test_queries()

        results = {}

        for i, query in enumerate(test_queries):
            query_name = f"query_{i+1}"

            try:
                import time

                # Warm up query
                session.execute(text(query))

                # Measure performance
                start_time = time.perf_counter()
                result = session.execute(text(query))
                rows = result.fetchall()
                end_time = time.perf_counter()

                execution_time_ms = (end_time - start_time) * 1000

                results[query_name] = {
                    'query': query,
                    'execution_time_ms': execution_time_ms,
                    'row_count': len(rows),
                    'performance_rating': self._rate_performance(execution_time_ms)
                }

                logger.info(f"{query_name}: {execution_time_ms:.2f}ms, {len(rows)} rows")

            except Exception as e:
                results[query_name] = {
                    'query': query,
                    'error': str(e),
                    'execution_time_ms': None,
                    'row_count': None,
                    'performance_rating': 'failed'
                }
                logger.error(f"Query {query_name} failed: {e}")

        return results

    def _get_default_test_queries(self) -> List[str]:
        """Get default test queries for performance analysis.

        Returns
        -------
        List[str]
            List of SQL queries for testing
        """
        return [
            # Basic list query with ordering
            "SELECT id, name, created_at FROM model_registry ORDER BY created_at DESC LIMIT 50",

            # Access control query
            "SELECT id, name FROM model_registry WHERE is_public = TRUE ORDER BY created_at DESC LIMIT 50",

            # User-specific query
            "SELECT id, name FROM model_registry WHERE owner_id IN (SELECT id FROM users LIMIT 1) ORDER BY created_at DESC",

            # Search-like query
            "SELECT id, name FROM model_registry WHERE LOWER(name) LIKE '%model%' OR LOWER(model_type) LIKE '%class%'",

            # Permission check query
            "SELECT COUNT(*) FROM model_access WHERE expires_at IS NULL OR expires_at > datetime('now')",

            # Analytics query
            "SELECT model_id, COUNT(*) as download_count FROM model_downloads GROUP BY model_id ORDER BY download_count DESC LIMIT 10"
        ]

    def _rate_performance(self, execution_time_ms: float) -> str:
        """Rate query performance based on execution time.

        Parameters
        ----------
        execution_time_ms : float
            Query execution time in milliseconds

        Returns
        -------
        str
            Performance rating
        """
        if execution_time_ms < 10:
            return "excellent"
        elif execution_time_ms < 50:
            return "good"
        elif execution_time_ms < 100:
            return "acceptable"
        elif execution_time_ms < 500:
            return "slow"
        else:
            return "very_slow"

    def drop_strategic_indexes(self) -> Dict[str, str]:
        """Drop strategic indexes (for cleanup/testing).

        Returns
        -------
        Dict[str, str]
            Dictionary of dropped indexes and their status
        """
        indexes_to_drop = [
            'idx_model_access_ordering',
            'idx_public_models_ordering',
            'idx_workspace_models_ordering',
            'idx_model_permission_composite',
            'idx_model_name_ci',
            'idx_model_type_ci',
            'idx_downloads_date',
            'idx_model_popularity',
            'idx_storage_tier'
        ]

        results = {}

        try:
            with self.engine.connect() as conn:
                for index_name in indexes_to_drop:
                    try:
                        conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                        results[index_name] = "dropped"
                        logger.info(f"Dropped index: {index_name}")
                    except Exception as e:
                        results[index_name] = f"failed: {str(e)}"
                        logger.warning(f"Failed to drop index {index_name}: {e}")

        except Exception as e:
            logger.error(f"Failed to drop indexes: {e}")
            results['error'] = str(e)

        return results
