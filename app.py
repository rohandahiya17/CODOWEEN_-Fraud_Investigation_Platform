from pathlib import Path
import sys

SOURCE_DIR = Path(__file__).resolve().parent / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from fraud_investigator.dashboard import run

run()
