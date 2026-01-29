#!/usr/bin/env python3
"""
Partial Result Analyzer

Specialized tool to analyze why queries return fewer results than expected.
Helps identify database capacity issues and filtering problems.

Usage:
    python analyze_partial_results.py --hours 24
    python analyze_partial_results.py --db chroma --threshold 0.5
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import dotenv
dotenv.load_dotenv()

from chatdku.core.tools.redis_listener.db_monitor import (
    DEFAULT_DB_PATH,
    DatabaseType,
)


def analyze_partial_results(
    db_path: str,
    hours: int = 24,
    db_type: str = None,
    min_fulfillment: float = 0.5
):
    """
    Analyze partial result patterns.
    
    Args:
        db_path: Path to metrics database
        hours: Hours to look back
        db_type: Filter by database ('chroma' or 'redis')
        min_fulfillment: Only show queries with fulfillment rate below this
    """
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cutoff = datetime.now() - timedelta(hours=hours)
    
    # Query for partial results
    query = """
        SELECT 
            timestamp,
            db_type,
            query_type,
            outcome,
            result_count,
            expected_top_k,
            latency_ms,
            query_text,
            user_id,
            search_mode
        FROM query_metrics
        WHERE timestamp >= ?
            AND outcome = 'partial_result'
            AND expected_top_k IS NOT NULL
            AND expected_top_k > 0
    """
    
    params = [cutoff.isoformat()]
    
    if db_type:
        query += " AND db_type = ?"
        params.append(db_type)
    
    query += " ORDER BY timestamp DESC"
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    
    if not rows:
        print(f"\n✅ No partial results found in the last {hours} hours!")
        print(f"All queries returned the expected number of documents.\n")
        conn.close()
        return
    
    # Analyze patterns
    print(f"\n{'='*80}")
    print(f"PARTIAL RESULT ANALYSIS - Last {hours} Hours")
    print(f"{'='*80}\n")
    
    print(f"Total Partial Results: {len(rows)}")
    print(f"Database Filter: {db_type.upper() if db_type else 'ALL'}\n")
    
    # Group by database
    by_db = defaultdict(list)
    by_search_mode = defaultdict(list)
    fulfillment_rates = []
    
    for row in rows:
        fulfillment = row['result_count'] / row['expected_top_k']
        fulfillment_rates.append(fulfillment)
        
        by_db[row['db_type']].append(row)
        by_search_mode[row['search_mode']].append(row)
    
    # Overall statistics
    print("━" * 80)
    print("📊 Overall Statistics")
    print("━" * 80)
    
    avg_fulfillment = sum(fulfillment_rates) / len(fulfillment_rates)
    min_fulfillment_seen = min(fulfillment_rates)
    max_fulfillment_seen = max(fulfillment_rates)
    
    print(f"Average Fulfillment Rate: {avg_fulfillment:.1%}")
    print(f"Min Fulfillment Rate: {min_fulfillment_seen:.1%}")
    print(f"Max Fulfillment Rate: {max_fulfillment_seen:.1%}")
    print()
    
    # Per-database breakdown
    print("━" * 80)
    print("📊 Per-Database Breakdown")
    print("━" * 80)
    
    for db, records in sorted(by_db.items()):
        db_name = "ChromaDB" if db == "chroma" else "Redis"
        emoji = "🔵" if db == "chroma" else "🔴"
        
        print(f"\n{emoji} {db_name}")
        print("-" * 40)
        print(f"Partial Results: {len(records)}")
        
        db_fulfillment = [r['result_count'] / r['expected_top_k'] for r in records]
        avg_db = sum(db_fulfillment) / len(db_fulfillment)
        print(f"Average Fulfillment: {avg_db:.1%}")
        
        # Expected vs returned
        expected_counts = defaultdict(int)
        returned_counts = defaultdict(int)
        
        for r in records:
            expected_counts[r['expected_top_k']] += 1
            returned_counts[r['result_count']] += 1
        
        print(f"\nMost Common Expected top_k:")
        for k, count in sorted(expected_counts.items(), key=lambda x: -x[1])[:3]:
            print(f"  {k}: {count} queries")
        
        print(f"\nMost Common Returned Counts:")
        for k, count in sorted(returned_counts.items(), key=lambda x: -x[1])[:3]:
            print(f"  {k}: {count} queries")
    
    # Search mode analysis
    if by_search_mode:
        print("\n" + "━" * 80)
        print("🔍 Per-Search-Mode Analysis")
        print("━" * 80)
        
        search_mode_names = {
            0: "Default (Chat_DKU only)",
            1: "User files only",
            2: "User files + Chat_DKU"
        }
        
        for mode, records in sorted(by_search_mode.items()):
            if mode is None:
                continue
            
            print(f"\nSearch Mode {mode}: {search_mode_names.get(mode, 'Unknown')}")
            print("-" * 40)
            print(f"Partial Results: {len(records)}")
            
            mode_fulfillment = [r['result_count'] / r['expected_top_k'] for r in records]
            avg_mode = sum(mode_fulfillment) / len(mode_fulfillment)
            print(f"Average Fulfillment: {avg_mode:.1%}")
    
    # Recent examples with low fulfillment
    print("\n" + "━" * 80)
    print(f"🔍 Recent Examples (Fulfillment < {min_fulfillment:.0%})")
    print("━" * 80)
    
    low_fulfillment_examples = [
        r for r in rows
        if (r['result_count'] / r['expected_top_k']) < min_fulfillment
    ]
    
    if low_fulfillment_examples:
        for i, row in enumerate(low_fulfillment_examples[:10], 1):
            fulfillment = row['result_count'] / row['expected_top_k']
            db_emoji = "🔵" if row['db_type'] == 'chroma' else "🔴"
            
            print(f"\n{i}. {db_emoji} {row['db_type'].upper()} - {row['timestamp'][:19]}")
            print(f"   Expected: {row['expected_top_k']} | Returned: {row['result_count']} | Fulfillment: {fulfillment:.1%}")
            print(f"   Latency: {row['latency_ms']:.1f}ms")
            print(f"   Search Mode: {row['search_mode']}")
            if row['query_text']:
                print(f"   Query: {row['query_text'][:80]}...")
    else:
        print(f"\n✅ No queries with fulfillment < {min_fulfillment:.0%}")
    
    # Recommendations
    print("\n" + "━" * 80)
    print("💡 Recommendations")
    print("━" * 80)
    
    if avg_fulfillment < 0.7:
        print("\n⚠️  WARNING: Low average fulfillment rate ({:.1%})".format(avg_fulfillment))
        print("\nPossible causes:")
        print("  1. Database doesn't have enough documents matching the filters")
        print("  2. User-specific filters (search_mode 1 or 2) are too restrictive")
        print("  3. Document filtering logic needs review")
        print("\nRecommended actions:")
        print("  • Review filtering logic in retrieval code")
        print("  • Check if users have sufficient documents uploaded")
        print("  • Consider reducing top_k for filtered searches")
        print("  • Verify index coverage and document distribution")
    elif avg_fulfillment < 0.9:
        print("\n⚠️  MODERATE: Average fulfillment rate is {:.1%}".format(avg_fulfillment))
        print("\nThis is acceptable but could be improved.")
        print("  • Monitor for trends over time")
        print("  • Check if specific search modes have lower fulfillment")
    else:
        print("\n✅ GOOD: Average fulfillment rate is {:.1%}".format(avg_fulfillment))
        print("\nMost queries are returning close to the expected number of results.")
    
    # Database-specific recommendations
    for db, records in by_db.items():
        db_fulfillment = [r['result_count'] / r['expected_top_k'] for r in records]
        avg_db = sum(db_fulfillment) / len(db_fulfillment)
        
        if avg_db < 0.8:
            db_name = "ChromaDB" if db == "chroma" else "Redis"
            print(f"\n⚠️  {db_name} has low fulfillment ({avg_db:.1%}):")
            
            if db == "chroma":
                print("  • Check ChromaDB collection size and document count")
                print("  • Verify embedding quality and similarity thresholds")
                print("  • Review metadata filtering (user_id, file_name)")
            else:
                print("  • Check Redis index size and document count")
                print("  • Verify keyword matching and BM25 scoring")
                print("  • Review query syntax and filtering logic")
    
    print("\n" + "=" * 80 + "\n")
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze partial result patterns in database queries",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to analyze (default: 24)'
    )
    
    parser.add_argument(
        '--db',
        choices=['chroma', 'redis'],
        help='Filter by database type (default: all)'
    )
    
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.5,
        help='Show examples with fulfillment below this threshold (default: 0.5)'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default=DEFAULT_DB_PATH,
        help=f'Path to metrics database (default: {DEFAULT_DB_PATH})'
    )
    
    args = parser.parse_args()
    
    # Validate database exists
    if not Path(args.db_path).exists():
        print(f"❌ Database not found: {args.db_path}")
        print("   Make sure the monitoring system is running and has recorded queries.")
        return 1
    
    analyze_partial_results(
        db_path=args.db_path,
        hours=args.hours,
        db_type=args.db,
        min_fulfillment=args.threshold
    )
    
    return 0


if __name__ == "__main__":
    exit(main())