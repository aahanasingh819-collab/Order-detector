# Order Detector

A Django order-risk review workspace that helps human reviewers investigate e-commerce orders using transparent scoring and optional, on-demand AI explanations.

## Run & Operate

- `python manage.py migrate` — apply Django migrations to the local SQLite database
- `python manage.py seed_orders` — create fictional customers and demo orders (safe to rerun)
- `python manage.py runserver 0.0.0.0:8000` — run the local Django server
- `python manage.py test` — run risk, API, and view tests
- Add `OPENAI_API_KEY` through Replit Secrets to enable the optional explainer

## Stack and architecture

- Django 5.2, Django REST Framework, Django ORM, SQLite for local development
- Django Templates, HTML, CSS, and vanilla JavaScript; no JavaScript backend
- Risk scoring is implemented in `orders/services/risk_engine.py` and persisted as `RiskSignal` records.
- AI explanations use the official OpenAI Python SDK in `orders/services/ai_explainer.py`. Calls happen only on explicit reviewer requests; cached text is stored on each order.
- API routes are under `/risk-api/v1/`; reviewer pages are Django-rendered.

## Product

- Search, filter, sort, and prioritize order reviews from a summary dashboard.
- Inspect transaction facts, product data, historical customer behavior, and detected risk signals.
- Record investigation notes and change review status. No automated fraud verdict or order approval/rejection is made.
- Seeded names, emails, addresses, and transactions are fictional.

## Security and operating notes

- `.env` and the local SQLite database are git-ignored. `.env.example` contains placeholders only.
- Never expose `OPENAI_API_KEY` to a template, browser response, source file, or log.
- The AI explanation endpoint returns a useful unavailable message without a key or when OpenAI is unavailable; risk scoring and review actions do not depend on AI.
- `seed_orders --reset` deletes existing demo orders and customers. Do not use it where investigation records must be retained.
- For production, disable debug mode, set allowed hosts and trusted HTTPS origins, run Django's deployment checks, collect static files, and select a persistent database.