"""
AI Processor for Grepr - Categorize and summarize posts using Groq or DeepSeek API
"""
import json
import re
import time
from openai import OpenAI
from groq import Groq
from backend.config import (
    AI_PROVIDER,
    GROQ_API_KEY, GROQ_MODEL,
    DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL,
    CATEGORIES, CATEGORY_DESCRIPTIONS
)


def extract_financial_data(text: str) -> dict:
    """
    Extract financial amounts, age, and duration from text using regex.
    Returns a dict with extracted data.
    """
    extracted = {
        "amounts": [],           # All monetary amounts found
        "patrimoine": None,      # Net worth if mentioned
        "revenus_annuels": None, # Annual income
        "revenus_mensuels": None,# Monthly income
        "epargne_mensuelle": None, # Monthly savings
        "age": None,             # Person's age
        "duree_annees": None,    # Duration in years
    }

    if not text:
        return extracted

    text_lower = text.lower()

    # Pattern for amounts: 100k€, 100 000€, 100000€, 1M€, etc.
    amount_patterns = [
        # 100k€, 100K€, 1.5M€
        r'(\d+(?:[.,]\d+)?)\s*([kKmM])\s*[€$]',
        # 100 000€, 100000€, 100 000 €
        r'(\d{1,3}(?:[\s\u00a0]\d{3})*)\s*[€$]',
        # 100€, 1000€
        r'(\d+(?:[.,]\d+)?)\s*[€$]',
        # €100, €100k
        r'[€$]\s*(\d+(?:[.,]\d+)?)\s*([kKmM])?',
        # 100 euros, 100 000 euros
        r'(\d{1,3}(?:[\s\u00a0]\d{3})*)\s*euros?',
        r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*euros?',
    ]

    amounts_found = []
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                num_str = match[0].replace('\u00a0', '').replace(' ', '').replace(',', '.')
                multiplier = 1
                if len(match) > 1 and match[1]:
                    mult_char = match[1].lower()
                    if mult_char == 'k':
                        multiplier = 1000
                    elif mult_char == 'm':
                        multiplier = 1000000
                try:
                    amount = float(num_str) * multiplier
                    if amount >= 100 and amount <= 100000000:  # Filter reasonable amounts
                        amounts_found.append(int(amount))
                except ValueError:
                    pass
            else:
                try:
                    num_str = match.replace('\u00a0', '').replace(' ', '').replace(',', '.')
                    amount = float(num_str)
                    if amount >= 100 and amount <= 100000000:
                        amounts_found.append(int(amount))
                except ValueError:
                    pass

    # Remove duplicates and sort
    extracted["amounts"] = sorted(list(set(amounts_found)), reverse=True)

    # Extract patrimoine (net worth)
    patrimoine_patterns = [
        r'patrimoine[^\d]*(\d+(?:[.,]\d+)?)\s*([kKmM])?',
        r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*(?:€|euros?)?\s*(?:de\s+)?patrimoine',
        r'atteint\s+(\d+(?:[.,]\d+)?)\s*([kKmM])?',
        r'j\'?ai\s+(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*[€$]',
    ]
    for pattern in patrimoine_patterns:
        match = re.search(pattern, text_lower)
        if match:
            num_str = match.group(1).replace(',', '.')
            multiplier = 1
            if match.lastindex >= 2 and match.group(2):
                mult_char = match.group(2).lower()
                if mult_char == 'k':
                    multiplier = 1000
                elif mult_char == 'm':
                    multiplier = 1000000
            try:
                extracted["patrimoine"] = int(float(num_str) * multiplier)
                break
            except ValueError:
                pass

    # Extract annual income
    revenus_patterns = [
        r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*[€$]?\s*(?:par\s+an|\/an|annuel)',
        r'salaire[^\d]*(\d+(?:[.,]\d+)?)\s*([kKmM])?',
        r'revenu[^\d]*(\d+(?:[.,]\d+)?)\s*([kKmM])?',
        r'gagne[^\d]*(\d+(?:[.,]\d+)?)\s*([kKmM])?',
    ]
    for pattern in revenus_patterns:
        match = re.search(pattern, text_lower)
        if match:
            num_str = match.group(1).replace(',', '.')
            multiplier = 1
            if match.lastindex >= 2 and match.group(2):
                mult_char = match.group(2).lower()
                if mult_char == 'k':
                    multiplier = 1000
                elif mult_char == 'm':
                    multiplier = 1000000
            try:
                amount = int(float(num_str) * multiplier)
                # If it looks like monthly, convert to annual
                if amount < 10000:
                    amount *= 12
                extracted["revenus_annuels"] = amount
                break
            except ValueError:
                pass

    # Extract monthly income
    mensuel_patterns = [
        r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*[€$]?\s*(?:par\s+mois|\/mois|mensuel)',
        r'(\d+(?:[.,]\d+)?)\s*[€$]\s*net',
    ]
    for pattern in mensuel_patterns:
        match = re.search(pattern, text_lower)
        if match:
            num_str = match.group(1).replace(',', '.')
            multiplier = 1
            if match.lastindex >= 2 and match.group(2):
                mult_char = match.group(2).lower()
                if mult_char == 'k':
                    multiplier = 1000
            try:
                extracted["revenus_mensuels"] = int(float(num_str) * multiplier)
                break
            except ValueError:
                pass

    # Extract monthly savings
    epargne_patterns = [
        r'épargn\w*[^\d]*(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*[€$]?\s*(?:par\s+mois|\/mois|mensuel)',
        r'met\w*\s+(?:de\s+côté\s+)?(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*[€$]?\s*(?:par\s+mois|\/mois)',
        r'investis?\w*\s+(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*[€$]?\s*(?:par\s+mois|\/mois)',
    ]
    for pattern in epargne_patterns:
        match = re.search(pattern, text_lower)
        if match:
            num_str = match.group(1).replace(',', '.')
            multiplier = 1
            if match.lastindex >= 2 and match.group(2):
                mult_char = match.group(2).lower()
                if mult_char == 'k':
                    multiplier = 1000
            try:
                extracted["epargne_mensuelle"] = int(float(num_str) * multiplier)
                break
            except ValueError:
                pass

    # Extract duration FIRST (to avoid confusion with age)
    duree_patterns = [
        r'(?:depuis|en|sur|pendant)\s+(\d+)\s*ans?',
        r'(\d+)\s*ans?\s+(?:plus\s+tard|après|de\s+travail|d\'investissement|d\'épargne)',
        r'ça\s+fait\s+(\d+)\s*ans?',
        r'il\s+y\s+a\s+(\d+)\s*ans?',
    ]
    duree_found = None
    for pattern in duree_patterns:
        match = re.search(pattern, text_lower)
        if match:
            years = int(match.group(1))
            if 1 <= years <= 50:
                extracted["duree_annees"] = years
                duree_found = years
                break

    # Extract age (more specific patterns to avoid confusion with duration)
    age_patterns = [
        r"j'?ai\s+(\d{2})\s*ans",           # "j'ai 28 ans"
        r'âgé(?:e)?\s+de\s+(\d{2})\s*ans',  # "âgé de 28 ans"
        r'âge\s*:?\s*(\d{2})',               # "âge: 28" ou "âge 28"
        r'(\d{2})\s*[aA]\s*[,\.]',           # "28A," ou "28a."
        r'^(\d{2})\s*ans\b',                 # "28 ans" au début
    ]
    for pattern in age_patterns:
        match = re.search(pattern, text_lower)
        if match:
            age = int(match.group(1))
            # Avoid confusion: if same number as duration, skip
            if 18 <= age <= 70 and age != duree_found:
                extracted["age"] = age
                break

    return extracted


def retry_with_backoff(func, max_retries=5, base_delay=2):
    """
    Retry wrapper with exponential backoff.
    Handles 429 rate limits by waiting longer.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate" in error_str.lower()

            if attempt == max_retries - 1:
                raise

            # Longer wait for rate limits
            if is_rate_limit:
                delay = base_delay * (3 ** attempt)  # More aggressive backoff for rate limits
                print(f"  Rate limit hit. Waiting {delay}s before retry {attempt + 1}/{max_retries}")
            else:
                delay = base_delay * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{max_retries} after {delay}s: {e}")

            time.sleep(delay)


# Lazy-initialized clients (avoids import-time issues with .env loading)
_groq_client = None
_deepseek_client = None


def get_ai_client():
    """Get or create AI client based on AI_PROVIDER setting."""
    global _groq_client, _deepseek_client

    if AI_PROVIDER == "deepseek":
        if _deepseek_client is None:
            if not DEEPSEEK_API_KEY:
                print("Warning: DEEPSEEK_API_KEY not set")
                return None, None, None
            _deepseek_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL
            )
        return _deepseek_client, DEEPSEEK_MODEL, "deepseek"
    else:
        # Default: Groq
        if _groq_client is None:
            if not GROQ_API_KEY:
                print("Warning: GROQ_API_KEY not set")
                return None, None, None
            _groq_client = Groq(api_key=GROQ_API_KEY)
        return _groq_client, GROQ_MODEL, "groq"


def categorize_and_summarize(post: dict) -> dict:
    """
    Use AI (Groq or DeepSeek) to categorize and summarize a Reddit post.
    Returns the post enriched with category, tags, and summary.
    """
    client, model, provider = get_ai_client()
    if not client:
        print(f"Warning: AI client not configured, skipping AI processing")
        return post

    print(f"  Using {provider} ({model})")

    title = post.get("title", "")
    content = post.get("selftext", "")[:1500]
    top_comment = post.get("comment_body", "")[:500]

    # Build category descriptions for better AI classification
    cat_desc = "\n".join([f"- {cat}: {CATEGORY_DESCRIPTIONS.get(cat, '')}" for cat in CATEGORIES])

    prompt = f"""Analyse ce post Reddit sur la finance personnelle (en français).

TITRE: {title}

CONTENU: {content}

TOP COMMENTAIRE: {top_comment}

Réponds en JSON avec ce format exact:
{{
    "category": "une des catégories listées ci-dessous",
    "tags": ["tag1", "tag2", "tag3"],
    "summary": "résumé en 1-2 phrases du conseil principal",
    "consensus": "fort/moyen/faible/divisé",
    "key_advice": "le conseil clé à retenir"
}}

CATÉGORIES DISPONIBLES:
{cat_desc}

RÈGLES:
- category: choisis LA catégorie principale qui correspond LE MIEUX au post
- IMPORTANT: Utilise "Milestone" pour les posts où quelqu'un partage sa réussite financière avec des montants
- IMPORTANT: Utilise "Question" pour les demandes d'aide personnelles avec situation concrète
- IMPORTANT: Utilise "Retour XP" pour les retours d'expérience détaillés
- tags: 2-5 mots-clés spécifiques (noms d'ETF, SCPI, stratégies mentionnées)
- summary: résumé factuel du post
- consensus: évalue si la communauté est d'accord (basé sur score et commentaire)
- key_advice: le conseil actionnable principal

Réponds UNIQUEMENT avec le JSON, pas de texte avant ou après."""

    try:
        # API call with retry logic
        def make_api_call():
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )

        response = retry_with_backoff(make_api_call)
        result_text = response.choices[0].message.content.strip()

        # Parse JSON response
        # Handle potential markdown code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        ai_result = json.loads(result_text)

        # Enrich post with AI analysis
        # Validate category is in allowed list
        category = ai_result.get("category", "Autre")
        post["category"] = category if category in CATEGORIES else "Autre"
        post["tags"] = ai_result.get("tags", [])
        post["summary"] = ai_result.get("summary", "")
        post["consensus"] = ai_result.get("consensus", "")
        post["key_advice"] = ai_result.get("key_advice", "")

        # Extract financial data from text
        full_text = f"{post.get('title', '')} {post.get('selftext', '')} {post.get('comment_body', '')}"
        extracted = extract_financial_data(full_text)
        post["extracted_data"] = extracted

    except json.JSONDecodeError as e:
        print(f"Error parsing AI response: {e}")
        post["category"] = "Autre"
        post["tags"] = []
        post["summary"] = ""
        # Still extract financial data even if AI fails
        full_text = f"{post.get('title', '')} {post.get('selftext', '')} {post.get('comment_body', '')}"
        post["extracted_data"] = extract_financial_data(full_text)
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        post["category"] = "Autre"
        post["tags"] = []
        post["summary"] = ""
        # Still extract financial data even if AI fails
        full_text = f"{post.get('title', '')} {post.get('selftext', '')} {post.get('comment_body', '')}"
        post["extracted_data"] = extract_financial_data(full_text)

    return post


def process_posts(posts: list[dict], delay_between_calls: float = 1.5) -> list[dict]:
    """
    Process all posts with AI categorization and summarization.
    Includes rate limiting delay between API calls.

    Args:
        posts: List of posts to process
        delay_between_calls: Seconds to wait between API calls (default 1.5s for Groq free tier)
    """
    processed = []
    total = len(posts)

    for i, post in enumerate(posts):
        print(f"Processing {i+1}/{total}: {post['title'][:50]}...")
        enriched_post = categorize_and_summarize(post)
        processed.append(enriched_post)

        # Rate limiting - wait between calls to avoid 429s
        if i < total - 1:  # Don't wait after the last call
            time.sleep(delay_between_calls)

    return processed


def find_similar_posts(posts: list[dict]) -> dict:
    """
    Group similar posts/advice together for aggregation.
    Returns a dict with tag -> list of posts mapping.
    """
    tag_groups = {}

    for post in posts:
        for tag in post.get("tags", []):
            tag_lower = tag.lower()
            if tag_lower not in tag_groups:
                tag_groups[tag_lower] = []
            tag_groups[tag_lower].append(post)

    # Sort by number of posts (most mentioned first)
    sorted_groups = dict(sorted(tag_groups.items(), key=lambda x: len(x[1]), reverse=True))

    return sorted_groups


# Test
if __name__ == "__main__":
    test_post = {
        "title": "Quel ETF pour PEA en 2025?",
        "selftext": "Je débute en bourse et je cherche un ETF monde pour mon PEA. J'hésite entre CW8 et WPEA. Des conseils?",
        "comment_body": "CW8 est le classique mais WPEA a des frais plus bas. Pour un débutant, les deux sont très bien.",
        "score": 45
    }

    print("Testing AI processor...")
    result = categorize_and_summarize(test_post)
    print(f"\nCategory: {result.get('category')}")
    print(f"Tags: {result.get('tags')}")
    print(f"Summary: {result.get('summary')}")
    print(f"Consensus: {result.get('consensus')}")
