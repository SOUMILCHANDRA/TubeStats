"""
parser.py - Loads and merges Google Takeout watch-history.json files.
Handles single or multiple files, supports fast local caching with SQLite or Parquet,
and compiles an initial ingestion quality report.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterable, List, Optional, Tuple, Union
import pandas as pd


@dataclass
class IngestionReport:
    """Detailed summary of raw data ingestion and initial filtering."""
    total_files: int = 0
    total_raw_records: int = 0
    dropped_ads: int = 0
    dropped_non_ytmusic: int = 0
    dropped_duplicates: int = 0
    unknown_artist_count: int = 0
    url_only_title_count: int = 0
    retained_records: int = 0
    included_regular_youtube: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


CACHE_DIR = Path(".cache")


def compute_file_hash(content_bytes: bytes) -> str:
    """Compute an MD5 hash of raw file content to identify cached runs."""
    return hashlib.md5(content_bytes).hexdigest()


def load_raw_entries(source: Union[str, Path, BinaryIO, bytes, dict, list]) -> List[Dict[str, Any]]:
    """
    Load raw JSON entries from a file path, BytesIO/StringIO, raw bytes, or pre-loaded structure.
    """
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {source}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif hasattr(source, "read"):
        content = source.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        data = json.loads(content)
    elif isinstance(source, bytes):
        data = json.loads(source.decode("utf-8", errors="replace"))
    elif isinstance(source, list):
        data = source
    elif isinstance(source, dict):
        data = [source]
    else:
        raise ValueError(f"Unsupported source type: {type(source)}")

    if not isinstance(data, list):
        raise ValueError("Invalid watch-history.json format: root must be a JSON array of objects.")
    return data


def parse_watch_histories(
    sources: Union[Any, List[Any]],
    include_regular_youtube: bool = False,
    cache_path: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, IngestionReport]:
    """
    Parse one or more watch-history.json sources into a structured pandas DataFrame.
    Applies initial row-level triage (dropping Google Ads, filtering non-music if requested),
    tracks data quality statistics, and prepares the dataset for cleaning.
    """
    if not isinstance(sources, list):
        sources = [sources]

    report = IngestionReport(
        total_files=len(sources),
        included_regular_youtube=include_regular_youtube,
    )

    all_raw_entries: List[Dict[str, Any]] = []
    for src in sources:
        entries = load_raw_entries(src)
        all_raw_entries.extend(entries)

    report.total_raw_records = len(all_raw_entries)
    if not all_raw_entries:
        return pd.DataFrame(), report

    # Fast conversion to intermediate dataframe
    raw_df = pd.DataFrame(all_raw_entries)

    # 1. Detect and count Google Ads
    # Ad entries often have 'details': [{'name': 'From Google Ads'}] or 'details': 'From Google Ads'
    def is_ad_entry(details_val: Any) -> bool:
        if details_val is None:
            return False
        if isinstance(details_val, str) and "From Google Ads" in details_val:
            return True
        if isinstance(details_val, list):
            for item in details_val:
                if isinstance(item, dict) and "From Google Ads" in item.get("name", ""):
                    return True
                if isinstance(item, str) and "From Google Ads" in item:
                    return True
        return False

    if "details" in raw_df.columns:
        ad_mask = raw_df["details"].apply(is_ad_entry)
        report.dropped_ads = int(ad_mask.sum())
        df = raw_df[~ad_mask].copy()
    else:
        df = raw_df.copy()

    # 2. Check header distribution
    if "header" in df.columns:
        header_counts = df["header"].value_counts().to_dict()
        report.details["headers_found"] = header_counts
        if not include_regular_youtube:
            music_mask = df["header"] == "YouTube Music"
            report.dropped_non_ytmusic = int((~music_mask).sum())
            df = df[music_mask].copy()
        else:
            report.dropped_non_ytmusic = 0
    else:
        report.dropped_non_ytmusic = 0

    # 3. Detect missing subtitles (unknown artist)
    if "subtitles" in df.columns:
        def has_valid_subtitle(sub_val: Any) -> bool:
            if not isinstance(sub_val, list) or len(sub_val) == 0:
                return False
            first = sub_val[0]
            if isinstance(first, dict) and first.get("name"):
                return True
            return False

        unknown_mask = ~df["subtitles"].apply(has_valid_subtitle)
        report.unknown_artist_count = int(unknown_mask.sum())
    else:
        df["subtitles"] = None
        report.unknown_artist_count = len(df)

    # 4. Detect URL-only / removed titles
    if "title" in df.columns:
        def is_url_or_empty_title(title_val: Any) -> bool:
            if not isinstance(title_val, str) or not title_val.strip():
                return True
            cleaned = title_val.strip()
            if cleaned.startswith("Watched "):
                cleaned = cleaned[8:].strip()
            return cleaned.startswith("http://") or cleaned.startswith("https://")

        url_title_mask = df["title"].apply(is_url_or_empty_title)
        report.url_only_title_count = int(url_title_mask.sum())

    report.retained_records = len(df)
    return df, report
