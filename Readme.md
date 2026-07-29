# BrandMarket Backend

FastAPI + PostgreSQL B2B marketplace API (modular monolith).

## Quick start

```bash
cd backend
cp .env.example .env
docker compose up -d
pip install -e ".[dev]"
python scripts/seed.py
uvicorn src.main:app --reload --port 8000
```

> **Note:** Docker Postgres uses host port **5433** (not 5432) to avoid conflict with a local PostgreSQL installation on Windows.

API docs: http://localhost:8000/docs

## API prefixes

| Prefix | Audience |
|--------|----------|
| `/api/v1/auth` | Registration, login, profile |
| `/api/v1/public` | Categories, supplier directory, public reviews |
| `/api/v1/buyer` | Buyer RFQs, proposals, contracts, payments |
| `/api/v1/supplier` | Supplier board, proposals, contracts |
| `/api/v1/admin` | User/company moderation, disputes |

## Demo accounts (after seed)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@example.com | Admin123! |
| Buyer | buyer@example.com | Buyer123! |
| Supplier | supplier@example.com | Supplier123! |

## Headers

- `Authorization: Bearer <access_token>`
- `X-Company-Id: <active_company_id>`

## Tests

```bash
python -m pytest
```
