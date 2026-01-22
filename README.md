# Grepr - Reddit Finance Aggregator

Grepr collecte automatiquement les meilleurs conseils financiers de Reddit, les catégorise avec de l'IA, et les stocke dans une base de données.

## Ce que ça fait

1. **Récupère les posts** des subreddits finance (r/vosfinances, r/personalfinance, r/financialindependence...)
2. **Analyse avec l'IA** pour extraire les conseils, catégoriser par thème, et résumer
3. **Stocke dans NocoDB** pour consultation via API ou interface web

## Installation

```bash
# Cloner le repo
git clone https://github.com/Jelil-ah/grepr.git
cd grepr

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos clés API
```

## Configuration

Créer un fichier `.env` avec:

```env
# Reddit API (créer une app sur https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=votre_client_id
REDDIT_CLIENT_SECRET=votre_client_secret
REDDIT_USER_AGENT=grepr/1.0

# OpenAI API (pour le traitement IA)
OPENAI_API_KEY=votre_clé_openai

# NocoDB (base de données)
NOCODB_URL=https://votre-instance.nocodb.com
NOCODB_API_TOKEN=votre_token
NOCODB_TABLE_ID=votre_table_id
```

## Utilisation

### Lancer le scheduler (recommandé)

Le scheduler tourne en continu et fetch les posts à intervalles réguliers:

```bash
python scheduler.py
```

### Commandes CLI

```bash
# Fetch les nouveaux posts
python -m backend.cli.fetch

# Traiter les posts avec l'IA
python -m backend.cli.process

# Pousser vers NocoDB
python -m backend.cli.push
```

## Structure du projet

```
grepr/
├── backend/
│   ├── cli/           # Commandes CLI (fetch, process, push)
│   ├── db/            # Client NocoDB
│   ├── fetchers/      # Reddit API
│   ├── processors/    # Traitement IA (OpenAI)
│   └── config.py      # Configuration
├── scheduler.py       # Scheduler automatique
├── requirements.txt   # Dépendances Python
└── .env.example       # Template de configuration
```

## Subreddits suivis

- **Français**: r/vosfinances
- **Anglais**: r/personalfinance, r/financialindependence, r/investing, r/stocks, r/bogleheads

## Déploiement

Le projet est conçu pour tourner sur n'importe quel PaaS (Dokploy, Railway, Render...) avec le `Procfile` inclus.

```bash
# Le Procfile lance automatiquement le scheduler
worker: python scheduler.py
```

## Licence

MIT
