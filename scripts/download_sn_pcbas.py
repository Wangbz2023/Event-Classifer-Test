"""Download SN-PCBAS-2026 archives for this project.

The dataset is currently exposed as a gated Hugging Face dataset rather than
through SoccerNetDownloader.downloadGame(). This script downloads split-level
zip archives and leaves inspection/extraction to a separate script.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


DEFAULT_DATASET_REPO = "SoccerNet/SN-PCBAS-2026"
DEFAULT_SPLITS = ["TRAIN", "VAL"]
ALL_SPLITS = ["TRAIN", "VAL", "CHALLENGE"]
DEFAULT_TOKEN_ENV = "HF_TOKEN"
DEFAULT_VIDEO_QUALITY = "352x640"
VIDEO_QUALITIES = ["352x640", "fullHD"]

# Publicly visible filenames may evolve. Keep the mapping explicit and
# adjustable through CLI args rather than assuming SoccerNetDownloader support.
TACTICAL_ARCHIVES = {
    "TRAIN": "tactical_data_TRAIN.zip",
    "VAL": "tactical_data_VAL.zip",
    "CHALLENGE": "tactical_data_CHALLENGE.zip",
}

VIDEO_ARCHIVES_BY_QUALITY = {
    "352x640": {
        "TRAIN": ["videos_352x640_TRAIN.zip"],
        "VAL": ["videos_352x640_VAL.zip"],
        "CHALLENGE": ["videos_352x640_CHALLENGE.zip"],
    },
    "fullHD": {
        "TRAIN": [
            "videos_fullHD_TRAIN_01.zip",
            "videos_fullHD_TRAIN_02.zip",
            "videos_fullHD_TRAIN_03.zip",
            "videos_fullHD_TRAIN_04.zip",
            "videos_fullHD_TRAIN_05.zip",
        ],
        "VAL": ["videos_fullHD_VAL.zip"],
        "CHALLENGE": ["videos_fullHD_CHALLENGE.zip"],
    },
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    return repo_root() / "data" / "pcbas2026" / "raw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download gated Hugging Face archives for SN-PCBAS-2026."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_data_root(),
        help="Download root. Defaults to data/pcbas2026/raw.",
    )
    parser.add_argument(
        "--dataset-repo",
        default=DEFAULT_DATASET_REPO,
        help="Hugging Face dataset repo id.",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=DEFAULT_SPLITS,
        choices=ALL_SPLITS,
        help="Dataset splits to download.",
    )
    parser.add_argument(
        "--with-video",
        action="store_true",
        help=(
            "Also download split-level video archives. Defaults to 352x640 "
            "video archives unless --video-quality is set."
        ),
    )
    parser.add_argument(
        "--video-only",
        action="store_true",
        help="Download only video archives and skip tactical-data archives.",
    )
    parser.add_argument(
        "--video-quality",
        choices=VIDEO_QUALITIES,
        default=DEFAULT_VIDEO_QUALITY,
        help="Video archive quality to download when video is requested.",
    )
    parser.add_argument(
        "--hf-token-env",
        default=DEFAULT_TOKEN_ENV,
        help="Environment variable holding the Hugging Face token.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned downloads without fetching files.",
    )
    parser.add_argument(
        "--tactical-archive-name",
        action="append",
        default=[],
        metavar="SPLIT=FILENAME",
        help=(
            "Override a tactical archive filename, for example "
            "TRAIN=tactical_data_TRAIN.zip."
        ),
    )
    parser.add_argument(
        "--video-archive-name",
        action="append",
        default=[],
        metavar="SPLIT=FILENAME",
        help=(
            "Override video archive filenames for a split, for example "
            "VAL=videos_352x640_VAL.zip. Repeat the argument or separate "
            "filenames with commas for multi-part splits."
        ),
    )
    return parser.parse_args()


def parse_override(values: list[str], allowed_splits: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(
                f"Invalid override '{value}'. Expected the form SPLIT=FILENAME."
            )
        split, filename = value.split("=", 1)
        split = split.strip().upper()
        filename = filename.strip()
        if split not in allowed_splits:
            raise SystemExit(
                f"Invalid split in override '{value}'. Expected one of: "
                f"{', '.join(allowed_splits)}."
            )
        if not filename:
            raise SystemExit(f"Missing filename in override '{value}'.")
        mapping[split] = filename
    return mapping


def parse_video_override(
    values: list[str],
    allowed_splits: list[str],
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(
                f"Invalid override '{value}'. Expected the form SPLIT=FILENAME."
            )
        split, filenames = value.split("=", 1)
        split = split.strip().upper()
        filenames = filenames.strip()
        if split not in allowed_splits:
            raise SystemExit(
                f"Invalid split in override '{value}'. Expected one of: "
                f"{', '.join(allowed_splits)}."
            )
        parsed_names = [name.strip() for name in filenames.split(",") if name.strip()]
        if not parsed_names:
            raise SystemExit(f"Missing filename in override '{value}'.")
        mapping.setdefault(split, []).extend(parsed_names)
    return mapping


def planned_files(
    splits: list[str],
    with_video: bool,
    video_only: bool,
    tactical_archives: dict[str, str],
    video_archives: dict[str, list[str]],
) -> list[tuple[str, str]]:
    downloads: list[tuple[str, str]] = []
    for split in splits:
        if not video_only:
            downloads.append((split, tactical_archives[split]))
        if with_video or video_only:
            for filename in video_archives[split]:
                downloads.append((split, filename))
    return downloads


def import_hf_hub():
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import (
            EntryNotFoundError,
            GatedRepoError,
            HfHubHTTPError,
            RepositoryNotFoundError,
        )
    except ImportError as exc:  # pragma: no cover - simple import failure path
        raise SystemExit(
            "huggingface_hub is not installed. Install it before downloading "
            "SN-PCBAS-2026."
        ) from exc

    return (
        hf_hub_download,
        EntryNotFoundError,
        GatedRepoError,
        HfHubHTTPError,
        RepositoryNotFoundError,
    )


def summarize_files(data_root: Path, downloads: list[tuple[str, str]]) -> None:
    print("\n[Local summary]")
    for split, filename in downloads:
        path = data_root / split / filename
        exists = path.exists()
        size = path.stat().st_size if exists else None
        print(f"- {split}/{filename}: exists={exists} size={size}")


def main() -> int:
    args = parse_args()
    tactical_archives = {**TACTICAL_ARCHIVES, **parse_override(args.tactical_archive_name, ALL_SPLITS)}
    video_archives = {
        split: list(filenames)
        for split, filenames in VIDEO_ARCHIVES_BY_QUALITY[args.video_quality].items()
    }
    video_archives.update(parse_video_override(args.video_archive_name, ALL_SPLITS))
    downloads = planned_files(
        args.splits,
        args.with_video,
        args.video_only,
        tactical_archives,
        video_archives,
    )

    print("SN-PCBAS-2026 download plan")
    print(f"- data root: {args.data_root}")
    print(f"- dataset repo: {args.dataset_repo}")
    print(f"- splits: {', '.join(args.splits)}")
    print(f"- with video: {args.with_video}")
    print(f"- video only: {args.video_only}")
    print(
        f"- video quality: {args.video_quality if args.with_video or args.video_only else 'not requested'}"
    )
    print(f"- token env: {args.hf_token_env}")
    print(f"- dry run: {args.dry_run}")
    print("- files:")
    for split, filename in downloads:
        print(f"  - {split}: {filename}")

    if args.dry_run:
        return 0

    token = os.environ.get(args.hf_token_env)
    if not token:
        raise SystemExit(
            f"Missing Hugging Face token. Set {args.hf_token_env} after "
            "requesting access to the gated dataset."
        )

    (
        hf_hub_download,
        EntryNotFoundError,
        GatedRepoError,
        HfHubHTTPError,
        RepositoryNotFoundError,
    ) = import_hf_hub()

    for split, filename in downloads:
        local_dir = args.data_root / split
        local_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[Download] {split}/{filename}")
        try:
            path = hf_hub_download(
                repo_id=args.dataset_repo,
                repo_type="dataset",
                filename=filename,
                token=token,
                local_dir=str(local_dir),
            )
        except GatedRepoError as exc:
            raise SystemExit(
                "Access denied by Hugging Face gated dataset policy. "
                f"Request access to {args.dataset_repo} and make sure "
                f"{args.hf_token_env} belongs to an approved account."
            ) from exc
        except RepositoryNotFoundError as exc:
            raise SystemExit(
                f"Dataset repo not found: {args.dataset_repo}. Check the repo id."
            ) from exc
        except EntryNotFoundError as exc:
            raise SystemExit(
                f"Remote file not found in {args.dataset_repo}: {filename}. "
                "The archive naming may have changed."
            ) from exc
        except HfHubHTTPError as exc:
            raise SystemExit(
                "Hugging Face request failed. This can happen when the token is "
                "invalid, access has not been approved, or network access is blocked."
            ) from exc

        print(f"Saved to: {path}")

    summarize_files(args.data_root, downloads)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
