import requests
from datetime import datetime
from typing import List, Dict
from .config import BASE_URL


def fetch_generation_data(start: datetime, end: datetime) -> List[Dict]:
    """Retrieve wind and solar generation data for the inclusive start-end window. """
    if (end - start).days > 6:
        raise ValueError("API window limited to 7 days; split your request.")
    params = {
        "from": start.strftime("%Y-%m-%d"),
        "to": end.strftime("%Y-%m-%d"),
        "format": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]

# Back-compat alias
fetch_chunk = fetch_generation_data 