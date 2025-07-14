from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1/generation/actual/per-type/wind-and-solar")
DB_PATH = os.getenv("DB_PATH", "elexon_generation.db") 