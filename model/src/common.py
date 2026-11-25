"""Shared, dependency-free utilities for the KuaiRec data pipeline."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TextIO

INTERACTION_COLUMNS = (
    "user_id",
    "video_id",
    "play_duration",
    "video_duration",
    "time",
    "date",
    "timestamp",
    "watch_ratio",
)

OUTPUT_COLUMNS = (
    "user_id",
    "video_id",
    "timestamp",
    "watch_ratio",
    "is_relevant",
    "play_duration",
    "video_duration",
)


class DatasetError(ValueError):
    """Raised when an input dataset cannot be interpreted safely."""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def interaction_path(data_dir: Path, filename: str) -> Path:
    candidates = (data_dir / filename, data_dir / "data" / filename)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    expected = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Could not find {filename}; checked {expected}")


def open_interactions(path: Path) -> tuple[TextIO, csv.DictReader[str]]:
    source = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        source.close()
        raise DatasetError(f"{path} has no CSV header")
    missing_columns = sorted(set(INTERACTION_COLUMNS) - set(reader.fieldnames))
    if missing_columns:
        source.close()
        raise DatasetError(
            f"{path} is missing required columns: {', '.join(missing_columns)}"
        )
    return source, reader


def parse_interaction(row: dict[str, str | None]) -> dict[str, int | float]:
    """Parse required interaction values and canonicalize integer IDs."""
    user_value = row.get("user_id")
    video_value = row.get("video_id")
    timestamp_value = row.get("timestamp")
    ratio_value = row.get("watch_ratio")
    if any(value is None or not value.strip() for value in (
        user_value,
        video_value,
        timestamp_value,
        ratio_value,
    )):
        raise DatasetError("missing user_id, video_id, timestamp, or watch_ratio")
    try:
        user_id = int(user_value)  # type: ignore[arg-type]
        video_id = int(video_value)  # type: ignore[arg-type]
        timestamp = float(timestamp_value)  # type: ignore[arg-type]
        watch_ratio = float(ratio_value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise DatasetError("invalid ID, timestamp, or watch_ratio") from error
    if user_id < 0 or video_id < 0:
        raise DatasetError("IDs must be non-negative")
    if not math.isfinite(timestamp) or not math.isfinite(watch_ratio):
        raise DatasetError("timestamp and watch_ratio must be finite")

    play_duration = _optional_nonnegative_int(row.get("play_duration"))
    video_duration = _optional_nonnegative_int(row.get("video_duration"))
    return {
        "user_id": user_id,
        "video_id": video_id,
        "timestamp": timestamp,
        "watch_ratio": watch_ratio,
        "play_duration": play_duration,
        "video_duration": video_duration,
    }


def _optional_nonnegative_int(value: str | None) -> int:
    if value is None or not value.strip():
        return -1
    parsed = int(value)
    if parsed < 0:
        raise DatasetError("duration values must be non-negative")
    return parsed


def format_timestamp(value: float) -> str:
    return format(value, ".15g")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
