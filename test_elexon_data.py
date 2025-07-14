import unittest
from unittest.mock import patch, Mock
from datetime import datetime
import sqlite3
import ocf_pipeline.elexon_api as api
import ocf_pipeline.storage as st

sample_response = {
    "data": [
        {
            "publishTime": "2023-07-21T06:58:08Z",
            "businessType": "Wind generation",
            "psrType": "Wind Onshore",
            "quantity": 640.283,
            "startTime": "2023-07-21T04:30:00Z",
            "settlementDate": "2023-07-21",
            "settlementPeriod": 12
        }
    ],
    "metadata": {"datasets": ["AGWS"]}
}

class TestElexonData(unittest.TestCase):
    @patch("ocf_pipeline.elexon_api.requests.get")
    def test_fetch_chunk(self, mock_get):
        mock_resp = Mock()
        mock_resp.json.return_value = sample_response
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        records = api.fetch_generation_data(datetime(2023, 7, 18), datetime(2023, 7, 19))
        self.assertEqual(records, sample_response["data"])

    def test_store_and_load(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE generation (publish_time TEXT, business_type TEXT, psr_type TEXT, quantity REAL, start_time TEXT, settlement_date TEXT, settlement_period INTEGER, PRIMARY KEY (psr_type, start_time))"
        )
        st.store_records(conn, sample_response["data"])
        df = st.load_dataframe(conn)
        self.assertEqual(len(df), 1)
        self.assertAlmostEqual(df["quantity"].iloc[0], 640.283, places=3)
        conn.close()

if __name__ == "__main__":
    unittest.main() 