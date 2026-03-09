import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "local")
DATA_DIR = os.getenv("DATA_DIR", str(ROOT_DIR / "data"))

# BASE_SCAN_PATH is used if this value is not specified on the command line.
BASE_SCAN_PATH = os.getenv("BASE_SCAN_PATH", r"c:\git")

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
