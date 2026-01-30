"""
Database Query Monitoring Module

Tracks query outcomes and performance metrics for both ChromaDB and Redis.
Separated from retrieval logic for clean architecture.
Storage: SQLite database for persistent metrics
"""

import os
import json
import logging
import time
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
from threading import Lock
from contextlib import contextmanager

from chatdku.core.tools.email.email_tool import EmailTools


# ------------ Storage Configuration ------------
DEFAULT_DB_PATH = "/datapool/redis_listener/db_query_metrics.db"
DEFAULT_LOG_PATH = "/datapool/redis_listener/db_query_monitor.log"


# ------------ Query Outcome Taxonomy ------------
class QueryOutcome(Enum):
    """Taxonomy for query result categorization"""
    SUCCESS = "success"  # Query returned valid results
    EMPTY_RESULT = "empty_result"  # Query succeeded but returned no documents
    TIMEOUT = "timeout"  # Query exceeded time limit
    CONNECTION_ERROR = "connection_error"  # Database connection failed
    QUERY_ERROR = "query_error"  # Malformed query or syntax error
    UNKNOWN_ERROR = "unknown_error"  # Unexpected error


class DatabaseType(Enum):
    """Database types being monitored"""
    CHROMA = "chroma"  # ChromaDB (vector search)
    REDIS = "redis"    # Redis (keyword search)


@dataclass
class QueryMetrics:
    """Metrics for a single query execution"""
    db_type: DatabaseType  # Which database
    query_type: str  # "vector" or "keyword" (for compatibility)
    outcome: QueryOutcome
    latency_ms: float
    timestamp: datetime
    result_count: int = 0
    expected_top_k: Optional[int] = None
    error_message: Optional[str] = None
    query_text: Optional[str] = None  # For debugging
    user_id: Optional[str] = None
    search_mode: Optional[int] = None


# ------------ Database Query Monitor ------------
class DatabaseQueryMonitor:
    """
    Monitor ChromaDB and Redis query performance and outcomes.
    
    Features:
    - Track query success/failure rates for both databases
    - Monitor query latency per database
    - Detect anomalies (high error rates, slow queries)
    - Send email alerts
    - Persist metrics to SQLite database
    - Generate periodic reports with per-database breakdown
    
    Storage:
    - SQLite database at /datapool/redis_listener/db_query_metrics.db
    - In-memory cache for fast recent queries (last 1000)
    """
    
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        log_file: str = DEFAULT_LOG_PATH,
        alert_error_threshold: float = 0.3,  # Alert if >30% queries fail
        alert_latency_threshold_ms: float = 5000,  # Alert if >5s average
        alert_cooldown: int = 600,  # 10 minutes between alerts
        metrics_window_size: int = 1000,  # Keep last 1000 queries in memory
    ):
        self.db_path = db_path
        self.alert_error_threshold = alert_error_threshold
        self.alert_latency_threshold_ms = alert_latency_threshold_ms
        self.alert_cooldown = alert_cooldown
        self.metrics_window_size = metrics_window_size
        
        # Thread-safe metrics storage (in-memory cache)
        self.metrics_queue = deque(maxlen=metrics_window_size)
        self.lock = Lock()
        
        # Alert tracking (per database type)
        self.last_alert_time = {
            DatabaseType.CHROMA: None,
            DatabaseType.REDIS: None,
        }
        
        # Initialize database
        self._init_database()
        
        # Logging
        self.logger = self._setup_logger(log_file)
    
    def _init_database(self):
        """Initialize SQLite database for persistent storage"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    db_type TEXT NOT NULL,
                    query_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    result_count INTEGER NOT NULL,
                    expected_top_k INTEGER NOT NULL,
                    error_message TEXT,
                    query_text TEXT,
                    user_id TEXT,
                    search_mode INTEGER
                )
            """)
            
            # Create indices for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON query_metrics(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_db_type 
                ON query_metrics(db_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outcome 
                ON query_metrics(outcome)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_type 
                ON query_metrics(query_type)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_db_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _setup_logger(self, log_file: str) -> logging.Logger:
        """Setup dedicated logger for query monitoring"""
        logger = logging.getLogger("db_query_monitor")
        logger.setLevel(logging.INFO)
        
        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        
        if not logger.hasHandlers():
            logger.addHandler(file_handler)
            
        return logger
    
    def record_query(self, metrics: QueryMetrics):
        """Record a query execution and its metrics (both memory and database)"""
        # Store in memory cache
        with self.lock:
            self.metrics_queue.append(metrics)
        
        # Store in database
        self._store_to_database(metrics)
        
        # Log based on outcome
        db_name = metrics.db_type.value.upper()
        outcome_value = metrics.outcome.value
        
        if outcome_value == 'success':
            self.logger.info(
                f"[{db_name}] {metrics.query_type.upper()} query succeeded: "
                f"{metrics.result_count} results in {metrics.latency_ms:.1f}ms"
            )
        elif outcome_value == 'partial_result':
            self.logger.warning(
                f"[{db_name}] {metrics.query_type.upper()} query returned PARTIAL results: "
                f"{metrics.result_count}/{metrics.expected_top_k} expected "
                f"(latency: {metrics.latency_ms:.1f}ms)"
            )
        elif outcome_value == 'empty_result':
            self.logger.warning(
                f"[{db_name}] {metrics.query_type.upper()} query returned empty results "
                f"(latency: {metrics.latency_ms:.1f}ms)"
            )
        else:
            self.logger.error(
                f"[{db_name}] {metrics.query_type.upper()} query {outcome_value}: "
                f"{metrics.error_message} (latency: {metrics.latency_ms:.1f}ms)"
            )
        
        # Check if alert needed (per database)
        self._check_alert_conditions(metrics.db_type)
    
    def _store_to_database(self, metrics: QueryMetrics):
        """Store metrics to SQLite database"""
        try:
            with self._get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO query_metrics 
                    (timestamp, db_type, query_type, outcome, latency_ms, result_count, 
                     expected_top_k, error_message, query_text, user_id, search_mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.timestamp.isoformat(),
                    metrics.db_type.value,
                    metrics.query_type,
                    metrics.outcome.value,
                    metrics.latency_ms,
                    metrics.result_count,
                    metrics.expected_top_k, 
                    metrics.error_message,
                    metrics.query_text,
                    metrics.user_id,
                    metrics.search_mode,
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store metrics to database: {e}")
    
    def get_stats(
        self, 
        window_size: Optional[int] = None,
        db_type: Optional[DatabaseType] = None
    ) -> Dict[str, Any]:
        """
        Get statistics for recent queries from in-memory cache.
        
        Args:
            window_size: Number of recent queries to analyze (default: all in memory)
            db_type: Filter by database type (default: all databases)
        """
        with self.lock:
            if not self.metrics_queue:
                return {"message": "No queries recorded yet"}
            
            recent_metrics = list(self.metrics_queue)
            
            # Filter by database type if specified
            if db_type:
                recent_metrics = [m for m in recent_metrics if m.db_type == db_type]
            
            if window_size:
                recent_metrics = recent_metrics[-window_size:]
            
            if not recent_metrics:
                return {"message": f"No queries found for {db_type.value if db_type else 'any database'}"}
            
            return self._calculate_stats(recent_metrics)
    
    def get_stats_from_db(
        self, 
        hours: int = 24, 
        query_type: Optional[str] = None,
        db_type: Optional[DatabaseType] = None
    ) -> Dict[str, Any]:
        """
        Get statistics from database for specified time range.
        
        Args:
            hours: Number of hours to look back (default: 24)
            query_type: Filter by query type ('vector' or 'keyword'), None for all
            db_type: Filter by database type (chroma or redis), None for all
        """
        try:
            with self._get_db_connection() as conn:
                cutoff = datetime.now() - timedelta(hours=hours)
                
                query = """
                    SELECT * FROM query_metrics 
                    WHERE timestamp >= ?
                """
                params = [cutoff.isoformat()]
                
                if query_type:
                    query += " AND query_type = ?"
                    params.append(query_type)
                
                if db_type:
                    query += " AND db_type = ?"
                    params.append(db_type.value)
                
                query += " ORDER BY timestamp DESC"
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                if not rows:
                    return {"message": f"No queries found in last {hours} hours"}
                
                # Convert rows to QueryMetrics objects
                metrics = []
                for row in rows:
                    m = QueryMetrics(
                        db_type=DatabaseType(row['db_type']),
                        query_type=row['query_type'],
                        outcome=QueryOutcome(row['outcome']),
                        latency_ms=row['latency_ms'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        result_count=row['result_count'],
                        expected_top_k=row['expected_top_k'],
                        error_message=row['error_message'],
                        query_text=row['query_text'],
                        user_id=row['user_id'],
                        search_mode=row['search_mode'],
                    )
                    metrics.append(m)
                
                stats = self._calculate_stats(metrics)
                stats['time_range_hours'] = hours
                stats['query_type_filter'] = query_type or 'all'
                stats['db_type_filter'] = db_type.value if db_type else 'all'
                return stats
                
        except Exception as e:
            return {"error": f"Failed to retrieve stats from database: {e}"}
    
    def _calculate_stats(self, metrics: List[QueryMetrics]) -> Dict[str, Any]:
        """Calculate statistics from a list of metrics"""
        total = len(metrics)
        
        # Overall outcome distribution
        outcomes = defaultdict(int)
        for m in metrics:
            outcomes[m.outcome.value] += 1
        
        # Database type distribution
        db_types = defaultdict(int)
        for m in metrics:
            db_types[m.db_type.value] += 1
        
        # Query type distribution
        query_types = defaultdict(int)
        for m in metrics:
            query_types[m.query_type] += 1
        
        # Per-database statistics
        db_stats = {}
        for db_type in DatabaseType:
            db_metrics = [m for m in metrics if m.db_type == db_type]
            if db_metrics:
                db_stats[db_type.value] = self._calculate_db_specific_stats(db_metrics)
        
        # Overall latency statistics
        latencies = [m.latency_ms for m in metrics]
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        
        # Overall error rate (excluding SUCCESS, EMPTY_RESULT, PARTIAL_RESULT)
        # Use string comparison to avoid attribute errors
        success_outcomes = {'success', 'empty_result', 'partial_result'}
        error_count = sum(
            1 for m in metrics 
            if m.outcome.value not in success_outcomes
        )
        error_rate = error_count / total if total > 0 else 0
        
        # Overall partial rate
        partial_count = sum(1 for m in metrics if m.outcome.value == 'partial_result')
        partial_rate = partial_count / total if total > 0 else 0
        
        # Result count statistics
        result_counts = [m.result_count for m in metrics]
        avg_results = sum(result_counts) / len(result_counts)
        
        return {
            "total_queries": total,
            "outcome_distribution": dict(outcomes),
            "db_type_distribution": dict(db_types),
            "query_type_distribution": dict(query_types),
            "per_database_stats": db_stats,
            "overall_latency_stats": {
                "avg_ms": round(avg_latency, 2),
                "min_ms": round(min_latency, 2),
                "max_ms": round(max_latency, 2),
            },
            "overall_result_stats": {
                "avg_count": round(avg_results, 2),
            },
            "overall_error_rate": round(error_rate, 3),
            "overall_partial_rate": round(partial_rate, 3),
            "time_range": {
                "start": metrics[0].timestamp.isoformat(),
                "end": metrics[-1].timestamp.isoformat(),
            }
        }
    
    def _calculate_db_specific_stats(self, metrics: List[QueryMetrics]) -> Dict[str, Any]:
        """Calculate statistics for a specific database"""
        total = len(metrics)
        
        # Outcome distribution
        outcomes = defaultdict(int)
        for m in metrics:
            outcomes[m.outcome.value] += 1
        
        # Latency statistics
        latencies = [m.latency_ms for m in metrics]
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        
        # Error rate (excluding SUCCESS, EMPTY_RESULT, and PARTIAL_RESULT)
        # Use string comparison to avoid attribute errors
        success_outcomes = {'success', 'empty_result', 'partial_result'}
        error_count = sum(
            1 for m in metrics 
            if m.outcome.value not in success_outcomes
        )
        error_rate = error_count / total if total > 0 else 0
        
        # Partial result rate
        partial_count = sum(1 for m in metrics if m.outcome.value == 'partial_result')
        partial_rate = partial_count / total if total > 0 else 0
        
        # Result count
        result_counts = [m.result_count for m in metrics]
        avg_results = sum(result_counts) / len(result_counts)
        
        # Result fulfillment rate (for queries with expected_top_k)
        queries_with_expected = [m for m in metrics if m.expected_top_k is not None and m.expected_top_k > 0]
        if queries_with_expected:
            fulfillment_rates = [
                min(1.0, m.result_count / m.expected_top_k) 
                for m in queries_with_expected
            ]
            avg_fulfillment = sum(fulfillment_rates) / len(fulfillment_rates)
        else:
            avg_fulfillment = None
        
        return {
            "query_count": total,
            "outcome_distribution": dict(outcomes),
            "latency_stats": {
                "avg_ms": round(avg_latency, 2),
                "min_ms": round(min_latency, 2),
                "max_ms": round(max_latency, 2),
            },
            "result_stats": {
                "avg_count": round(avg_results, 2),
                "avg_fulfillment_rate": round(avg_fulfillment, 3) if avg_fulfillment is not None else None,
            },
            "error_rate": round(error_rate, 3),
            "partial_rate": round(partial_rate, 3),
        }
    
    def _check_alert_conditions(self, db_type: DatabaseType):
        """Check if current metrics warrant an alert for specific database"""
        # Cooldown check (per database)
        if self.last_alert_time[db_type]:
            elapsed = time.time() - self.last_alert_time[db_type]
            if elapsed < self.alert_cooldown:
                return
        
        # Get stats for this specific database (last 100 queries)
        stats = self.get_stats(window_size=100, db_type=db_type)
        
        if stats.get("total_queries", 0) < 10:
            return  # Not enough data
        
        # Check error rate
        error_rate = stats.get("overall_error_rate", 0)
        if error_rate > self.alert_error_threshold:
            self._send_alert(
                db_type=db_type,
                subject=f"High {db_type.value.upper()} Query Error Rate",
                stats=stats,
                reason=f"Error rate {error_rate:.1%} exceeds threshold {self.alert_error_threshold:.1%}"
            )
            return
        
        # Check latency
        avg_latency = stats.get("latency_stats", {}).get("avg_ms", 0)
        if avg_latency > self.alert_latency_threshold_ms:
            self._send_alert(
                db_type=db_type,
                subject=f"High {db_type.value.upper()} Query Latency",
                stats=stats,
                reason=f"Average latency {avg_latency:.0f}ms exceeds threshold {self.alert_latency_threshold_ms:.0f}ms"
            )
    
    def _send_alert(self, db_type: DatabaseType, subject: str, stats: Dict[str, Any], reason: str):
        """Send email alert about query issues"""
        host = os.getenv("EMAIL_HOST")
        port = int(os.getenv("EMAIL_PORT", 25))
        from_email = os.getenv("EMAIL_HOST_USER")
        to_email = os.getenv("EMAIL_TO")
        
        if not all([host, port, from_email, to_email]):
            self.logger.error("Missing email configuration. Cannot send alert.")
            return
        
        try:
            to_email_list = json.loads(to_email)
            
            message = f"""Database Query Performance Alert - {db_type.value.upper()}
                Reason: {reason}

                Recent Query Statistics (last 100 queries for {db_type.value.upper()}):
                -------------------------------------------
                Total Queries: {stats['total_queries']}
                Error Rate: {stats['overall_error_rate']:.1%}

                Outcome Distribution:
                {json.dumps(stats['outcome_distribution'], indent=2)}

                Latency Statistics:
                Average: {stats['overall_latency_stats']['avg_ms']:.1f}ms
                Min: {stats['overall_latency_stats']['min_ms']:.1f}ms
                Max: {stats['overall_latency_stats']['max_ms']:.1f}ms

                Result Statistics:
                Average Results: {stats['overall_result_stats']['avg_count']:.1f}

                Time Range:
                Start: {stats['time_range']['start']}
                End: {stats['time_range']['end']}

                Alert Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

                Action Required:
                Please investigate {db_type.value.upper()} query performance and error causes.
                """
            
            email = EmailTools(
                host=host,
                port=port,
                receiver_email=to_email_list,
                sender_name="ChatDKU",
                sender_email=from_email
            )
            
            result = email.send_mail(f"[ChatDKU Alert] {subject}", message)
            self.logger.info(f"Alert email sent for {db_type.value}: {result}")
            self.last_alert_time[db_type] = time.time()
            
        except Exception as e:
            self.logger.error(f"Failed to send alert email: {e}")
    
    def get_summary_report(self, hours: int = 24) -> str:
        """Generate a comprehensive summary report from database"""
        try:
            # Get overall stats
            overall_stats = self.get_stats_from_db(hours=hours)
            
            if "error" in overall_stats or "message" in overall_stats:
                return f"Error generating report: {overall_stats}"
            
            # Get per-database stats
            chroma_stats = self.get_stats_from_db(hours=hours, db_type=DatabaseType.CHROMA)
            redis_stats = self.get_stats_from_db(hours=hours, db_type=DatabaseType.REDIS)
            
            # Get total count from database
            with self._get_db_connection() as conn:
                cutoff = datetime.now() - timedelta(hours=hours)
                cursor = conn.execute(
                    "SELECT COUNT(*) as total FROM query_metrics WHERE timestamp >= ?",
                    [cutoff.isoformat()]
                )
                total_in_period = cursor.fetchone()['total']
            
            report = f"""
                ========================================
                Database Query Monitor - Summary Report
                ========================================
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                Report Period: Last {hours} hours
                Database Location: {self.db_path}

                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                📊 Overall Statistics (All Databases)
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                Total Queries: {total_in_period}
                Overall Error Rate: {overall_stats['overall_error_rate']:.1%}
                Overall Partial Result Rate: {overall_stats.get('overall_partial_rate', 0):.1%}
                Average Latency: {overall_stats['overall_latency_stats']['avg_ms']:.1f}ms
                Max Latency: {overall_stats['overall_latency_stats']['max_ms']:.1f}ms

                Database Distribution:
                {json.dumps(overall_stats['db_type_distribution'], indent=2)}

                Overall Outcome Distribution:
                {json.dumps(overall_stats['outcome_distribution'], indent=2)}

                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                🔵 ChromaDB (Vector Search) Performance
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                """
            
            if "error" not in chroma_stats and "message" not in chroma_stats:
                chroma_db_stats = chroma_stats['per_database_stats'].get('chroma', {})
                if chroma_db_stats:
                    fulfillment = chroma_db_stats['result_stats'].get('avg_fulfillment_rate')
                    fulfillment_str = f"{fulfillment:.1%}" if fulfillment is not None else "N/A"
                    
                    report += f"""Query Count: {chroma_db_stats['query_count']}
                        Error Rate: {chroma_db_stats['error_rate']:.1%}
                        Partial Result Rate: {chroma_db_stats.get('partial_rate', 0):.1%}
                        Average Latency: {chroma_db_stats['latency_stats']['avg_ms']:.1f}ms
                        Average Results: {chroma_db_stats['result_stats']['avg_count']:.1f}
                        Result Fulfillment Rate: {fulfillment_str}

                        Outcomes:
                        {json.dumps(chroma_db_stats['outcome_distribution'], indent=2)}
                        """
                else:
                    report += "No ChromaDB queries in this period.\n"
            else:
                report += f"{chroma_stats.get('message', 'No data')}\n"
            
            report += """
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                🔴 Redis (Keyword Search) Performance
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                """
            
            if "error" not in redis_stats and "message" not in redis_stats:
                redis_db_stats = redis_stats['per_database_stats'].get('redis', {})
                if redis_db_stats:
                    fulfillment = redis_db_stats['result_stats'].get('avg_fulfillment_rate')
                    fulfillment_str = f"{fulfillment:.1%}" if fulfillment is not None else "N/A"
                    
                    report += f"""Query Count: {redis_db_stats['query_count']}
                        Error Rate: {redis_db_stats['error_rate']:.1%}
                        Partial Result Rate: {redis_db_stats.get('partial_rate', 0):.1%}
                        Average Latency: {redis_db_stats['latency_stats']['avg_ms']:.1f}ms
                        Average Results: {redis_db_stats['result_stats']['avg_count']:.1f}
                        Result Fulfillment Rate: {fulfillment_str}

                        Outcomes:
                        {json.dumps(redis_db_stats['outcome_distribution'], indent=2)}
                        """
                else:
                    report += "No Redis queries in this period.\n"
            else:
                report += f"{redis_stats.get('message', 'No data')}\n"
            
            report += f"""
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                Time Range:
                Start: {overall_stats['time_range']['start']}
                End: {overall_stats['time_range']['end']}

                ========================================
                """
            return report
        except Exception as e:
            return f"Error generating summary report: {e}"


# ------------ Global Monitor Instance ------------
# Singleton pattern for easy import and use
_monitor_instance = None


def get_query_monitor() -> DatabaseQueryMonitor:
    """Get or create the global query monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = DatabaseQueryMonitor()
    return _monitor_instance


# ------------ Convenience Functions ------------
def record_chroma_query(
    outcome: QueryOutcome,
    latency_ms: float,
    result_count: int = 0,
    expected_top_k: Optional[int] = None,
    error_message: Optional[str] = None,
    query_text: Optional[str] = None,
    user_id: Optional[str] = None,
    search_mode: Optional[int] = None,
):
    """Record a ChromaDB (vector) query"""
    monitor = get_query_monitor()
    metrics = QueryMetrics(
        db_type=DatabaseType.CHROMA,
        query_type="vector",
        outcome=outcome,
        latency_ms=latency_ms,
        timestamp=datetime.now(),
        result_count=result_count,
        expected_top_k=expected_top_k,
        error_message=error_message,
        query_text=query_text,
        user_id=user_id,
        search_mode=search_mode,
    )
    monitor.record_query(metrics)


def record_redis_query(
    outcome: QueryOutcome,
    latency_ms: float,
    result_count: int = 0,
    expected_top_k: Optional[int] = None,
    error_message: Optional[str] = None,
    query_text: Optional[str] = None,
    user_id: Optional[str] = None,
    search_mode: Optional[int] = None,
):
    """Record a Redis (keyword) query"""
    monitor = get_query_monitor()
    metrics = QueryMetrics(
        db_type=DatabaseType.REDIS,
        query_type="keyword",
        outcome=outcome,
        latency_ms=latency_ms,
        timestamp=datetime.now(),
        result_count=result_count,
        expected_top_k=expected_top_k,
        error_message=error_message,
        query_text=query_text,
        user_id=user_id,
        search_mode=search_mode,
    )
    monitor.record_query(metrics)


# Backward compatibility aliases
def record_vector_query(*args, **kwargs):
    """Alias for record_chroma_query (backward compatibility)"""
    return record_chroma_query(*args, **kwargs)


def record_keyword_query(*args, **kwargs):
    """Alias for record_redis_query (backward compatibility)"""
    return record_redis_query(*args, **kwargs)


def get_query_stats(
    window_size: Optional[int] = None, 
    from_db: bool = False, 
    hours: int = 24,
    db_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get query statistics.
    
    Args:
        window_size: For in-memory stats, number of recent queries
        from_db: If True, get stats from database instead of memory
        hours: For database stats, hours to look back
        db_type: Filter by database ('chroma' or 'redis')
    """
    monitor = get_query_monitor()
    db_type_enum = DatabaseType(db_type) if db_type else None
    
    if from_db:
        return monitor.get_stats_from_db(hours=hours, db_type=db_type_enum)
    else:
        return monitor.get_stats(window_size, db_type=db_type_enum)


def print_summary_report(hours: int = 24):
    """
    Print summary report to stdout.
    
    Args:
        hours: Number of hours to include in report
    """
    monitor = get_query_monitor()
    print(monitor.get_summary_report(hours=hours))