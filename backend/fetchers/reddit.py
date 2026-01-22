"""
Reddit Fetcher - Fetch posts using .json endpoint (no auth required)
"""
import requests
import time
from datetime import datetime
from typing import Generator
from backend.config import SUBREDDITS, MIN_SCORE, POSTS_PER_REQUEST, TIME_FILTER, USER_AGENT


def fetch_subreddit_posts(subreddit: str, time_filter: str = TIME_FILTER, limit: int = POSTS_PER_REQUEST) -> Generator[dict, None, None]:
    """
    Fetch posts from a subreddit using .json endpoint.
    Yields posts one by one, handling pagination automatically.
    """
    base_url = f"https://www.reddit.com/r/{subreddit}/top/.json"
    headers = {"User-Agent": USER_AGENT}
    after = None
    total_fetched = 0

    while True:
        params = {
            "t": time_filter,
            "limit": min(limit, 100),  # Max 100 per request
            "raw_json": 1  # Get unescaped JSON
        }
        if after:
            params["after"] = after

        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Error fetching r/{subreddit}: {e}")
            break

        posts = data.get("data", {}).get("children", [])
        if not posts:
            break

        for post in posts:
            post_data = post.get("data", {})
            score = post_data.get("score", 0)

            # Filter by minimum score
            if score >= MIN_SCORE:
                # Convert Unix timestamp to readable datetime
                created_utc = post_data.get("created_utc", 0)
                created_at = datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%d %H:%M:%S") if created_utc else None

                yield {
                    "id": post_data.get("id"),
                    "subreddit": subreddit,
                    "title": post_data.get("title"),
                    "selftext": post_data.get("selftext", "")[:2000],  # Limit text length
                    "score": score,
                    "num_comments": post_data.get("num_comments", 0),
                    "created_utc": created_utc,
                    "created_at": created_at,  # Human-readable datetime
                    "url": f"https://reddit.com{post_data.get('permalink')}",
                    "author": post_data.get("author"),
                    "upvote_ratio": post_data.get("upvote_ratio", 0),
                }
                total_fetched += 1

        # Get next page token
        after = data.get("data", {}).get("after")
        if not after:
            break

        # Rate limiting - be nice to Reddit
        time.sleep(1)

    print(f"Fetched {total_fetched} posts from r/{subreddit} (score >= {MIN_SCORE})")


def fetch_top_comment(post_id: str, subreddit: str) -> dict | None:
    """
    Fetch the top comment for a specific post.
    """
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/.json"
    headers = {"User-Agent": USER_AGENT}
    params = {"limit": 1, "sort": "top", "raw_json": 1}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        # Comments are in the second element of the response
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
        print(f"Error fetching comments for {post_id}: {e}")

    return None


def fetch_all_posts(with_comments: bool = True) -> list[dict]:
    """
    Fetch all posts from all configured subreddits.
    Optionally includes top comment for each post.
    """
    all_posts = []

    for subreddit in SUBREDDITS:
        print(f"\nFetching r/{subreddit}...")

        for post in fetch_subreddit_posts(subreddit):
            # Fetch top comment if requested
            if with_comments:
                top_comment = fetch_top_comment(post["id"], subreddit)
                if top_comment:
                    post.update(top_comment)
                time.sleep(0.5)  # Rate limiting for comment requests

            all_posts.append(post)

    print(f"\nTotal: {len(all_posts)} posts fetched")
    return all_posts


# Test
if __name__ == "__main__":
    # Quick test - fetch first 10 posts
    print("Testing reddit_fetcher...")

    for i, post in enumerate(fetch_subreddit_posts("vosfinances", limit=10)):
        print(f"\n{i+1}. [{post['score']}] {post['title'][:60]}...")
        if i >= 4:  # Just show first 5
            break
