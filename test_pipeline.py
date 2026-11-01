"""
test_pipeline.py - Unit test suite for YT Music Wrapped Pro.
Tests parser ingestion, data cleaning, session detection, time calculation,
and discovery/replay metrics against synthetic and edge-case inputs.
"""
from datetime import datetime, timezone
import pandas as pd
import pytest

from parser import parse_watch_histories
from cleaner import clean_watch_history
import metrics


@pytest.fixture
def sample_raw_records():
    return [
        {
            "header": "YouTube Music",
            "title": "Watched Instant Crush",
            "titleUrl": "https://music.youtube.com/watch?v=a5uQMwRMHcs",
            "subtitles": [{"name": "Daft Punk - Topic", "url": "https://music.youtube.com/channel/dp"}],
            "time": "2024-01-01T10:00:00.000Z",
            "products": ["YouTube"],
        },
        {
            # Immediate consecutive replay (loop)
            "header": "YouTube Music",
            "title": "Watched Instant Crush",
            "titleUrl": "https://music.youtube.com/watch?v=a5uQMwRMHcs",
            "subtitles": [{"name": "Daft Punk - Topic", "url": "https://music.youtube.com/channel/dp"}],
            "time": "2024-01-01T10:03:30.000Z",
            "products": ["YouTube"],
        },
        {
            # Quick skip (<30s)
            "header": "YouTube Music",
            "title": "Watched Blinding Lights",
            "titleUrl": "https://music.youtube.com/watch?v=4NRXx6U8ABQ",
            "subtitles": [{"name": "The Weeknd - Topic", "url": "https://music.youtube.com/channel/tw"}],
            "time": "2024-01-01T10:07:00.000Z",
            "products": ["YouTube"],
        },
        {
            # Follow-up play in same session
            "header": "YouTube Music",
            "title": "Watched Starboy (feat. Daft Punk)",
            "titleUrl": "https://music.youtube.com/watch?v=34Na4j8AVgA",
            "subtitles": [{"name": "The Weeknd feat. Daft Punk - Topic", "url": "https://music.youtube.com/channel/tw"}],
            "time": "2024-01-01T10:07:15.000Z",
            "products": ["YouTube"],
        },
        {
            # New session (> 30 min break: 4 hours later)
            "header": "YouTube Music",
            "title": "Watched Creep",
            "titleUrl": "https://music.youtube.com/watch?v=XFkzRNyygfk",
            "subtitles": [{"name": "Radiohead", "url": "https://music.youtube.com/channel/rh"}],
            "time": "2024-01-01T14:15:00.000Z",
            "products": ["YouTube"],
        },
        {
            # Google Ad entry (should be dropped)
            "header": "YouTube",
            "title": "Watched Commercial Ad",
            "titleUrl": "https://www.youtube.com/watch?v=ad123456789",
            "details": [{"name": "From Google Ads"}],
            "time": "2024-01-01T14:18:00.000Z",
            "products": ["YouTube"],
        },
        {
            # Non-music YouTube video (dropped when include_regular_youtube=False)
            "header": "YouTube",
            "title": "Watched Tech Podcast #12",
            "titleUrl": "https://www.youtube.com/watch?v=podcast12345",
            "subtitles": [{"name": "Tech Channel", "url": "https://www.youtube.com/channel/tech"}],
            "time": "2024-01-01T15:00:00.000Z",
            "products": ["YouTube"],
        },
        {
            # Deleted video with missing subtitles
            "header": "YouTube Music",
            "title": "https://music.youtube.com/watch?v=deletedvid01",
            "titleUrl": "https://music.youtube.com/watch?v=deletedvid01",
            "time": "2024-01-01T16:00:00.000Z",
            "products": ["YouTube"],
        },
        {
            # Duplicate entry of the first track (exact same video_id and timestamp)
            "header": "YouTube Music",
            "title": "Watched Instant Crush",
            "titleUrl": "https://music.youtube.com/watch?v=a5uQMwRMHcs",
            "subtitles": [{"name": "Daft Punk - Topic", "url": "https://music.youtube.com/channel/dp"}],
            "time": "2024-01-01T10:00:00.000Z",
            "products": ["YouTube"],
        }
    ]


def test_parser_triage(sample_raw_records):
    raw_df, report = parse_watch_histories(sample_raw_records, include_regular_youtube=False)
    
    assert report.total_raw_records == 9
    assert report.dropped_ads == 1
    assert report.dropped_non_ytmusic == 1
    assert report.unknown_artist_count == 1
    assert report.url_only_title_count == 1
    assert report.retained_records == 7


def test_cleaner_transformations(sample_raw_records):
    raw_df, _ = parse_watch_histories(sample_raw_records, include_regular_youtube=False)
    clean_df, report = clean_watch_history(
        raw_df,
        target_timezone="Asia/Kolkata",
        gap_cap_minutes=6.0,
        default_track_minutes=3.5,
        session_gap_minutes=30.0
    )

    # Duplicate check: 1 duplicate should be dropped
    assert report.duplicate_rows_dropped == 1
    assert len(clean_df) == 6

    # Title prefix stripping
    assert clean_df.iloc[0]["clean_title"] == "Instant Crush"
    # Artist topic suffix stripping
    assert clean_df.iloc[0]["primary_artist"] == "Daft Punk"

    # Multi-artist normalization
    starboy_row = clean_df[clean_df["clean_title"].str.contains("Starboy")].iloc[0]
    assert starboy_row["primary_artist"] == "The Weeknd"

    # Ascending sort verification
    timestamps = clean_df["timestamp"].tolist()
    assert all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))


def test_sessions_and_skips(sample_raw_records):
    raw_df, _ = parse_watch_histories(sample_raw_records, include_regular_youtube=False)
    clean_df, report = clean_watch_history(raw_df, session_gap_minutes=30.0)

    # Check skip detection:
    # "Blinding Lights" played at 10:07:00, "Starboy" played at 10:07:15 -> gap is 15s (<30s)
    blinding_lights_row = clean_df[clean_df["clean_title"] == "Blinding Lights"].iloc[0]
    assert blinding_lights_row["is_skip"] == True
    assert report.skips_detected >= 1

    # Check session splitting:
    # Morning plays (10:00 - 10:07) belong to session 1
    # 14:15 play is > 30 min later, belongs to session 2
    sess_ids = clean_df["session_id"].tolist()
    assert sess_ids[0] == 1
    assert sess_ids[1] == 1
    assert sess_ids[2] == 1
    assert sess_ids[3] == 1
    assert sess_ids[4] == 2
    assert report.total_sessions >= 2


def test_metrics_calculations(sample_raw_records):
    raw_df, _ = parse_watch_histories(sample_raw_records, include_regular_youtube=False)
    clean_df, _ = clean_watch_history(raw_df)

    overview = metrics.compute_overview_stats(clean_df)
    assert overview["total_plays"] == 6
    assert overview["unique_artists"] >= 3

    # Repeat loops: Instant Crush played twice back to back
    loop_count, loops_df = metrics.get_repeat_loops(clean_df)
    assert loop_count >= 1
    assert "Instant Crush" in loops_df["Track"].values

    # Top artists
    top_artists = metrics.get_top_artists(clean_df, top_n=5)
    assert "Daft Punk" in top_artists["Artist"].values

    # Streaks
    streaks = metrics.compute_listening_streaks(clean_df)
    assert streaks["longest_streak_days"] == 1
