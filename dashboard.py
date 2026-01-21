"""
Grepr Dashboard - Visualize Reddit finance posts
"""
import streamlit as st
import requests
import pandas as pd
from config import NOCODB_BASE_URL, NOCODB_API_TOKEN, NOCODB_TABLE_ID

st.set_page_config(
    page_title="Grepr - Reddit Finance",
    page_icon="📊",
    layout="wide"
)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_posts():
    """Fetch all posts from NocoDB."""
    if not NOCODB_API_TOKEN or not NOCODB_TABLE_ID:
        return []

    url = f"{NOCODB_BASE_URL}/api/v2/tables/{NOCODB_TABLE_ID}/records"
    headers = {"xc-token": NOCODB_API_TOKEN}
    all_posts = []
    offset = 0

    while True:
        params = {"limit": 1000, "offset": offset}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            break
        data = response.json()
        records = data.get("list", [])
        if not records:
            break
        all_posts.extend(records)
        if len(records) < 1000:
            break
        offset += 1000

    return all_posts


def main():
    st.title("📊 Grepr - Reddit Finance Aggregator")
    st.markdown("*Conseils financiers agrégés de r/vosfinances*")

    # Fetch data
    posts = fetch_posts()

    if not posts:
        st.warning("Aucun post trouvé. Lancez `python main.py` pour récupérer des posts.")
        return

    df = pd.DataFrame(posts)

    # Ensure required columns exist with defaults
    for col, default in [("num_comments", 0), ("consensus", ""), ("key_advice", ""), ("top_comment", ""), ("comment_score", 0)]:
        if col not in df.columns:
            df[col] = default

    # Sidebar filters
    st.sidebar.header("Filtres")

    # Category filter
    categories = ["Tous"] + sorted(df["category"].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox("Catégorie", categories)

    # Consensus filter
    consensus_vals = df["consensus"].dropna().unique().tolist()
    consensus_vals = [c for c in consensus_vals if c]  # Remove empty strings
    consensus_options = ["Tous"] + sorted(consensus_vals) if consensus_vals else ["Tous"]
    selected_consensus = st.sidebar.selectbox("Consensus", consensus_options)

    # Score filter
    min_score = st.sidebar.slider("Score minimum", 0, int(df["score"].max()), 10)

    # Apply filters
    filtered_df = df.copy()
    if selected_category != "Tous":
        filtered_df = filtered_df[filtered_df["category"] == selected_category]
    if selected_consensus != "Tous":
        filtered_df = filtered_df[filtered_df["consensus"] == selected_consensus]
    filtered_df = filtered_df[filtered_df["score"] >= min_score]

    # Sort by score
    filtered_df = filtered_df.sort_values("score", ascending=False)

    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Posts", len(filtered_df))
    with col2:
        st.metric("Score Moyen", f"{filtered_df['score'].mean():.0f}")
    with col3:
        st.metric("Commentaires Moyens", f"{filtered_df['num_comments'].mean():.0f}")
    with col4:
        top_category = filtered_df["category"].mode().iloc[0] if len(filtered_df) > 0 else "N/A"
        st.metric("Top Catégorie", top_category)

    st.divider()

    # Category distribution
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("📈 Par Catégorie")
        category_counts = filtered_df["category"].value_counts()
        st.bar_chart(category_counts)

    with col_right:
        st.subheader("🏷️ Tags Populaires")
        all_tags = []
        for tags in filtered_df["tags"].dropna():
            if isinstance(tags, str):
                all_tags.extend([t.strip() for t in tags.split(",")])
        if all_tags:
            tag_counts = pd.Series(all_tags).value_counts().head(10)
            st.bar_chart(tag_counts)

    st.divider()

    # Posts list
    st.subheader(f"📝 Posts ({len(filtered_df)})")

    for _, post in filtered_df.iterrows():
        with st.container():
            # Header with score and category
            col1, col2, col3 = st.columns([1, 8, 2])
            with col1:
                st.markdown(f"### ⬆️ {post.get('score', 0)}")
            with col2:
                st.markdown(f"### [{post.get('title', 'Sans titre')}]({post.get('url', '#')})")
                st.caption(f"r/{post.get('subreddit', '?')} • {post.get('num_comments', 0)} commentaires • {post.get('created_a', '')}")
            with col3:
                category = post.get('category', 'Autre')
                consensus = post.get('consensus', '')
                st.markdown(f"**{category}**")
                if consensus:
                    emoji = {"fort": "🟢", "moyen": "🟡", "faible": "🟠", "divisé": "🔴"}.get(consensus.lower(), "⚪")
                    st.caption(f"{emoji} {consensus}")

            # Summary and key advice
            if post.get('summary'):
                st.info(f"**Résumé:** {post.get('summary')}")
            if post.get('key_advice'):
                st.success(f"**Conseil clé:** {post.get('key_advice')}")

            # Tags
            if post.get('tags'):
                tags = post.get('tags', '').split(',')
                st.markdown(" ".join([f"`{t.strip()}`" for t in tags if t.strip()]))

            # Top comment
            if post.get('top_comment'):
                with st.expander("💬 Top commentaire"):
                    st.markdown(f"> {post.get('top_comment')}")
                    st.caption(f"Score: {post.get('comment_score', 0)}")

            st.divider()


if __name__ == "__main__":
    main()
