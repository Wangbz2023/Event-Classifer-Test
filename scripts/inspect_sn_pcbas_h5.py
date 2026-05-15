"""Inspect extracted SN-PCBAS-2026 tactical HDF5 files.

This script is meant for files such as:
data/pcbas2026/extracted/VAL/val_tactical_data.h5

It reports validated structure information, per-sequence summary statistics,
sample event rows, and can export the HDF5 content to readable JSON, JSONL,
or CSV files.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np


FRAME = 0
PLAYER_ID = 1
LEFT_TO_RIGHT = 2
SHIRT_NUMBER = 3
ROLE_ID = 4
X_POS = 5
Y_POS = 6
X_SPEED = 7
Y_SPEED = 8
ROI_X = 9
ROI_Y = 10
ROI_WIDTH = 11
ROI_HEIGHT = 12
CLS = 13

COLUMN_NAMES = [
    "frame",
    "player_id",
    "left_to_right",
    "shirt_number",
    "role_id",
    "x_pos",
    "y_pos",
    "x_speed",
    "y_speed",
    "roi_x",
    "roi_y",
    "roi_width",
    "roi_height",
    "cls",
]

ROLE_NAMES = {
    1: "Goalkeeper",
    2: "Left Back",
    3: "Left Central Back",
    4: "Mid Central Back",
    5: "Right Central Back",
    6: "Left Midfielder",
    7: "Right Midfielder",
    8: "Defensive Midfielder",
    9: "Attacking Midfielder",
    10: "Left Winger",
    11: "Right Winger",
    12: "Central Forward",
    13: "Right Back",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_h5_path() -> Path:
    return repo_root() / "data" / "pcbas2026" / "extracted" / "VAL" / "val_tactical_data.h5"


def default_processed_root() -> Path:
    return repo_root() / "data" / "pcbas2026" / "processed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect an extracted SN-PCBAS-2026 tactical HDF5 file."
    )
    parser.add_argument(
        "--h5-path",
        type=Path,
        default=default_h5_path(),
        help="Path to a tactical HDF5 file. Defaults to data/pcbas2026/extracted/VAL/val_tactical_data.h5.",
    )
    parser.add_argument(
        "--sequence",
        default="",
        help="Optional sequence key such as game_18_H1. Defaults to all sequences.",
    )
    parser.add_argument(
        "--sample-event-limit",
        type=int,
        default=10,
        help="How many event rows to print for the selected sequence.",
    )
    parser.add_argument(
        "--sample-row-limit",
        type=int,
        default=3,
        help="How many raw rows to print for the selected sequence.",
    )
    parser.add_argument(
        "--export-format",
        choices=["json", "jsonl", "csv"],
        default="",
        help="Optional export format for readable output.",
    )
    parser.add_argument(
        "--export-scope",
        choices=["events", "rows"],
        default="events",
        help=(
            "Export only event rows (cls > 0) or all rows. Defaults to events "
            "to avoid generating very large files by accident."
        ),
    )
    parser.add_argument(
        "--export-limit",
        type=int,
        default=0,
        help="Maximum number of rows to export. 0 means no limit.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional export path. Defaults to data/pcbas2026/processed/.",
    )
    return parser.parse_args()


def as_float(value: float) -> float | None:
    if np.isnan(value):
        return None
    return float(value)


def summarize_sequence(name: str, data: np.ndarray) -> dict[str, Any]:
    frames = data[:, FRAME].astype(int)
    event_mask = data[:, CLS] > 0
    event_rows = data[event_mask]
    bbox_mask = ~np.isnan(data[:, ROI_X])
    event_bbox_mask = ~np.isnan(event_rows[:, ROI_X]) if len(event_rows) else np.array([])
    unique_roles = sorted(int(x) for x in np.unique(data[:, ROLE_ID]) if not np.isnan(x))

    return {
        "name": name,
        "shape": list(data.shape),
        "dtype": str(data.dtype),
        "frame_min": int(frames.min()),
        "frame_max": int(frames.max()),
        "unique_frames": int(len(np.unique(frames))),
        "rows_per_frame_avg": float(data.shape[0] / len(np.unique(frames))),
        "unique_players": int(len(np.unique(data[:, PLAYER_ID]))),
        "unique_jerseys": int(len(np.unique(data[:, SHIRT_NUMBER]))),
        "unique_roles": unique_roles,
        "role_names_present": {str(role): ROLE_NAMES.get(role, "unknown") for role in unique_roles},
        "all_rows_bbox_ratio": float(bbox_mask.mean()),
        "event_rows": int(event_mask.sum()),
        "event_bbox_ratio": float(event_bbox_mask.mean()) if len(event_bbox_mask) else None,
        "class_values": sorted(int(x) for x in np.unique(data[:, CLS]) if not np.isnan(x)),
    }


def sample_raw_rows(data: np.ndarray, limit: int) -> list[list[float | None]]:
    rows: list[list[float | None]] = []
    for row in data[: max(limit, 0)]:
        rows.append([as_float(value) for value in row])
    return rows


def sample_event_rows(sequence_name: str, data: np.ndarray, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in data[data[:, CLS] > 0][: max(limit, 0)]:
        rows.append(row_to_record(sequence_name, row))
    return rows


def team_side(left_to_right: int) -> str:
    return "right" if left_to_right == 1 else "left"


def row_to_record(sequence: str, row: np.ndarray) -> dict[str, Any]:
    left_to_right = int(row[LEFT_TO_RIGHT])
    role_id = int(row[ROLE_ID])
    cls_id = int(row[CLS])
    record = {
        "sequence": sequence,
        "frame": int(row[FRAME]),
        "player_id": int(row[PLAYER_ID]),
        "left_to_right": left_to_right,
        "team_side": team_side(left_to_right),
        "shirt_number": int(row[SHIRT_NUMBER]),
        "role_id": role_id,
        "role_name": ROLE_NAMES.get(role_id, "unknown"),
        "x_pos": float(row[X_POS]),
        "y_pos": float(row[Y_POS]),
        "x_speed": float(row[X_SPEED]),
        "y_speed": float(row[Y_SPEED]),
        "roi_x": as_float(row[ROI_X]),
        "roi_y": as_float(row[ROI_Y]),
        "roi_width": as_float(row[ROI_WIDTH]),
        "roi_height": as_float(row[ROI_HEIGHT]),
        "cls": cls_id,
        "is_event": cls_id > 0,
    }
    return record


def iter_records(
    sequence_name: str,
    data: np.ndarray,
    scope: str,
    export_limit: int,
) -> list[dict[str, Any]]:
    if scope == "events":
        selected = data[data[:, CLS] > 0]
    else:
        selected = data

    if export_limit > 0:
        selected = selected[:export_limit]

    return [row_to_record(sequence_name, row) for row in selected]


def default_output_path(
    h5_path: Path,
    sequence: str,
    export_scope: str,
    export_format: str,
) -> Path:
    sequence_suffix = f"_{sequence}" if sequence else "_all_sequences"
    return default_processed_root() / f"{h5_path.stem}{sequence_suffix}_{export_scope}.{export_format}"


def write_json(path: Path, rows: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    payload = {"metadata": metadata, "rows": rows}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "sequence",
                    "frame",
                    "player_id",
                    "left_to_right",
                    "team_side",
                    "shirt_number",
                    "role_id",
                    "role_name",
                    "x_pos",
                    "y_pos",
                    "x_speed",
                    "y_speed",
                    "roi_x",
                    "roi_y",
                    "roi_width",
                    "roi_height",
                    "cls",
                    "is_event",
                ]
            )
        return

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_rows(
    output_path: Path,
    export_format: str,
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if export_format == "json":
        write_json(output_path, rows, metadata)
        return
    if export_format == "jsonl":
        write_jsonl(output_path, rows)
        return
    if export_format == "csv":
        write_csv(output_path, rows)
        return
    raise ValueError(f"Unsupported export format: {export_format}")


def main() -> int:
    args = parse_args()
    if not args.h5_path.exists():
        raise SystemExit(f"HDF5 file not found: {args.h5_path}")

    print(f"HDF5 path: {args.h5_path}")
    print(f"Size bytes: {args.h5_path.stat().st_size}")
    print(f"Column order: {COLUMN_NAMES}")

    with h5py.File(args.h5_path, "r") as handle:
        keys = list(handle.keys())
        print(f"Sequences: {keys}")

        selected = keys if not args.sequence else [args.sequence]
        missing = [name for name in selected if name not in handle]
        if missing:
            raise SystemExit(f"Sequence not found: {missing[0]}")

        summaries: list[dict[str, Any]] = []
        total_event_rows = 0
        total_event_bbox_rows = 0
        total_rows = 0

        for name in selected:
            data = handle[name][:]
            if data.ndim != 2 or data.shape[1] != len(COLUMN_NAMES):
                raise SystemExit(
                    f"Unexpected dataset shape for {name}: {data.shape}. "
                    "Expected (N, 14)."
                )

            summaries.append(
                {
                    "summary": summarize_sequence(name, data),
                    "sample_raw_rows": sample_raw_rows(data, args.sample_row_limit),
                    "sample_event_rows": sample_event_rows(
                        name, data, args.sample_event_limit
                    ),
                }
            )

            event_mask = data[:, CLS] > 0
            event_rows = data[event_mask]
            total_event_rows += int(event_mask.sum())
            total_event_bbox_rows += int(np.sum(~np.isnan(event_rows[:, ROI_X])))
            total_rows += int(data.shape[0])

        payload = {
            "h5_path": str(args.h5_path),
            "root_keys": keys,
            "column_order": COLUMN_NAMES,
            "selected_sequence_count": len(selected),
            "total_rows_selected": total_rows,
            "total_event_rows_selected": total_event_rows,
            "total_event_bbox_ratio_selected": (
                total_event_bbox_rows / total_event_rows if total_event_rows else None
            ),
            "sequences": summaries,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        if args.export_format:
            exported_rows: list[dict[str, Any]] = []
            remaining = args.export_limit
            for name in selected:
                data = handle[name][:]
                limit_for_sequence = remaining if remaining > 0 else 0
                rows = iter_records(name, data, args.export_scope, limit_for_sequence)
                exported_rows.extend(rows)
                if remaining > 0:
                    remaining -= len(rows)
                    if remaining <= 0:
                        break

            output_path = args.output_path or default_output_path(
                args.h5_path,
                args.sequence,
                args.export_scope,
                args.export_format,
            )
            export_metadata = {
                "h5_path": str(args.h5_path),
                "selected_sequences": selected,
                "column_order": COLUMN_NAMES,
                "export_scope": args.export_scope,
                "export_format": args.export_format,
                "exported_row_count": len(exported_rows),
            }
            export_rows(output_path, args.export_format, exported_rows, export_metadata)
            print(f"\nExported readable file: {output_path}")
            print(f"Exported rows: {len(exported_rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
