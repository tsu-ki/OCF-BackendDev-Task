from datetime import datetime, timedelta
from .elexon_api import fetch_generation_data as fetch_chunk
from .storage import initialize_db, store_records, load_dataframe
from .plotting import plot_generation


def fetch_year(year: int) -> None:
    """Download a full calendar year of generation data and persist to SQLite."""
    conn = initialize_db()
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31)
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=6), end)
        data = fetch_chunk(current, chunk_end)
        if data:
            store_records(conn, data)
        current = chunk_end + timedelta(days=1)
    conn.close()

__all__ = [
    "fetch_year",
    "initialize_db",
    "store_records",
    "load_dataframe",
    "plot_generation",
]  # explicit re-export for convenience
__all__.append("fetch_chunk") 