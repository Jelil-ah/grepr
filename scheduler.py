"""
Grepr Scheduler - Automated daily fetching with progress tracking
Fetches posts incrementally going back 2-3 years, then continues daily.
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from backend.fetchers.reddit import fetch_subreddit_posts, fetch_top_comment
from backend.processors.ai import process_posts
from backend.db.nocodb import push_posts, get_existing_post_ids
from backend.config import SUBREDDITS, logger

# Configuration
POSTS_PER_DAY_PER_SUBREDDIT = 500  # Max posts per subreddit per day
PROGRESS_FILE = Path(__file__).parent / "scheduler_progress.json"
AI_DELAY = 2.0  # Seconds between AI API calls (conservative for free tier)
TARGET_YEARS_BACK = 1  # Fetch posts up to 1 year back (changed from 3)

# Time periods for historical fetch (from newest to oldest)
# Limited to 1 year of data
TIME_PERIODS = [
    ("day", "Last 24 hours"),
    ("week", "Last week"),
    ("month", "Last month"),
    ("year", "Last year"),
]


def load_progress() -> dict:
    """Load progress from file or return default."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "last_run": None,
        "current_period_index": 0,
        "total_fetched": 0,
        "subreddit_progress": {sub: {"fetched": 0, "period_index": 0} for sub in SUBREDDITS}
    }


def save_progress(progress: dict):
    """Save progress to file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def fetch_batch(subreddit: str, time_filter: str, limit: int, existing_ids: set) -> list[dict]:
    """
    Fetch a batch of posts from a subreddit, filtering out already existing ones.
    Returns list of new posts.
    """
    new_posts = []
    for post in fetch_subreddit_posts(subreddit, time_filter=time_filter, limit=limit):
        # Skip if we already have this post
        if post["id"] in existing_ids:
            continue

        # Fetch top comment
        top_comment = fetch_top_comment(post["id"], subreddit)
        if top_comment:
            post.update(top_comment)

        new_posts.append(post)
        time.sleep(0.5)  # Rate limit for Reddit

        # Stop if we've reached our batch limit
        if len(new_posts) >= limit:
            break

    return new_posts


def run_scheduler(dry_run: bool = False):
    """
    Main scheduler function. Call this daily (via cron or manually).
    Fetches up to POSTS_PER_DAY_PER_SUBREDDIT new posts per subreddit.
    """
    progress = load_progress()
    today = datetime.now().strftime("%Y-%m-%d")

    # Check if we already ran today
    if progress["last_run"] == today:
        logger.info(f"Already ran today ({today}). Skipping.")
        return

    logger.info("=" * 50)
    logger.info("🚀 GREPR SCHEDULER")
    logger.info("=" * 50)
    logger.info(f"Date: {today}")
    logger.info(f"Posts per subreddit: {POSTS_PER_DAY_PER_SUBREDDIT}")

    # Get existing post IDs from NocoDB
    existing_ids = get_existing_post_ids()
    logger.info(f"Existing posts in DB: {len(existing_ids)}")

    all_new_posts = []

    for subreddit in SUBREDDITS:
        logger.info(f"\n📥 Processing r/{subreddit}...")

        sub_progress = progress["subreddit_progress"].get(subreddit, {"fetched": 0, "period_index": 0})
        period_index = sub_progress["period_index"]

        posts_fetched_today = 0

        # Try fetching from current period, then move to older periods
        while posts_fetched_today < POSTS_PER_DAY_PER_SUBREDDIT and period_index < len(TIME_PERIODS):
            time_filter, period_name = TIME_PERIODS[period_index]
            remaining = POSTS_PER_DAY_PER_SUBREDDIT - posts_fetched_today

            logger.info(f"  Fetching from {period_name} (time_filter={time_filter})...")

            new_posts = fetch_batch(
                subreddit,
                time_filter=time_filter,
                limit=remaining,
                existing_ids=existing_ids
            )

            if new_posts:
                logger.info(f"  Found {len(new_posts)} new posts")
                all_new_posts.extend(new_posts)
                posts_fetched_today += len(new_posts)

                # Add to existing_ids to avoid duplicates
                for post in new_posts:
                    existing_ids.add(post["id"])
            else:
                logger.info(f"  No new posts found, moving to older period...")
                period_index += 1

        # Update progress for this subreddit
        progress["subreddit_progress"][subreddit] = {
            "fetched": sub_progress["fetched"] + posts_fetched_today,
            "period_index": period_index
        }

        logger.info(f"  Total fetched today from r/{subreddit}: {posts_fetched_today}")

    # Process with AI
    if all_new_posts and not dry_run:
        logger.info(f"\n🤖 Processing {len(all_new_posts)} posts with AI...")
        processed_posts = process_posts(all_new_posts, delay_between_calls=AI_DELAY)

        # Push to NocoDB
        logger.info(f"\n📤 Pushing to NocoDB...")
        stats = push_posts(processed_posts)
        logger.info(f"  Pushed: {stats['pushed']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")

    # Update and save progress
    progress["last_run"] = today
    progress["total_fetched"] += len(all_new_posts)
    save_progress(progress)

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 SUMMARY")
    logger.info("=" * 50)
    logger.info(f"New posts fetched today: {len(all_new_posts)}")
    logger.info(f"Total posts fetched all time: {progress['total_fetched']}")

    for sub, sub_prog in progress["subreddit_progress"].items():
        period_idx = sub_prog["period_index"]
        if period_idx < len(TIME_PERIODS):
            current_period = TIME_PERIODS[period_idx][1]
        else:
            current_period = "Completed all periods"
        logger.info(f"  r/{sub}: {sub_prog['fetched']} total, currently at '{current_period}'")


def reset_progress():
    """Reset progress to start fresh."""
    if PROGRESS_FILE.exists():
        os.remove(PROGRESS_FILE)
        logger.info("Progress reset. Next run will start fresh.")
    else:
        logger.info("No progress file found.")


def estimate_remaining():
    """
    Estimate how many posts remain to fetch to cover 1 year of data.
    Returns dict with estimates per subreddit.
    """
    progress = load_progress()
    existing_count = len(get_existing_post_ids())

    # Rough estimates based on subreddit activity (1 year)
    # vosfinances: ~15-20 posts/day with score > 10 = ~5500-7300/year
    # vossous: ~5-10 posts/day with score > 10 = ~1800-3650/year
    estimated_totals = {
        "vosfinances": 6000,   # Conservative estimate for 1 year
        "vossous": 2500,       # Conservative estimate for 1 year
    }

    estimates = {}
    total_estimated = 0
    total_remaining = 0

    for sub in SUBREDDITS:
        sub_prog = progress["subreddit_progress"].get(sub, {"fetched": 0, "period_index": 0})
        estimated = estimated_totals.get(sub, 10000)
        fetched = sub_prog["fetched"]
        remaining = max(0, estimated - fetched)
        period_idx = sub_prog["period_index"]

        if period_idx >= len(TIME_PERIODS):
            remaining = 0  # All periods completed

        estimates[sub] = {
            "fetched": fetched,
            "estimated_total": estimated,
            "remaining": remaining,
            "period_index": period_idx,
            "days_to_complete": remaining // POSTS_PER_DAY_PER_SUBREDDIT + (1 if remaining % POSTS_PER_DAY_PER_SUBREDDIT else 0)
        }
        total_estimated += estimated
        total_remaining += remaining

    return {
        "existing_in_db": existing_count,
        "total_estimated": total_estimated,
        "total_remaining": total_remaining,
        "days_to_complete": total_remaining // (POSTS_PER_DAY_PER_SUBREDDIT * len(SUBREDDITS)) + 1,
        "subreddits": estimates
    }


def status():
    """Show current progress status with remaining estimates."""
    progress = load_progress()
    estimates = estimate_remaining()

    print("\n" + "=" * 50)
    print("📊 GREPR SCHEDULER STATUS")
    print("=" * 50)
    print(f"Last run: {progress['last_run'] or 'Never'}")
    print(f"Total fetched by scheduler: {progress['total_fetched']}")
    print(f"Total posts in database: {estimates['existing_in_db']}")

    print("\n📈 PROGRESS TO 1-YEAR GOAL:")
    print(f"  Estimated total needed: ~{estimates['total_estimated']:,} posts")
    print(f"  Remaining to fetch: ~{estimates['total_remaining']:,} posts")
    print(f"  Days to complete (at {POSTS_PER_DAY_PER_SUBREDDIT * len(SUBREDDITS)}/day): ~{estimates['days_to_complete']} days")

    print("\n📁 Subreddit progress:")
    for sub, sub_est in estimates["subreddits"].items():
        period_idx = sub_est["period_index"]
        if period_idx < len(TIME_PERIODS):
            current_period = TIME_PERIODS[period_idx][1]
        else:
            current_period = "✅ All periods completed"

        pct = (sub_est["fetched"] / sub_est["estimated_total"]) * 100 if sub_est["estimated_total"] > 0 else 0
        bar_len = int(pct / 5)  # 20 char bar
        bar = "█" * bar_len + "░" * (20 - bar_len)

        print(f"\n  r/{sub}:")
        print(f"    [{bar}] {pct:.1f}%")
        print(f"    Fetched: {sub_est['fetched']:,} / ~{sub_est['estimated_total']:,}")
        print(f"    Remaining: ~{sub_est['remaining']:,} posts (~{sub_est['days_to_complete']} days)")
        print(f"    Current period: {current_period}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            status()
        elif cmd == "reset":
            reset_progress()
        elif cmd == "dry":
            run_scheduler(dry_run=True)
        else:
            print("Usage: python scheduler.py [status|reset|dry]")
    else:
        run_scheduler()
