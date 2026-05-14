# 🎮 Twitch Clip Pipeline

Automated pipeline for collecting, processing, and analyzing Twitch clips, focused on identifying the best content for reuse. Future phases will include automatic download, editing, and publishing of videos.

---

## 🏗️ Architecture

The project follows the **Medallion** architecture (Bronze → Silver → Gold), a common pattern in modern data pipelines:

```
Twitch API
    │
    ▼
[Bronze] → Raw clip collection per streamer
    │
    ▼
[Silver] → Cleaning, typing, enrichment and scoring
    │
    ▼
[Gold]   → Final filtering and ranking of the best clips
```

---

## 📦 Pipeline Stages

### 🥉 Bronze — Collection
- Reads the streamer list from `data/streamers.txt`
- Authenticates with the Twitch API via OAuth2 (Client Credentials)
- Fetches all clips from the last **N days** for each streamer
- Saves raw data to `data/bronze.json`

### 🥈 Silver — Transformation
- Removes duplicates and clips with zero views
- Converts data types (`created_at`, `duration`)
- Enriches data with derived fields:
  - `created_date`, `created_hour`, `clip_age_days`
- Calculates a **score** for each clip based on:
  - `view_velocity` — views per day of the clip's life
  - `duration_weight` — higher weight for clips between 15s and 60s
  - `featured_boost` — bonus for featured clips
- Saves to `data/silver.json`

### 🥇 Gold — Curation
- Filters only clips within the ideal duration range (15s–60s)
- Sorts by score descending
- Adds a `rank` column
- Saves the final ranking to `data/gold.json`

---

## 🗺️ Roadmap

- [x] Clip collection via Twitch API
- [x] Data cleaning and enrichment
- [x] Clip scoring and ranking
- [ ] Automatic download of selected clips
- [ ] Automatic video editing (cuts, captions, etc.)
- [ ] Automatic publishing to social media

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+
- A [Twitch Developer](https://dev.twitch.tv/) account with an application created

### 2. Installation

```bash
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file at the project root:

```env
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
```

Create the `data/streamers.txt` file with one streamer per line:

```
gaules
cellbit
coringa
```

### 4. Run

```bash
python src/extracion.py
```

The pipeline runs all three stages in sequence and generates the output files under `data/`.

---

## 📁 Project Structure

```
.
├── data/
│   ├── streamers.txt       # List of monitored streamers
│   ├── bronze.json         # Raw data collected from the API
│   ├── silver.json         # Cleaned and enriched data
│   └── gold.json           # Final ranking of the best clips
├── logs/
│   └── app.log             # Rotating logs (7-day retention)
├── src/
│   ├── config.py           # Logger configuration
│   ├── extracion.py        # Pipeline orchestration (bronze/silver/gold)
│   └── controllers/
│       └── twitch.py       # Twitch API integration
├── .env                    # Credentials (do not commit)
├── requirements.txt
└── README.md
```

---

## 🔧 Main Dependencies

| Package | Purpose |
|---|---|
| `requests` | Twitch API calls |
| `pandas` | Data transformation and analysis |
| `python-dotenv` | Environment variable loading |
| `loguru` | Structured logging with rotation |
