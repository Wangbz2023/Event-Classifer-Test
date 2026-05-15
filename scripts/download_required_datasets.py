"""Download the datasets required by the event classification pipeline.

By default this script downloads the minimum label files needed to run the
pipeline on the sample Chelsea vs Burnley match. Use ``--with-gamestate`` to
also fetch the Game State Reconstruction archives, and ``--with-video`` to
download the match videos.

Examples:
    python scripts/download_required_datasets.py
    python scripts/download_required_datasets.py --with-gamestate
    python scripts/download_required_datasets.py --with-gamestate --with-video
"""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_MATCH = "england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley"
DEFAULT_MATCH_SPLIT = "train"
GAMESTATE_TASK = "gamestate-2024"
GAMESTATE_SPLITS = ["train", "valid", "test", "challenge"]
CORE_LABEL_FILES = ["Labels-v2.json", "Labels-cameras.json"]
CAPTION_FILES = ["Labels-caption.json"]
VIDEO_FILES = ["video.ini", "1.mkv", "2.mkv"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    return repo_root() / "data" / "soccernet" / "raw" / "as2023"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the SoccerNet files required by this project. "
            "Defaults to the minimum label set needed for the sample match."
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_data_root(),
        help="SoccerNet data root. Defaults to data/soccernet/raw/as2023.",
    )
    parser.add_argument(
        "--match",
        default=DEFAULT_MATCH,
        help="SoccerNet match path to download.",
    )
    parser.add_argument(
        "--match-split",
        default=DEFAULT_MATCH_SPLIT,
        help="SoccerNet split used by downloadGame for the target match.",
    )
    parser.add_argument(
        "--password",
        default="SoccerNet",
        help="SoccerNet public data password.",
    )
    parser.add_argument(
        "--with-gamestate",
        action="store_true",
        help="Also download Game State Reconstruction archives.",
    )
    parser.add_argument(
        "--with-video",
        action="store_true",
        help="Also download video.ini, 1.mkv, and 2.mkv for the target match.",
    )
    parser.add_argument(
        "--gamestate-splits",
        nargs="+",
        default=GAMESTATE_SPLITS,
        choices=GAMESTATE_SPLITS,
        help="Game State Reconstruction splits to download.",
    )
    return parser.parse_args()


def import_downloader():
    try:
        from SoccerNet.Downloader import SoccerNetDownloader
    except ImportError as exc:  # pragma: no cover - import error path is simple
        raise SystemExit(
            "SoccerNet is not installed in the current Python environment. "
            "Install it before running this script."
        ) from exc

    return SoccerNetDownloader


def match_dir(data_root: Path, match: str) -> Path:
    return data_root / Path(match)


def download_match_files(
    downloader_cls,
    *,
    data_root: Path,
    match: str,
    split: str,
    password: str,
    files: list[str],
    label: str,
) -> None:
    print(f"\n[{label}]")
    print(f"Target match: {match}")
    print(f"Split: {split}")
    print(f"Files: {', '.join(files)}")

    data_root.mkdir(parents=True, exist_ok=True)
    downloader = downloader_cls(str(data_root))
    downloader.password = password
    downloader.downloadGame(match, files=files, spl=split)


def print_match_summary(data_root: Path, match: str, include_video: bool) -> None:
    root = match_dir(data_root, match)
    expected_files = CORE_LABEL_FILES + CAPTION_FILES
    if include_video:
        expected_files.extend(VIDEO_FILES)

    print("\n[Match summary]")
    print(f"Directory: {root}")
    for name in expected_files:
        path = root / name
        exists = path.exists()
        size = path.stat().st_size if exists else None
        print(f"- {name}: exists={exists} size={size}")

    caption_path = root / "Labels-caption.json"
    if not caption_path.exists():
        print(
            "WARNING: Labels-caption.json was not found in the match directory. "
            "If SoccerNet stored caption data in a task-style layout, move the "
            "file into this match directory before running the pipeline."
        )


def download_gamestate(
    downloader_cls,
    *,
    data_root: Path,
    splits: list[str],
    password: str,
) -> None:
    task_parent = data_root / "_tasks"
    task_root = task_parent / GAMESTATE_TASK
    task_parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[Game State Reconstruction: {GAMESTATE_TASK}]")
    print(f"Task parent: {task_parent}")
    print(f"Splits: {', '.join(splits)}")

    downloader = downloader_cls(str(task_parent))
    downloader.downloadDataTask(
        task=GAMESTATE_TASK,
        split=splits,
        password=password,
    )

    print("\n[GameState summary]")
    print(f"Directory: {task_root}")
    for split in splits:
        path = task_root / f"{split}.zip"
        exists = path.exists()
        size = path.stat().st_size if exists else None
        print(f"- {split}: exists={exists} size={size}")


def main() -> int:
    args = parse_args()
    downloader_cls = import_downloader()

    print("SoccerNet download plan")
    print(f"- data root: {args.data_root}")
    print(f"- match: {args.match}")
    print(f"- match split: {args.match_split}")
    print(f"- with gamestate: {args.with_gamestate}")
    print(f"- with video: {args.with_video}")

    download_match_files(
        downloader_cls,
        data_root=args.data_root,
        match=args.match,
        split=args.match_split,
        password=args.password,
        files=CORE_LABEL_FILES,
        label="Core labels",
    )
    download_match_files(
        downloader_cls,
        data_root=args.data_root,
        match=args.match,
        split=args.match_split,
        password=args.password,
        files=CAPTION_FILES,
        label="Caption labels",
    )

    if args.with_video:
        download_match_files(
            downloader_cls,
            data_root=args.data_root,
            match=args.match,
            split=args.match_split,
            password=args.password,
            files=VIDEO_FILES,
            label="Videos",
        )

    print_match_summary(args.data_root, args.match, args.with_video)

    if args.with_gamestate:
        download_gamestate(
            downloader_cls,
            data_root=args.data_root,
            splits=args.gamestate_splits,
            password=args.password,
        )

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
