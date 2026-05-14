"""Download SoccerNet Game State Reconstruction data for this project.

The downloader stores task archives under:
data/soccernet/raw/as2023/_tasks/gamestate-2024/
"""

from __future__ import annotations

import argparse
from pathlib import Path


TASK_NAME = "gamestate-2024"
DEFAULT_SPLITS = ["train", "valid", "test", "challenge"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    return repo_root() / "data" / "soccernet" / "raw" / "as2023"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download SoccerNet Game State Reconstruction archives."
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
        help="Dataset splits to download.",
    )
    parser.add_argument(
        "--password",
        default="SoccerNet",
        help="SoccerNet public data password.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task_parent = args.data_root / "_tasks"
    task_root = task_parent / TASK_NAME
    task_parent.mkdir(parents=True, exist_ok=True)

    print(f"Task: {TASK_NAME}")
    print(f"Data root: {args.data_root}")
    print(f"Download parent: {task_parent}")
    print(f"Expected task directory: {task_root}")
    print(f"Splits: {', '.join(args.splits)}")

    from SoccerNet.Downloader import SoccerNetDownloader

    downloader = SoccerNetDownloader(str(task_parent))
    downloader.downloadDataTask(
        task=TASK_NAME,
        split=args.splits,
        password=args.password,
    )

    print("\nExpected archives:")
    for split in args.splits:
        path = task_root / f"{split}.zip"
        state = "exists" if path.exists() else "missing"
        size = f"{path.stat().st_size} bytes" if path.exists() else "-"
        print(f"- {split}: {path} [{state}, {size}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
