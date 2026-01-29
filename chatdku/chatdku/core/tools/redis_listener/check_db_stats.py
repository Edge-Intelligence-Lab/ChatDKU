from chatdku.core.tools.redis_listener.db_monitor import (
    get_query_monitor, 
    DatabaseType
)

monitor = get_query_monitor()

# 打印综合报告（最近24小时）
print(monitor.get_summary_report(hours=24))

# 获取所有数据库统计
all_stats = monitor.get_stats_from_db(hours=24)
print(f"Overall error rate: {all_stats['overall_error_rate']:.1%}")

# 只看 ChromaDB
chroma_stats = monitor.get_stats_from_db(hours=24, db_type=DatabaseType.CHROMA)
chroma_perf = chroma_stats['per_database_stats'].get('chroma', {})
print(f"ChromaDB queries: {chroma_perf.get('query_count', 0)}")
print(f"ChromaDB avg latency: {chroma_perf['latency_stats']['avg_ms']:.1f}ms")

# 只看 Redis
redis_stats = monitor.get_stats_from_db(hours=24, db_type=DatabaseType.REDIS)
redis_perf = redis_stats['per_database_stats'].get('redis', {})
print(f"Redis queries: {redis_perf.get('query_count', 0)}")
print(f"Redis avg latency: {redis_perf['latency_stats']['avg_ms']:.1f}ms")