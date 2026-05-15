import sys
import os

# Allow src/ modules to resolve their own imports (e.g. `from config import ...`)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.extracion import medallion
from src.download import run as run_downloads
from src.edit import run as run_edit


def run_pipeline():
    for stage in medallion:
        stage()
    run_downloads()
    run_edit()


if __name__ == "__main__":
    run_pipeline()
