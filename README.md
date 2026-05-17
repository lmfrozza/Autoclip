# 🎮 Autoclip

Automated pipeline that collects, ranks, downloads, transcribes, and edits Twitch clips into vertical Reels-ready videos — with karaoke subtitles, watermark, and GPU-accelerated encoding.

---

## 🏗️ Architecture

The project follows the **Medallion** architecture (Bronze → Silver → Gold) for data processing, followed by download, transcription, and editing stages:

```
Twitch API
    │
    ▼
[Bronze]    → Raw clip collection per streamer
    │
    ▼
[Silver]    → Cleaning, typing, enrichment and scoring
    │
    ▼
[Gold]      → Final filtering and ranking of the best clips
    │
    ▼
[Download]  → Top N clips downloaded via yt-dlp
    │
    ▼
[Subtitles] → Word-level transcription via faster-whisper → .srt files
    │
    ▼
[Edit]      → Resize to 9:16, karaoke subtitles, watermark → data/edit/
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
- Reads the top N clips from `data/gold.json` (controlled by `download_cap`)
- Downloads each clip as `.mp4` to `data/raw/` using `yt-dlp`

### 📝 Subtitles
- Transcribes all `.mp4` files in `data/raw/` using `faster-whisper` (`turbo` model)
- Uses `word_timestamps=True` — each word gets its own precise start/end timestamp
- Generates a `.srt` file per clip with one entry per word
- Runs in parallel (one worker per clip on CPU; single worker on CUDA to avoid OOM)
- Auto-detects GPU: uses `cuda/float16` if available, falls back to `cpu/int8`

### 🎬 Edit
- Resizes each clip to **1080×1920** (9:16, Reels/Shorts format) with black letterbox bars
- Burns in **karaoke subtitles** from the `.srt` file:
  - Current word → yellow
  - Already spoken → white
  - Upcoming words → light gray
  - Sliding window of 5 words for context
- Overlays a **watermark** PNG (configurable position, scale, opacity)
- Encodes with hardware acceleration when available (`h264_nvenc` → `h264_amf` → `h264_qsv` → `libx264`)
- Processes all clips in parallel (one FFmpeg process per clip)
- Outputs to `data/edit/`

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

Edit `config.yaml` to configure the pipeline:

```yaml
streamers:
  - cellbit
  - gaules

pipeline:
  range_days: 1      # how many days back to fetch clips
  download_cap: 5    # how many top clips to download and edit

watermark:
  path: "assets/watermark.png"  # RGBA PNG — replace with your logo
  opacity: 0.8                  # 0.0 (invisible) → 1.0 (fully opaque)
  position: "top-right"         # top-right | top-left | bottom-right | bottom-left
  scale: 0.15                   # fraction of video width (~162px at 1080p)
  margin: 40                    # pixels from the edge
```

A placeholder watermark is included at `assets/watermark.png`. Replace it with your own RGBA PNG.

### 4. Run

Run the full pipeline end-to-end:

```bash
python main.py
```

Or run individual stages from `src/`:

```bash
python src/extracion.py   # Bronze → Silver → Gold
python src/download.py    # Download + transcription
python src/edit.py        # Edit + encode
```

---

## 📁 Project Structure

```
.
├── assets/
│   └── watermark.png       # Watermark logo (RGBA PNG)
├── data/
│   ├── bronze.json         # Raw data collected from the API
│   ├── silver.json         # Cleaned and enriched data
│   ├── gold.json           # Final ranking of the best clips
│   ├── raw/                # Downloaded .mp4 clips and .srt subtitles
│   └── edit/               # Final edited Reels-ready videos
├── logs/
│   └── app.log             # Rotating logs (7-day retention)
├── src/
│   ├── config.py           # Logger and config loader
│   ├── extracion.py        # Medallion pipeline (bronze/silver/gold)
│   ├── download.py         # Download and word-level transcription
│   └── edit.py             # FFmpeg editing (resize, karaoke, watermark)
├── main.py                 # Full pipeline entry point
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
| `faster-whisper` | Word-level audio transcription |
| `imageio-ffmpeg` | Bundled FFmpeg binary |
| `pillow` | Watermark placeholder generation |
| `python-dotenv` | Environment variable loading |
| `loguru` | Structured logging with rotation |
| `PyYAML` | Config file parsing |

---

## ⚡ Performance

| Stage | Strategy |
|---|---|
| Transcription | Parallel workers (1 per clip on CPU, 1 on CUDA) |
| Encoding | Hardware encoder auto-detection (NVENC / AMF / QSV / x264) |
| Editing | Parallel FFmpeg processes (1 per clip) |

On a machine without GPU, 5 clips of ~30s each take roughly:
- ~50s transcription (parallel CPU)
- ~60s editing/encoding (parallel CPU x264)

---

## 🗺️ Roadmap

- [x] Clip collection via Twitch API
- [x] Data cleaning, enrichment and scoring
- [x] Clip ranking (Medallion architecture)
- [x] Automatic download of top clips
- [x] Word-level transcription with faster-whisper
- [x] Reels editing — resize, karaoke subtitles, watermark
- [x] GPU-accelerated encoding with CPU fallback
- [x] Full pipeline via `main.py`
- [ ] Docker Compose (pipeline + scheduler services)
- [ ] Automatic publishing to social media
