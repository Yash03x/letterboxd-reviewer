from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class LoadedProfileData:
    username: str
    profile_info: Dict
    ratings: pd.DataFrame
    reviews: pd.DataFrame
    watched: pd.DataFrame
    diary: pd.DataFrame
    watchlist: pd.DataFrame
    comments: pd.DataFrame
    lists: List[pd.DataFrame]
    likes: pd.DataFrame
    all_films: pd.DataFrame
    avg_rating: float
    total_reviews: int
    join_date: Optional[date]


def _safe_read_csv(path: str, label: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path)
        print(f"Loaded {label}: {len(frame)} entries")
        return frame
    except Exception as exc:
        print(f"Failed to load {label}: {exc}")
        return pd.DataFrame()


def _parse_join_date(profile_info: Dict) -> Optional[date]:
    raw_join_date = profile_info.get("Date Joined")
    if not raw_join_date:
        return None

    parsed = pd.to_datetime(raw_join_date, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def load_profile_data(profile_path: str, username: str) -> LoadedProfileData:
    """
    Lightweight profile loader used by uploads and scrape workers.
    Keeps the runtime path focused on CSV ingestion only.
    """
    profile_csv = os.path.join(profile_path, "profile.csv")
    if os.path.exists(profile_csv):
        profile_df = _safe_read_csv(profile_csv, "profile.csv")
        profile_info = profile_df.iloc[0].to_dict() if not profile_df.empty else {}
    else:
        profile_info = {}

    files_to_load = ["ratings", "reviews", "watched", "diary", "watchlist", "comments", "likes"]
    loaded: Dict[str, pd.DataFrame] = {}
    for name in files_to_load:
        file_path = os.path.join(profile_path, f"{name}.csv")
        loaded[name] = _safe_read_csv(file_path, f"{name}.csv") if os.path.exists(file_path) else pd.DataFrame()

    all_films = pd.DataFrame()
    for candidate in ["films.csv", "all_films.csv", "films_comprehensive.csv"]:
        candidate_path = os.path.join(profile_path, candidate)
        if not os.path.exists(candidate_path):
            continue
        all_films = _safe_read_csv(candidate_path, candidate)
        if not all_films.empty:
            break

    lists: List[pd.DataFrame] = []
    lists_dir = os.path.join(profile_path, "lists")
    if os.path.isdir(lists_dir):
        for entry in os.listdir(lists_dir):
            if not entry.endswith(".csv"):
                continue
            list_path = os.path.join(lists_dir, entry)
            list_df = _safe_read_csv(list_path, f"lists/{entry}")
            if not list_df.empty:
                list_df["list_name"] = entry.replace(".csv", "")
                lists.append(list_df)

    ratings = loaded.get("ratings", pd.DataFrame())
    reviews = loaded.get("reviews", pd.DataFrame())

    avg_rating = 0.0
    if not ratings.empty and "Rating" in ratings.columns:
        numeric_ratings = pd.to_numeric(ratings["Rating"], errors="coerce").dropna()
        if not numeric_ratings.empty:
            candidate_avg = float(numeric_ratings.mean())
            if math.isfinite(candidate_avg):
                avg_rating = candidate_avg

    return LoadedProfileData(
        username=username,
        profile_info=profile_info,
        ratings=ratings,
        reviews=reviews,
        watched=loaded.get("watched", pd.DataFrame()),
        diary=loaded.get("diary", pd.DataFrame()),
        watchlist=loaded.get("watchlist", pd.DataFrame()),
        comments=loaded.get("comments", pd.DataFrame()),
        lists=lists,
        likes=loaded.get("likes", pd.DataFrame()),
        all_films=all_films,
        avg_rating=avg_rating,
        total_reviews=len(reviews),
        join_date=_parse_join_date(profile_info),
    )
