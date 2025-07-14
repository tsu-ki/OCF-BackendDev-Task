import sqlite3
from typing import List, Dict, Optional
import pandas as pd
from .config import DB_PATH


def initialize_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS generation (publish_time TEXT, business_type TEXT, psr_type TEXT, quantity REAL, start_time TEXT, settlement_date TEXT, settlement_period INTEGER, PRIMARY KEY (psr_type, start_time))"
    )
    return conn


def store_records(conn: sqlite3.Connection, records: List[Dict]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO generation (publish_time, business_type, psr_type, quantity, start_time, settlement_date, settlement_period) VALUES (:publishTime, :businessType, :psrType, :quantity, :startTime, :settlementDate, :settlementPeriod)",
        records,
    )
    conn.commit()


def load_dataframe(
    conn: sqlite3.Connection,
    start: Optional[str] = None,
    end: Optional[str] = None,
    psr_type: Optional[str] = None,
):
    query = "SELECT start_time, psr_type, quantity FROM generation"
    clauses, params = [], []
    if start:
        clauses.append("start_time >= ?")
        params.append(start)
    if end:
        clauses.append("start_time <= ?")
        params.append(end)
    if psr_type:
        clauses.append("psr_type = ?")
        params.append(psr_type)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY start_time"
    return pd.read_sql_query(query, conn, params=params, parse_dates=["start_time"]) 