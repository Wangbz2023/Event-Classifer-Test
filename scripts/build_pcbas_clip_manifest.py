"""Build 4-second PCABS clip labels from tactical HDF5 annotations.

This script uses only the PCABS tactical H5 file. It does not need the videos:

1. read player-centric action anchors where cls > 0
2. segment the action stream with coarse event rules
3. project the segments into fixed-length clips
4. mark whether a memory token should update in each clip
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass
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

CLASS_NAMES = {
    1: "Drive",
    2: "Pass",
    3: "Cross",
    4: "Shot",
    5: "Header",
    6: "Throw-in",
    7: "Tackle",
    8: "Block",
}

ACTION_FAMILIES = {
    "Drive": "carry",
    "Pass": "circulate",
    "Cross": "deliver",
    "Shot": "finish",
    "Header": "finish",
    "Throw-in": "restart",
    "Tackle": "disrupt",
    "Block": "disrupt",
}

COARSE_PRIORITY = {
    "transition": 6,
    "chance_creation": 5,
    "restart_phase": 4,
    "duel_recovery": 3,
    "delivery_attack": 2,
    "build_up": 1,
    "background": 0,
}


@dataclass(frozen=True)
class Event:
    sequence: str
    frame: int
    player_id: int
    team_side: str
    shirt_number: int
    role_id: int
    x_pos: float
    y_pos: float
    x_speed: float
    y_speed: float
    bbox_visible: bool
    cls: int
    action: str
    action_family: str

    @property
    def x_attack(self) -> float:
        return self.x_pos if self.team_side == "left" else 1.0 - self.x_pos

    @property
    def speed_norm(self) -> float:
        return math.sqrt(self.x_speed * self.x_speed + self.y_speed * self.y_speed)


@dataclass
class Segment:
    segment_id: str
    sequence: str
    events: list[Event]
    boundary_reasons: list[str]
    coarse_event: str
    transition_from_side: str | None = None
    transition_to_side: str | None = None

    @property
    def start_frame(self) -> int:
        return self.events[0].frame

    @property
    def end_frame(self) -> int:
        return self.events[-1].frame


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_h5_path() -> Path:
    return repo_root() / "data" / "pcbas2026" / "extracted" / "VAL" / "val_tactical_data.h5"


def default_output_path(h5_path: Path, clip_seconds: float) -> Path:
    suffix = f"{clip_seconds:g}s".replace(".", "p")
    return (
        repo_root()
        / "data"
        / "pcbas2026"
        / "processed"
        / f"{h5_path.stem}_clip_manifest_{suffix}.jsonl"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build 4-second clip-level coarse event labels from PCABS H5."
    )
    parser.add_argument(
        "--h5-path",
        type=Path,
        default=default_h5_path(),
        help="Path to tactical HDF5. Defaults to data/pcbas2026/extracted/VAL/val_tactical_data.h5.",
    )
    parser.add_argument(
        "--sequences",
        nargs="+",
        default=[],
        help="Optional sequence keys such as game_18_H1. Defaults to all sequences.",
    )
    parser.add_argument("--fps", type=float, default=25.0, help="Video frame rate.")
    parser.add_argument(
        "--clip-seconds",
        type=float,
        default=4.0,
        help="Clip window length in seconds.",
    )
    parser.add_argument(
        "--max-event-gap-frames",
        type=int,
        default=75,
        help="Start a new segment when adjacent event anchors are farther apart.",
    )
    parser.add_argument(
        "--x-jump-threshold",
        type=float,
        default=0.25,
        help="Medium boundary threshold for normalized attacking x-position jump.",
    )
    parser.add_argument(
        "--speed-jump-threshold",
        type=float,
        default=0.75,
        help="Medium boundary threshold for speed norm jump.",
    )
    parser.add_argument(
        "--events-only",
        action="store_true",
        help="Emit only clips containing at least one action event.",
    )
    parser.add_argument(
        "--max-events-per-clip",
        type=int,
        default=12,
        help="Maximum representative event records to include per clip.",
    )
    parser.add_argument(
        "--clip-limit",
        type=int,
        default=0,
        help="Maximum number of clip rows to write. 0 means no limit.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Output JSONL path. Defaults to data/pcbas2026/processed/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing a manifest file.",
    )
    return parser.parse_args()


def team_side(raw_side: float) -> str:
    return "right" if int(raw_side) == 1 else "left"


def parse_events(sequence: str, data: np.ndarray) -> list[Event]:
    event_rows = data[data[:, CLS] > 0]
    events: list[Event] = []
    for row in event_rows:
        cls_id = int(row[CLS])
        action = CLASS_NAMES.get(cls_id, f"Unknown-{cls_id}")
        events.append(
            Event(
                sequence=sequence,
                frame=int(row[FRAME]),
                player_id=int(row[PLAYER_ID]),
                team_side=team_side(row[LEFT_TO_RIGHT]),
                shirt_number=int(row[SHIRT_NUMBER]),
                role_id=int(row[ROLE_ID]),
                x_pos=float(row[X_POS]),
                y_pos=float(row[Y_POS]),
                x_speed=float(row[X_SPEED]),
                y_speed=float(row[Y_SPEED]),
                bbox_visible=not bool(np.isnan(row[ROI_X])),
                cls=cls_id,
                action=action,
                action_family=ACTION_FAMILIES.get(action, "unknown"),
            )
        )
    return sorted(events, key=lambda item: (item.frame, item.player_id, item.cls))


def boundary_before(
    previous: Event,
    current: Event,
    max_event_gap_frames: int,
    x_jump_threshold: float,
    speed_jump_threshold: float,
) -> list[str]:
    reasons: list[str] = []
    frame_gap = current.frame - previous.frame

    if frame_gap > max_event_gap_frames:
        return [f"event_gap>{max_event_gap_frames}"]

    if current.team_side != previous.team_side:
        return ["team_side_change"]

    if current.action_family == "restart":
        return ["restart_action"]

    medium: list[str] = []
    if current.player_id != previous.player_id:
        medium.append("player_change")
    if current.action_family != previous.action_family:
        medium.append("action_family_change")
    if abs(current.x_attack - previous.x_attack) > x_jump_threshold:
        medium.append("x_attack_jump")
    if abs(current.speed_norm - previous.speed_norm) > speed_jump_threshold:
        medium.append("speed_jump")

    if len(medium) >= 2:
        reasons.extend(medium)
    return reasons


def classify_segment(
    events: list[Event],
    boundary_reasons: list[str],
    previous_segment: Segment | None,
) -> tuple[str, str | None, str | None]:
    actions = [event.action for event in events]
    families = [event.action_family for event in events]
    first = events[0]
    last = events[-1]

    if previous_segment and "team_side_change" in boundary_reasons:
        has_fast_progress = any(
            event.action in {"Drive", "Pass"} and event.frame - first.frame <= 50
            for event in events
        )
        if has_fast_progress and last.x_attack >= first.x_attack:
            return "transition", previous_segment.events[-1].team_side, first.team_side

    if first.action_family == "restart":
        return "restart_phase", None, None

    if first.action_family == "disrupt":
        return "duel_recovery", None, None

    if last.action_family == "finish":
        has_setup = any(
            event.action in {"Drive", "Pass", "Cross"}
            and last.frame - event.frame <= 50
            for event in events[:-1]
        )
        if has_setup or len(events) == 1:
            return "chance_creation", None, None

    if "Cross" in actions:
        if any(event.action_family == "finish" for event in events):
            return "chance_creation", None, None
        return "delivery_attack", None, None

    if set(families).issubset({"carry", "circulate"}):
        return "build_up", None, None

    if "finish" in families:
        return "chance_creation", None, None

    if "disrupt" in families:
        return "duel_recovery", None, None

    return "build_up", None, None


def build_segments(
    sequence: str,
    events: list[Event],
    max_event_gap_frames: int,
    x_jump_threshold: float,
    speed_jump_threshold: float,
) -> list[Segment]:
    if not events:
        return []

    segments: list[Segment] = []
    current: list[Event] = []
    current_reasons: list[str] = ["sequence_start"]

    def close_current() -> None:
        if not current:
            return
        previous_segment = segments[-1] if segments else None
        coarse, from_side, to_side = classify_segment(
            current,
            current_reasons,
            previous_segment,
        )
        segments.append(
            Segment(
                segment_id=f"{sequence}_seg_{len(segments):06d}",
                sequence=sequence,
                events=list(current),
                boundary_reasons=list(current_reasons),
                coarse_event=coarse,
                transition_from_side=from_side,
                transition_to_side=to_side,
            )
        )

    for event in events:
        if not current:
            current = [event]
            current_reasons = ["sequence_start"] if not segments else ["new_segment"]
        else:
            reasons = boundary_before(
                current[-1],
                event,
                max_event_gap_frames,
                x_jump_threshold,
                speed_jump_threshold,
            )
            if reasons:
                close_current()
                current = [event]
                current_reasons = reasons
            else:
                current.append(event)

        if event.action_family == "finish":
            close_current()
            current = []
            current_reasons = ["after_finish"]

    close_current()
    return segments


def event_to_record(event: Event, fps: float) -> dict[str, Any]:
    return {
        "frame": event.frame,
        "time_sec": round(event.frame / fps, 3),
        "player_id": event.player_id,
        "team_side": event.team_side,
        "shirt_number": event.shirt_number,
        "role_id": event.role_id,
        "x_pos": event.x_pos,
        "y_pos": event.y_pos,
        "x_attack": event.x_attack,
        "bbox_visible": event.bbox_visible,
        "cls": event.cls,
        "action": event.action,
        "action_family": event.action_family,
    }


def segment_to_record(segment: Segment, fps: float) -> dict[str, Any]:
    actions = Counter(event.action for event in segment.events)
    families = Counter(event.action_family for event in segment.events)
    sides = sorted({event.team_side for event in segment.events})
    players = sorted({event.player_id for event in segment.events})
    return {
        "segment_id": segment.segment_id,
        "sequence": segment.sequence,
        "start_frame": segment.start_frame,
        "end_frame": segment.end_frame,
        "start_sec": round(segment.start_frame / fps, 3),
        "end_sec": round(segment.end_frame / fps, 3),
        "duration_frames": segment.end_frame - segment.start_frame,
        "coarse_event": segment.coarse_event,
        "boundary_reasons": segment.boundary_reasons,
        "event_count": len(segment.events),
        "actions": dict(actions),
        "action_families": dict(families),
        "team_sides": sides,
        "player_ids": players,
        "transition_from_side": segment.transition_from_side,
        "transition_to_side": segment.transition_to_side,
    }


def primary_label(labels: list[str]) -> str:
    if not labels:
        return "background"
    counts = Counter(labels)
    return max(
        counts,
        key=lambda label: (counts[label], COARSE_PRIORITY.get(label, 0), label),
    )


def build_clip_records(
    sequence: str,
    data: np.ndarray,
    events: list[Event],
    segments: list[Segment],
    fps: float,
    clip_seconds: float,
    events_only: bool,
    max_events_per_clip: int,
) -> list[dict[str, Any]]:
    frames = data[:, FRAME].astype(int)
    frame_min = int(frames.min())
    frame_max = int(frames.max())
    clip_frames = int(round(fps * clip_seconds))
    first_clip_start = (frame_min // clip_frames) * clip_frames
    last_clip_start = (frame_max // clip_frames) * clip_frames

    event_by_clip: dict[int, list[Event]] = {}
    for event in events:
        start = (event.frame // clip_frames) * clip_frames
        event_by_clip.setdefault(start, []).append(event)

    segments_by_clip: dict[int, list[Segment]] = {}
    segment_starts_by_clip: dict[int, list[Segment]] = {}
    for segment in segments:
        start_clip = (segment.start_frame // clip_frames) * clip_frames
        end_clip = (segment.end_frame // clip_frames) * clip_frames
        segment_starts_by_clip.setdefault(start_clip, []).append(segment)
        for clip_start in range(start_clip, end_clip + 1, clip_frames):
            segments_by_clip.setdefault(clip_start, []).append(segment)

    records: list[dict[str, Any]] = []
    previous_primary = "background"
    clip_index = 0
    for clip_start in range(first_clip_start, last_clip_start + 1, clip_frames):
        clip_end = clip_start + clip_frames
        clip_events = event_by_clip.get(clip_start, [])
        if events_only and not clip_events:
            previous_primary = "background"
            continue

        overlapping_segments = segments_by_clip.get(clip_start, [])
        starting_segments = segment_starts_by_clip.get(clip_start, [])
        coarse_events = [segment.coarse_event for segment in overlapping_segments]
        coarse_event = primary_label(coarse_events)

        reasons: list[str] = []
        if starting_segments:
            reasons.append("segment_start")
        if coarse_event != previous_primary and coarse_event != "background":
            reasons.append("coarse_event_change")
        memory_update = bool(reasons)

        action_counts = Counter(event.action for event in clip_events)
        family_counts = Counter(event.action_family for event in clip_events)
        record = {
            "sequence": sequence,
            "clip_index": clip_index,
            "clip_start_frame": clip_start,
            "clip_end_frame": clip_end,
            "clip_start_sec": round(clip_start / fps, 3),
            "clip_end_sec": round(clip_end / fps, 3),
            "fps": fps,
            "clip_seconds": clip_seconds,
            "event_count": len(clip_events),
            "fine_action_counts": dict(action_counts),
            "action_family_counts": dict(family_counts),
            "team_sides": sorted({event.team_side for event in clip_events}),
            "actor_count": len({event.player_id for event in clip_events}),
            "coarse_events": sorted(set(coarse_events)),
            "primary_coarse_event": coarse_event,
            "memory_update": memory_update,
            "memory_update_reasons": reasons,
            "segment_ids_starting": [segment.segment_id for segment in starting_segments],
            "segment_ids_overlapping": [
                segment.segment_id for segment in overlapping_segments
            ],
            "representative_events": [
                event_to_record(event, fps)
                for event in clip_events[: max(max_events_per_clip, 0)]
            ],
        }
        records.append(record)
        previous_primary = coarse_event
        clip_index += 1

    return records


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def summarize(rows: list[dict[str, Any]], segments: list[Segment]) -> dict[str, Any]:
    clip_labels = Counter(row["primary_coarse_event"] for row in rows)
    memory_updates = sum(1 for row in rows if row["memory_update"])
    segment_labels = Counter(segment.coarse_event for segment in segments)
    return {
        "clip_count": len(rows),
        "memory_update_clip_count": memory_updates,
        "clip_label_counts": dict(clip_labels),
        "segment_count": len(segments),
        "segment_label_counts": dict(segment_labels),
    }


def main() -> int:
    args = parse_args()
    if not args.h5_path.exists():
        raise SystemExit(f"HDF5 file not found: {args.h5_path}")

    all_clip_rows: list[dict[str, Any]] = []
    all_segments: list[Segment] = []
    sequence_summaries: dict[str, Any] = {}

    with h5py.File(args.h5_path, "r") as handle:
        available = list(handle.keys())
        sequences = args.sequences or available
        missing = [sequence for sequence in sequences if sequence not in handle]
        if missing:
            raise SystemExit(f"Sequence not found: {missing[0]}")

        for sequence in sequences:
            data = handle[sequence][:]
            if data.ndim != 2 or data.shape[1] != 14:
                raise SystemExit(
                    f"Unexpected dataset shape for {sequence}: {data.shape}. "
                    "Expected (N, 14)."
                )
            events = parse_events(sequence, data)
            segments = build_segments(
                sequence,
                events,
                args.max_event_gap_frames,
                args.x_jump_threshold,
                args.speed_jump_threshold,
            )
            clip_rows = build_clip_records(
                sequence,
                data,
                events,
                segments,
                args.fps,
                args.clip_seconds,
                args.events_only,
                args.max_events_per_clip,
            )

            all_segments.extend(segments)
            all_clip_rows.extend(clip_rows)
            sequence_summaries[sequence] = summarize(clip_rows, segments)

    if args.clip_limit > 0:
        all_clip_rows = all_clip_rows[: args.clip_limit]

    output_path = args.output_path or default_output_path(args.h5_path, args.clip_seconds)
    summary = {
        "h5_path": str(args.h5_path),
        "sequences": args.sequences or "all",
        "fps": args.fps,
        "clip_seconds": args.clip_seconds,
        "class_mapping": CLASS_NAMES,
        "class_mapping_note": (
            "Class ids follow the published FOOTPASS class order: "
            "Drive, Pass, Cross, Shot, Header, Throw-in, Tackle, Block."
        ),
        "rules": {
            "max_event_gap_frames": args.max_event_gap_frames,
            "x_jump_threshold": args.x_jump_threshold,
            "speed_jump_threshold": args.speed_jump_threshold,
            "memory_update": (
                "true when a semantic segment starts in the clip or the "
                "primary coarse event changes from background/previous label"
            ),
        },
        "overall": summarize(all_clip_rows, all_segments),
        "by_sequence": sequence_summaries,
        "output_path": str(output_path),
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.dry_run:
        write_jsonl(output_path, all_clip_rows)
        print(f"\nWrote clip manifest: {output_path}")
        print(f"Rows: {len(all_clip_rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
