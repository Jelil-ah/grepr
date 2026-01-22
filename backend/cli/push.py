"""
STEP 3: Push processed posts to NocoDB
Reads processed posts JSON and pushes to database.

Usage:
    python3 push_only.py                              # Push latest processed file
    python3 push_only.py --file data/processed_xxx.json  # Push specific file
    python3 push_only.py --all-unpushed              # Push all unpushed files
"""
import json
import argparse
from datetime import datetime
from pathlib import Path
from backend.db.nocodb import push_post, get_existing_post_ids
from backend.config import logger

# Configuration
DATA_DIR = Path(__file__).parent / "data"
PUSHED_DIR = DATA_DIR / "pushed"


def find_latest_processed_file() -> Path | None:
    """Find the most recent processed_posts_*.json file."""
    DATA_DIR.mkdir(exist_ok=True)
    files = list(DATA_DIR.glob("processed_posts_*.json"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def find_unpushed_files() -> list[Path]:
    """Find processed files that haven't been pushed yet."""
    DATA_DIR.mkdir(exist_ok=True)
    PUSHED_DIR.mkdir(exist_ok=True)

    processed_files = list(DATA_DIR.glob("processed_posts_*.json"))
    pushed_files = set(f.name for f in PUSHED_DIR.glob("*.json"))

    unpushed = [f for f in processed_files if f.name not in pushed_files]
    return sorted(unpushed, key=lambda f: f.stat().st_mtime)


def push_posts_to_db(posts: list[dict]) -> dict:
    """
    Push posts to NocoDB, skipping duplicates.
    Returns stats dict.
    """
    existing_ids = get_existing_post_ids()
    logger.info(f"Found {len(existing_ids)} existing posts in DB")

    stats = {"pushed": 0, "skipped": 0, "errors": 0}

    for i, post in enumerate(posts):
        post_id = post.get("id")

        if post_id in existing_ids:
            stats["skipped"] += 1
            continue

        try:
            if push_post(post):
                stats["pushed"] += 1
                existing_ids.add(post_id)
                logger.info(f"  [{stats['pushed']}] Pushed: {post.get('title', '')[:40]}...")
            else:
                stats["errors"] += 1
        except Exception as e:
            logger.error(f"  Error pushing {post_id}: {e}")
            stats["errors"] += 1

    return stats


def mark_as_pushed(file_path: Path):
    """Move/copy file to pushed directory to track what's been pushed."""
    PUSHED_DIR.mkdir(exist_ok=True)
    pushed_marker = PUSHED_DIR / file_path.name
    pushed_marker.write_text(datetime.now().isoformat())


def main():
    parser = argparse.ArgumentParser(description="Push posts to NocoDB")
    parser.add_argument("--file", type=str, help="Specific processed file to push")
    parser.add_argument("--all-unpushed", action="store_true", help="Push all unpushed files")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually push, just show what would be pushed")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("PUSH ONLY - NocoDB Upload")
    logger.info("=" * 50)

    DATA_DIR.mkdir(exist_ok=True)

    # Determine which files to push
    if args.file:
        files_to_push = [Path(args.file)]
    elif args.all_unpushed:
        files_to_push = find_unpushed_files()
        if not files_to_push:
            logger.info("No unpushed files found!")
            return
    else:
        latest = find_latest_processed_file()
        if not latest:
            logger.error("No processed_posts_*.json files found in data/")
            logger.info("Run process_only.py first!")
            return
        files_to_push = [latest]

    total_stats = {"pushed": 0, "skipped": 0, "errors": 0}

    for input_file in files_to_push:
        logger.info(f"\nPushing: {input_file}")

        # Load processed posts
        with open(input_file, "r", encoding="utf-8") as f:
            posts = json.load(f)

        logger.info(f"Loaded {len(posts)} posts")

        if not posts:
            continue

        if args.dry_run:
            logger.info(f"[DRY RUN] Would push {len(posts)} posts")
            continue

        # Push to DB
        stats = push_posts_to_db(posts)

        # Mark as pushed
        mark_as_pushed(input_file)

        logger.info(f"Stats: pushed={stats['pushed']}, skipped={stats['skipped']}, errors={stats['errors']}")

        for key in total_stats:
            total_stats[key] += stats[key]

    logger.info("\n" + "=" * 50)
    logger.info("TOTAL STATS")
    logger.info(f"  Pushed: {total_stats['pushed']}")
    logger.info(f"  Skipped: {total_stats['skipped']}")
    logger.info(f"  Errors: {total_stats['errors']}")


if __name__ == "__main__":
    main()
