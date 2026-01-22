#!/usr/bin/env python3

import argparse
import os
import sys
import json
import logging
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from chatdku.chatdku.config import config

from openpyxl import load_workbook


DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatdku_db",
    "user": "chatdku_user",
}


class ScheduleIngestor:
    """Ingest DKU course schedule data into PostgreSQL"""

    def __init__(self, args):
        self.args = args

        if not args.term or not str(args.term).strip():
            raise ValueError(
                "Argument --term is required and cannot be empty. "
                "Example: --term 'Spring 2026'"
            )

        self.term = args.term.strip()
        self.setup_logging()
        self.setup_database_connection()
        self.load_schema()

    def setup_logging(self):
        log_file = Path(self.args.pool) / "schedule_ingestor.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode="a"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Schedule Ingestor started")

    def setup_database_connection(self):
        db_config = DEFAULT_DB_CONFIG.copy()

        if self.args.db_host:
            db_config["host"] = self.args.db_host
        if self.args.db_port:
            db_config["port"] = self.args.db_port
        if self.args.db_name:
            db_config["database"] = self.args.db_name
        if self.args.db_user:
            db_config["user"] = self.args.db_user

        db_config["password"] = os.environ.get("DB_PWD")

        self.conn = psycopg2.connect(**db_config)
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        self.logger.info(f"Connected to PostgreSQL database: {db_config['database']}")

    def load_schema(self):
        schema_path = Path(self.args.schema)
        if not schema_path.is_absolute():
            schema_path = Path(__file__).parent / schema_path

        with open(schema_path, "r") as f:
            self.schema = json.load(f)

        self.logger.info(f"Schema loaded from: {schema_path}")

    def store_row(self, row: dict, table="dku_class_schedule"):
        from psycopg2 import sql

        cursor = self.conn.cursor()
        columns = list(row.keys())
        values = [row[c] for c in columns]

        insert_sql = sql.SQL(
            "INSERT INTO {table} ({fields}) VALUES ({placeholders})"
        ).format(
            table=sql.Identifier(table),
            fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
            placeholders=sql.SQL(", ").join(sql.Placeholder() * len(columns)),
        )

        cursor.execute(insert_sql, values)
        cursor.close()

    # ===== XLSX PART =====

    def process_xlsx(self, file_path: Path):
        self.logger.info(f"Processing schedule XLSX: {file_path}")

        wb = load_workbook(file_path, data_only=True)

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            self.logger.info(f"Processing sheet: {sheet_name}")

            rows = list(sheet.iter_rows(values_only=True))
            if len(rows) < 2:
                continue

            # 第二行才是 column name
            headers = [str(h).strip() if h else None for h in rows[1]]

            for row_values in rows[2:]:
                row_dict = {
                    headers[i]: row_values[i]
                    for i in range(len(headers))
                    if headers[i] is not None
                }

                cleaned = self.clean_row(row_dict)
                cleaned["term"] = self.term
                
                if "term" not in cleaned or not cleaned["term"]:
                    raise RuntimeError(
                        f"Missing term when ingesting row from {file_path}"
                    )
                self.store_row(cleaned)

    # ===== CLEANING =====

    def clean_row(self, row: dict) -> dict:
        EXCEL_TO_DB_COL = {
            # "Term": "term",
            "Session": "session",
            "Subject": "subject",
            "Catalog": "catalog",
            "Section": "section",
            "Name": "instructor_name",
            "Descr": "course_title",
            "Facil ID": "facility_id",
            "Mtg Start": "meeting_start",
            "Mtg End": "meeting_end",
            "Max Units": "max_units",
            "Type": "class_type",
            "Email": "instructor_email",
            "Preferred": "preferred"
        }

        cleaned = {}

        def empty_to_none(v):
            return None if v is None or v == "" else v

        # 映射列
        for key, value in row.items():
            db_col = EXCEL_TO_DB_COL.get(key)
            if db_col:
                cleaned[db_col] = empty_to_none(value)
        if "catalog" in cleaned and isinstance(cleaned["catalog"], str):
            cleaned["catalog"] = cleaned["catalog"].strip()

        # 处理 days 列，组合 Mon-Fri
        days_list = []
        for day in ["Mon","Tues","Wed","Thurs","Fri"]:
            val = row.get(day)
            if isinstance(val, str) and val.strip().upper() in ("Y", "YES"):
                days_list.append(day)
        if days_list:
            cleaned["days"] = days_list

        # 处理时间
        for k in ["meeting_start", "meeting_end"]:
            if k in cleaned and cleaned[k]:
                if isinstance(cleaned[k], str) and len(cleaned[k]) == 5:  # HH:MM
                    cleaned[k] += ":00"

        # 处理 max_units
        if "max_units" in cleaned and cleaned["max_units"]:
            cleaned["max_units"] = float(cleaned["max_units"])

        # 全部列名小写
        cleaned = {k.lower(): v for k, v in cleaned.items()}
        return cleaned

    def process_pool(self):
        pool_path = Path(self.args.pool)
        self.logger.info(f"Resolved pool path: {pool_path.resolve()}")

        if not pool_path.exists():
            self.logger.error(f"Pool directory does not exist: {pool_path}")
            sys.exit(1)

        xlsx_files = list(pool_path.rglob("*.xlsx"))
        if not xlsx_files:
            self.logger.info("No XLSX schedule files found")
            return

        self.logger.info(f"Found {len(xlsx_files)} XLSX files to ingest")

        for file_path in xlsx_files:
            self.process_xlsx(file_path)

        self.logger.info("Schedule ingestion completed")

    def cleanup(self):
        if hasattr(self, "conn"):
            self.conn.close()
            self.logger.info("Database connection closed")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest DKU course schedule XLSX into PostgreSQL"
    )

    parser.add_argument(
        "--pool",
        default=config.course_schedule_path,
        help="Directory containing schedule XLSX files",
    )

    parser.add_argument(
        "--schema",
        default="schedule_schema.json",
        help="JSON schema file",
    )

    parser.add_argument(
        "--term",
        default="Spring 2026",
        help="Term of the course schedule (e.g., Spring 2026)",
    )

    parser.add_argument("--db-host")
    parser.add_argument("--db-port", type=int)
    parser.add_argument("--db-name")
    parser.add_argument("--db-user")

    args = parser.parse_args()

    ingestor = None
    try:
        ingestor = ScheduleIngestor(args)
        ingestor.process_pool()
    finally:
        if ingestor:
            ingestor.cleanup()


if __name__ == "__main__":
    main()