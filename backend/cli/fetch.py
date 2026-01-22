"""
STEP 1: Fetch Reddit posts only (no AI, no DB push)
Saves raw posts to JSON file for later processing.

Usage:
    python3 fetch_only.py              # Fetch today's posts
    python3 fetch_only.py --all        # Fetch all time periods
    python3 fetch_only.py --period week # Fetch specific period
"""
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from backend.fetchers.reddit import fetch_subreddit_posts, fetch_top_comment
from backend.db.nocodb import get_existing_post_ids
from backend.config import SUBREDDITS, logger

# Configuration
OUTPUT_DIR = Path(__file__).parent / "data"
REDDIT_DELAY = 2.0  # Seconds between Reddit requests (be nice)
MAX_POSTS_PER_SUBREDDIT = 100  # Per run

TIME_PERIODS = ["day", "week", "month", "year", "all"]


def fetch_and_save(time_filter: str = "day", skip_existing: bool = True) -> dict:
    """
    Fetch posts from Reddit and save to JSON file.
    Returns stats dict.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Get existing IDs to skip
    existing_ids = get_existing_post_ids() if skip_existing else set()
    logger.info(f"Skipping {len(existing_ids)} existing posts")

    all_posts = []
    stats = {"fetched": 0, "skipped": 0, "errors": 0}

    for subreddit in SUBREDDITS:
        logger.info(f"Fetching r/{subreddit} ({time_filter})...")

        try:
            posts = list(fetch_subreddit_posts(
                subreddit,
                time_filter=time_filter,
                limit=MAX_POSTS_PER_SUBREDDIT
            ))
            logger.info(f"  Got {len(posts)} posts from API")

            for post in posts:
                if post["id"] in existing_ids:
                    stats["skipped"] += 1
                    continue

                # Fetch top comment (with delay)
                time.sleep(REDDIT_DELAY)
                try:
                    top_comment = fetch_top_comment(post["id"], subreddit)
                    if top_comment:
                        post.update(top_comment)
                except Exception as e:
                    logger.warning(f"  Comment fetch failed for {post['id']}: {e}")

                all_posts.append(post)
                existing_ids.add(post["id"])  # Don't fetch same post twice
                stats["fetched"] += 1

                logger.info(f"  [{stats['fetched']}] {post['title'][:50]}...")

        except Exception as e:
            logger.error(f"  Error fetching r/{subreddit}: {e}")
            stats["errors"] += 1

    # Save to file
    if all_posts:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"raw_posts_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_posts, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(all_posts)} posts to {output_file}")
        stats["output_file"] = str(output_file)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Fetch Reddit posts")
    parser.add_argument("--period", choices=TIME_PERIODS, default="day",
                       help="Time period to fetch")
    parser.add_argument("--all", action="store_true",
                       help="Fetch all time periods")
    parser.add_argument("--no-skip", action="store_true",
                       help="Don't skip existing posts")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("FETCH ONLY - Reddit Posts")
    logger.info("=" * 50)

    if args.all:
        for period in TIME_PERIODS:
            logger.info(f"\n--- Period: {period} ---")
            stats = fetch_and_save(period, skip_existing=not args.no_skip)
            logger.info(f"Stats: {stats}")
            time.sleep(5)  # Pause between periods
    else:
        stats = fetch_and_save(args.period, skip_existing=not args.no_skip)
        logger.info(f"Stats: {stats}")


if __name__ == "__main__":
    main()
