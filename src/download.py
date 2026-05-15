from config import logger, pipeline
import os
import json
import pandas as pd

def run():
  # LOAD INFO 
    df = pd.read_json("data/gold.json")
    DOWNLOAD_CAP = pipeline.get("download_cap", 5)  
    logger.info(f"Selected {DOWNLOAD_CAP}/{len(df)}")
    df = df.head(DOWNLOAD_CAP)

    # SET DIRECTORY
    os.makedirs("data/raw", exist_ok=True)


if __name__ == "__main__":
    run()

