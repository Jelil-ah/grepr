"""
Enrich existing posts in NocoDB with extracted financial data.
Reads from raw files and updates DB records.
"""
import json
import requests
import os
from pathlib import Path
from dotenv import load_dotenv
from ai_processor import extract_financial_data
from config import logger

load_dotenv()

DATA_DIR = Path(__file__).parent / "data" / "raw"
NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL")
NOCODB_API_TOKEN = os.getenv("NOCODB_API_TOKEN")
NOCODB_TABLE_ID = os.getenv("NOCODB_TABLE_ID")


def load_all_raw_posts() -> dict:
    """Load all posts from raw files, indexed by reddit_id."""
    all_posts = {}

    for file_path in DATA_DIR.glob("*.json"):
        logger.info(f"Loading {file_path.name}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle different file formats
        if isinstance(data, dict) and "posts" in data:
            posts = data["posts"]
        elif isinstance(data, list):
            posts = data
        else:
            continue

        for post in posts:
            reddit_id = post.get("id")
            if reddit_id and reddit_id not in all_posts:
                all_posts[reddit_id] = post

    return all_posts


def get_db_posts_needing_update() -> list:
    """Get posts from DB that need enrichment (missing extracted_data)."""
    url = f"{NOCODB_BASE_URL}/api/v2/tables/{NOCODB_TABLE_ID}/records"
    headers = {"xc-token": NOCODB_API_TOKEN}

    all_records = []
    offset = 0
    limit = 100

    while True:
        params = {"limit": limit, "offset": offset}
        r = requests.get(url, headers=headers, params=params)
        data = r.json()

        records = data.get("list", [])
        if not records:
            break

        all_records.extend(records)
        offset += limit

        if len(records) < limit:
            break

    # Filter records needing update (no extracted_data or no montant_max)
    needs_update = [
        r for r in all_records
        if not r.get("extracted_data") or not r.get("montant_max")
    ]

    return needs_update


def update_db_post(record_id: int, data: dict) -> bool:
    """Update a post in NocoDB."""
    url = f"{NOCODB_BASE_URL}/api/v2/tables/{NOCODB_TABLE_ID}/records"
    headers = {
        "xc-token": NOCODB_API_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {"Id": record_id, **data}
    r = requests.patch(url, headers=headers, json=payload)
    return r.status_code == 200


def main():
    logger.info("=" * 50)
    logger.info("ENRICHING EXISTING POSTS")
    logger.info("=" * 50)

    # Load all raw posts
    raw_posts = load_all_raw_posts()
    logger.info(f"Loaded {len(raw_posts)} unique posts from raw files")

    # Get DB posts needing update
    db_posts = get_db_posts_needing_update()
    logger.info(f"Found {len(db_posts)} posts in DB needing enrichment")

    stats = {"updated": 0, "skipped": 0, "not_found": 0}

    for db_post in db_posts:
        reddit_id = db_post.get("reddit_id")
        record_id = db_post.get("Id")
        title = db_post.get("title", "")[:40]

        # Find raw post
        raw_post = raw_posts.get(reddit_id)
        if not raw_post:
            logger.warning(f"  [{record_id}] Not found in raw: {reddit_id}")
            stats["not_found"] += 1
            continue

        # Build full text for extraction
        full_text = " ".join([
            raw_post.get("title", ""),
            raw_post.get("selftext", ""),
            raw_post.get("comment_body", "")
        ])

        if not full_text.strip():
            stats["skipped"] += 1
            continue

        # Extract financial data
        extracted = extract_financial_data(full_text)

        # Prepare update data
        amounts = extracted.get("amounts", [])
        update_data = {
            "selftext": (raw_post.get("selftext") or "")[:5000],  # Truncate if needed
            "top_comment": (raw_post.get("comment_body") or "")[:2000],
            "comment_score": raw_post.get("comment_score"),
            "extracted_data": json.dumps(extracted, ensure_ascii=False),
            "patrimoine": extracted.get("patrimoine"),
            "revenus_annuels": extracted.get("revenus_annuels"),
            "age_auteur": extracted.get("age"),
            "montant_max": max(amounts) if amounts else None
        }

        # Update DB
        if update_db_post(record_id, update_data):
            stats["updated"] += 1
            amounts_str = amounts[:3] if amounts else []
            logger.info(f"  [{stats['updated']}] Updated: {title}... | {amounts_str}")
        else:
            logger.error(f"  Failed to update {record_id}")

    logger.info("\n" + "=" * 50)
    logger.info("DONE")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Not found: {stats['not_found']}")


if __name__ == "__main__":
    main()
