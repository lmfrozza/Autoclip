# 🎮 Autoclip

Automated pipeline for collecting, processing, downloading, and transcribing Twitch clips — focused on identifying the best content for reuse.

---

## 🏗️ Architecture

The project follows the **Medallion** architecture (Bronze → Silver → Gold) for data processing, followed by a download and transcription stage:

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
    │
    ▼
[Download] → Top N clips downloaded from Twitch
    │
    ▼
[Subtitles] → Auto-transcription via faster-whisper → .srt files
```

---

## 📦 Pipeline Stages

### 🥉 Bronze — Collection
- Authenticates with the Twitch API via OAuth2 (Client Credentials)
- Reads the streamer list from `config.yaml`
- Fetches all clips from the last **N days** for each streamer
- Saves raw data to `data/bronze.json`

### 🥈 Silver — Transformation
- Removes duplicates and clips with zero views
- Converts data types (`created_at`, `duration`)
- Enriches data with derived fields: `created_date`, `created_hour`, `clip_age_days`
- Calculates a **score** for each clip based on:
  - `view_velocity` — views per day of the clip's life
  - `duration_weight` — higher weight for clips between 15s and 60s
  - `featured_boost` — bonus for featured clips
- Saves to `data/silver.json`

### 🥇 Gold — Curation
- Filters only clips within the ideal duration range (15s–60s)
- Sorts by score descending and adds a `rank` column
- Saves the final ranking to `data/gold.json`

### ⬇️ Download
- Reads the top N clips from `data/gold.json` (controlled by `download_cap` in `config.yaml`)
- Downloads each clip as `.mp4` to `data/raw/` using `yt-dlp`

### 📝 Subtitles
- Transcribes all `.mp4` files in `data/raw/` using `faster-whisper`
- Generates a `.srt` subtitle file alongside each video
- Uses the `turbo` model with VAD filter for silence removal

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

Edit `config.yaml` to set your streamers and pipeline parameters:

```yaml
streamers:
  - cellbit
  - gaules
  - coringa
  - razah

pipeline:
  range_days: 1      # how many days back to fetch clips
  download_cap: 2    # how many top clips to download
```

### 4. Run

**Extraction pipeline** (Bronze → Silver → Gold):
```bash
python src/extracion.py
```

**Download + transcription** (top N clips from gold):
```bash
python src/download.py
```

---

## 📁 Project Structure

```
.
├── data/
│   ├── bronze.json         # Raw data collected from the API
│   ├── silver.json         # Cleaned and enriched data
│   ├── gold.json           # Final ranking of the best clips
│   └── raw/                # Downloaded .mp4 clips and .srt subtitles
├── logs/
│   └── app.log             # Rotating logs (7-day retention)
├── src/
│   ├── config.py           # Logger and config loader
│   ├── extracion.py        # Medallion pipeline (bronze/silver/gold)
│   └── download.py         # Download and transcription
├── config.yaml             # Streamers list and pipeline settings
├── .env                    # Credentials (do not commit)
├── requirements.txt
└── README.md
```

---

## 🔧 Main Dependencies

| Package | Purpose |
|---|---|
| `twitch-package` | Twitch API integration |
| `pandas` | Data transformation and analysis |
| `yt-dlp` | Clip download from Twitch |
| `faster-whisper` | Audio transcription to subtitles |
| `python-dotenv` | Environment variable loading |
| `loguru` | Structured logging with rotation |
| `PyYAML` | Config file parsing |

---

## 🗺️ Roadmap

- [x] Clip collection via Twitch API
- [x] Data cleaning, enrichment and scoring
- [x] Clip ranking (Medallion architecture)
- [x] Automatic download of top clips
- [x] Auto-transcription and subtitle generation (.srt)
- [ ] Automatic video editing (cuts, captions, etc.)
- [ ] Automatic publishing to social media
