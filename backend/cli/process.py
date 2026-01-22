"""
STEP 2: Process raw posts with AI (categorize + summarize)
Reads raw posts JSON, processes with Groq, saves processed posts.

Usage:
    python3 process_only.py                          # Process latest raw file
    python3 process_only.py --file data/raw_posts_xxx.json  # Process specific file
    python3 process_only.py --batch 10               # Process in batches of 10
"""
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from backend.processors.ai import categorize_and_summarize, extract_financial_data
from backend.config import logger

# Configuration
DATA_DIR = Path(__file__).parent / "data"
GROQ_DELAY = 3.0  # Seconds between Groq API calls (conservative for free tier)
GROQ_DELAY_AFTER_429 = 60.0  # Wait 1 minute after rate limit
MAX_RETRIES = 3


def find_latest_raw_file() -> Path | None:
    """Find the most recent raw_posts_*.json file."""
    DATA_DIR.mkdir(exist_ok=True)
    files = list(DATA_DIR.glob("raw_posts_*.json"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def find_unprocessed_files() -> list[Path]:
    """Find raw files that haven't been processed yet."""
    DATA_DIR.mkdir(exist_ok=True)
    raw_files = set(DATA_DIR.glob("raw_posts_*.json"))
    processed_files = set(DATA_DIR.glob("processed_posts_*.json"))

    # Extract timestamps from processed files
    processed_timestamps = set()
    for pf in processed_files:
        # processed_posts_20240121_120000_from_raw_posts_20240121_115500.json
        name = pf.stem
        if "_from_" in name:
            source = name.split("_from_")[1]
            processed_timestamps.add(source)

    # Find raw files not yet processed
    unprocessed = []
    for rf in raw_files:
        if rf.stem not in processed_timestamps:
            unprocessed.append(rf)

    return sorted(unprocessed, key=lambda f: f.stat().st_mtime)


def process_posts_with_retry(posts: list[dict], batch_size: int = 10) -> list[dict]:
    """
    Process posts with AI, handling rate limits gracefully.
    Saves progress after each batch.
    """
    processed = []
    total = len(posts)
    consecutive_429s = 0

    for i, post in enumerate(posts):
        logger.info(f"Processing [{i+1}/{total}]: {post.get('title', '')[:50]}...")

        retries = 0
        while retries < MAX_RETRIES:
            try:
                # Categorize and summarize
                enriched = categorize_and_summarize(post.copy())

                # Extract financial data (always works, no API)
                full_text = f"{post.get('title', '')} {post.get('selftext', '')} {post.get('comment_body', '')}"
                enriched["extracted_data"] = extract_financial_data(full_text)

                processed.append(enriched)
                consecutive_429s = 0  # Reset counter

                logger.info(f"  -> {enriched.get('category', 'Autre')} | {enriched.get('extracted_data', {}).get('amounts', [])}")
                break

            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    consecutive_429s += 1
                    wait_time = GROQ_DELAY_AFTER_429 * consecutive_429s
                    logger.warning(f"  Rate limited! Waiting {wait_time}s (429 count: {consecutive_429s})")
                    time.sleep(wait_time)
                    retries += 1
                else:
                    logger.error(f"  Error: {e}")
                    # Still add post with default category
                    post["category"] = "Autre"
                    post["extracted_data"] = extract_financial_data(
                        f"{post.get('title', '')} {post.get('selftext', '')}"
                    )
                    processed.append(post)
                    break

        # Delay between calls
        time.sleep(GROQ_DELAY)

        # Progress save every batch_size posts
        if (i + 1) % batch_size == 0:
            logger.info(f"  Checkpoint: {i+1}/{total} processed")

    return processed


def main():
    parser = argparse.ArgumentParser(description="Process posts with AI")
    parser.add_argument("--file", type=str, help="Specific raw file to process")
    parser.add_argument("--batch", type=int, default=10, help="Batch size for checkpoints")
    parser.add_argument("--all-unprocessed", action="store_true", help="Process all unprocessed files")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("PROCESS ONLY - AI Categorization")
    logger.info("=" * 50)

    DATA_DIR.mkdir(exist_ok=True)

    # Determine which files to process
    if args.file:
        files_to_process = [Path(args.file)]
    elif args.all_unprocessed:
        files_to_process = find_unprocessed_files()
        if not files_to_process:
            logger.info("No unprocessed files found!")
            return
    else:
        latest = find_latest_raw_file()
        if not latest:
            logger.error("No raw_posts_*.json files found in data/")
            logger.info("Run fetch_only.py first!")
            return
        files_to_process = [latest]

    for input_file in files_to_process:
        logger.info(f"\nProcessing: {input_file}")

        # Load raw posts
        with open(input_file, "r", encoding="utf-8") as f:
            posts = json.load(f)

        logger.info(f"Loaded {len(posts)} posts")

        if not posts:
            continue

        # Process with AI
        processed = process_posts_with_retry(posts, batch_size=args.batch)

        # Save processed posts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = DATA_DIR / f"processed_posts_{timestamp}_from_{input_file.stem}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(processed)} processed posts to {output_file}")

        # Stats
        categories = {}
        for p in processed:
            cat = p.get("category", "Autre")
            categories[cat] = categories.get(cat, 0) + 1

        logger.info("Categories distribution:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            logger.info(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
