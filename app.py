"""
app.py - YT Music Wrapped Pro Streamlit Application.
Interactive local dashboard for Google Takeout YouTube Music history analysis.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import List, Optional
import pandas as pd
import streamlit as st

import charts
import cleaner
import metrics
import parser

# Page configuration
st.set_page_config(
    page_title="YT Music Wrapped Pro — Telemetry",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ferrari Luxury-Automotive Design System CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global canvas & typography */
    .stApp {
        background-color: #181818 !important;
        color: #ffffff !important;
        font-family: 'FerrariSans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }

    /* Top livery band */
    header[data-testid="stHeader"] {
        background: #181818 !important;
        border-bottom: 1px solid #303030 !important;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #141414 !important;
        border-right: 1px solid #303030 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #ffffff !important;
        font-weight: 500 !important;
        letter-spacing: -0.36px !important;
    }

    /* Metric cards: Sharp 0px corners, #202020 elevated card, 1px #303030 hairline */
    div[data-testid="stMetric"] {
        background: #202020 !important;
        border: 1px solid #303030 !important;
        border-radius: 0px !important;
        padding: 16px 20px !important;
        box-shadow: none !important;
    }
    div[data-testid="stMetric"] label[data-testid="stMetricLabel"] {
        font-size: 11px !important;
        font-weight: 600 !important;
        letter-spacing: 1.1px !important;
        text-transform: uppercase !important;
        color: #969696 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 32px !important;
        font-weight: 700 !important;
        letter-spacing: -1px !important;
        color: #ffffff !important;
        line-height: 1.1 !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 12px !important;
        font-weight: 500 !important;
    }

    /* Buttons: Primary Rosso Corsa #da291c, sharp 0px corners, uppercase tracked text */
    div.stButton > button,
    div.stDownloadButton > button {
        background-color: #da291c !important;
        color: #ffffff !important;
        border: 1px solid #da291c !important;
        border-radius: 0px !important;
        padding: 12px 28px !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        letter-spacing: 1.4px !important;
        text-transform: uppercase !important;
        box-shadow: none !important;
        transition: background-color 0.15s ease !important;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover {
        background-color: #9d2211 !important;
        border-color: #9d2211 !important;
        color: #ffffff !important;
    }
    div.stButton > button:active,
    div.stDownloadButton > button:active {
        background-color: #b01e0a !important;
        border-color: #b01e0a !important;
    }

    /* Tabs: Sharp corners, hairlines, Rosso Corsa active indicator */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px !important;
        border-bottom: 1px solid #303030 !important;
        background: transparent !important;
        padding-bottom: 0px !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px !important;
        border-radius: 0px !important;
        color: #969696 !important;
        background: transparent !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.65px !important;
        text-transform: uppercase !important;
        border-bottom: 2px solid transparent !important;
        transition: all 0.15s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #ffffff !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #202020 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #da291c !important;
    }

    /* Form inputs: rounded.sm (4px), 1px #303030 hairline */
    input, select, textarea, div[data-baseweb="select"] {
        border-radius: 4px !important;
        border: 1px solid #303030 !important;
        background-color: #181818 !important;
        color: #ffffff !important;
    }

    /* Expanders: Sharp 0px corners, hairline */
    div[data-testid="stExpander"] {
        background-color: #202020 !important;
        border: 1px solid #303030 !important;
        border-radius: 0px !important;
    }

    /* Tables */
    div[data-testid="stDataFrame"] {
        border: 1px solid #303030 !important;
        border-radius: 0px !important;
        background: #181818 !important;
    }
    .dataframe {
        font-size: 13px !important;
        background-color: #181818 !important;
        color: #ffffff !important;
    }

    /* Alerts and banners */
    div[data-testid="stAlert"] {
        background-color: #202020 !important;
        border: 1px solid #303030 !important;
        border-left: 3px solid #da291c !important;
        border-radius: 0px !important;
        color: #ffffff !important;
    }

    /* Dividers */
    hr {
        border-color: #303030 !important;
        margin: 28px 0 !important;
    }
</style>
""", unsafe_allow_html=True)



# ============================================================================
# CACHED DATA PIPELINE
# ============================================================================

@st.cache_data(show_spinner=False)
def load_and_clean_data(
    file_bytes_list: List[bytes],
    include_regular_youtube: bool,
    target_timezone: str,
    duration_method: str,
    gap_cap_minutes: float,
    default_track_minutes: float,
    session_gap_minutes: float,
    yt_api_key: Optional[str] = None
):
    """Cached loader and cleaner that takes raw bytes of uploaded files."""
    # 1. Parse raw entries
    raw_df, ingestion_report = parser.parse_watch_histories(
        file_bytes_list,
        include_regular_youtube=include_regular_youtube
    )

    # 2. Clean, deduplicate, compute listening times & sessions
    clean_df, cleaning_report = cleaner.clean_watch_history(
        raw_df,
        target_timezone=target_timezone,
        duration_method=duration_method,
        gap_cap_minutes=gap_cap_minutes,
        default_track_minutes=default_track_minutes,
        session_gap_minutes=session_gap_minutes,
        yt_api_key=yt_api_key
    )

    return clean_df, ingestion_report, cleaning_report


# ============================================================================
# SIDEBAR CONTROLS
# ============================================================================

st.sidebar.markdown("""
<div style="margin-bottom: 16px;">
    <span style="background: #da291c; color: #ffffff; font-size: 10px; font-weight: 700; padding: 3px 8px; letter-spacing: 1.4px; text-transform: uppercase;">
        TELEMETRY PRO
    </span>
    <h2 style="font-size: 20px; font-weight: 700; letter-spacing: 0.5px; color: #ffffff; margin: 8px 0 2px 0; text-transform: uppercase;">
        YT MUSIC WRAPPED
    </h2>
    <div style="font-size: 11px; color: #969696; text-transform: uppercase; letter-spacing: 1px;">
        100% Local • Private • Sub-ms Engine
    </div>
</div>
""", unsafe_allow_html=True)

# Demo file option
use_demo = st.sidebar.checkbox("Load Demo Sample Data", value=False, help="Try the app with synthetic watch history data.")


uploaded_files = st.sidebar.file_uploader(
    "Upload watch-history.json",
    type=["json"],
    accept_multiple_files=True,
    help="Export from Google Takeout (YouTube and YouTube Music > history > watch-history.json)"
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings & Configuration")

# Timezone selector
COMMON_TIMEZONES = [
    "Asia/Kolkata",
    "UTC",
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Paris",
    "Asia/Tokyo",
    "Asia/Singapore",
    "Asia/Dubai",
    "Australia/Sydney",
]
selected_tz = st.sidebar.selectbox("Your Timezone", COMMON_TIMEZONES, index=0)

# Listening Time Method
time_method = st.sidebar.radio(
    "Listening Time Method",
    options=[
        "ytmusicapi Auto-Lookup (Free, No Key Required)",
        "Gap-based Estimate (Instant & Offline)",
        "YouTube Data API v3 (Google Cloud Key)"
    ],
    index=0,
    help="ytmusicapi fetches exact track durations directly from YouTube Music with local SQLite caching. Gap-based estimate uses intervals between plays."
)

api_key = None
gap_cap = 6.0
default_track = 3.5

if time_method.startswith("ytmusicapi"):
    duration_method_choice = "ytmusicapi"
    st.sidebar.caption("⚡ Direct unauthenticated YouTube Music lookup with local SQLite caching (`ytmusic_duration_cache.db`).")
elif time_method.startswith("YouTube Data API"):
    duration_method_choice = "api_lookup"
    api_key = st.sidebar.text_input("YouTube Data API Key", type="password", help="Free API key from Google Cloud Console.")
    st.sidebar.info("Durations are cached locally in SQLite. Missing or quota-limited tracks fall back to gap estimate.")
else:
    duration_method_choice = "gap"
    col_g1, col_g2 = st.sidebar.columns(2)
    with col_g1:
        gap_cap = st.number_input("Max Gap (min)", min_value=1.0, max_value=30.0, value=6.0, step=0.5,
                                  help="Gaps longer than this cap mark session breaks or idle pauses.")
    with col_g2:
        default_track = st.number_input("Default Track (min)", min_value=1.0, max_value=10.0, value=3.5, step=0.5,
                                        help="Duration assigned when gap exceeds cap or track is last in a session.")

# Session detection
session_gap = st.sidebar.slider(
    "Session Break Threshold (minutes)",
    min_value=5,
    max_value=120,
    value=30,
    step=5,
    help="Consecutive plays separated by more than this duration start a new session."
)

# Service filter toggle
include_regular_yt = st.sidebar.toggle(
    "Include Regular YouTube Videos",
    value=False,
    help="When enabled, videos watched on regular YouTube (header != 'YouTube Music') are also included."
)

# Optional ytmusicapi Direct Account Sync
with st.sidebar.expander("🔗 Direct YT Music Account Sync", expanded=False):
    st.caption("Sync history directly from your account via `ytmusicapi` without waiting for Google Takeout.")
    auth_file = st.file_uploader("Upload browser.json or oauth.json", type=["json"], key="auth_json",
                                 help="Exported using ytmusicapi.setup(filepath='browser.json') or ytmusicapi.setup_oauth()")
    if auth_file:
        if st.button("Fetch Live Account History", use_container_width=True):
            try:
                from ytmusicapi import YTMusic
                auth_data = json.loads(auth_file.getvalue().decode("utf-8"))
                yt_auth = YTMusic(auth=auth_data)
                account_history = yt_auth.get_history()
                converted_records = cleaner.convert_ytmusicapi_history_to_records(account_history)
                st.session_state["ytmusicapi_live_history"] = json.dumps(converted_records).encode("utf-8")
                st.success(f"Fetched {len(converted_records)} tracks from your account!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to fetch account history: {e}")


st.sidebar.markdown("---")
st.sidebar.caption("🔒 All processing runs locally on your computer. No data is sent to external servers.")


# ============================================================================
# DATA INGESTION
# ============================================================================

file_bytes_to_load = []

if "ytmusicapi_live_history" in st.session_state:
    file_bytes_to_load.append(st.session_state["ytmusicapi_live_history"])

if uploaded_files:
    for f in uploaded_files:
        file_bytes_to_load.append(f.getvalue())
elif use_demo and not file_bytes_to_load:
    demo_path = Path("sample_watch_history.json")
    if not demo_path.exists():
        import generate_sample_data
        generate_sample_data.generate_sample_watch_history(1500, str(demo_path))
    with open(demo_path, "rb") as f:
        file_bytes_to_load.append(f.read())

if not file_bytes_to_load:
    st.info("👋 **Welcome to YT Music Wrapped Pro!**")
    st.markdown("""
    ### Quick Start Guide:
    1. Check **'Load Demo Sample Data'** in the sidebar to test out the dashboard immediately with realistic data.
    2. Or upload your own **`watch-history.json`** from Google Takeout:
       - Go to [Google Takeout](https://takeout.google.com/)
       - Deselect all, then check only **YouTube and YouTube Music**
       - Click **'Multiple formats'** and ensure History is set to **JSON**
       - Download and extract the archive, then upload `watch-history.json` here.
    3. Or connect your YouTube Music account via **ytmusicapi** in the sidebar to sync your live history directly!
    """)
    st.stop()
    clean_df = pd.DataFrame()
else:
    # Run ingestion with progress indicator
    with st.spinner("Processing watch history & calculating metrics..."):
        clean_df, ing_report, clean_report = load_and_clean_data(
            file_bytes_list=file_bytes_to_load,
            include_regular_youtube=include_regular_yt,
            target_timezone=selected_tz,
            duration_method=duration_method_choice,
            gap_cap_minutes=gap_cap,
            default_track_minutes=default_track,
            session_gap_minutes=session_gap,
            yt_api_key=api_key
        )


if clean_df.empty or "year" not in clean_df.columns:
    if file_bytes_to_load:
        st.warning("⚠️ No valid music records were found in the uploaded file(s). Please verify the JSON contents.")
    st.stop()
    import sys
    sys.exit(0)


# ============================================================================
# DATE FILTERING IN SIDEBAR
# ============================================================================

st.sidebar.subheader("📅 Date Range Filter")
filter_mode = st.sidebar.radio("Filter Scope", ["All-Time", "By Year", "Custom Date Range"], index=0)

filtered_df = clean_df.copy()
available_years = sorted(clean_df["year"].unique(), reverse=True)

if filter_mode == "By Year":
    chosen_year = st.sidebar.selectbox("Select Year", available_years)
    filtered_df = filtered_df[filtered_df["year"] == chosen_year]
elif filter_mode == "Custom Date Range":
    min_date = clean_df["date"].min()
    max_date = clean_df["date"].max()
    date_range = st.sidebar.date_input("Date Span", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
        filtered_df = filtered_df[(filtered_df["date"] >= start_d) & (filtered_df["date"] <= end_d)]


# ============================================================================
# TOP DATA-QUALITY PANEL
# ============================================================================

with st.expander("📊 Data Quality & Ingestion Summary", expanded=False):
    col_q1, col_q2, col_q3, col_q4, col_q5 = st.columns(5)
    col_q1.metric("Raw Rows Parsed", f"{ing_report.total_raw_records:,}")
    col_q2.metric("Google Ads Dropped", f"{ing_report.dropped_ads:,}")
    col_q3.metric("Non-Music Dropped", f"{ing_report.dropped_non_ytmusic:,}", help="YouTube non-music videos filtered out")
    col_q4.metric("Duplicates Merged", f"{clean_report.duplicate_rows_dropped:,}")
    col_q5.metric("Clean Music Plays", f"{len(clean_df):,}")

    col_sub1, col_sub2, col_sub3 = st.columns(3)
    col_sub1.info(f"❓ **Unknown Artists**: {clean_report.unknown_artists_flagged} deleted/private items flagged")
    col_sub2.info(f"🔗 **URL-only Titles**: {clean_report.url_titles_flagged} removed tracks recovered")
    if clean_report.duration_method_used == "ytmusicapi":
        duration_label = f"ytmusicapi Verified Durations ({clean_report.cached_api_durations_used} tracks synced)"
    elif clean_report.duration_method_used == "api_lookup":
        duration_label = f"YouTube Data API v3 Verified ({clean_report.cached_api_durations_used} tracks)"
    else:
        duration_label = f"Gap-based Estimate (Cap: {gap_cap}m, Default: {default_track}m)"
    col_sub3.info(f"⏱️ **Duration Engine**: {duration_label}")


# Editorial Top Telemetry Hero Band
st.markdown("""
<div style="background: #202020; border: 1px solid #303030; border-left: 4px solid #da291c; padding: 24px 32px; margin-bottom: 24px;">
    <div style="font-size: 11px; font-weight: 700; letter-spacing: 1.4px; text-transform: uppercase; color: #da291c; margin-bottom: 6px;">
        HIGH-PERFORMANCE AUDIO TELEMETRY
    </div>
    <h1 style="font-size: 36px; font-weight: 500; letter-spacing: -0.36px; margin: 0 0 8px 0; color: #ffffff; text-transform: uppercase;">
        YT MUSIC TELEMETRY PRO
    </h1>
    <p style="color: #969696; font-size: 14px; margin: 0; max-width: 800px;">
        Luxury editorial intelligence for your personal listening history. 100% private, local processing with Scuderia telemetry precision.
    </p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# MAIN TABS INTERFACE
# ============================================================================

tabs = st.tabs([
    "📈 Overview",
    "🏆 Top Charts",
    "⏳ Timeline",
    "🌙 Patterns & Sessions",
    "🔄 Discovery & Replay",
    "🔍 Explorer",
    "🎁 Wrapped Cards"
])


# ----------------------------------------------------------------------------
# TAB 1: OVERVIEW
# ----------------------------------------------------------------------------
with tabs[0]:
    ov = metrics.compute_overview_stats(filtered_df)
    
    st.subheader(f"Listening Summary ({ov['start_date']} to {ov['end_date']})")
    if ov["is_estimated_duration"]:
        st.caption("ℹ️ Listening time metrics are **estimated** using playback gaps between tracks.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Plays", f"{ov['total_plays']:,}")
    m2.metric("Unique Tracks", f"{ov['unique_tracks']:,}")
    m3.metric("Unique Artists", f"{ov['unique_artists']:,}")
    m4.metric("Listening Time", f"{ov['total_listening_hours']:,.1f} hrs", delta=f"{ov['total_listening_days']} days")
    m5.metric("Active Days", f"{ov['active_days_pct']}%", delta=f"{ov['active_days_count']} / {ov['total_days_span']} days")

    m6, m7, m8, m9 = st.columns(4)
    m6.metric("Avg Plays / Day", f"{ov['avg_plays_per_day']}")
    m7.metric("Avg Plays / Active Day", f"{ov['avg_plays_per_active_day']}")
    m8.metric("Listening Sessions", f"{ov['total_sessions']:,}")
    
    streaks = metrics.compute_listening_streaks(filtered_df)
    m9.metric("Longest Daily Streak", f"{streaks['longest_streak_days']} days", delta=f"Current: {streaks['current_streak_days']}d")

    st.markdown("---")

    col_chart_left, col_chart_right = st.columns([3, 2])
    with col_chart_left:
        monthly_sum = metrics.get_monthly_summary(filtered_df)
        st.plotly_chart(charts.plot_monthly_timeline(monthly_sum), use_container_width=True)

    with col_chart_right:
        bucket_df, listener_type = metrics.get_time_bucket_summary(filtered_df)
        st.plotly_chart(charts.plot_time_bucket_donut(bucket_df, listener_type), use_container_width=True)

    # Activity Heatmap Calendar
    daily_cal = metrics.get_daily_calendar_data(filtered_df)
    st.plotly_chart(charts.plot_calendar_heatmap(daily_cal), use_container_width=True)


# ----------------------------------------------------------------------------
# TAB 2: TOP CHARTS
# ----------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Leaderboards & Rankings")
    top_limit = st.select_slider("Show Top N Items", options=[10, 25, 50, 100], value=25)

    chart_subtabs = st.tabs(["Top Artists", "Top Tracks", "Monthly Leaderboard"])

    with chart_subtabs[0]:
        top_art_df = metrics.get_top_artists(filtered_df, top_n=top_limit)
        col_metric_choice = st.radio("Rank Artists By", ["Plays", "Hours"], horizontal=True)

        st.plotly_chart(
            charts.plot_top_horizontal_bars(
                top_art_df,
                x_col=col_metric_choice,
                y_col="Artist",
                title=f"Top {top_limit} Artists by {col_metric_choice}",
                x_label=f"Total {col_metric_choice}",
                color_scale="Plasma"
            ),
            use_container_width=True
        )

        st.dataframe(top_art_df, use_container_width=True, hide_index=True)
        csv_art = top_art_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Top Artists CSV", data=csv_art, file_name="top_artists.csv", mime="text/csv")

    with chart_subtabs[1]:
        top_trk_df = metrics.get_top_tracks(filtered_df, top_n=top_limit)
        st.plotly_chart(
            charts.plot_top_horizontal_bars(
                top_trk_df,
                x_col="Plays",
                y_col="Track",
                title=f"Top {top_limit} Tracks by Plays",
                x_label="Total Plays",
                color_scale="Viridis"
            ),
            use_container_width=True
        )

        st.dataframe(top_trk_df, use_container_width=True, hide_index=True)
        csv_trk = top_trk_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Top Tracks CSV", data=csv_trk, file_name="top_tracks.csv", mime="text/csv")

    with chart_subtabs[2]:
        monthly_leaders = metrics.get_top_artist_and_track_per_month(filtered_df)
        st.dataframe(monthly_leaders, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------------
# TAB 3: TIMELINE
# ----------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Historical Timeline & Trends")

    # Animated Race
    st.markdown("#### 🏁 Monthly Artist Race")
    st.caption("Press Play on the slider to watch the top artists evolve over time.")
    st.plotly_chart(charts.plot_bar_chart_race_monthly(filtered_df, top_k=8), use_container_width=True)

    # YoY Comparison
    yearly_df = metrics.get_yearly_summary(clean_df)
    if len(yearly_df) > 1:
        st.markdown("#### 📅 Year-over-Year Comparison")
        st.plotly_chart(charts.plot_year_over_year(yearly_df), use_container_width=True)
        st.dataframe(yearly_df, use_container_width=True, hide_index=True)

    # Busiest Records
    busiest = metrics.get_busiest_periods(filtered_df)
    if busiest:
        st.markdown("#### ⚡ All-Time Records")
        b1, b2, b3 = st.columns(3)
        b1.info(f"🏆 **Busiest Day**: {busiest['busiest_day']['date']}\n\n**{busiest['busiest_day']['plays']} plays** ({busiest['busiest_day']['hours']} hours)")
        b2.info(f"🏆 **Busiest Week**: {busiest['busiest_week']['week']}\n\n**{busiest['busiest_week']['plays']} plays** ({busiest['busiest_week']['hours']} hours)")
        b3.info(f"🏆 **Busiest Month**: {busiest['busiest_month']['month']}\n\n**{busiest['busiest_month']['plays']} plays** ({busiest['busiest_month']['hours']} hours)")


# ----------------------------------------------------------------------------
# TAB 4: PATTERNS & SESSIONS
# ----------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Listening Habits, Time Distributions & Sessions")

    col_p1, col_p2 = st.columns([1, 1])
    with col_p1:
        hourly_data = metrics.get_hourly_distribution(filtered_df)
        st.plotly_chart(charts.plot_hourly_breakdown(hourly_data), use_container_width=True)

    with col_p2:
        heatmap_matrix = metrics.get_weekday_hour_heatmap_matrix(filtered_df)
        st.plotly_chart(charts.plot_weekday_hour_heatmap(heatmap_matrix), use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🎧 Session Dynamics & Behavioral Stats")
    sess_stats = metrics.get_session_statistics(filtered_df)
    wk_stats = metrics.get_weekday_vs_weekend_summary(filtered_df)

    if sess_stats:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total Sessions", f"{sess_stats['total_sessions']:,}")
        s2.metric("Avg Session Length", f"{sess_stats['avg_session_length_minutes']} min")
        s3.metric("Longest Session", f"{sess_stats['longest_session_minutes']} min")
        s4.metric("Avg Tracks / Session", f"{sess_stats['avg_tracks_per_session']}")

    if wk_stats:
        w1, w2 = st.columns(2)
        w1.info(f"🏢 **Weekdays**: {wk_stats['weekday_total_plays']:,} plays ({wk_stats['weekday_pct']}%) • Avg {wk_stats['weekday_avg_plays_per_day']} plays/day")
        w2.info(f"🏖️ **Weekends**: {wk_stats['weekend_total_plays']:,} plays ({wk_stats['weekend_pct']}%) • Avg {wk_stats['weekend_avg_plays_per_day']} plays/day")

    # Seasonal distribution
    seasonal_df = metrics.get_seasonal_trends(filtered_df)
    if not seasonal_df.empty:
        st.markdown("#### 🍂 Seasonal Distribution")
        st.dataframe(seasonal_df, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------------
# TAB 5: DISCOVERY & REPLAY
# ----------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Music Discovery, Replay Rates & Variety")

    disc_monthly, cum_disc = metrics.get_discovery_trends(filtered_df)
    st.plotly_chart(charts.plot_cumulative_growth(cum_disc), use_container_width=True)

    replay_stats = metrics.get_replay_statistics(filtered_df)
    r1, r2, r3 = st.columns(3)
    r1.metric("Replay Rate", f"{replay_stats.get('repeat_rate_pct', 0)}%", help="% of plays that are repeated tracks")
    r2.metric("Avg Plays / Track", f"{replay_stats.get('avg_plays_per_track', 0)}")
    
    loyalty = metrics.compute_loyalty_and_diversity(filtered_df)
    r3.metric("Artist Diversity Score", f"{loyalty.get('diversity_score_pct', 0)}%", help="Normalized Shannon Entropy (100% = perfectly uniform listening)")

    col_r_left, col_r_right = st.columns(2)
    with col_r_left:
        st.plotly_chart(charts.plot_repeat_tiers_donut(replay_stats.get("tiers_df", pd.DataFrame())), use_container_width=True)

    with col_r_right:
        st.plotly_chart(charts.plot_concentration_curve(loyalty.get("concentration_curve", pd.DataFrame()), loyalty.get("top10_share_pct", 0), loyalty.get("gini_coefficient", 0)), use_container_width=True)

    # Repeat Loops & Obsessions
    st.markdown("---")
    st.markdown("#### 🔁 Repeat Loops & Obsessions")
    loop_count, top_loops = metrics.get_repeat_loops(filtered_df)
    st.write(f"You placed tracks on back-to-back loop **{loop_count:,} times**.")

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.markdown("**Top Consecutive Loop Tracks:**")
        st.dataframe(top_loops, use_container_width=True, hide_index=True)

    daily_obs, weekly_obs = metrics.get_obsession_tracks(filtered_df)
    with col_l2:
        st.markdown("**Top Single-Day Obsessions (Most Plays in 24h):**")
        st.dataframe(daily_obs, use_container_width=True, hide_index=True)

    # Comeback Tracks & Skip Proxy
    st.markdown("---")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown("#### 🌟 Comeback Tracks")
        st.caption("Songs you stopped playing for 6+ months and later returned to.")
        comebacks = metrics.get_comeback_tracks(filtered_df, min_dormant_days=180)
        st.dataframe(comebacks, use_container_width=True, hide_index=True)

    with col_c2:
        st.markdown("#### ⏭️ Heuristic Skip Proxy")
        skip_overall, skip_artists = metrics.compute_skip_proxy(filtered_df)
        st.caption(f"Overall skip rate: **{skip_overall.get('overall_skip_rate_pct', 0)}%** ({skip_overall.get('total_skips', 0):,} tracks listened for <30s)")
        st.dataframe(skip_artists, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------------
# TAB 6: EXPLORER (ARTIST & TRACK DEEP-DIVE)
# ----------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Deep-Dive Explorer")
    explore_type = st.radio("Explore By", ["Artist Deep-Dive", "Track Deep-Dive"], horizontal=True)

    if explore_type == "Artist Deep-Dive":
        all_artists = sorted(filtered_df["primary_artist"].unique())
        selected_artist = st.selectbox("Select Artist", all_artists, index=0)

        art_data = metrics.get_artist_deep_dive(filtered_df, selected_artist)
        if art_data["found"]:
            a1, a2, a3, a4, a5 = st.columns(5)
            a1.metric("Total Plays", f"{art_data['total_plays']:,}")
            a2.metric("Listening Time", f"{art_data['total_hours']} hrs")
            a3.metric("Your Listening Share", f"{art_data['share_plays_pct']}%")
            a4.metric("Unique Tracks", f"{art_data['unique_tracks_count']}")
            a5.metric("Listening Span", f"{art_data['lifespan_days']} days")

            col_ad1, col_ad2 = st.columns([1, 1])
            with col_ad1:
                st.markdown(f"**Top Tracks by {selected_artist}:**")
                st.dataframe(art_data["top_tracks"], use_container_width=True, hide_index=True)

            with col_ad2:
                st.markdown(f"**Plays Over Time:**")
                st.plotly_chart(charts.plot_top_horizontal_bars(
                    art_data["monthly_timeline"].rename(columns={"Plays": "Monthly Plays", "month": "Month"}),
                    x_col="Monthly Plays",
                    y_col="Month",
                    title="Plays by Month",
                    x_label="Plays"
                ), use_container_width=True)

    else:
        all_tracks = sorted(filtered_df["clean_title"].unique())
        selected_track = st.selectbox("Select Track", all_tracks, index=0)

        trk_data = metrics.get_track_deep_dive(filtered_df, selected_track)
        if trk_data["found"]:
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Artist", trk_data["artist"])
            t2.metric("Total Plays", f"{trk_data['total_plays']:,}")
            t3.metric("Listening Time", f"{trk_data['total_hours']} hrs")
            t4.metric("Peak Month", f"{trk_data['peak_month']} ({trk_data['peak_month_plays']} plays)")

            st.caption(f"First played: **{trk_data['first_play']}** • Last played: **{trk_data['last_play']}**")
            st.dataframe(trk_data["monthly_timeline"], use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------------
# TAB 7: WRAPPED CARDS & MILESTONES
# ----------------------------------------------------------------------------
with tabs[6]:
    st.subheader("Your Personalized Wrapped Card")
    wrap_year = st.selectbox("Select Wrapped Year", ["All-Time"] + list(available_years), index=0)
    year_param = int(wrap_year) if wrap_year != "All-Time" else None

    card_data = metrics.get_wrapped_card_data(clean_df, year=year_param)
    card_html = charts.render_wrapped_card_html(card_data)

    st.components.v1.html(card_html, height=540)
    st.download_button(
        label="📥 Download Wrapped Card (HTML)",
        data=card_html,
        file_name=f"YT_Music_Wrapped_{wrap_year}.html",
        mime="text/html"
    )

    st.markdown("---")
    st.markdown("#### 🚩 Play Milestones")
    milestones_df = metrics.get_play_milestones(clean_df)
    st.dataframe(milestones_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 📻 Forgotten Gems (Rediscovery)")
    st.caption("Tracks you loved in previous years (5+ plays) that you haven't played once in the last 12 months.")
    rediscover_df = metrics.get_rediscovery_tracks(clean_df)
    st.dataframe(rediscover_df, use_container_width=True, hide_index=True)
