"""
Re-categorize posts marked as "Autre" using local LM Studio.
Uses CATEGORY_DESCRIPTIONS from config.py for better classification.
"""
import json
import time
import requests
import os
from dotenv import load_dotenv
from ai_processor import categorize_and_summarize
from config import logger

load_dotenv()

NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL")
NOCODB_API_TOKEN = os.getenv("NOCODB_API_TOKEN")
NOCODB_TABLE_ID = os.getenv("NOCODB_TABLE_ID")


def get_autre_posts() -> list:
    """Get all posts with category 'Autre' from NocoDB."""
    url = f"{NOCODB_BASE_URL}/api/v2/tables/{NOCODB_TABLE_ID}/records"
    headers = {"xc-token": NOCODB_API_TOKEN}
    all_records = []
    offset = 0

    while True:
        params = {"limit": 100, "offset": offset, "where": "(category,eq,Autre)"}
        r = requests.get(url, headers=headers, params=params)
        records = r.json().get("list", [])
        if not records:
            break
        all_records.extend(records)
        offset += 100
        if len(records) < 100:
            break

    return all_records


def update_post(record_id: int, data: dict) -> bool:
    """Update a post in NocoDB."""
    url = f"{NOCODB_BASE_URL}/api/v2/tables/{NOCODB_TABLE_ID}/records"
    headers = {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}
    payload = {"Id": record_id, **data}
    r = requests.patch(url, headers=headers, json=payload)
    return r.status_code == 200


def main():
    logger.info("=" * 50)
    logger.info("RE-CATEGORIZING 'AUTRE' POSTS")
    logger.info("=" * 50)

    posts = get_autre_posts()
    logger.info(f"Found {len(posts)} posts with category 'Autre'")

    if not posts:
        return

    stats = {"updated": 0, "still_autre": 0, "failed": 0}
    new_categories = {}

    for i, post in enumerate(posts):
        title = post.get("title", "")[:40]
        record_id = post.get("Id")

        logger.info(f"[{i+1}/{len(posts)}] {title}...")

        # Build post dict for AI
        post_dict = {
            "title": post.get("title", ""),
            "selftext": post.get("selftext", "") or "",
            "comment_body": post.get("top_comment", "") or "",
            "score": post.get("score", 0)
        }

        # Process with local AI
        result = categorize_and_summarize(post_dict)
        new_cat = result.get("category", "Autre")

        new_categories[new_cat] = new_categories.get(new_cat, 0) + 1

        if new_cat == "Autre":
            stats["still_autre"] += 1
            logger.info(f"  -> Still Autre")
            continue

        # Update DB
        update_data = {"category": new_cat}
        if result.get("tags"):
            tags = result["tags"]
            if isinstance(tags, list):
                update_data["tags"] = ", ".join(tags)
        if result.get("summary") and not post.get("summary"):
            update_data["summary"] = result["summary"]

        if update_post(record_id, update_data):
            stats["updated"] += 1
            logger.info(f"  -> {new_cat}")
        else:
            stats["failed"] += 1

        time.sleep(1)  # Delay between AI calls

    logger.info("\n" + "=" * 50)
    logger.info("DONE")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Still Autre: {stats['still_autre']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info("\nNew distribution:")
    for cat, count in sorted(new_categories.items(), key=lambda x: -x[1]):
        logger.info(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
