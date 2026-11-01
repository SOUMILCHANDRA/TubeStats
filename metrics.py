"""
metrics.py - Pure functions for computing detailed listening statistics.
No UI or side-effects; fully unit-testable.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# ============================================================================
# 1. OVERVIEW METRICS
# ============================================================================

def compute_overview_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes high-level overview metrics:
    - total plays, unique tracks, unique artists
    - date span, total listening hours / days
    - average plays per day, % active days
    """
    if df.empty:
        return {
            "total_plays": 0,
            "unique_tracks": 0,
            "unique_artists": 0,
            "start_date": None,
            "end_date": None,
            "total_days_span": 0,
            "active_days_count": 0,
            "active_days_pct": 0.0,
            "total_listening_hours": 0.0,
            "total_listening_days": 0.0,
            "avg_plays_per_day": 0.0,
            "avg_plays_per_active_day": 0.0,
            "total_sessions": 0,
            "is_estimated_duration": True,
        }

    total_plays = len(df)
    unique_tracks = df["track_id"].nunique()
    unique_artists = df["primary_artist"].nunique()

    min_ts = df["timestamp"].min()
    max_ts = df["timestamp"].max()
    
    unique_dates = df["date"].nunique()
    total_days_span = max((max_ts.date() - min_ts.date()).days + 1, 1)
    active_days_pct = (unique_dates / total_days_span) * 100.0

    total_duration_sec = df["duration_sec"].sum()
    total_listening_hours = total_duration_sec / 3600.0
    total_listening_days = total_listening_hours / 24.0

    avg_plays_per_day = total_plays / total_days_span
    avg_plays_per_active_day = total_plays / max(unique_dates, 1)
    total_sessions = df["session_id"].nunique() if "session_id" in df.columns else 0

    is_estimated = (df["duration_source"] == "gap_estimate").any() if "duration_source" in df.columns else True

    return {
        "total_plays": int(total_plays),
        "unique_tracks": int(unique_tracks),
        "unique_artists": int(unique_artists),
        "start_date": min_ts.strftime("%Y-%m-%d"),
        "end_date": max_ts.strftime("%Y-%m-%d"),
        "total_days_span": int(total_days_span),
        "active_days_count": int(unique_dates),
        "active_days_pct": round(active_days_pct, 1),
        "total_listening_hours": round(total_listening_hours, 1),
        "total_listening_days": round(total_listening_days, 2),
        "avg_plays_per_day": round(avg_plays_per_day, 1),
        "avg_plays_per_active_day": round(avg_plays_per_active_day, 1),
        "total_sessions": int(total_sessions),
        "is_estimated_duration": bool(is_estimated),
    }


# ============================================================================
# 2. TOP LISTS & DEEP DIVES
# ============================================================================

def get_top_artists(df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    """Computes top artists by total plays and listening hours."""
    if df.empty:
        return pd.DataFrame(columns=["Artist", "Plays", "Hours", "Share %", "Unique Tracks"])

    agg = df.groupby("primary_artist").agg(
        Plays=("track_id", "count"),
        Hours=("duration_hours", "sum"),
        Unique_Tracks=("clean_title", "nunique"),
        First_Listened=("timestamp", "min"),
        Last_Listened=("timestamp", "max")
    ).reset_index()

    agg = agg.rename(columns={"primary_artist": "Artist", "Unique_Tracks": "Unique Tracks"})
    total_plays = len(df)
    agg["Share %"] = (agg["Plays"] / total_plays * 100.0).round(2)
    agg["Hours"] = agg["Hours"].round(1)
    agg = agg.sort_values(by=["Plays", "Hours"], ascending=False).reset_index(drop=True)
    agg["Rank"] = agg.index + 1
    cols = ["Rank", "Artist", "Plays", "Hours", "Share %", "Unique Tracks", "First_Listened", "Last_Listened"]
    return agg[cols].head(top_n)


def get_top_tracks(df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    """Computes top tracks by total plays and listening hours."""
    if df.empty:
        return pd.DataFrame(columns=["Track", "Artist", "Plays", "Hours", "Share %"])

    agg = df.groupby(["clean_title", "primary_artist"]).agg(
        Plays=("duration_sec", "count"),
        Hours=("duration_hours", "sum"),
        First_Played=("timestamp", "min"),
        Last_Played=("timestamp", "max")
    ).reset_index()

    agg = agg.rename(columns={"clean_title": "Track", "primary_artist": "Artist"})
    total_plays = len(df)
    agg["Share %"] = (agg["Plays"] / total_plays * 100.0).round(2)
    agg["Hours"] = agg["Hours"].round(1)
    agg = agg.sort_values(by=["Plays", "Hours"], ascending=False).reset_index(drop=True)
    agg["Rank"] = agg.index + 1
    cols = ["Rank", "Track", "Artist", "Plays", "Hours", "Share %", "First_Played", "Last_Played"]
    return agg[cols].head(top_n)


def get_artist_deep_dive(df: pd.DataFrame, artist_name: str) -> Dict[str, Any]:
    """Generates a comprehensive deep dive for a selected artist."""
    sub = df[df["primary_artist"] == artist_name].copy()
    if sub.empty:
        return {"found": False, "artist": artist_name}

    total_user_plays = len(df)
    total_user_hours = df["duration_hours"].sum()

    artist_plays = len(sub)
    artist_hours = sub["duration_hours"].sum()
    share_plays_pct = (artist_plays / max(total_user_plays, 1)) * 100.0
    share_hours_pct = (artist_hours / max(total_user_hours, 1e-6)) * 100.0

    first_listened = sub["timestamp"].min()
    last_listened = sub["timestamp"].max()
    lifespan_days = (last_listened.date() - first_listened.date()).days

    # Top tracks by this artist
    top_tracks = sub.groupby("clean_title").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum")
    ).reset_index().sort_values(by="Plays", ascending=False).reset_index(drop=True)
    top_tracks["Rank"] = top_tracks.index + 1
    top_tracks["Hours"] = top_tracks["Hours"].round(1)

    # Monthly plays timeline
    monthly = sub.groupby("month").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum")
    ).reset_index().sort_values("month")

    # Skip rate for this artist
    skips = sub["is_skip"].sum()
    skip_rate = (skips / artist_plays) * 100.0

    return {
        "found": True,
        "artist": artist_name,
        "total_plays": int(artist_plays),
        "total_hours": round(artist_hours, 1),
        "share_plays_pct": round(share_plays_pct, 2),
        "share_hours_pct": round(share_hours_pct, 2),
        "unique_tracks_count": int(sub["clean_title"].nunique()),
        "first_listened": first_listened.strftime("%Y-%m-%d %H:%M"),
        "last_listened": last_listened.strftime("%Y-%m-%d %H:%M"),
        "lifespan_days": int(lifespan_days),
        "skip_rate_pct": round(skip_rate, 1),
        "top_tracks": top_tracks,
        "monthly_timeline": monthly,
    }


def get_track_deep_dive(df: pd.DataFrame, track_title: str, artist_name: Optional[str] = None) -> Dict[str, Any]:
    """Generates a comprehensive deep dive for a selected track."""
    cond = df["clean_title"] == track_title
    if artist_name:
        cond &= (df["primary_artist"] == artist_name)
    sub = df[cond].copy()

    if sub.empty:
        return {"found": False, "track": track_title}

    total_plays = len(sub)
    total_hours = sub["duration_hours"].sum()
    first_play = sub["timestamp"].min()
    last_play = sub["timestamp"].max()

    # Peak month
    month_counts = sub["month"].value_counts()
    peak_month = month_counts.index[0] if not month_counts.empty else "N/A"
    peak_month_plays = int(month_counts.iloc[0]) if not month_counts.empty else 0

    # Monthly timeline
    monthly = sub.groupby("month").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum")
    ).reset_index().sort_values("month")

    return {
        "found": True,
        "track": track_title,
        "artist": sub["primary_artist"].iloc[0],
        "total_plays": int(total_plays),
        "total_hours": round(total_hours, 2),
        "first_play": first_play.strftime("%Y-%m-%d %H:%M"),
        "last_play": last_play.strftime("%Y-%m-%d %H:%M"),
        "peak_month": peak_month,
        "peak_month_plays": peak_month_plays,
        "monthly_timeline": monthly,
    }


# ============================================================================
# 3. TIME-BASED METRICS
# ============================================================================

def get_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Computes monthly play counts, listening hours, and unique tracks/artists."""
    if df.empty:
        return pd.DataFrame()

    monthly = df.groupby("month").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum"),
        Unique_Artists=("primary_artist", "nunique"),
        Unique_Tracks=("clean_title", "nunique")
    ).reset_index().sort_values("month")

    monthly["Hours"] = monthly["Hours"].round(1)
    return monthly


def get_yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Computes yearly plays, listening hours, and YoY percentage changes."""
    if df.empty:
        return pd.DataFrame()

    yearly = df.groupby("year").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum"),
        Unique_Artists=("primary_artist", "nunique"),
        Unique_Tracks=("clean_title", "nunique")
    ).reset_index().sort_values("year")

    yearly["Hours"] = yearly["Hours"].round(1)
    yearly["Plays_YoY_%"] = yearly["Plays"].pct_change() * 100.0
    yearly["Hours_YoY_%"] = yearly["Hours"].pct_change() * 100.0
    yearly["Plays_YoY_%"] = yearly["Plays_YoY_%"].round(1).fillna(0.0)
    yearly["Hours_YoY_%"] = yearly["Hours_YoY_%"].round(1).fillna(0.0)
    return yearly


def get_top_artist_and_track_per_month(df: pd.DataFrame) -> pd.DataFrame:
    """Determines the #1 artist and #1 track for each calendar month."""
    if df.empty:
        return pd.DataFrame()

    results = []
    for month_val, group in df.groupby("month"):
        top_art = group["primary_artist"].value_counts().head(1)
        top_trk = (group["clean_title"] + " (" + group["primary_artist"] + ")").value_counts().head(1)
        results.append({
            "Month": month_val,
            "Total Plays": len(group),
            "Top Artist": top_art.index[0] if not top_art.empty else "N/A",
            "Artist Plays": int(top_art.iloc[0]) if not top_art.empty else 0,
            "Top Track": top_trk.index[0] if not top_trk.empty else "N/A",
            "Track Plays": int(top_trk.iloc[0]) if not top_trk.empty else 0,
        })

    return pd.DataFrame(results).sort_values("Month").reset_index(drop=True)


def get_busiest_periods(df: pd.DataFrame) -> Dict[str, Any]:
    """Finds busiest day ever, busiest week, and busiest month."""
    if df.empty:
        return {}

    # Busiest day
    day_counts = df.groupby("date").agg(Plays=("timestamp", "count"), Hours=("duration_hours", "sum")).reset_index()
    top_day = day_counts.sort_values("Plays", ascending=False).iloc[0]

    # Busiest month
    month_counts = df.groupby("month").agg(Plays=("timestamp", "count"), Hours=("duration_hours", "sum")).reset_index()
    top_month = month_counts.sort_values("Plays", ascending=False).iloc[0]

    # Busiest week
    df_copy = df.copy()
    df_copy["week"] = df_copy["timestamp"].dt.to_period("W").astype(str)
    week_counts = df_copy.groupby("week").agg(Plays=("timestamp", "count"), Hours=("duration_hours", "sum")).reset_index()
    top_week = week_counts.sort_values("Plays", ascending=False).iloc[0]

    return {
        "busiest_day": {
            "date": str(top_day["date"]),
            "plays": int(top_day["Plays"]),
            "hours": round(float(top_day["Hours"]), 1),
        },
        "busiest_week": {
            "week": str(top_week["week"]),
            "plays": int(top_week["Plays"]),
            "hours": round(float(top_week["Hours"]), 1),
        },
        "busiest_month": {
            "month": str(top_month["month"]),
            "plays": int(top_month["Plays"]),
            "hours": round(float(top_month["Hours"]), 1),
        }
    }


def get_daily_calendar_data(df: pd.DataFrame) -> pd.DataFrame:
    """Generates daily plays and hours suitable for a GitHub-style calendar heatmap."""
    if df.empty:
        return pd.DataFrame(columns=["date", "plays", "hours"])

    daily = df.groupby("date").agg(
        plays=("timestamp", "count"),
        hours=("duration_hours", "sum")
    ).reset_index()
    daily["hours"] = daily["hours"].round(1)
    daily["date_str"] = daily["date"].astype(str)
    return daily


# ============================================================================
# 4. LISTENING PATTERNS & SESSIONS
# ============================================================================

def get_hourly_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Returns 24-hour play and duration breakdown."""
    if df.empty:
        return pd.DataFrame()

    full_hours = pd.DataFrame({"hour": list(range(24))})
    grouped = df.groupby("hour").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum")
    ).reset_index()
    merged = full_hours.merge(grouped, on="hour", how="left").fillna(0)
    merged["Hours"] = merged["Hours"].round(1)
    merged["Plays"] = merged["Plays"].astype(int)
    merged["Label"] = merged["hour"].apply(lambda h: f"{h:02d}:00")
    return merged


def get_weekday_hour_heatmap_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Returns 7 x 24 pivot table of play counts (Day of Week vs Hour of Day)."""
    if df.empty:
        return pd.DataFrame()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = pd.crosstab(
        index=df["day_name"],
        columns=df["hour"],
        dropna=False
    ).reindex(index=days, columns=list(range(24)), fill_value=0)
    return pivot


def get_time_bucket_summary(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Computes distribution by time buckets and identifies primary 'Listener Type'."""
    if df.empty:
        return pd.DataFrame(), "Unknown"

    buckets = ["Morning (5am - 12pm)", "Afternoon (12pm - 5pm)", "Evening (5pm - 10pm)", "Night Owl (10pm - 5am)"]
    counts = df["time_bucket"].value_counts().reindex(buckets, fill_value=0).reset_index()
    counts.columns = ["Bucket", "Plays"]
    total = len(df)
    counts["Share %"] = (counts["Plays"] / max(total, 1) * 100.0).round(1)

    top_bucket = counts.sort_values("Plays", ascending=False).iloc[0]["Bucket"]
    type_map = {
        "Morning (5am - 12pm)": "Early Bird (Morning Energizer)",
        "Afternoon (12pm - 5pm)": "Daytime Focuser (Work & Flow)",
        "Evening (5pm - 10pm)": "Sunset Unwinder (Evening Groover)",
        "Night Owl (10pm - 5am)": "Creature of the Night (Night Owl)",
    }
    listener_type = type_map.get(top_bucket, "Eclectic Listener")
    return counts, listener_type


def get_weekday_vs_weekend_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Compares listening volume and averages between weekdays and weekends."""
    if df.empty:
        return {}

    weekday_mask = ~df["is_weekend"]
    weekend_mask = df["is_weekend"]

    weekday_plays = int(weekday_mask.sum())
    weekend_plays = int(weekend_mask.sum())

    weekday_days = df[weekday_mask]["date"].nunique()
    weekend_days = df[weekend_mask]["date"].nunique()

    return {
        "weekday_total_plays": weekday_plays,
        "weekend_total_plays": weekend_plays,
        "weekday_pct": round((weekday_plays / len(df)) * 100.0, 1),
        "weekend_pct": round((weekend_plays / len(df)) * 100.0, 1),
        "weekday_avg_plays_per_day": round(weekday_plays / max(weekday_days, 1), 1),
        "weekend_avg_plays_per_day": round(weekend_plays / max(weekend_days, 1), 1),
    }


def get_seasonal_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Groups listening by seasons (Meteorological)."""
    if df.empty:
        return pd.DataFrame()

    def get_season(dt: datetime) -> str:
        m = dt.month
        if m in (12, 1, 2):
            return "Winter"
        elif m in (3, 4, 5):
            return "Spring"
        elif m in (6, 7, 8):
            return "Summer"
        else:
            return "Fall / Autumn"

    seasons_order = ["Spring", "Summer", "Fall / Autumn", "Winter"]
    temp = df.copy()
    temp["season"] = temp["timestamp"].apply(get_season)

    agg = temp.groupby("season").agg(
        Plays=("timestamp", "count"),
        Hours=("duration_hours", "sum")
    ).reindex(seasons_order).fillna(0).reset_index()

    agg["Hours"] = agg["Hours"].round(1)
    total_plays = len(df)
    agg["Share %"] = (agg["Plays"] / max(total_plays, 1) * 100.0).round(1)
    return agg


def get_session_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculates granular session metrics."""
    if df.empty or "session_id" not in df.columns:
        return {}

    session_groups = df.groupby("session_id")
    sess_summary = session_groups.agg(
        track_count=("clean_title", "count"),
        duration_min=("duration_min", "sum"),
        start_time=("timestamp", "min"),
        end_time=("timestamp", "max")
    ).reset_index()

    total_sessions = len(sess_summary)
    avg_length_min = sess_summary["duration_min"].mean()
    longest_session_min = sess_summary["duration_min"].max()
    avg_tracks_per_sess = sess_summary["track_count"].mean()

    # Most common session start hour
    sess_summary["start_hour"] = sess_summary["start_time"].dt.hour
    hour_counts = sess_summary["start_hour"].value_counts()
    peak_start_hour = int(hour_counts.index[0]) if not hour_counts.empty else 0

    return {
        "total_sessions": int(total_sessions),
        "avg_session_length_minutes": round(float(avg_length_min), 1),
        "longest_session_minutes": round(float(longest_session_min), 1),
        "avg_tracks_per_session": round(float(avg_tracks_per_sess), 1),
        "peak_session_start_hour": peak_start_hour,
        "peak_session_start_hour_label": f"{peak_start_hour:02d}:00",
    }


def compute_listening_streaks(df: pd.DataFrame) -> Dict[str, Any]:
    """Computes longest consecutive daily streak, current streak, and longest break."""
    if df.empty:
        return {
            "longest_streak_days": 0,
            "longest_streak_start": None,
            "longest_streak_end": None,
            "current_streak_days": 0,
            "longest_break_days": 0,
        }

    unique_dates = sorted(list(df["date"].unique()))
    if not unique_dates:
        return {"longest_streak_days": 0, "current_streak_days": 0, "longest_break_days": 0}

    # 1. Streaks
    longest_streak = 1
    current_streak = 1
    best_streak_start = unique_dates[0]
    best_streak_end = unique_dates[0]
    curr_start = unique_dates[0]

    # Breaks
    longest_break = 0

    for i in range(1, len(unique_dates)):
        gap = (unique_dates[i] - unique_dates[i - 1]).days
        if gap == 1:
            current_streak += 1
            if current_streak > longest_streak:
                longest_streak = current_streak
                best_streak_start = curr_start
                best_streak_end = unique_dates[i]
        else:
            current_streak = 1
            curr_start = unique_dates[i]
            break_days = gap - 1
            if break_days > longest_break:
                longest_break = break_days

    # Current streak (calculated from latest date in dataset backwards)
    latest_date = unique_dates[-1]
    active_streak = 1
    for i in range(len(unique_dates) - 2, -1, -1):
        if (unique_dates[i + 1] - unique_dates[i]).days == 1:
            active_streak += 1
        else:
            break

    return {
        "longest_streak_days": int(longest_streak),
        "longest_streak_start": str(best_streak_start),
        "longest_streak_end": str(best_streak_end),
        "current_streak_days": int(active_streak),
        "longest_break_days": int(longest_break),
    }


# ============================================================================
# 5. DISCOVERY & REPLAY METRICS
# ============================================================================

def get_discovery_trends(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Computes monthly discovery rates:
    - New artists discovered per month
    - New tracks discovered per month
    - % of plays in that month that were first-ever listens
    - Cumulative unique artists & tracks over time
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_sorted = df.sort_values("timestamp", ascending=True).copy()

    # Tag first occurrence of each artist & track
    df_sorted["is_new_artist"] = ~df_sorted.duplicated(subset=["primary_artist"])
    df_sorted["is_new_track"] = ~df_sorted.duplicated(subset=["track_id"])

    # Monthly discoveries
    monthly = df_sorted.groupby("month").agg(
        Total_Plays=("timestamp", "count"),
        New_Artists=("is_new_artist", "sum"),
        New_Tracks=("is_new_track", "sum"),
    ).reset_index().sort_values("month")

    monthly["First_Listen_Plays_%"] = (monthly["New_Tracks"] / monthly["Total_Plays"] * 100.0).round(1)

    # Cumulative growth over all plays
    df_sorted["cum_artists"] = df_sorted["is_new_artist"].cumsum()
    df_sorted["cum_tracks"] = df_sorted["is_new_track"].cumsum()
    cum_timeline = df_sorted.groupby("date").agg(
        Cumulative_Artists=("cum_artists", "max"),
        Cumulative_Tracks=("cum_tracks", "max")
    ).reset_index()

    return monthly, cum_timeline


def get_replay_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates replay metrics:
    - Repeat play %
    - Average plays per track
    - Track tier distribution (1 play vs 2-5 vs 6-20 vs 20+)
    """
    if df.empty:
        return {}

    track_counts = df["track_id"].value_counts()
    total_plays = len(df)
    unique_tracks = len(track_counts)

    avg_plays_per_track = total_plays / max(unique_tracks, 1)

    # Repeat plays = total plays minus the first play of each unique track
    repeat_plays = total_plays - unique_tracks
    repeat_rate_pct = (repeat_plays / max(total_plays, 1)) * 100.0

    # Tiers
    tier_1 = int((track_counts == 1).sum())
    tier_2_5 = int(((track_counts >= 2) & (track_counts <= 5)).sum())
    tier_6_20 = int(((track_counts >= 6) & (track_counts <= 20)).sum())
    tier_20_plus = int((track_counts > 20).sum())

    tiers_df = pd.DataFrame([
        {"Tier": "Played Once (1)", "Tracks": tier_1, "Share %": round(tier_1 / unique_tracks * 100, 1)},
        {"Tier": "Occasional (2 - 5)", "Tracks": tier_2_5, "Share %": round(tier_2_5 / unique_tracks * 100, 1)},
        {"Tier": "Frequent (6 - 20)", "Tracks": tier_6_20, "Share %": round(tier_6_20 / unique_tracks * 100, 1)},
        {"Tier": "Obsessions (20+)", "Tracks": tier_20_plus, "Share %": round(tier_20_plus / unique_tracks * 100, 1)},
    ])

    return {
        "repeat_rate_pct": round(repeat_rate_pct, 1),
        "avg_plays_per_track": round(avg_plays_per_track, 1),
        "tiers_df": tiers_df,
    }


def get_repeat_loops(df: pd.DataFrame, top_n: int = 15) -> Tuple[int, pd.DataFrame]:
    """
    Identifies repeat loops: tracks played back-to-back 2+ times consecutively.
    Returns (total_loop_count, top_looped_tracks_dataframe).
    """
    if df.empty or len(df) < 2:
        return 0, pd.DataFrame(columns=["Track", "Artist", "Consecutive Loops"])

    df_sorted = df.sort_values("timestamp", ascending=True).copy()
    same_as_prev = (df_sorted["track_id"] == df_sorted["track_id"].shift(1)) & (df_sorted["session_id"] == df_sorted["session_id"].shift(1))
    
    total_loop_instances = int(same_as_prev.sum())

    # Count loops per track
    loop_tracks = df_sorted[same_as_prev].groupby(["clean_title", "primary_artist"]).size().reset_index(name="Consecutive Loops")
    loop_tracks = loop_tracks.rename(columns={"clean_title": "Track", "primary_artist": "Artist"})
    loop_tracks = loop_tracks.sort_values("Consecutive Loops", ascending=False).reset_index(drop=True)
    loop_tracks["Rank"] = loop_tracks.index + 1

    return total_loop_instances, loop_tracks.head(top_n)


def get_obsession_tracks(df: pd.DataFrame, top_n: int = 10) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detects single-day and single-week obsession spikes:
    - Tracks with the highest play count in any single calendar day
    - Tracks with the highest play count in any single calendar week
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Daily obsessions
    daily_obs = df.groupby(["date", "clean_title", "primary_artist"]).size().reset_index(name="Plays")
    daily_obs = daily_obs.rename(columns={"date": "Date", "clean_title": "Track", "primary_artist": "Artist"})
    daily_obs = daily_obs.sort_values("Plays", ascending=False).head(top_n).reset_index(drop=True)
    daily_obs["Date"] = daily_obs["Date"].astype(str)
    daily_obs["Rank"] = daily_obs.index + 1

    # Weekly obsessions
    df_copy = df.copy()
    df_copy["week"] = df_copy["timestamp"].dt.to_period("W").astype(str)
    weekly_obs = df_copy.groupby(["week", "clean_title", "primary_artist"]).size().reset_index(name="Plays")
    weekly_obs = weekly_obs.rename(columns={"week": "Week", "clean_title": "Track", "primary_artist": "Artist"})
    weekly_obs = weekly_obs.sort_values("Plays", ascending=False).head(top_n).reset_index(drop=True)
    weekly_obs["Rank"] = weekly_obs.index + 1

    return daily_obs, weekly_obs


def get_comeback_tracks(df: pd.DataFrame, min_dormant_days: int = 180, top_n: int = 20) -> pd.DataFrame:
    """
    Detects songs that had a hiatus >= min_dormant_days (default ~6 months) between plays,
    then were returned to.
    """
    if df.empty or len(df) < 2:
        return pd.DataFrame()

    df_sorted = df.sort_values(["track_id", "timestamp"]).copy()
    df_sorted["prev_play"] = df_sorted.groupby("track_id")["timestamp"].shift(1)
    df_sorted["dormant_gap_days"] = (df_sorted["timestamp"] - df_sorted["prev_play"]).dt.total_seconds() / 86400.0

    comebacks = df_sorted[df_sorted["dormant_gap_days"] >= min_dormant_days].copy()
    if comebacks.empty:
        return pd.DataFrame(columns=["Track", "Artist", "Gap (Days)", "Last Played Before Hiatus", "Comeback Date"])

    # Aggregate max dormant gap per track
    agg = comebacks.groupby(["clean_title", "primary_artist"]).agg(
        Max_Gap_Days=("dormant_gap_days", "max"),
        Last_Played_Before=("prev_play", "first"),
        Comeback_Date=("timestamp", "first")
    ).reset_index().rename(columns={"clean_title": "Track", "primary_artist": "Artist", "Max_Gap_Days": "Gap (Days)"})

    agg["Gap (Days)"] = agg["Gap (Days)"].astype(int)
    agg["Last Played Before Hiatus"] = agg["Last_Played_Before"].dt.strftime("%Y-%m-%d")
    agg["Comeback Date"] = agg["Comeback_Date"].dt.strftime("%Y-%m-%d")
    agg = agg.sort_values("Gap (Days)", ascending=False).reset_index(drop=True)
    agg["Rank"] = agg.index + 1
    return agg[["Rank", "Track", "Artist", "Gap (Days)", "Last Played Before Hiatus", "Comeback Date"]].head(top_n)


def compute_loyalty_and_diversity(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates artist concentration (share from top 1, 10, 50 artists),
    Shannon entropy (normalized 0-1 diversity score), and Gini coefficient.
    """
    if df.empty:
        return {}

    artist_counts = df["primary_artist"].value_counts().values
    total_plays = artist_counts.sum()
    n_artists = len(artist_counts)

    # Top 1, 10, 50 shares
    top1_share = (artist_counts[:1].sum() / total_plays) * 100.0 if n_artists >= 1 else 0.0
    top10_share = (artist_counts[:10].sum() / total_plays) * 100.0 if n_artists >= 10 else 100.0
    top50_share = (artist_counts[:50].sum() / total_plays) * 100.0 if n_artists >= 50 else 100.0

    # Shannon Entropy H = -sum(p * ln(p))
    p = artist_counts / total_plays
    shannon_entropy = -np.sum(p * np.log(p))
    # Normalized entropy (0 to 1)
    max_entropy = np.log(n_artists) if n_artists > 1 else 1.0
    normalized_entropy = shannon_entropy / max_entropy if max_entropy > 0 else 1.0

    # Gini Coefficient
    sorted_counts = np.sort(artist_counts)
    index = np.arange(1, n_artists + 1)
    gini = (2.0 * np.sum(index * sorted_counts)) / (n_artists * np.sum(sorted_counts)) - (n_artists + 1.0) / n_artists

    # Cumulative concentration curve
    cum_share = (np.cumsum(artist_counts) / total_plays) * 100.0
    curve_data = pd.DataFrame({
        "Artist_Rank": np.arange(1, min(n_artists, 100) + 1),
        "Cumulative_Share_%": cum_share[:min(n_artists, 100)]
    })

    return {
        "top1_share_pct": round(top1_share, 1),
        "top10_share_pct": round(top10_share, 1),
        "top50_share_pct": round(top50_share, 1),
        "shannon_entropy": round(float(shannon_entropy), 2),
        "diversity_score_pct": round(float(normalized_entropy) * 100.0, 1),
        "gini_coefficient": round(float(gini), 3),
        "concentration_curve": curve_data,
    }


def get_artist_lifespan_and_one_hit_wonders(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Computes duration of listening relationship per artist and one-hit-wonders count.
    """
    if df.empty:
        return pd.DataFrame(), {}

    agg = df.groupby("primary_artist").agg(
        Plays=("timestamp", "count"),
        First_Play=("timestamp", "min"),
        Last_Play=("timestamp", "max")
    ).reset_index()

    agg["Lifespan_Days"] = (agg["Last_Play"].dt.date - agg["First_Play"].dt.date).dt.days
    total_artists = len(agg)
    one_hits = agg[agg["Plays"] == 1]
    one_hit_count = len(one_hits)

    summary = {
        "total_artists": total_artists,
        "one_hit_wonder_count": one_hit_count,
        "one_hit_wonder_pct": round(one_hit_count / max(total_artists, 1) * 100.0, 1),
        "avg_artist_lifespan_days": round(float(agg["Lifespan_Days"].mean()), 1),
        "max_artist_lifespan_days": int(agg["Lifespan_Days"].max()),
    }

    # Top enduring artists
    enduring = agg.sort_values(by=["Lifespan_Days", "Plays"], ascending=False).head(20).reset_index(drop=True)
    enduring["Rank"] = enduring.index + 1
    enduring = enduring.rename(columns={"primary_artist": "Artist", "Lifespan_Days": "Lifespan (Days)"})

    return enduring[["Rank", "Artist", "Plays", "Lifespan (Days)", "First_Play", "Last_Play"]], summary


def compute_skip_proxy(df: pd.DataFrame, min_artist_plays: int = 10) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Analyzes heuristic skips (tracks followed in < 30 seconds).
    Returns overall skip metrics and per-artist skip breakdown.
    """
    if df.empty or "is_skip" not in df.columns:
        return {}, pd.DataFrame()

    total_plays = len(df)
    total_skips = int(df["is_skip"].sum())
    overall_skip_rate = (total_skips / max(total_plays, 1)) * 100.0

    artist_skips = df.groupby("primary_artist").agg(
        Total_Plays=("is_skip", "count"),
        Skips=("is_skip", "sum")
    ).reset_index()

    artist_skips = artist_skips[artist_skips["Total_Plays"] >= min_artist_plays].copy()
    artist_skips["Skip_Rate_%"] = (artist_skips["Skips"] / artist_skips["Total_Plays"] * 100.0).round(1)
    artist_skips = artist_skips.sort_values(by="Skip_Rate_%", ascending=False).reset_index(drop=True)
    artist_skips = artist_skips.rename(columns={"primary_artist": "Artist", "Total_Plays": "Plays", "Skip_Rate_%": "Skip Rate %"})
    artist_skips["Rank"] = artist_skips.index + 1

    overall = {
        "total_skips": total_skips,
        "overall_skip_rate_pct": round(overall_skip_rate, 1),
        "skip_definition": "Track followed by next play in < 30 seconds"
    }

    return overall, artist_skips[["Rank", "Artist", "Plays", "Skips", "Skip Rate %"]].head(25)


# ============================================================================
# 6. WRAPPED SUMMARY & MILESTONES
# ============================================================================

def get_wrapped_card_data(df: pd.DataFrame, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Generates data payload for the Spotify/YT Wrapped-style summary card for a given year.
    """
    if df.empty:
        return {}

    sub = df[df["year"] == year].copy() if year else df.copy()
    if sub.empty:
        return {"year": year, "total_plays": 0}

    total_plays = len(sub)
    total_hours = round(sub["duration_hours"].sum(), 1)
    unique_artists = sub["primary_artist"].nunique()
    unique_tracks = sub["clean_title"].nunique()

    # Top 5 artists
    top_artists = sub["primary_artist"].value_counts().head(5).to_dict()

    # Top 5 tracks
    top_tracks = sub.groupby(["clean_title", "primary_artist"]).size().sort_values(ascending=False).head(5)
    top_tracks_list = [{"title": idx[0], "artist": idx[1], "plays": int(count)} for idx, count in top_tracks.items()]

    # Busiest day
    day_counts = sub.groupby("date").agg(Plays=("timestamp", "count"), Hours=("duration_hours", "sum")).reset_index()
    top_day = day_counts.sort_values("Plays", ascending=False).iloc[0]

    # Listener type
    _, listener_type = get_time_bucket_summary(sub)

    return {
        "year": year or "All-Time",
        "total_plays": int(total_plays),
        "total_hours": float(total_hours),
        "unique_artists": int(unique_artists),
        "unique_tracks": int(unique_tracks),
        "top_artists": [{"name": k, "plays": int(v)} for k, v in top_artists.items()],
        "top_tracks": top_tracks_list,
        "busiest_day": {
            "date": str(top_day["date"]),
            "plays": int(top_day["Plays"]),
            "hours": round(float(top_day["Hours"]), 1)
        },
        "listener_type": listener_type,
    }


def get_play_milestones(df: pd.DataFrame) -> pd.DataFrame:
    """Finds exact track & timestamp of 1st play, 100th, 500th, 1000th, 5000th, 10000th, etc."""
    if df.empty:
        return pd.DataFrame()

    df_sorted = df.sort_values("timestamp", ascending=True).reset_index(drop=True)
    n = len(df_sorted)

    milestone_targets = [1, 100, 500, 1000, 2500, 5000, 10000, 25000, 50000]
    records = []
    for m in milestone_targets:
        if m <= n:
            row = df_sorted.iloc[m - 1]
            records.append({
                "Milestone": f"#{m:,} Play",
                "Date & Time": row["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "Track": row["clean_title"],
                "Artist": row["primary_artist"],
            })

    return pd.DataFrame(records)


def get_rediscovery_tracks(df: pd.DataFrame, min_past_plays: int = 5, lookback_days: int = 365) -> pd.DataFrame:
    """
    Identifies tracks the user loved in the past (>= min_past_plays),
    but hasn't played at all in the last lookback_days (default 365 days).
    """
    if df.empty:
        return pd.DataFrame()

    max_date = df["timestamp"].max()
    cutoff_date = max_date - timedelta(days=lookback_days)

    past_df = df[df["timestamp"] < cutoff_date]
    recent_df = df[df["timestamp"] >= cutoff_date]

    past_counts = past_df.groupby(["clean_title", "primary_artist"]).agg(
        Past_Plays=("timestamp", "count"),
        Last_Played=("timestamp", "max")
    ).reset_index()

    past_favorites = past_counts[past_counts["Past_Plays"] >= min_past_plays]
    recent_played_keys = set(recent_df["clean_title"] + " - " + recent_df["primary_artist"])

    past_favorites["key"] = past_favorites["clean_title"] + " - " + past_favorites["primary_artist"]
    rediscovered = past_favorites[~past_favorites["key"].isin(recent_played_keys)].copy()

    if rediscovered.empty:
        return pd.DataFrame(columns=["Rank", "Track", "Artist", "Past Plays", "Last Played"])

    rediscovered = rediscovered.sort_values("Past_Plays", ascending=False).reset_index(drop=True)
    rediscovered["Rank"] = rediscovered.index + 1
    rediscovered["Last Played"] = rediscovered["Last_Played"].dt.strftime("%Y-%m-%d")
    rediscovered = rediscovered.rename(columns={"clean_title": "Track", "primary_artist": "Artist", "Past_Plays": "Past Plays"})

    return rediscovered[["Rank", "Track", "Artist", "Past Plays", "Last Played"]].head(25)
