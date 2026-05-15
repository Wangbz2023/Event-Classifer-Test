"""Inspect and extract SN-PCBAS-2026 tactical-data archives.

This script focuses on local split-level zip archives. It can list candidate
games, search by keyword, optionally extract matching members, and sample JSON
payloads to report key field presence.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SPLITS = ["TRAIN", "VAL"]
ALL_SPLITS = ["TRAIN", "VAL", "CHALLENGE"]
DEFAULT_SAMPLE_LIMIT = 3

TACTICAL_ARCHIVES = {
    "TRAIN": "tactical_data_TRAIN.zip",
    "VAL": "tactical_data_VAL.zip",
    "CHALLENGE": "tactical_data_CHALLENGE.zip",
}

JSON_SUFFIXES = {".json", ".jsonl"}


@dataclass(frozen=True)
class ArchiveMember:
    split: str
    archive_path: Path
    member_name: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    return repo_root() / "data" / "soccernet" / "raw" / "sn-pcbas-2026"


def default_output_root() -> Path:
    return default_data_root() / "extracted"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect local SN-PCBAS-2026 tactical-data archives."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_data_root(),
        help="Dataset root. Defaults to data/soccernet/raw/sn-pcbas-2026.",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=DEFAULT_SPLITS,
        choices=ALL_SPLITS,
        help="Dataset splits to inspect.",
    )
    parser.add_argument(
        "--list-games",
        action="store_true",
        help="List candidate top-level game identifiers from archive contents.",
    )
    parser.add_argument(
        "--game-query",
        default="",
        help="Filter archive members by game id, directory name, or keyword.",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract matching archive members to the output root.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=DEFAULT_SAMPLE_LIMIT,
        help="Maximum number of JSON-like members to inspect.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_output_root(),
        help="Extraction root. Defaults to data/soccernet/raw/sn-pcbas-2026/extracted.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def query_tokens(query: str) -> list[str]:
    return [token for token in normalize_text(query).split() if token]


def has_all_tokens(text: str, tokens: list[str]) -> bool:
    normalized = normalize_text(text)
    return all(token in normalized for token in tokens)


def archive_path(data_root: Path, split: str) -> Path:
    return data_root / split / TACTICAL_ARCHIVES[split]


def iter_archive_members(data_root: Path, splits: Iterable[str]) -> Iterable[ArchiveMember]:
    for split in splits:
        path = archive_path(data_root, split)
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as archive:
            for member_name in archive.namelist():
                yield ArchiveMember(split=split, archive_path=path, member_name=member_name)


def top_level_identifier(member_name: str) -> str:
    pieces = [piece for piece in member_name.split("/") if piece]
    if not pieces:
        return ""
    if len(pieces) == 1:
        return pieces[0]
    return pieces[0] if pieces[0] != "__MACOSX" else pieces[1]


def find_candidates(
    data_root: Path, splits: Iterable[str], query: str
) -> tuple[list[ArchiveMember], set[str]]:
    tokens = query_tokens(query)
    matches: list[ArchiveMember] = []
    identifiers: set[str] = set()

    for member in iter_archive_members(data_root, splits):
        identifier = top_level_identifier(member.member_name)
        if identifier:
            identifiers.add(identifier)
        if tokens and not has_all_tokens(member.member_name, tokens):
            continue
        if tokens:
            matches.append(member)

    return matches, identifiers


def json_candidates(members: Iterable[ArchiveMember]) -> list[ArchiveMember]:
    return [
        member
        for member in members
        if Path(member.member_name).suffix.lower() in JSON_SUFFIXES
    ]


def load_member_payload(member: ArchiveMember) -> Any:
    with zipfile.ZipFile(member.archive_path) as archive:
        with archive.open(member.member_name) as handle:
            raw = handle.read().decode("utf-8")
    if member.member_name.endswith(".jsonl"):
        lines = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return lines
    return json.loads(raw)


def first_dict(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                return item
    return None


def nested_keys(payload: dict[str, Any], prefixes: tuple[str, ...] = ()) -> list[str]:
    keys: list[str] = []
    for key, value in payload.items():
        path = ".".join(prefixes + (str(key),))
        keys.append(path)
        if isinstance(value, dict):
            keys.extend(nested_keys(value, prefixes + (str(key),)))
    return keys


def summarize_payload(member: ArchiveMember) -> dict[str, Any]:
    payload = load_member_payload(member)
    root = first_dict(payload) or {}
    keys = nested_keys(root)
    lowered = {key.lower() for key in keys}

    def has_any(*patterns: str) -> bool:
        return any(pattern in key for key in patterns for key in lowered)

    return {
        "split": member.split,
        "archive_path": str(member.archive_path),
        "member_name": member.member_name,
        "root_type": type(payload).__name__,
        "top_level_keys": sorted(root.keys()),
        "has_action_label": has_any("action", "label", "event"),
        "has_timestamp_or_frame": has_any("time", "frame", "position"),
        "has_player_id": has_any("player_id", "playerid", "actor_id"),
        "has_team": has_any("team"),
        "has_jersey": has_any("jersey", "shirt"),
        "has_role": has_any("role"),
        "has_track": has_any("track"),
        "has_spatiotemporal": has_any("bbox", "position", "pitch", "coord", "spatio"),
    }


def safe_extract_members(members: Iterable[ArchiveMember], output_root: Path) -> list[str]:
    extracted: list[str] = []
    for member in members:
        split_root = output_root / member.split
        split_root.mkdir(parents=True, exist_ok=True)
        resolved_root = split_root.resolve()

        target = (split_root / member.member_name).resolve()
        if not str(target).startswith(str(resolved_root)):
            raise ValueError(f"Unsafe archive member path: {member.member_name}")

        with zipfile.ZipFile(member.archive_path) as archive:
            archive.extract(member.member_name, split_root)
        extracted.append(str(target))
    return extracted


def main() -> int:
    args = parse_args()

    print("SN-PCBAS-2026 inspection plan")
    print(f"- data root: {args.data_root}")
    print(f"- splits: {', '.join(args.splits)}")
    print(f"- game query: {args.game_query or '(none)'}")
    print(f"- list games: {args.list_games}")
    print(f"- extract: {args.extract}")
    print(f"- sample limit: {args.sample_limit}")
    print(f"- output root: {args.output_root}")

    print("\n[Archive status]")
    for split in args.splits:
        path = archive_path(args.data_root, split)
        exists = path.exists()
        size = path.stat().st_size if exists else None
        print(f"- {split}: {path} exists={exists} size={size}")

    matches, identifiers = find_candidates(args.data_root, args.splits, args.game_query)

    if args.list_games:
        print("\n[Candidate game identifiers]")
        for identifier in sorted(identifiers):
            print(f"- {identifier}")

    if args.game_query:
        print("\n[Query matches]")
        print(f"- match count: {len(matches)}")
        for member in matches[:20]:
            print(f"- {member.split}: {member.member_name}")

    members_for_sampling = json_candidates(matches) if args.game_query else json_candidates(
        iter_archive_members(args.data_root, args.splits)
    )

    samples = [summarize_payload(member) for member in members_for_sampling[: max(args.sample_limit, 0)]]
    print("\n[Sample summaries]")
    print(json.dumps(samples, ensure_ascii=False, indent=2))

    if args.extract:
        members_to_extract = matches if args.game_query else members_for_sampling
        if not members_to_extract:
            print("\nNo matching members to extract.")
            return 1
        extracted = safe_extract_members(members_to_extract, args.output_root)
        print("\n[Extracted files]")
        for path in extracted[:50]:
            print(f"- {path}")
        if len(extracted) > 50:
            print(f"- ... total extracted: {len(extracted)}")

    if not any(archive_path(args.data_root, split).exists() for split in args.splits):
        print(
            "\nNo tactical-data archives were found. Download split archives first with "
            "scripts/download_sn_pcbas.py."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
