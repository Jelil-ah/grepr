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


# Reddit settings - validate subreddit names
_raw_subreddits = [
    # Francophone
    "vosfinances",
    "vossous",
    # Europe
    "eupersonalfinance",
    "ETFs_Europe",
    "UKPersonalFinance",
    # Anglophone - ETF/Investing
    "Bogleheads",
    "ETFs",
    "investing",
    "portfolios",
    # Anglophone - Personal Finance
    "personalfinance",
    "financialindependence",
    "Fire",
    "dividends",
]
SUBREDDITS = [s for s in _raw_subreddits if validate_subreddit_name(s)]
if len(SUBREDDITS) != len(_raw_subreddits):
    invalid = [s for s in _raw_subreddits if not validate_subreddit_name(s)]
    logger.warning(f"Invalid subreddit names removed: {invalid}")
MIN_SCORE = 10  # Minimum upvotes to include
POSTS_PER_REQUEST = 100  # Max 100 per Reddit API
TIME_FILTER = "all"  # hour, day, week, month, year, all

# AI Provider selection: "groq" or "deepseek"
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")

# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast and capable

# DeepSeek API (alternative when Groq is rate-limited)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek V3
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

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
