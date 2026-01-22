# Grepr

Reddit personal finance aggregator. Fetches top posts, categorizes them with AI, and stores everything in NocoDB.

## How it works

1. **Fetch** - Grabs posts from finance subreddits (vosfinances, personalfinance, etc.)
2. **Process** - AI analyzes, categorizes and summarizes each post
3. **Push** - Sends everything to NocoDB

## Setup

```bash
git clone https://github.com/Jelil-ah/grepr.git
cd grepr

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Fill in your API keys
```

## Config

The `.env` file is where you put your API keys:

```env
# Reddit - create an app at reddit.com/prefs/apps
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...

# AI - either Groq (free) or DeepSeek (cheap)
AI_PROVIDER=groq
GROQ_API_KEY=...

# NocoDB - your database
NOCODB_BASE_URL=...
NOCODB_API_TOKEN=...
NOCODB_TABLE_ID=...
```

## Usage

Easiest way is to run the scheduler:

```bash
python scheduler.py
```

It runs on its own, fetches posts once a day, processes and pushes them.

Or run each step manually:

```bash
python -m backend.cli.fetch    # fetch posts
python -m backend.cli.process  # AI processing
python -m backend.cli.push     # push to NocoDB
```

## Structure

```
grepr/
├── backend/
│   ├── cli/         # commands
│   ├── db/          # NocoDB client
│   ├── fetchers/    # Reddit API
│   └── processors/  # AI processing
├── scheduler.py     # auto scheduler
└── requirements.txt
```

## Subreddits

FR: vosfinances, vossous
EN: personalfinance, financialindependence, investing, bogleheads, etc.

## Deployment

Works on any PaaS (Dokploy, Railway, Render...). Procfile included.

## License

MIT
