import json
from datetime import datetime


def render_summary_report(
    overall_stats: dict,
    chroma_stats: dict,
    redis_stats: dict,
    *,
    hours: int = 24,
    db_path: str,
) -> str:
    """
    Render a human-readable summary report from precomputed stats.
    This function does NOT access database or monitor logic.
    """
    
    # Get overall stats
    if not overall_stats or "error" in overall_stats or "message" in overall_stats:
        return f"Error generating report: {overall_stats}"
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def fmt_percent(v):
        return f"{v:.1%}" if isinstance(v, (int, float)) else "N/A"

    def fmt_latency(stats):
        return (
            f"avg={stats['avg_ms']:.1f}ms, "
            f"min={stats['min_ms']:.1f}ms, "
            f"max={stats['max_ms']:.1f}ms"
        )
    
    report = f"""
        ========================================
        Database Query Monitor - Summary Report
        ========================================
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Report Period: Last {hours} hours
        Database Location: {db_path}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        📊 Overall Statistics (All Databases)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Total Queries: {overall_stats['total_queries']}
        Overall Error Rate: {fmt_percent(overall_stats['overall_error_rate'])}
        Overall Partial Rate: {fmt_percent(overall_stats.get('overall_partial_rate', 0))}
        Latency: {fmt_latency(overall_stats['overall_latency_stats'])}

        Database Distribution:
        {json.dumps(overall_stats['db_type_distribution'], indent=2)}

        Outcome Distribution:
        {json.dumps(overall_stats['outcome_distribution'], indent=2)}
        """


    def render_db_block(title: str, stats: dict, key: str) -> str:
        db_stats = stats.get("per_database_stats", {}).get(key)
        if not db_stats:
            return f"\n{title}\nNo queries in this period.\n"

        fulfillment = db_stats["result_stats"].get("avg_fulfillment_rate")
        fulfillment_str = fmt_percent(fulfillment) if fulfillment is not None else "N/A"

        return f"""
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            {title}
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            Query Count: {db_stats['query_count']}
            Error Rate: {fmt_percent(db_stats['error_rate'])}
            Partial Rate: {fmt_percent(db_stats['partial_rate'])}
            Latency: {fmt_latency(db_stats['latency_stats'])}
            Average Results: {db_stats['result_stats']['avg_count']:.1f}
            Fulfillment Rate: {fulfillment_str}

            Outcomes:
            {json.dumps(db_stats['outcome_distribution'], indent=2)}
            """

    report += render_db_block("🔵 ChromaDB (Vector Search)", chroma_stats, "chroma")
    report += render_db_block("🔴 Redis (Keyword Search)", redis_stats, "redis")

    report += f"""
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Time Range
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Start: {overall_stats['time_range']['start']}
        End:   {overall_stats['time_range']['end']}

        ========================================
        """

    return report.strip()
