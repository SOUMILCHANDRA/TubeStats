# 🎵 YT Music Wrapped Pro

A privacy-first local web application built with **Python**, **Streamlit**, **pandas**, and **Plotly** that transforms your Google Takeout YouTube Music `watch-history.json` into an exhaustive, Spotify/YouTube Wrapped-style dashboard.

Everything runs **100% locally on your machine**. No files are uploaded to external cloud servers, and no Google account login or authentication is required.

---

## 🌟 Key Features

1. **Robust Ingestion & Cleaning Engine (`parser.py`, `cleaner.py`)**:
   - Strips `"Watched "` title prefixes and `"- Topic"` artist suffixes.
   - Cleans removed/private video URLs and missing subtitle entries (with counts flagged).
   - Automatically drops Google Ads entries (`"From Google Ads"`).
   - Filters out non-music YouTube videos (with an instant toggle to include them if desired).
   - Multi-artist normalization (handles `feat.`, `ft.`, `&`, and comma delimiters).
   - Parses UTC timestamps and converts everything to your chosen timezone (default: `Asia/Kolkata`).
   - Deduplicates identical plays and sorts ascending chronologically.

2. **Listening Time Estimation & API Lookup**:
   - **Method 1 (Gap-based estimate)**: Duration of play = gap to next play, capped at e.g. 6 minutes. Pauses longer than the cap transition to a configurable default track length (default: 3.5 min). Clearly labeled as *estimated*.
   - **Method 2 (API Lookup)**: Optional YouTube Data API v3 integration with local SQLite caching (`ytmusic_duration_cache.db`) and batching (50 IDs per call).

3. **Session Intelligence**:
   - Groups continuous listening runs separated by under N minutes (default: 30 min) into distinct sessions.
   - Computes total sessions, average session duration, longest session, and peak session start hour.

4. **Interactive Dashboard Tabs (`app.py`)**:
   - **📈 Overview**: Total plays, unique tracks, unique artists, total listening hours/days, active days %, daily streaks, GitHub-style activity calendar heatmap.
   - **🏆 Top Charts**: Top artists (by plays and listening time) & tracks (top 10/25/50/100) with searchable tables, downloadable CSVs, and horizontal bar charts.
   - **⏳ Timeline**: Animated monthly artist race bar chart, Year-over-Year (YoY) comparison, and all-time records (busiest day, week, month).
   - **🌙 Patterns & Sessions**: 24-hour distribution, Day-of-week x Hour heatmap, Weekday vs Weekend dynamics, and time-of-day personas (*Early Bird*, *Daytime Focuser*, *Sunset Unwinder*, *Night Owl*).
   - **🔄 Discovery & Replay**: Discovery rates (new tracks/artists per month), cumulative growth curve, replay frequency tiers (1 play vs 2-5 vs 6-20 vs 20+), consecutive repeat loops, single-day/week obsessions, comeback tracks (>6 month hiatus), and artist loyalty curve (Shannon entropy & Gini coefficient).
   - **🔍 Explorer**: Granular artist and track deep-dives (plays over time, top songs, listening share, lifespan).
   - **🎁 Wrapped Cards**: Interactive, exportable Wrapped card for any calendar year or all-time, milestone badges (#1, #1,000, #10,000 play), and forgotten gems rediscovery list.

---

## 🚀 Quick Setup & Installation

### 1. Prerequisites
- Python 3.11 or higher (Python 3.13 tested)

### 2. Clone / Open Directory & Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. (Optional) Generate Demo Sample Data
If you don't have your Google Takeout archive yet, generate a realistic synthetic history file in seconds:
```bash
python generate_sample_data.py
```

### 4. Launch the App
```bash
streamlit run app.py
```
Open your browser to the local URL (typically `http://localhost:8501`).

---

## 📥 How to Export Your YouTube Music History from Google Takeout

1. Visit **[Google Takeout](https://takeout.google.com/)**.
2. Click **"Deselect all"** at the top.
3. Scroll down and check the box for **"YouTube and YouTube Music"**.
4. Click **"Multiple formats"** and ensure **History** is formatted as **JSON** (NOT HTML).
5. Click **"All YouTube data included"**, deselect all items, and select **ONLY "history"**.
6. Click **Next step**, choose `.zip` export, and click **Create export**.
7. Once downloaded and extracted, look for:
   `Takeout/YouTube and YouTube Music/history/watch-history.json`
8. Upload `watch-history.json` directly into **YT Music Wrapped Pro** via the sidebar!

---

## 🧪 Running the Unit Tests

The test suite validates parser filtering, cleaning transformations, session detection, skip heuristics, and metrics calculations:

```bash
pytest test_pipeline.py
```

---

## 📁 Project Structure

```
YT STATS/
├── parser.py                   # Ingestion, triage, Google Ads & non-music filtering
├── cleaner.py                  # Deduplication, timezone conversion, gap duration, sessions
├── metrics.py                  # Pure calculation functions (overview, streaks, discovery, wrapped)
├── charts.py                   # Plotly dark-theme interactive visualizations & Wrapped HTML card
├── app.py                      # Streamlit application UI with 7 tabs & sidebar controls
├── test_pipeline.py            # Pytest unit tests for all core algorithms
├── generate_sample_data.py     # Realistic synthetic watch-history generator
├── requirements.txt            # Python dependencies
└── README.md                   # Documentation and Takeout instructions
```

---

## ⚠️ Known Limitations

1. **Track Duration**: Google Takeout watch history logs only play event timestamps, not the duration listened. The app provides both a gap-based heuristic estimate and an optional YouTube Data API v3 lookup with SQLite caching.
2. **Removed or Private Videos**: Tracks that have been made private or deleted will appear with missing subtitles or URL titles. The app flags these gracefully as `"Unknown Artist"` or `"Removed Track [ID]"`.
3. **Regular YouTube Videos**: Some users watch music or podcasts on main YouTube. Use the sidebar toggle to either exclude or include non-music entries (`header != 'YouTube Music'`).
