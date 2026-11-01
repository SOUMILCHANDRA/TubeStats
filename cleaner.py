"""
cleaner.py - Cleans, standardizes, enriches, and computes listening metrics.
Handles artist normalization, timestamp parsing with timezone conversion,
vectorized deduplication, gap-based listening time estimation, optional API duration fetching,
and session detection.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


@dataclass
class CleaningQualityReport:
    """Summary of cleaning and enrichment transformations."""
    initial_rows: int = 0
    duplicate_rows_dropped: int = 0
    final_clean_rows: int = 0
    unknown_artists_flagged: int = 0
    url_titles_flagged: int = 0
    skips_detected: int = 0
    total_sessions: int = 0
    timezone_applied: str = "Asia/Kolkata"
    duration_method_used: str = "gap_based_estimate"
    cached_api_durations_used: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None


VIDEO_ID_REGEX = re.compile(r"(?:v=|youtu\.be/|vi/|watch\?v=)([\w-]{11})")
TOPIC_SUFFIX_REGEX = re.compile(r"\s*-\s*Topic$", re.IGNORECASE)
FEAT_REGEX = re.compile(r"\s*(?:[\(\[\{]?\s*(?:feat\.|ft\.|featuring)\s+([^\)\]\}]+)[\)\]\}]?)", re.IGNORECASE)


def extract_video_id(url_val: Any) -> Optional[str]:
    """Extract 11-character YouTube video ID from URL string."""
    if not isinstance(url_val, str) or not url_val:
        return None
    match = VIDEO_ID_REGEX.search(url_val)
    if match:
        return match.group(1)
    return None


def clean_title_string(title_val: Any, video_id: Optional[str] = None) -> Tuple[str, bool]:
    """
    Strip 'Watched ' prefix and check if the title is just a raw URL or deleted.
    Returns (cleaned_title, is_url_or_removed).
    """
    if not isinstance(title_val, str) or not title_val.strip():
        fallback = f"Deleted Video [{video_id}]" if video_id else "Deleted / Unavailable Video"
        return fallback, True

    title = title_val.strip()
    if title.startswith("Watched "):
        title = title[8:].strip()

    # Check if title itself is a URL (removed/private video)
    if title.startswith("http://") or title.startswith("https://") or "youtube.com/watch" in title:
        fallback = f"Removed Track [{video_id}]" if video_id else "Removed Track"
        return fallback, True

    return title, False


def parse_and_normalize_artist(subtitles_val: Any) -> Tuple[str, str, List[str], bool]:
    """
    Extract and normalize artist names from Google Takeout subtitles field.
    Returns:
        - display_artist: Standard display string (e.g. "Daft Punk feat. Pharrell Williams")
        - primary_artist: Leading artist for chart aggregation (e.g. "Daft Punk")
        - all_artists: List of individual parsed artist strings
        - is_unknown: True if missing or private
    """
    if not isinstance(subtitles_val, list) or len(subtitles_val) == 0:
        return "Unknown Artist", "Unknown Artist", ["Unknown Artist"], True

    raw_names = []
    for item in subtitles_val:
        if isinstance(item, dict) and "name" in item and item["name"]:
            name = item["name"].strip()
            # Strip " - Topic"
            name = TOPIC_SUFFIX_REGEX.sub("", name).strip()
            if name:
                raw_names.append(name)

    if not raw_names:
        return "Unknown Artist", "Unknown Artist", ["Unknown Artist"], True

    # First subtitle entry is typically the primary artist or joint credits
    first_name = raw_names[0]
    
    # Check for multiple artists separated by commas, ampersands, or 'feat.'
    # Normalize variants of featuring
    normalized_first = FEAT_REGEX.sub(r" feat. \1", first_name)
    normalized_first = re.sub(r"\s+", " ", normalized_first).strip()

    # Split to extract individual artists
    delimiters = r",|\s+&\s+|\s+feat\.\s+|\s+ft\.\s+|\s+with\s+"
    split_artists = [a.strip() for a in re.split(delimiters, normalized_first, flags=re.IGNORECASE) if a.strip()]

    if not split_artists:
        split_artists = [normalized_first]

    primary_artist = split_artists[0]
    # If there are additional items in subtitles list, add them to all_artists
    for extra in raw_names[1:]:
        if extra not in split_artists:
            split_artists.append(extra)

    return normalized_first, primary_artist, split_artists, False


class DurationCache:
    """Local SQLite cache for fetched YouTube track durations."""
    def __init__(self, db_path: str = "ytmusic_duration_cache.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS track_durations (
                    video_id TEXT PRIMARY KEY,
                    duration_sec REAL,
                    title TEXT,
                    artist TEXT,
                    source TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_batch(self, video_ids: List[str]) -> Dict[str, float]:
        if not video_ids:
            return {}
        result = {}
        with sqlite3.connect(self.db_path) as conn:
            # Chunking query for SQLite limit
            chunk_size = 500
            for i in range(0, len(video_ids), chunk_size):
                chunk = video_ids[i:i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                cursor = conn.execute(
                    f"SELECT video_id, duration_sec FROM track_durations WHERE video_id IN ({placeholders})",
                    chunk
                )
                for vid, dur in cursor.fetchall():
                    if dur is not None and dur > 0:
                        result[vid] = float(dur)
        return result

    def set_batch(self, records: List[Tuple[str, float, str, str, str]]) -> None:
        if not records:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO track_durations (video_id, duration_sec, title, artist, source)
                VALUES (?, ?, ?, ?, ?)
            """, records)
            conn.commit()


def fetch_durations_ytmusicapi(
    video_ids: List[str],
    duration_cache: DurationCache,
    max_lookups: int = 250,
    max_workers: int = 5
) -> Dict[str, float]:
    """
    Fetch exact track durations and metadata directly from YouTube Music using ytmusicapi.
    Requires no API keys, credentials, or Google Cloud setup.
    Results are cached in local SQLite for sub-millisecond future runs.
    """
    from concurrent.futures import ThreadPoolExecutor

    try:
        from ytmusicapi import YTMusic
        yt = YTMusic()
    except Exception:
        return duration_cache.get_batch(video_ids)

    cached_durations = duration_cache.get_batch(video_ids)
    missing_ids = [vid for vid in video_ids if vid and vid not in cached_durations]

    if not missing_ids:
        return cached_durations

    to_fetch = missing_ids[:max_lookups]
    fetched_records = []

    def fetch_single(vid: str) -> Optional[Tuple[str, float, str, str, str]]:
        try:
            song = yt.get_song(vid)
            video_details = song.get("videoDetails", {})
            dur_str = video_details.get("lengthSeconds")
            if not dur_str:
                dur_str = song.get("microformat", {}).get("microformatDataRenderer", {}).get("videoDetails", {}).get("durationSeconds")
            if dur_str:
                dur_sec = float(dur_str)
                title = video_details.get("title", "")
                author = video_details.get("author", "")
                return (vid, dur_sec, title, author, "ytmusicapi")
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(fetch_single, to_fetch)
        for r in results:
            if r:
                vid, dur_sec, title, author, source = r
                cached_durations[vid] = dur_sec
                fetched_records.append(r)

    if fetched_records:
        duration_cache.set_batch(fetched_records)

    return cached_durations


def convert_ytmusicapi_history_to_records(history_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converts items returned by ytmusic.get_history() into standard watch-history format
    so they can be fed directly into the parsing and cleaning pipeline.
    """
    records = []
    now_ts = pd.Timestamp.now(tz="UTC")
    for i, item in enumerate(history_list):
        vid = item.get("videoId")
        title = item.get("title", "Unknown Title")
        artists = item.get("artists", [])
        artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
        ts = (now_ts - pd.Timedelta(minutes=(len(history_list) - i) * 4)).isoformat()
        records.append({
            "header": "YouTube Music",
            "title": f"Watched {title}",
            "titleUrl": f"https://music.youtube.com/watch?v={vid}" if vid else None,
            "subtitles": [{"name": artist_name, "url": f"https://music.youtube.com/channel/{artists[0].get('id', '')}" if artists else None}],
            "time": ts,
            "products": ["YouTube Music"]
        })
    return records


def fetch_durations_yt_api(
    video_ids: List[str],
    api_key: str,
    duration_cache: DurationCache
) -> Dict[str, float]:
    """
    Fetch exact track durations via YouTube Data API v3 (videos.list endpoint) in batches of 50.
    Caches results locally.
    """
    import urllib.request
    import json
    import isodate  # fallback if installed, or regex for ISO 8601 duration

    iso_duration_regex = re.compile(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
    )

    def parse_iso8601_duration(dur_str: str) -> float:
        match = iso_duration_regex.match(dur_str)
        if not match:
            return 210.0
        parts = match.groupdict()
        hours = int(parts.get("hours") or 0)
        minutes = int(parts.get("minutes") or 0)
        seconds = int(parts.get("seconds") or 0)
        return float(hours * 3600 + minutes * 60 + seconds)

    cached_durations = duration_cache.get_batch(video_ids)
    missing_ids = [vid for vid in video_ids if vid and vid not in cached_durations]
    
    if not missing_ids or not api_key:
        return cached_durations

    fetched_records = []
    chunk_size = 50
    for i in range(0, min(len(missing_ids), 500), chunk_size):  # respect quota max
        chunk = missing_ids[i:i + chunk_size]
        url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails,snippet&id={','.join(chunk)}&key={api_key}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "YTMusicWrappedPro/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                for item in payload.get("items", []):
                    vid = item.get("id")
                    content_details = item.get("contentDetails", {})
                    iso_dur = content_details.get("duration", "PT3M30S")
                    dur_sec = parse_iso8601_duration(iso_dur)
                    title = item.get("snippet", {}).get("title", "")
                    artist = item.get("snippet", {}).get("channelTitle", "")
                    cached_durations[vid] = dur_sec
                    fetched_records.append((vid, dur_sec, title, artist, "youtube_v3_api"))
        except Exception as e:
            # Silently fall back if quota exceeded or offline
            break

    if fetched_records:
        duration_cache.set_batch(fetched_records)

    return cached_durations


def clean_watch_history(
    df: pd.DataFrame,
    target_timezone: str = "Asia/Kolkata",
    duration_method: str = "gap",
    gap_cap_minutes: float = 6.0,
    default_track_minutes: float = 3.5,
    session_gap_minutes: float = 30.0,
    yt_api_key: Optional[str] = None,
) -> Tuple[pd.DataFrame, CleaningQualityReport]:
    """
    Main cleaning and feature engineering pipeline:
    1. Extracts video_id, clean title, and normalized artist names.
    2. Parses timestamps as UTC and converts to target timezone.
    3. Sorts ASCENDING chronologically (critical for gaps and sessions).
    4. Merges & deduplicates entries (same video_id + same timestamp).
    5. Computes play durations (Gap-based capped estimate or API duration lookup).
    6. Identifies skips (<30s before next track).
    7. Detects listening sessions.
    8. Generates time-based feature columns (year, month, hour, day_name, date, etc.).
    """
    report = CleaningQualityReport(
        initial_rows=len(df),
        timezone_applied=target_timezone,
        duration_method_used=duration_method,
    )

    if df.empty:
        report.final_clean_rows = 0
        return pd.DataFrame(), report

    clean_df = df.copy()

    # 1. Extract video ID
    if "titleUrl" in clean_df.columns:
        clean_df["video_id"] = clean_df["titleUrl"].apply(extract_video_id)
    else:
        clean_df["video_id"] = None

    # 2. Clean track title
    title_res = [
        clean_title_string(t, v)
        for t, v in zip(clean_df.get("title", [None] * len(clean_df)), clean_df["video_id"])
    ]
    clean_df["clean_title"] = [r[0] for r in title_res]
    clean_df["is_url_title"] = [r[1] for r in title_res]
    report.url_titles_flagged = int(clean_df["is_url_title"].sum())

    # 3. Clean and normalize artist
    subtitles_col = clean_df.get("subtitles", [None] * len(clean_df))
    artist_res = [parse_and_normalize_artist(sub) for sub in subtitles_col]
    clean_df["artist"] = [r[0] for r in artist_res]
    clean_df["primary_artist"] = [r[1] for r in artist_res]
    clean_df["all_artists"] = [r[2] for r in artist_res]
    clean_df["is_unknown_artist"] = [r[3] for r in artist_res]
    report.unknown_artists_flagged = int(clean_df["is_unknown_artist"].sum())

    # Combined track identifier for accurate aggregation
    clean_df["track_id"] = clean_df["clean_title"] + " - " + clean_df["primary_artist"]

    # 4. Parse timestamp as UTC, convert to local timezone
    # Takeout timestamps look like '2024-03-15T18:42:11.123Z'
    try:
        clean_df["time_utc"] = pd.to_datetime(clean_df["time"], format="ISO8601", utc=True)
    except Exception:
        clean_df["time_utc"] = pd.to_datetime(clean_df["time"], utc=True, errors="coerce")
    clean_df = clean_df.dropna(subset=["time_utc"]).copy()

    # Sort ascending chronologically (Google Takeout is newest-first)
    clean_df = clean_df.sort_values("time_utc", ascending=True).reset_index(drop=True)

    # 5. Deduplicate: same video_id (or same track_id) at identical timestamp
    pre_dedupe_len = len(clean_df)
    clean_df["dedupe_key"] = clean_df["video_id"].fillna(clean_df["track_id"])
    clean_df = clean_df.drop_duplicates(subset=["dedupe_key", "time_utc"]).reset_index(drop=True)
    clean_df = clean_df.drop(columns=["dedupe_key"])
    report.duplicate_rows_dropped = pre_dedupe_len - len(clean_df)

    # Convert to target timezone
    try:
        clean_df["timestamp"] = clean_df["time_utc"].dt.tz_convert(target_timezone)
    except Exception:
        # Fallback to UTC if timezone string is invalid
        clean_df["timestamp"] = clean_df["time_utc"]
        report.timezone_applied = "UTC"

    # Time partition features
    clean_df["date"] = clean_df["timestamp"].dt.date
    clean_df["year"] = clean_df["timestamp"].dt.year
    clean_df["month"] = clean_df["timestamp"].dt.strftime("%Y-%m")
    clean_df["month_name"] = clean_df["timestamp"].dt.strftime("%b %Y")
    clean_df["hour"] = clean_df["timestamp"].dt.hour
    clean_df["day_name"] = clean_df["timestamp"].dt.day_name()
    clean_df["day_of_week"] = clean_df["timestamp"].dt.dayofweek  # 0=Monday, 6=Sunday
    clean_df["is_weekend"] = clean_df["day_of_week"] >= 5

    # Listener time-of-day bucket
    # Morning: 05-11:59, Afternoon: 12-16:59, Evening: 17-21:59, Night Owl: 22-04:59
    def get_time_bucket(hour: int) -> str:
        if 5 <= hour < 12:
            return "Morning (5am - 12pm)"
        elif 12 <= hour < 17:
            return "Afternoon (12pm - 5pm)"
        elif 17 <= hour < 22:
            return "Evening (5pm - 10pm)"
        else:
            return "Night Owl (10pm - 5am)"

    clean_df["time_bucket"] = clean_df["hour"].apply(get_time_bucket)

    # 6. Listening Time Estimation & Session Detection
    gap_cap_sec = float(gap_cap_minutes) * 60.0
    default_track_sec = float(default_track_minutes) * 60.0
    session_gap_sec = float(session_gap_minutes) * 60.0

    # Calculate gap to next play in seconds
    next_timestamp = clean_df["timestamp"].shift(-1)
    gap_to_next = (next_timestamp - clean_df["timestamp"]).dt.total_seconds()
    clean_df["gap_to_next_sec"] = gap_to_next

    # Calculate gap from previous play for session splitting
    prev_timestamp = clean_df["timestamp"].shift(1)
    gap_from_prev = (clean_df["timestamp"] - prev_timestamp).dt.total_seconds()
    clean_df["gap_from_prev_sec"] = gap_from_prev

    # Sessions: new session if gap_from_prev > session_gap_sec or first row
    is_new_session = (gap_from_prev > session_gap_sec) | gap_from_prev.isna()
    clean_df["session_id"] = is_new_session.cumsum()
    clean_df["session_track_idx"] = clean_df.groupby("session_id").cumcount() + 1
    report.total_sessions = int(clean_df["session_id"].max()) if not clean_df.empty else 0

    # Skip detection: gap to next play < 30 seconds within a session
    clean_df["is_skip"] = (clean_df["gap_to_next_sec"] < 30.0) & (clean_df["gap_to_next_sec"] > 0)
    report.skips_detected = int(clean_df["is_skip"].sum())

    # Duration calculation
    # Method 1: Gap-based estimate
    # If gap is within (0, gap_cap_sec], duration = gap; otherwise (session break or last track) = default_track_sec
    gap_durations = np.where(
        (clean_df["gap_to_next_sec"] > 0) & (clean_df["gap_to_next_sec"] <= gap_cap_sec),
        clean_df["gap_to_next_sec"],
        default_track_sec
    )

    clean_df["duration_sec"] = gap_durations
    clean_df["duration_source"] = "gap_estimate"

    # Method 2: ytmusicapi Lookup (Free, No API key required)
    if duration_method == "ytmusicapi":
        duration_cache = DurationCache()
        unique_vids = [v for v in clean_df["video_id"].dropna().unique() if v]
        api_durations = fetch_durations_ytmusicapi(unique_vids, duration_cache)
        if api_durations:
            api_dur_series = clean_df["video_id"].map(api_durations)
            matched_mask = api_dur_series.notna() & (api_dur_series > 0)
            clean_df.loc[matched_mask, "duration_sec"] = api_dur_series[matched_mask]
            clean_df.loc[matched_mask, "duration_source"] = "ytmusicapi"
            report.cached_api_durations_used = int(matched_mask.sum())
            report.duration_method_used = "ytmusicapi"

    # Method 3: YouTube Data API v3 lookup (Google Cloud Key)
    elif duration_method == "api_lookup" and yt_api_key:
        duration_cache = DurationCache()
        unique_vids = [v for v in clean_df["video_id"].dropna().unique() if v]
        api_durations = fetch_durations_yt_api(unique_vids, yt_api_key, duration_cache)
        if api_durations:
            api_dur_series = clean_df["video_id"].map(api_durations)
            matched_mask = api_dur_series.notna() & (api_dur_series > 0)
            clean_df.loc[matched_mask, "duration_sec"] = api_dur_series[matched_mask]
            clean_df.loc[matched_mask, "duration_source"] = "api_lookup"
            report.cached_api_durations_used = int(matched_mask.sum())
            report.duration_method_used = "api_lookup"

    clean_df["duration_min"] = clean_df["duration_sec"] / 60.0
    clean_df["duration_hours"] = clean_df["duration_sec"] / 3600.0

    # Date range
    if not clean_df.empty:
        report.date_range_start = clean_df["timestamp"].min().strftime("%Y-%m-%d %H:%M")
        report.date_range_end = clean_df["timestamp"].max().strftime("%Y-%m-%d %H:%M")

    report.final_clean_rows = len(clean_df)
    return clean_df, report
