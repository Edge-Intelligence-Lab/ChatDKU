#!/usr/bin/env python3
"""
Database Query Monitor - Report Generation CLI

This CLI is intended for developer diagnostics and ad-hoc analysis.
It is not used by the email reporting pipeline.

Standalone tool to generate reports from ChromaDB and Redis query monitoring.
Can be run from anywhere, independent of the retriever/agent.

Usage:
    python query_report.py                      # Default: last 24 hours, all databases
    python query_report.py --hours 48           # Last 48 hours
    python query_report.py --db chroma          # Only ChromaDB queries
    python query_report.py --db redis           # Only Redis queries
    python query_report.py --json               # Output as JSON
    python query_report.py --export report.txt  # Export to file
    python query_report.py --compare            # Side-by-side comparison
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add ChatDKU to path if needed
import dotenv
dotenv.load_dotenv()

from chatdku.core.tools.db_monitor.db_monitor import (
    get_query_monitor,
    DatabaseType,
    DEFAULT_DB_PATH,
)


def format_report_text(stats: dict, hours: int, db_filter: str = None) -> str:
    """Format statistics as human-readable text"""
    if "error" in stats or "message" in stats:
        return f"Error: {stats}"
    
    db_name = db_filter.upper() if db_filter else "ALL DATABASES"
    
    report = f"""
╔════════════════════════════════════════════════════════════╗
║    Database Query Monitor - Report ({db_name})            ║
╚════════════════════════════════════════════════════════════╝

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Report Period: Last {hours} hours
Database: {DEFAULT_DB_PATH}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Overview Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Queries: {stats['total_queries']}
Overall Error Rate: {stats['overall_error_rate']:.1%}
Overall Partial Result Rate: {stats.get('overall_partial_rate', 0):.1%}
Time Range: {stats['time_range']['start']} → {stats['time_range']['end']}
"""
    
    # Database distribution (if showing all databases)
    if not db_filter and 'db_type_distribution' in stats:
        report += "\nDatabase Distribution:\n"
        for db, count in stats['db_type_distribution'].items():
            percentage = (count / stats['total_queries'] * 100) if stats['total_queries'] > 0 else 0
            emoji = "🔵" if db == "chroma" else "🔴"
            report += f"{emoji} {db.upper():10s}: {count:6d} ({percentage:5.1f}%)\n"
    
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  Latency Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Average: {stats['overall_latency_stats']['avg_ms']:.1f}ms
Minimum: {stats['overall_latency_stats']['min_ms']:.1f}ms
Maximum: {stats['overall_latency_stats']['max_ms']:.1f}ms

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Results Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Average Results per Query: {stats['overall_result_stats']['avg_count']:.1f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Outcome Distribution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # Outcome distribution with percentages and emojis
    total = stats['total_queries']
    outcome_emojis = {
        "success": "✅",
        "empty_result": "⚠️",
        "partial_result": "⚡",
        "timeout": "⏱️",
        "connection_error": "🔌",
        "query_error": "❌",
        "unknown_error": "❓"
    }
    
    for outcome, count in sorted(stats['outcome_distribution'].items()):
        percentage = (count / total * 100) if total > 0 else 0
        emoji = outcome_emojis.get(outcome, "❓")
        report += f"{emoji} {outcome:20s}: {count:6d} ({percentage:5.1f}%)\n"
    
    # Per-database breakdown
    if 'per_database_stats' in stats and stats['per_database_stats']:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "📊 Per-Database Breakdown\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for db_name, db_stats in stats['per_database_stats'].items():
            emoji = "🔵 ChromaDB" if db_name == "chroma" else "🔴 Redis"
            report += f"{emoji} (Vector Search)" if db_name == "chroma" else f"{emoji} (Keyword Search)"
            report += "\n" + "-" * 60 + "\n"
            report += f"Query Count: {db_stats['query_count']}\n"
            report += f"Error Rate: {db_stats['error_rate']:.1%}\n"
            report += f"Partial Result Rate: {db_stats.get('partial_rate', 0):.1%}\n"
            report += f"Avg Latency: {db_stats['latency_stats']['avg_ms']:.1f}ms\n"
            report += f"Avg Results: {db_stats['result_stats']['avg_count']:.1f}\n"
            
            # Result fulfillment rate
            fulfillment = db_stats['result_stats'].get('avg_fulfillment_rate')
            if fulfillment is not None:
                report += f"Result Fulfillment: {fulfillment:.1%}\n"
            
            report += "\nOutcomes:\n"
            for outcome, count in sorted(db_stats['outcome_distribution'].items()):
                percentage = (count / db_stats['query_count'] * 100) if db_stats['query_count'] > 0 else 0
                emoji_out = outcome_emojis.get(outcome, "❓")
                report += f"  {emoji_out} {outcome:18s}: {count:4d} ({percentage:5.1f}%)\n"
            report += "\n"
        
    # Query snippets (recent samples)
    samples = stats.get("query_samples", [])
    if samples:
        report += """
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🔍 Recent Query Samples
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
        for s in samples:
            report += (
                f"[{s['timestamp']}] "
                f"{s['db_type'].upper()} | {s['query_type']} | "
                f"{s['outcome']} | {s['latency_ms']:.0f}ms\n"
                f"  → \"{s['query_snippet']}\"\n\n"
            )

    report += "\n" + "═" * 80 + "\n"
    # report += "═" * 60 + "\n"
    return report


def format_comparison_report(hours: int) -> str:
    """Generate side-by-side comparison of ChromaDB vs Redis"""
    monitor = get_query_monitor()
    
    chroma_stats = monitor.get_stats_from_db(hours=hours, db_type=DatabaseType.CHROMA)
    redis_stats = monitor.get_stats_from_db(hours=hours, db_type=DatabaseType.REDIS)
    
    report = f"""
        ╔════════════════════════════════════════════════════════════╗
        ║        ChromaDB vs Redis - Performance Comparison          ║
        ╚════════════════════════════════════════════════════════════╝

        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Report Period: Last {hours} hours

        """
    
    # Extract stats
    def get_db_specific(stats):
        if "error" in stats or "message" in stats:
            return None
        db_key = stats.get('db_type_filter', 'unknown')
        return stats.get('per_database_stats', {}).get(db_key, None)
    
    chroma_db = get_db_specific(chroma_stats)
    redis_db = get_db_specific(redis_stats)
    
    # Header
    report += f"{'Metric':<35} {'ChromaDB (Vector)':^22} {'Redis (Keyword)':^22}\n"
    report += "━" * 80 + "\n"
    
    # Query counts
    chroma_count = chroma_db['query_count'] if chroma_db else 0
    redis_count = redis_db['query_count'] if redis_db else 0
    report += f"{'Total Queries':<35} {chroma_count:^22} {redis_count:^22}\n"
    
    # Error rates
    chroma_err = f"{chroma_db['error_rate']:.1%}" if chroma_db else "N/A"
    redis_err = f"{redis_db['error_rate']:.1%}" if redis_db else "N/A"
    report += f"{'Error Rate':<35} {chroma_err:^22} {redis_err:^22}\n"
    
    # Partial result rates
    chroma_partial = f"{chroma_db.get('partial_rate', 0):.1%}" if chroma_db else "N/A"
    redis_partial = f"{redis_db.get('partial_rate', 0):.1%}" if redis_db else "N/A"
    report += f"{'Partial Result Rate':<35} {chroma_partial:^22} {redis_partial:^22}\n"
    
    # Average latency
    chroma_lat = f"{chroma_db['latency_stats']['avg_ms']:.1f}ms" if chroma_db else "N/A"
    redis_lat = f"{redis_db['latency_stats']['avg_ms']:.1f}ms" if redis_db else "N/A"
    report += f"{'Average Latency':<35} {chroma_lat:^22} {redis_lat:^22}\n"
    
    # Max latency
    chroma_max = f"{chroma_db['latency_stats']['max_ms']:.1f}ms" if chroma_db else "N/A"
    redis_max = f"{redis_db['latency_stats']['max_ms']:.1f}ms" if redis_db else "N/A"
    report += f"{'Max Latency':<35} {chroma_max:^22} {redis_max:^22}\n"
    
    # Average results
    chroma_res = f"{chroma_db['result_stats']['avg_count']:.1f}" if chroma_db else "N/A"
    redis_res = f"{redis_db['result_stats']['avg_count']:.1f}" if redis_db else "N/A"
    report += f"{'Average Results':<35} {chroma_res:^22} {redis_res:^22}\n"
    
    # Result fulfillment
    chroma_fulfill = chroma_db['result_stats'].get('avg_fulfillment_rate') if chroma_db else None
    redis_fulfill = redis_db['result_stats'].get('avg_fulfillment_rate') if redis_db else None
    chroma_fulfill_str = f"{chroma_fulfill:.1%}" if chroma_fulfill is not None else "N/A"
    redis_fulfill_str = f"{redis_fulfill:.1%}" if redis_fulfill is not None else "N/A"
    report += f"{'Result Fulfillment Rate':<35} {chroma_fulfill_str:^22} {redis_fulfill_str:^22}\n"
    
    report += "━" * 80 + "\n\n"
    
    # Analysis
    if chroma_db and redis_db:
        report += "📊 Analysis\n"
        report += "━" * 80 + "\n\n"
        
        # Success rates
        chroma_success = chroma_db['outcome_distribution'].get('success', 0) / chroma_count if chroma_count > 0 else 0
        redis_success = redis_db['outcome_distribution'].get('success', 0) / redis_count if redis_count > 0 else 0
        
        report += f"✅ Success Rate:\n"
        report += f"   ChromaDB: {chroma_success:.1%}  |  Redis: {redis_success:.1%}\n"
        if abs(chroma_success - redis_success) < 0.01:
            report += f"   → Both databases have similar success rates\n\n"
        elif chroma_success > redis_success:
            report += f"   → ChromaDB has {(chroma_success - redis_success):.1%} higher success rate\n\n"
        else:
            report += f"   → Redis has {(redis_success - chroma_success):.1%} higher success rate\n\n"
        
        # Partial result rates
        chroma_partial_val = chroma_db.get('partial_rate', 0)
        redis_partial_val = redis_db.get('partial_rate', 0)
        
        if chroma_partial_val > 0 or redis_partial_val > 0:
            report += f"⚡ Partial Result Rate:\n"
            report += f"   ChromaDB: {chroma_partial_val:.1%}  |  Redis: {redis_partial_val:.1%}\n"
            if chroma_partial_val > redis_partial_val:
                report += f"   → ChromaDB has {(chroma_partial_val - redis_partial_val):.1%} more partial results\n"
                report += f"   → This means ChromaDB more often returns fewer documents than requested\n\n"
            elif redis_partial_val > chroma_partial_val:
                report += f"   → Redis has {(redis_partial_val - chroma_partial_val):.1%} more partial results\n"
                report += f"   → This means Redis more often returns fewer documents than requested\n\n"
        
        # Latency comparison
        c_lat = chroma_db['latency_stats']['avg_ms']
        r_lat = redis_db['latency_stats']['avg_ms']
        diff = abs(c_lat - r_lat)
        
        report += f"⏱️  Latency:\n"
        report += f"   ChromaDB: {c_lat:.1f}ms  |  Redis: {r_lat:.1f}ms\n"
        if diff < 10:
            report += f"   → Both databases have similar latency ({diff:.1f}ms difference)\n\n"
        elif c_lat < r_lat:
            report += f"   → ChromaDB is {diff:.1f}ms faster ({(diff/r_lat*100):.1f}% faster)\n\n"
        else:
            report += f"   → Redis is {diff:.1f}ms faster ({(diff/c_lat*100):.1f}% faster)\n\n"
        
        # Result fulfillment comparison
        if chroma_fulfill is not None and redis_fulfill is not None:
            report += f"📈 Result Fulfillment:\n"
            report += f"   ChromaDB: {chroma_fulfill:.1%}  |  Redis: {redis_fulfill:.1%}\n"
            if abs(chroma_fulfill - redis_fulfill) < 0.05:
                report += f"   → Both databases fulfill similar proportion of requested results\n\n"
            elif chroma_fulfill > redis_fulfill:
                report += f"   → ChromaDB returns closer to requested top_k ({(chroma_fulfill - redis_fulfill):.1%} better)\n\n"
            else:
                report += f"   → Redis returns closer to requested top_k ({(redis_fulfill - chroma_fulfill):.1%} better)\n\n"
    return report


def generate_report(
    hours: int = 24, 
    query_type: str = None, 
    db_type: str = None,
    output_format: str = "text",
    compare: bool = False
):
    """Generate and display report"""
    if compare:
        return format_comparison_report(hours)
    
    monitor = get_query_monitor()
    db_type_enum = DatabaseType(db_type) if db_type else None
    stats = monitor.get_stats_from_db(hours=hours, query_type=query_type, db_type=db_type_enum)
    
    if output_format == "json":
        return json.dumps(stats, indent=2, default=str)
    else:
        return format_report_text(stats, hours, db_type)


def export_report(content: str, filepath: str):
    """Export report to file"""
    try:
        Path(filepath).write_text(content, encoding='utf-8')
        print(f"✅ Report exported to: {filepath}")
    except Exception as e:
        print(f"❌ Failed to export report: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Database Query Monitor reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            %(prog)s                          # Last 24 hours, all databases
            %(prog)s --hours 48               # Last 48 hours
            %(prog)s --db chroma              # Only ChromaDB queries
            %(prog)s --db redis               # Only Redis queries
            %(prog)s --compare                # Side-by-side comparison
            %(prog)s --json                   # Output as JSON
            %(prog)s --export report.txt      # Save to file
            """
    )
    
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to include in report (default: 24)'
    )
    
    parser.add_argument(
        '--type',
        choices=['vector', 'keyword'],
        help='Filter by query type (default: all)'
    )
    
    parser.add_argument(
        '--db',
        choices=['chroma', 'redis'],
        help='Filter by database type (default: all)'
    )
    
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Show side-by-side comparison of ChromaDB vs Redis'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output report in JSON format'
    )
    
    parser.add_argument(
        '--export',
        type=str,
        metavar='FILE',
        help='Export report to file'
    )
    
    args = parser.parse_args()
    
    # Validate database exists
    if not Path(DEFAULT_DB_PATH).exists():
        print(f"❌ Database not found: {DEFAULT_DB_PATH}", file=sys.stderr)
        print("   Make sure the monitoring system is running and has recorded queries.")
        sys.exit(1)
    
    # Generate report
    output_format = 'json' if args.json else 'text'
    report = generate_report(
        hours=args.hours,
        query_type=args.type,
        db_type=args.db,
        output_format=output_format,
        compare=args.compare
    )
    
    # Output or export
    if args.export:
        export_report(report, args.export)
    else:
        print(report)


if __name__ == "__main__":
    main()