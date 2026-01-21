"""
Configuration for Grepr - Reddit Aggregator
"""
import os
import re
import logging
from dotenv import load_dotenv

load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('grepr')


def validate_subreddit_name(name: str) -> bool:
    """Validate subreddit name (alphanumeric and underscore only, 3-21 chars)."""
    return bool(re.match(r'^[a-zA-Z0-9_]{3,21}$', name))


# Reddit API credentials (Official API via PRAW)
# Create app at https://www.reddit.com/prefs/apps (choose "script" type)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "grepr:v1.0 (personal finance aggregator)")

# Check if Reddit API is configured
REDDIT_API_ENABLED = bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)
if not REDDIT_API_ENABLED:
    logger.info("Reddit API not configured - using public .json endpoint (limited)")

# Reddit settings - validate subreddit names
# French finance communities (primary)
# English finance communities (secondary - for ETF/strategy insights)
_raw_subreddits = [
    # French
    "vosfinances",      # Main French personal finance
    "vossous",          # Secondary French finance
    # English - Popular investing subs
    "Bogleheads",       # Index investing philosophy
    "eupersonalfinance", # European personal finance
    "ETFs_Europe",      # European ETF discussion
]
SUBREDDITS = [s for s in _raw_subreddits if validate_subreddit_name(s)]
if len(SUBREDDITS) != len(_raw_subreddits):
    invalid = [s for s in _raw_subreddits if not validate_subreddit_name(s)]
    logger.warning(f"Invalid subreddit names removed: {invalid}")
MIN_SCORE = 10  # Minimum upvotes to include
POSTS_PER_REQUEST = 100  # Max 100 per Reddit API
TIME_FILTER = "all"  # hour, day, week, month, year, all

# AI Provider selection: "groq", "deepseek", or "local" (LM Studio)
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")

# Groq API (cloud)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# DeepSeek API (cloud - alternative when Groq is rate-limited)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Local LM Studio (FREE - no API key needed)
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek")  # Model name in LM Studio

# NocoDB
NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL", "http://localhost:8080")
NOCODB_API_TOKEN = os.getenv("NOCODB_API_TOKEN")
NOCODB_TABLE_ID = os.getenv("NOCODB_TABLE_ID")

# Categories for AI classification - Extended to reduce "Autre"
CATEGORIES = [
    "ETF",
    "Immobilier",
    "Crypto",
    "Epargne",
    "Fiscalite",
    "Actions",
    "Strategie",
    "Milestone",    # Success stories, réussites financières
    "Question",     # Demandes d'aide, cas pratiques personnels
    "Retour XP",    # Retours d'expérience détaillés
    "Budget",       # Gestion de budget, dépenses, revenus
    "Retraite",     # Préparation retraite, PER, PERCO
    "Credit",       # Crédits, prêts, remboursements
    "Carriere",     # Salaire, négociation, reconversion liée aux finances
    "Actualite",    # News financières, changements de loi, taux
    "Autre"
]

# Category descriptions for AI prompt
CATEGORY_DESCRIPTIONS = {
    "ETF": "Posts sur les ETF (CW8, WPEA, S&P500, MSCI World, Nasdaq, etc.)",
    "Immobilier": "SCPI, résidence principale (RP), investissement locatif, crédit immo, LMNP",
    "Crypto": "Bitcoin, Ethereum, cryptomonnaies, DeFi, staking",
    "Epargne": "Livrets (A, LDDS), assurance-vie, PEA, épargne de précaution, fonds euros",
    "Fiscalite": "Impôts, déclarations, optimisation fiscale, niches fiscales, PFU",
    "Actions": "Stock picking, actions individuelles, dividendes, analyse fondamentale",
    "Strategie": "DCA, allocation d'actifs, diversification, rééquilibrage",
    "Milestone": "Réussites financières avec montants (ex: 'J'ai atteint 100k€', 'premier million')",
    "Question": "Cas pratique personnel demandant des conseils (ex: 'J'ai 25 ans, 30k€, que faire?')",
    "Retour XP": "Retours d'expérience détaillés sur un investissement, courtier, ou stratégie",
    "Budget": "Gestion de budget, suivi des dépenses, épargne mensuelle, taux d'épargne",
    "Retraite": "Préparation retraite, PER, PERCO, PERCOL, simulation retraite, trimestres",
    "Credit": "Crédits conso, prêts immo, rachat de crédit, remboursement anticipé, taux",
    "Carriere": "Salaire, négociation salariale, reconversion pro liée aux finances, freelance",
    "Actualite": "News financières, changements de loi, évolution des taux, réforme",
    "Autre": "Sujets ne rentrant dans AUCUNE autre catégorie (utiliser en dernier recours)"
}

# User agent for Reddit requests (required)
USER_AGENT = "grepr:v1.0 (personal use)"

# ETF Database for detection - Tickers and common names
ETF_TICKERS = [
    # World ETFs - PEA
    "CW8", "WPEA", "DCAM", "EWLD", "MWRD",
    # S&P 500
    "PE500", "PSP5", "ESE", "SP500",
    # NASDAQ
    "PUST", "PANX", "CNDX", "UST",
    # Europe
    "PCEU", "STOXX600", "MEU",
    # Emerging Markets
    "PAEEM", "AEEM", "PAASI",
    # CAC 40 / France
    "CAC", "CAC40", "PMEH",
    # CTO Popular
    "VWCE", "VWRA", "IWDA", "EUNL", "CSPX",
    # Bonds
    "OBLI", "GOVT",
    # Thematic
    "ARKK", "QQQM", "VTI", "VOO",
]

# ETF Keywords (for fuzzy matching)
ETF_KEYWORDS = [
    # General ETF terms
    "etf", "tracker", "indice",
    # Index names
    "msci world", "msci europe", "msci em", "msci emerging",
    "s&p 500", "s&p500", "sp500",
    "nasdaq", "nasdaq-100", "nasdaq100",
    "cac 40", "cac40",
    "stoxx 600", "stoxx600",
    "ftse", "ftse all-world",
    # Providers
    "amundi", "ishares", "lyxor", "vanguard", "blackrock",
    # PEA specific
    "etf pea", "pea etf", "éligible pea",
]
