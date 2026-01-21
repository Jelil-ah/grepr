"""
Grepr - Reddit Aggregator for Personal Finance
Main orchestration script
"""
import json
from datetime import datetime
from reddit_fetcher import fetch_all_posts
from ai_processor import process_posts, find_similar_posts
from nocodb_client import push_posts
from config import SUBREDDITS, MIN_SCORE, TIME_FILTER


def run_grepr(save_to_file: bool = True, with_ai: bool = True, push_to_nocodb: bool = True):
    """
    Main function to run Grepr pipeline:
    1. Fetch posts from Reddit
    2. Process with AI (categorize, summarize)
    3. Find similar posts for aggregation
    4. Push to NocoDB
    5. Save results to JSON
    """
    print("=" * 50)
    print("🚀 GREPR - Reddit Aggregator")
    print("=" * 50)
    print(f"Subreddits: {', '.join(SUBREDDITS)}")
    print(f"Min score: {MIN_SCORE}")
    print(f"Time filter: {TIME_FILTER}")
    print("=" * 50)

    # Step 1: Fetch posts
    print("\n📥 Step 1: Fetching posts from Reddit...")
    posts = fetch_all_posts(with_comments=True)

    if not posts:
        print("No posts found. Exiting.")
        return

    # Step 2: AI Processing
    if with_ai:
        print("\n🤖 Step 2: Processing with AI...")
        posts = process_posts(posts)
    else:
        print("\n⏭️ Skipping AI processing")

    # Step 3: Find similar posts
    print("\n🔍 Step 3: Grouping similar posts...")
    tag_groups = find_similar_posts(posts)

    # Step 4: Push to NocoDB
    if push_to_nocodb:
        print("\n📤 Step 4: Pushing to NocoDB...")
        stats = push_posts(posts)
        print(f"  Pushed: {stats['pushed']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")
    else:
        print("\n⏭️ Skipping NocoDB push")

    # Print summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"Total posts: {len(posts)}")
    print(f"\nTop tags by frequency:")
    for tag, tag_posts in list(tag_groups.items())[:10]:
        print(f"  • {tag}: {len(tag_posts)} posts")

    # Category breakdown
    categories = {}
    for post in posts:
        cat = post.get("category", "Autre")
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nCategory breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {cat}: {count}")

    # Step 5: Save results
    if save_to_file:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"grepr_output_{timestamp}.json"

        output = {
            "metadata": {
                "generated_at": timestamp,
                "subreddits": SUBREDDITS,
                "min_score": MIN_SCORE,
                "time_filter": TIME_FILTER,
                "total_posts": len(posts)
            },
            "posts": posts,
            "tag_groups": {k: len(v) for k, v in tag_groups.items()}
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Results saved to: {filename}")

    return posts, tag_groups


def quick_test():
    """
    Quick test with limited posts and no AI.
    """
    print("🧪 Running quick test (5 posts, no AI)...")
    from reddit_fetcher import fetch_subreddit_posts

    posts = []
    for post in fetch_subreddit_posts("vosfinances", limit=5):
        posts.append(post)
        print(f"  [{post['score']}] {post['title'][:60]}...")
        if len(posts) >= 5:
            break

    print(f"\n✅ Test complete: {len(posts)} posts fetched")
    return posts


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        quick_test()
    else:
        # Full run
        run_grepr(save_to_file=True, with_ai=True)
