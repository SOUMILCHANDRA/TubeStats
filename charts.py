"""
charts.py - Plotly interactive charts for YT Music Wrapped Pro.
Features dark themes, hover tooltips, and responsive layouts.
"""
from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# Ferrari Design Tokens & Layout
DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#181818",
    plot_bgcolor="#181818",
    font=dict(family="'FerrariSans', Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", color="#ffffff"),
    margin=dict(l=40, r=40, t=50, b=40),
    hoverlabel=dict(bgcolor="#303030", font_size=13, font_color="#ffffff", bordercolor="#da291c"),
)

PALETTE = ["#da291c", "#ffffff", "#969696", "#d2d2d2", "#666666", "#b01e0a", "#4c98b9", "#f6e500"]
FERRARI_RED = "#da291c"
FERRARI_RED_ACTIVE = "#b01e0a"
FERRARI_INK = "#ffffff"
FERRARI_BODY = "#969696"
FERRARI_HAIRLINE = "#303030"



def plot_top_horizontal_bars(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    x_label: str,
    color_col: Optional[str] = None,
    color_scale: str = "Viridis"
) -> go.Figure:
    """Horizontal bar chart with rank order and custom hover tooltips."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title=title)
        return fig

    # Reverse to have #1 at the top of horizontal chart
    chart_df = df.iloc[::-1].copy()

    fig = px.bar(
        chart_df,
        x=x_col,
        y=y_col,
        orientation="h",
        title=title,
        color=color_col or x_col,
        color_continuous_scale=[[0, "#303030"], [0.5, "#8f1b13"], [1.0, "#da291c"]],
        text=x_col
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate=f"<b>%{{y}}</b><br>{x_label}: %{{x:,.1f}}<extra></extra>",
        marker=dict(line=dict(width=1, color=FERRARI_HAIRLINE))
    )
    fig.update_layout(
        **DARK_LAYOUT,
        xaxis_title=x_label,
        yaxis_title="",
        coloraxis_showscale=False,
        height=max(400, len(chart_df) * 28),
    )
    return fig


def plot_monthly_timeline(monthly_df: pd.DataFrame) -> go.Figure:
    """Dual-axis timeline: Monthly plays (bar) and listening hours (spline line)."""
    fig = go.Figure()
    if monthly_df.empty:
        fig.update_layout(**DARK_LAYOUT, title="Monthly Listening Activity")
        return fig

    fig.add_trace(
        go.Bar(
            x=monthly_df["month"],
            y=monthly_df["Plays"],
            name="Plays",
            marker_color=FERRARI_RED,
            opacity=0.9,
            hovertemplate="<b>%{x}</b><br>Plays: %{y:,}<extra></extra>"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=monthly_df["month"],
            y=monthly_df["Hours"],
            name="Hours",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=FERRARI_INK, width=2.5, shape="spline"),
            marker=dict(size=7, color=FERRARI_INK),
            hovertemplate="<b>%{x}</b><br>Listening Time: %{y:,.1f} hrs<extra></extra>"
        )
    )

    fig.update_layout(
        **DARK_LAYOUT,
        title="Monthly Listening Volume (Plays & Hours)",
        xaxis=dict(title="Month", tickangle=-45, showgrid=True, gridcolor=FERRARI_HAIRLINE),
        yaxis=dict(title="Total Plays", showgrid=True, gridcolor=FERRARI_HAIRLINE),
        yaxis2=dict(title="Listening Hours", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=450,
    )
    return fig


def plot_year_over_year(yearly_df: pd.DataFrame) -> go.Figure:
    """Year-over-year plays and hours with growth annotations."""
    if yearly_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Year-Over-Year Trends")
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=yearly_df["year"].astype(str),
            y=yearly_df["Plays"],
            name="Total Plays",
            marker_color=FERRARI_RED,
            hovertemplate="<b>Year %{x}</b><br>Plays: %{y:,}<extra></extra>"
        )
    )
    fig.add_trace(
        go.Scatter(
            x=yearly_df["year"].astype(str),
            y=yearly_df["Hours"],
            name="Total Hours",
            yaxis="y2",
            mode="lines+markers+text",
            line=dict(color=FERRARI_INK, width=2.5),
            marker=dict(size=9, color=FERRARI_INK),
            text=[f"{h:.0f}h" for h in yearly_df["Hours"]],
            textposition="top center",
            hovertemplate="<b>Year %{x}</b><br>Hours: %{y:,.1f}h<extra></extra>"
        )
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title="Year-Over-Year Comparison",
        xaxis=dict(title="Year", showgrid=True, gridcolor=FERRARI_HAIRLINE),
        yaxis=dict(title="Plays", showgrid=True, gridcolor=FERRARI_HAIRLINE),
        yaxis2=dict(title="Listening Hours", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
    )
    return fig


def plot_calendar_heatmap(daily_df: pd.DataFrame) -> go.Figure:
    """
    Ferrari Telemetry calendar heatmap displaying daily listening volume.
    X-axis: Week of Year, Y-axis: Day of Week (Mon-Sun).
    """
    if daily_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Daily Listening Heatmap")
        return fig

    temp = daily_df.copy()
    temp["dt"] = pd.to_datetime(temp["date"])
    temp["year"] = temp["dt"].dt.year
    temp["week"] = temp["dt"].dt.isocalendar().week
    temp["day_of_week"] = temp["dt"].dt.dayofweek  # 0=Monday, 6=Sunday
    temp["day_name"] = temp["dt"].dt.day_name()

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Pivot: rows = day_of_week (0-6), columns = (year, week)
    pivot = temp.pivot_table(
        index="day_of_week",
        columns=["year", "week"],
        values="plays",
        aggfunc="sum",
        fill_value=0
    )

    # Format column labels
    col_labels = [f"W{c[1]} '{str(c[0])[-2:]}" for c in pivot.columns]

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=col_labels,
            y=day_names,
            colorscale=[
                [0.0, "#1f1f1f"],
                [0.2, "#38120f"],
                [0.5, "#6b1711"],
                [0.8, "#b01e0a"],
                [1.0, "#da291c"]
            ],
            hoverongaps=False,
            hovertemplate="Week: %{x}<br>Day: %{y}<br>Plays: %{z:,}<extra></extra>"
        )
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title="Activity Calendar (Daily Telemetry Heatmap)",
        xaxis=dict(title="", tickangle=-45, showgrid=False),
        yaxis=dict(title="", autorange="reversed", showgrid=False),
        height=320,
    )
    return fig


def plot_hourly_breakdown(hourly_df: pd.DataFrame) -> go.Figure:
    """24-hour distribution bar chart."""
    if hourly_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Listening by Hour of Day")
        return fig

    fig = px.bar(
        hourly_df,
        x="Label",
        y="Plays",
        title="Listening by Hour of Day (24-Hour Cycle)",
        color="Plays",
        color_continuous_scale=[[0, "#303030"], [0.5, "#8f1b13"], [1.0, "#da291c"]]
    )
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Plays: %{y:,}<extra></extra>",
        marker=dict(line=dict(width=1, color=FERRARI_HAIRLINE))
    )
    fig.update_layout(
        **DARK_LAYOUT,
        xaxis_title="Time of Day",
        yaxis_title="Total Plays",
        coloraxis_showscale=False,
        height=380,
    )
    return fig


def plot_weekday_hour_heatmap(matrix_df: pd.DataFrame) -> go.Figure:
    """7 Days x 24 Hours listening intensity heatmap."""
    if matrix_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Day-of-Week x Hour Heatmap")
        return fig

    hours_labels = [f"{h:02d}:00" for h in matrix_df.columns]
    days_labels = matrix_df.index.tolist()

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix_df.values,
            x=hours_labels,
            y=days_labels,
            colorscale=[
                [0.0, "#181818"],
                [0.25, "#303030"],
                [0.55, "#7a1710"],
                [0.8, "#b01e0a"],
                [1.0, "#da291c"]
            ],
            hovertemplate="<b>%{y} at %{x}</b><br>Plays: %{z:,}<extra></extra>"
        )
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title="Listening Intensity (Day of Week vs Hour)",
        xaxis=dict(title="Hour of Day", tickangle=-45, showgrid=False),
        yaxis=dict(title="", autorange="reversed", showgrid=False),
        height=360,
    )
    return fig


def plot_time_bucket_donut(bucket_df: pd.DataFrame, listener_type: str) -> go.Figure:
    """Donut chart for Time-of-Day buckets with listener archetype annotation."""
    if bucket_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Time-of-Day Buckets")
        return fig

    fig = go.Figure(
        data=[
            go.Pie(
                labels=bucket_df["Bucket"],
                values=bucket_df["Plays"],
                hole=0.6,
                marker=dict(colors=["#da291c", "#b01e0a", "#ffffff", "#666666"]),
                hovertemplate="<b>%{label}</b><br>Plays: %{value:,} (%{percent})<extra></extra>",
                textinfo="label+percent"
            )
        ]
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title=f"Listener Persona: <b>{listener_type}</b>",
        annotations=[
            dict(
                text="TIME OF DAY",
                x=0.5,
                y=0.5,
                font_size=12,
                showarrow=False,
                font=dict(color="#969696", family="'FerrariSans', Inter, sans-serif")
            )
        ],
        height=380,
        showlegend=False
    )
    return fig


def plot_cumulative_growth(growth_df: pd.DataFrame) -> go.Figure:
    """Cumulative growth curve of unique artists and unique tracks discovered."""
    if growth_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Discovery Growth Over Time")
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=growth_df["date"],
            y=growth_df["Cumulative_Tracks"],
            name="Unique Tracks",
            line=dict(color=FERRARI_INK, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(255, 255, 255, 0.04)",
            hovertemplate="<b>%{x}</b><br>Tracks: %{y:,}<extra></extra>"
        )
    )
    fig.add_trace(
        go.Scatter(
            x=growth_df["date"],
            y=growth_df["Cumulative_Artists"],
            name="Unique Artists",
            line=dict(color=FERRARI_RED, width=2.5),
            hovertemplate="<b>%{x}</b><br>Artists: %{y:,}<extra></extra>"
        )
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title="Cumulative Music Discovery Over Time",
        xaxis=dict(title="Date", showgrid=True, gridcolor=FERRARI_HAIRLINE),
        yaxis=dict(title="Cumulative Count", showgrid=True, gridcolor=FERRARI_HAIRLINE),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
    )
    return fig


def plot_repeat_tiers_donut(tiers_df: pd.DataFrame) -> go.Figure:
    """Donut chart of track replay frequency tiers."""
    if tiers_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Replay Tiers")
        return fig

    fig = go.Figure(
        data=[
            go.Pie(
                labels=tiers_df["Tier"],
                values=tiers_df["Tracks"],
                hole=0.6,
                marker=dict(colors=["#303030", "#666666", "#d2d2d2", "#da291c"]),
                hovertemplate="<b>%{label}</b><br>Tracks: %{value:,} (%{percent})<extra></extra>",
                textinfo="label+percent"
            )
        ]
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title="Track Replay Distribution (One-off vs Repeat Plays)",
        height=380,
        showlegend=False
    )
    return fig


def plot_concentration_curve(curve_df: pd.DataFrame, top10_share: float, gini: float) -> go.Figure:
    """Concentration curve (Lorenz curve) showing artist loyalty vs variety."""
    if curve_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Artist Concentration Curve")
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=curve_df["Artist_Rank"],
            y=curve_df["Cumulative_Share_%"],
            mode="lines+markers",
            name="Your Listening",
            line=dict(color=FERRARI_RED, width=2.5),
            marker=dict(color=FERRARI_RED, size=6),
            hovertemplate="Top %{x} Artists: %{y:.1f}% of total plays<extra></extra>"
        )
    )
    # Perfect equality reference line
    fig.add_shape(
        type="line",
        x0=1,
        y0=0,
        x1=len(curve_df),
        y1=100,
        line=dict(color="#666666", dash="dash")
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title=f"Artist Concentration Curve (Top 10 Share: <b>{top10_share}%</b> | Gini: <b>{gini}</b>)",
        xaxis=dict(title="Top N Artists", showgrid=True, gridcolor=FERRARI_HAIRLINE),
        yaxis=dict(title="Cumulative Listening Share (%)", range=[0, 105], showgrid=True, gridcolor=FERRARI_HAIRLINE),
        height=380,
    )
    return fig

    # Perfect equality reference line
    fig.add_shape(
        type="line",
        x0=1,
        y0=0,
        x1=len(curve_df),
        y1=100,
        line=dict(color="rgba(255, 255, 255, 0.2)", dash="dash")
    )
    fig.update_layout(
        **DARK_LAYOUT,
        title=f"Artist Concentration Curve (Top 10 Share: <b>{top10_share}%</b> | Gini: <b>{gini}</b>)",
        xaxis=dict(title="Top N Artists", showgrid=True, gridcolor="#21262D"),
        yaxis=dict(title="Cumulative Listening Share (%)", range=[0, 105], showgrid=True, gridcolor="#21262D"),
        height=380,
    )
    return fig


def plot_bar_chart_race_monthly(df: pd.DataFrame, top_k: int = 8) -> go.Figure:
    """
    Monthly animated race showing the evolution of top artists over time.
    """
    if df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT, title="Monthly Artist Race")
        return fig

    # Cumulative plays per artist up to each month
    months = sorted(df["month"].unique())
    if len(months) < 2:
        # Not enough months for animation, show standard top artists
        top_art = df["primary_artist"].value_counts().head(top_k).reset_index()
        top_art.columns = ["Artist", "Plays"]
        return plot_top_horizontal_bars(top_art, "Plays", "Artist", "Top Artists", "Plays")

    frames_data = []
    all_artists = df["primary_artist"].unique()

    # Pre-build monthly counts
    monthly_cross = df.groupby(["month", "primary_artist"]).size().unstack(fill_value=0)
    monthly_cum = monthly_cross.cumsum(axis=0)

    for m in months:
        row = monthly_cum.loc[m].sort_values(ascending=False).head(top_k)
        for rank, (art, plays) in enumerate(row.items(), start=1):
            frames_data.append({
                "month": m,
                "artist": art,
                "cum_plays": int(plays),
                "rank": rank
            })

    race_df = pd.DataFrame(frames_data)

    fig = px.bar(
        race_df,
        x="cum_plays",
        y="artist",
        animation_frame="month",
        orientation="h",
        range_x=[0, race_df["cum_plays"].max() * 1.15],
        title=f"Monthly Artist Race (Cumulative Top {top_k})",
        color="artist",
        text="cum_plays"
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Cumulative Plays: %{x:,}<extra></extra>"
    )
    fig.update_layout(
        **DARK_LAYOUT,
        xaxis_title="Cumulative Plays",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        height=480,
    )
    return fig


def render_wrapped_card_html(card_data: Dict[str, Any]) -> str:
    """
    Generates a high-precision, editorial Ferrari-aesthetic Wrapped card in HTML/CSS.
    Uses near-black canvas, Rosso Corsa accents, sharp 0px corners, and telemetry typography.
    """
    if not card_data or not card_data.get("total_plays"):
        return "<div style='color: #ffffff; background: #181818; padding: 24px; border: 1px solid #303030; font-family: sans-serif;'>No telemetry data available for Wrapped card.</div>"

    artists_html = "".join([
        f"<li style='display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #303030;'>"
        f"<span><span style='color: #da291c; font-weight: 700; font-size: 14px; margin-right: 8px;'>P{i+1}</span>"
        f"<span style='color: #ffffff; font-weight: 500; font-size: 14px;'>{a['name']}</span></span>"
        f"<span style='color: #969696; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>{a['plays']:,} plays</span></li>"
        for i, a in enumerate(card_data.get("top_artists", []))
    ])

    tracks_html = "".join([
        f"<li style='display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #303030;'>"
        f"<span style='overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 250px;'>"
        f"<span style='color: #da291c; font-weight: 700; font-size: 14px; margin-right: 8px;'>P{i+1}</span>"
        f"<span style='color: #ffffff; font-weight: 500; font-size: 14px;'>{t['title']}</span> "
        f"<span style='font-size: 11px; color: #666666;'>{t['artist']}</span></span>"
        f"<span style='color: #ffffff; font-weight: 700; font-size: 13px;'>{t['plays']:,}</span></li>"
        for i, t in enumerate(card_data.get("top_tracks", []))
    ])

    busiest = card_data.get("busiest_day", {})
    busiest_str = f"{busiest.get('date', 'N/A')} ({busiest.get('plays', 0)} plays • {busiest.get('hours', 0)} hrs)"

    html = f"""
    <div id="wrapped-card" style="
        max-width: 620px;
        margin: 16px auto;
        background: #181818;
        border: 1px solid #303030;
        border-radius: 0px;
        padding: 32px;
        color: #ffffff;
        font-family: 'FerrariSans', Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        box-sizing: border-box;
    ">
        <!-- Top Editorial Livery Band -->
        <div style="height: 3px; background: #da291c; margin: -32px -32px 24px -32px;"></div>

        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; border-bottom: 1px solid #303030; padding-bottom: 20px;">
            <div>
                <span style="background: #303030; color: #ffffff; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 1.1px; text-transform: uppercase;">
                    WRAPPED TELEMETRY
                </span>
                <h1 style="margin: 10px 0 0 0; font-size: 32px; font-weight: 500; letter-spacing: -0.5px; color: #ffffff; text-transform: uppercase;">
                    {card_data['year']} REWIND
                </h1>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 11px; text-transform: uppercase; color: #969696; letter-spacing: 1.1px; font-weight: 600;">Listening Time</div>
                <div style="font-size: 38px; font-weight: 700; color: #da291c; line-height: 1; margin-top: 4px; letter-spacing: -1.6px;">
                    {card_data['total_hours']:,.1f} <span style="font-size: 14px; font-weight: 500; color: #ffffff; letter-spacing: 0;">HRS</span>
                </div>
            </div>
        </div>

        <!-- Telemetry Spec Cells Grid -->
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px;">
            <div style="background: #202020; border: 1px solid #303030; padding: 16px; border-radius: 0px;">
                <div style="font-size: 11px; text-transform: uppercase; color: #969696; letter-spacing: 1.1px; font-weight: 600; margin-bottom: 6px;">Total Plays</div>
                <div style="font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.8px;">{card_data['total_plays']:,}</div>
            </div>
            <div style="background: #202020; border: 1px solid #303030; padding: 16px; border-radius: 0px;">
                <div style="font-size: 11px; text-transform: uppercase; color: #969696; letter-spacing: 1.1px; font-weight: 600; margin-bottom: 6px;">Artists</div>
                <div style="font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.8px;">{card_data['unique_artists']:,}</div>
            </div>
            <div style="background: #202020; border: 1px solid #303030; padding: 16px; border-radius: 0px;">
                <div style="font-size: 11px; text-transform: uppercase; color: #969696; letter-spacing: 1.1px; font-weight: 600; margin-bottom: 6px;">Tracks</div>
                <div style="font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.8px;">{card_data['unique_tracks']:,}</div>
            </div>
        </div>

        <!-- Top Artists & Songs Editorial Columns -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 28px;">
            <div style="background: #1c1c1c; border: 1px solid #303030; padding: 18px; border-radius: 0px;">
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.4px; color: #ffffff; margin-bottom: 12px; border-bottom: 1px solid #303030; padding-bottom: 6px;">
                    TOP ARTISTS
                </div>
                <ul style="list-style: none; padding: 0; margin: 0;">
                    {artists_html}
                </ul>
            </div>
            <div style="background: #1c1c1c; border: 1px solid #303030; padding: 18px; border-radius: 0px;">
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.4px; color: #ffffff; margin-bottom: 12px; border-bottom: 1px solid #303030; padding-bottom: 6px;">
                    TOP TRACKS
                </div>
                <ul style="list-style: none; padding: 0; margin: 0;">
                    {tracks_html}
                </ul>
            </div>
        </div>

        <!-- Footer Archetype Callout -->
        <div style="background: #202020; border: 1px solid #303030; padding: 14px 18px; border-radius: 0px; display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
            <div>
                <span style="color: #969696; text-transform: uppercase; font-size: 11px; letter-spacing: 1.1px; font-weight: 600;">Archetype:</span>
                <span style="font-weight: 700; color: #ffffff; margin-left: 8px;">{card_data['listener_type']}</span>
            </div>
            <div style="color: #969696; font-size: 12px;">
                Peak Session: <span style="color: #ffffff; font-weight: 600;">{busiest_str}</span>
            </div>
        </div>
    </div>
    """
    return html
