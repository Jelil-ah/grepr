"""
Reddit Fetcher - Fetch posts using official Reddit API (PRAW) or public .json fallback
"""
import requests
import time
from datetime import datetime
from typing import Generator
from config import (
    SUBREDDITS, MIN_SCORE, POSTS_PER_REQUEST, TIME_FILTER, USER_AGENT,
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_API_ENABLED,
    logger
)

# Try to import PRAW
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed. Run: pip install praw")

# Global Reddit instance (lazy initialized)
_reddit_instance = None


def get_reddit_client():
    """Get or create Reddit API client (PRAW)."""
    global _reddit_instance

    if not REDDIT_API_ENABLED or not PRAW_AVAILABLE:
        return None

    if _reddit_instance is None:
        try:
            _reddit_instance = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT,
            )
            # Test connection
            _reddit_instance.user.me()  # Will raise if not authenticated
            logger.info("Reddit API connected successfully (read-only mode)")
        except Exception as e:
            logger.warning(f"Reddit API auth failed, falling back to public API: {e}")
            return None

    return _reddit_instance


def fetch_subreddit_posts_praw(subreddit: str, time_filter: str = TIME_FILTER, limit: int = POSTS_PER_REQUEST) -> Generator[dict, None, None]:
    """
    Fetch posts from a subreddit using official Reddit API (PRAW).
    Yields posts one by one.
    """
    reddit = get_reddit_client()
    if not reddit:
        # Fallback to public API
        yield from fetch_subreddit_posts_public(subreddit, time_filter, limit)
        return

    try:
        sub = reddit.subreddit(subreddit)
        total_fetched = 0

        # Get top posts with time filter
        for post in sub.top(time_filter=time_filter, limit=limit):
            if post.score >= MIN_SCORE:
                created_at = datetime.utcfromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S")

                yield {
                    "id": post.id,
                    "subreddit": subreddit,
                    "title": post.title,
                    "selftext": (post.selftext or "")[:2000],
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "created_utc": post.created_utc,
                    "created_at": created_at,
                    "url": f"https://reddit.com{post.permalink}",
                    "author": str(post.author) if post.author else "[deleted]",
                    "upvote_ratio": post.upvote_ratio,
                }
                total_fetched += 1

        logger.info(f"Fetched {total_fetched} posts from r/{subreddit} via PRAW (score >= {MIN_SCORE})")

    except Exception as e:
        logger.error(f"PRAW error for r/{subreddit}: {e}")
        # Fallback to public API
        yield from fetch_subreddit_posts_public(subreddit, time_filter, limit)


def fetch_top_comment_praw(post_id: str, subreddit: str) -> dict | None:
    """
    Fetch the top comment for a specific post using PRAW.
    """
    reddit = get_reddit_client()
    if not reddit:
        return fetch_top_comment_public(post_id, subreddit)

    try:
        submission = reddit.submission(id=post_id)
        submission.comment_sort = "top"
        submission.comments.replace_more(limit=0)  # Don't expand "more comments"

        if submission.comments:
            top_comment = submission.comments[0]
            return {
                "comment_id": top_comment.id,
                "comment_body": (top_comment.body or "")[:1000],
                "comment_score": top_comment.score,
                "comment_author": str(top_comment.author) if top_comment.author else "[deleted]",
            }
    except Exception as e:
        logger.debug(f"Error fetching comment for {post_id}: {e}")

    return None


# ============ PUBLIC API FALLBACK ============

def fetch_subreddit_posts_public(subreddit: str, time_filter: str = TIME_FILTER, limit: int = POSTS_PER_REQUEST) -> Generator[dict, None, None]:
    """
    Fetch posts from a subreddit using public .json endpoint (no auth).
    Yields posts one by one, handling pagination automatically.
    """
    base_url = f"https://www.reddit.com/r/{subreddit}/top/.json"
    headers = {"User-Agent": USER_AGENT}
    after = None
    total_fetched = 0

    while total_fetched < limit:
        params = {
            "t": time_filter,
            "limit": min(limit - total_fetched, 100),
            "raw_json": 1
        }
        if after:
            params["after"] = after

        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching r/{subreddit}: {e}")
            break

        posts = data.get("data", {}).get("children", [])
        if not posts:
            break

        for post in posts:
            post_data = post.get("data", {})
            score = post_data.get("score", 0)

            if score >= MIN_SCORE:
                created_utc = post_data.get("created_utc", 0)
                created_at = datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%d %H:%M:%S") if created_utc else None

                yield {
                    "id": post_data.get("id"),
                    "subreddit": subreddit,
                    "title": post_data.get("title"),
                    "selftext": post_data.get("selftext", "")[:2000],
                    "score": score,
                    "num_comments": post_data.get("num_comments", 0),
                    "created_utc": created_utc,
                    "created_at": created_at,
                    "url": f"https://reddit.com{post_data.get('permalink')}",
                    "author": post_data.get("author"),
                    "upvote_ratio": post_data.get("upvote_ratio", 0),
                }
                total_fetched += 1

        after = data.get("data", {}).get("after")
        if not after:
            break

        time.sleep(1)  # Rate limiting

    logger.info(f"Fetched {total_fetched} posts from r/{subreddit} via public API (score >= {MIN_SCORE})")


def fetch_top_comment_public(post_id: str, subreddit: str) -> dict | None:
    """
    Fetch the top comment for a specific post using public .json endpoint.
    """
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/.json"
    headers = {"User-Agent": USER_AGENT}
    params = {"limit": 1, "sort": "top", "raw_json": 1}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if len(data) > 1:
            comments = data[1].get("data", {}).get("children", [])
            if comments and comments[0].get("kind") == "t1":
                comment_data = comments[0].get("data", {})
                return {
                    "comment_id": comment_data.get("id"),
                    "comment_body": comment_data.get("body", "")[:1000],
                    "comment_score": comment_data.get("score", 0),
                    "comment_author": comment_data.get("author"),
                }
    except requests.RequestException as e:
        logger.debug(f"Error fetching comments for {post_id}: {e}")

    return None


# ============ MAIN API ============

def fetch_subreddit_posts(subreddit: str, time_filter: str = TIME_FILTER, limit: int = POSTS_PER_REQUEST) -> Generator[dict, None, None]:
    """
    Fetch posts from a subreddit.
    Automatically uses PRAW if available, otherwise falls back to public API.
    """
    if REDDIT_API_ENABLED and PRAW_AVAILABLE:
        yield from fetch_subreddit_posts_praw(subreddit, time_filter, limit)
    else:
        yield from fetch_subreddit_posts_public(subreddit, time_filter, limit)


def fetch_top_comment(post_id: str, subreddit: str) -> dict | None:
    """
    Fetch the top comment for a specific post.
    Automatically uses PRAW if available, otherwise falls back to public API.
    """
    if REDDIT_API_ENABLED and PRAW_AVAILABLE:
        return fetch_top_comment_praw(post_id, subreddit)
    else:
        return fetch_top_comment_public(post_id, subreddit)


def fetch_all_posts(with_comments: bool = True, limit_per_sub: int = POSTS_PER_REQUEST) -> list[dict]:
    """
    Fetch all posts from all configured subreddits.
    Optionally includes top comment for each post.

    Args:
        with_comments: Whether to fetch top comment for each post
        limit_per_sub: Max posts per subreddit
    """
    all_posts = []

    # Log which API we're using
    if REDDIT_API_ENABLED and PRAW_AVAILABLE:
        logger.info("Using Reddit Official API (PRAW)")
    else:
        logger.info("Using Reddit Public API (.json endpoint)")

    for subreddit in SUBREDDITS:
        logger.info(f"\nFetching r/{subreddit}...")

        for post in fetch_subreddit_posts(subreddit, limit=limit_per_sub):
            if with_comments:
                top_comment = fetch_top_comment(post["id"], subreddit)
                if top_comment:
                    post.update(top_comment)
                time.sleep(0.3 if REDDIT_API_ENABLED else 0.5)

            all_posts.append(post)

    logger.info(f"\nTotal: {len(all_posts)} posts fetched from {len(SUBREDDITS)} subreddits")
    return all_posts


def fetch_new_posts(since_hours: int = 24, with_comments: bool = True) -> list[dict]:
    """
    Fetch only new posts from the last N hours.
    Useful for incremental updates.
    """
    all_posts = []
    cutoff_time = time.time() - (since_hours * 3600)

    for subreddit in SUBREDDITS:
        logger.info(f"Fetching new posts from r/{subreddit} (last {since_hours}h)...")

        for post in fetch_subreddit_posts(subreddit, time_filter="day", limit=100):
            if post.get("created_utc", 0) >= cutoff_time:
                if with_comments:
                    top_comment = fetch_top_comment(post["id"], subreddit)
                    if top_comment:
                        post.update(top_comment)
                    time.sleep(0.3)
                all_posts.append(post)

    logger.info(f"Found {len(all_posts)} new posts in the last {since_hours} hours")
    return all_posts


# Test
if __name__ == "__main__":
    print("Testing reddit_fetcher...")
    print(f"PRAW available: {PRAW_AVAILABLE}")
    print(f"Reddit API enabled: {REDDIT_API_ENABLED}")

    # Quick test - fetch first 5 posts
    for i, post in enumerate(fetch_subreddit_posts("vosfinances", limit=10)):
        print(f"\n{i+1}. [{post['score']}] {post['title'][:60]}...")
        if i >= 4:
            break
