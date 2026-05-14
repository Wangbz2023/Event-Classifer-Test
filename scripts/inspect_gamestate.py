"""Inspect downloaded SoccerNet Game State Reconstruction archives.

This script checks archive presence, optionally extracts archives, samples
Labels-GameState JSON files, and reports whether path-level evidence suggests
the target Chelsea vs Burnley match is present.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


TASK_NAME = "gamestate-2024"
DEFAULT_SPLITS = ["train", "valid", "test", "challenge"]
DEFAULT_MATCH_QUERY = "2015-02-21 Chelsea Burnley"


@dataclass(frozen=True)
class JsonCandidate:
    source: str
    split: str | None
    path: str
    zip_member: str | None = None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    return repo_root() / "data" / "soccernet" / "raw" / "as2023"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect SoccerNet Game State Reconstruction data."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_data_root(),
        help="Project SoccerNet data root. Defaults to data/soccernet/raw/as2023.",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=DEFAULT_SPLITS,
        choices=DEFAULT_SPLITS,
        help="Dataset splits to inspect.",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract found split archives into _tasks/gamestate-2024/extracted/.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=3,
        help="Maximum number of Labels-GameState JSON files to sample.",
    )
    parser.add_argument(
        "--match-query",
        default=DEFAULT_MATCH_QUERY,
        help="Words used for a path-level search for the target match.",
    )
    return parser.parse_args()


def task_root(data_root: Path) -> Path:
    return data_root / "_tasks" / TASK_NAME


def archive_path(root: Path, split: str) -> Path:
    return root / f"{split}.zip"


def normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def query_tokens(query: str) -> list[str]:
    return [token for token in normalize_text(query).split() if token]


def has_all_tokens(text: str, tokens: list[str]) -> bool:
    normalized = normalize_text(text)
    return all(token in normalized for token in tokens)


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()

    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(resolved_destination)):
                raise ValueError(f"Unsafe zip member path: {member.filename}")
        archive.extractall(destination)


def find_extracted_jsons(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("Labels-GameState.json"))


def iter_zip_jsons(root: Path, splits: Iterable[str]) -> Iterable[JsonCandidate]:
    for split in splits:
        path = archive_path(root, split)
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.endswith("Labels-GameState.json"):
                    yield JsonCandidate(
                        source="zip",
                        split=split,
                        path=str(path),
                        zip_member=member,
                    )


def iter_file_jsons(root: Path) -> Iterable[JsonCandidate]:
    for path in find_extracted_jsons(root):
        yield JsonCandidate(source="file", split=None, path=str(path))


def load_candidate(candidate: JsonCandidate) -> dict[str, Any]:
    if candidate.source == "file":
        with Path(candidate.path).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    if candidate.source == "zip" and candidate.zip_member:
        with zipfile.ZipFile(candidate.path) as archive:
            with archive.open(candidate.zip_member) as handle:
                return json.load(handle)

    raise ValueError(f"Unsupported candidate: {candidate}")


def first_detection(payload: dict[str, Any]) -> dict[str, Any] | None:
    annotations = payload.get("annotations")
    if isinstance(annotations, list):
        for annotation in annotations:
            if isinstance(annotation, dict):
                return annotation
    return None


def summarize_candidate(candidate: JsonCandidate) -> dict[str, Any]:
    payload = load_candidate(candidate)
    detection = first_detection(payload) or {}
    attributes = detection.get("attributes") or {}
    bbox_pitch = detection.get("bbox_pitch") or {}

    return {
        "source": candidate.source,
        "split": candidate.split,
        "path": candidate.path,
        "zip_member": candidate.zip_member,
        "info_version": (payload.get("info") or {}).get("version"),
        "image_count": len(payload.get("images") or []),
        "annotation_count": len(payload.get("annotations") or []),
        "sample_detection_fields": sorted(detection.keys()),
        "sample_image_id": detection.get("image_id"),
        "sample_track_id": detection.get("track_id"),
        "sample_role": attributes.get("role") or detection.get("role"),
        "sample_team": attributes.get("team") or detection.get("team"),
        "sample_jersey": (
            attributes.get("jersey")
            or attributes.get("jersey_number")
            or detection.get("jersey")
        ),
        "has_bbox_pitch": bool(bbox_pitch),
        "has_pitch_bottom_middle": isinstance(bbox_pitch, dict)
        and "x_bottom_middle" in bbox_pitch
        and "y_bottom_middle" in bbox_pitch,
    }


def scan_path_level_match(root: Path, splits: Iterable[str], query: str) -> dict[str, Any]:
    tokens = query_tokens(query)
    matches: list[str] = []

    for path in root.rglob("*") if root.exists() else []:
        if has_all_tokens(str(path), tokens):
            matches.append(str(path))
            if len(matches) >= 20:
                break

    if len(matches) < 20:
        for split in splits:
            path = archive_path(root, split)
            if not path.exists():
                continue
            with zipfile.ZipFile(path) as archive:
                for member in archive.namelist():
                    haystack = f"{path} {member}"
                    if has_all_tokens(haystack, tokens):
                        matches.append(f"{path}!{member}")
                        if len(matches) >= 20:
                            break
                if len(matches) >= 20:
                    break

    return {
        "query": query,
        "path_level_match": bool(matches),
        "matches": matches,
        "note": (
            "Path-level matching is only a quick screen. A false result means no "
            "obvious filename match was found, not that temporal overlap is impossible."
        ),
    }


def main() -> int:
    args = parse_args()
    root = task_root(args.data_root)
    extract_root = root / "extracted"

    print(f"Task root: {root}")
    print("\nArchive status:")
    for split in args.splits:
        path = archive_path(root, split)
        exists = path.exists()
        size = path.stat().st_size if exists else None
        print(f"- {split}: {path} exists={exists} size={size}")

    if args.extract:
        print("\nExtraction:")
        for split in args.splits:
            path = archive_path(root, split)
            if not path.exists():
                print(f"- {split}: skipped, archive missing")
                continue
            destination = extract_root / split
            safe_extract_zip(path, destination)
            print(f"- {split}: extracted to {destination}")

    file_candidates = list(iter_file_jsons(root))
    zip_candidates = list(iter_zip_jsons(root, args.splits))
    candidates = file_candidates + zip_candidates

    print("\nLabels-GameState.json candidates:")
    print(f"- extracted files: {len(file_candidates)}")
    print(f"- zip members: {len(zip_candidates)}")
    print(f"- total: {len(candidates)}")

    print("\nSample summaries:")
    samples = []
    for candidate in candidates[: max(args.sample_limit, 0)]:
        samples.append(summarize_candidate(candidate))
    print(json.dumps(samples, ensure_ascii=False, indent=2))

    print("\nTarget match scan:")
    match_scan = scan_path_level_match(root, args.splits, args.match_query)
    print(json.dumps(match_scan, ensure_ascii=False, indent=2))

    if not candidates:
        print("\nNo Labels-GameState.json files were found. Download and/or extract data first.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
