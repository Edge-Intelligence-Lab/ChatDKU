#!/usr/bin/env python3
"""
Database Query Monitor - Daily Email Report Sender

Sends periodic summary emails instead of immediate alerts.
Designed to run via cron job.

Usage:
    # Send daily summary (last 24 hours)
    python send_daily_report.py
    
    # Send weekly summary (last 7 days)
    python send_daily_report.py --hours 168
    
    # Dry run (no email, just print)
    python send_daily_report.py --dry-run

Cron examples:
    # Daily at 9 AM
    0 9 * * * cd /path/to/chatdku && python -m chatdku.core.tools.redis_listener.send_daily_report
    
    # Twice daily (9 AM and 6 PM)
    0 9,18 * * * cd /path/to/chatdku && python -m chatdku.core.tools.redis_listener.send_daily_report --hours 12
"""

import argparse
import sys
import os
from pathlib import Path
import json

import dotenv
dotenv.load_dotenv()

from chatdku.core.tools.db_monitor.db_monitor import (
    get_query_monitor,
    DEFAULT_DB_PATH,
)
from chatdku.core.tools.db_monitor.report.text import render_summary_report
from chatdku.core.tools.email.email_tool import EmailTools


def send_daily_report(hours: int = 24, dry_run: bool = False):
    if not Path(DEFAULT_DB_PATH).exists():
        print(f"Database not found: {DEFAULT_DB_PATH}", file=sys.stderr)
        return 1

    monitor = get_query_monitor()

    summary = monitor.collect_summary_data(hours=hours)

    report_text = render_summary_report(
        overall_stats=summary["overall"],
        chroma_stats=summary["chroma"],
        redis_stats=summary["redis"],
        hours=summary["meta"]["hours"],
        db_path=summary["meta"]["db_path"],
    )

    if dry_run:
        print("=" * 80)
        print("DRY RUN MODE - NO EMAIL SENT")
        print("=" * 80)
        print(report_text)
        print("=" * 80)
        return 0

    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", 25))
    from_email = os.getenv("EMAIL_HOST_USER")
    to_email = os.getenv("EMAIL_TO")

    if not all([host, port, from_email, to_email]):
        print("Missing email configuration", file=sys.stderr)
        return 1

    to_email_list = json.loads(to_email)

    subject = f"[ChatDKU] Database Daily Summary ({hours}h)"

    email = EmailTools(
        host=host,
        port=port,
        receiver_email=to_email_list,
        sender_name="ChatDKU",
        sender_email=from_email,
    )

    email.send_mail(subject, report_text)
    print("Daily summary email sent")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Send periodic database query monitoring reports via email",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Send daily report (last 24 hours)
  %(prog)s --hours 168        # Send weekly report (last 7 days)
  %(prog)s --hours 12         # Send twice-daily report (last 12 hours)
  %(prog)s --dry-run          # Test without sending email

Cron Setup:
  # Daily at 9 AM
  0 9 * * * /path/to/python /path/to/send_daily_report.py
  
  # Twice daily (9 AM and 6 PM) with 12-hour reports
  0 9,18 * * * /path/to/python /path/to/send_daily_report.py --hours 12
  
  # Weekly on Monday at 8 AM
  0 8 * * 1 /path/to/python /path/to/send_daily_report.py --hours 168
        """
    )
    
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to include in report (default: 24)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print report without sending email'
    )
    
    args = parser.parse_args()
    
    return send_daily_report(hours=args.hours, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())