# Children's Literacy Learning Platform

![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)

A production-grade backend for a children's literacy learning platform inspired by Duolingo ABC.
Built with **FastAPI + PostgreSQL + SQLAlchemy (async) + JWT auth**.

> 🚀 **Live API**: https://YOUR_DEPLOYMENT_URL  
> 📖 **Swagger UI**: https://YOUR_DEPLOYMENT_URL/docs

---

## Features

- **3-role system**: Parent, Child, Admin with full RBAC
- **JWT auth** (access + refresh tokens, logout with blacklist)
- **Curriculum**: Units → Lessons → Exercises (phonics, handwriting, sight words, vocabulary)
- **Gamification**: XP, levels, daily streaks, badges, leaderboard
- **Progress tracking**: per-exercise results, lesson history, accuracy rate
- **Notifications**: persisted DB notifications + real-time WebSocket delivery
- **Admin panel**: audit logs, platform-wide stats
- **Dockerized**: app + PostgreSQL + pgAdmin via Docker Compose

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+

### Setup

```bash
# 1. Clone and enter
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DB credentials and JWT secret

# 5. Run database migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for Swagger UI.

---

## Docker Compose (Recommended)

```bash
docker-compose up --build
```

| Service  | URL                        |
|----------|----------------------------|
| API      | http://localhost:8000       |
| Swagger  | http://localhost:8000/docs  |
| pgAdmin  | http://localhost:8080       |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable                   | Description                          | Default                  |
|----------------------------|--------------------------------------|--------------------------|
| `DATABASE_URL`             | PostgreSQL async connection string   | *(required)*             |
| `JWT_SECRET_KEY`           | Secret for signing JWT tokens        | *(required, min 32 chars)*|
| `JWT_ACCESS_TOKEN_EXPIRES` | Access token TTL in minutes          | `15`                     |
| `JWT_REFRESH_TOKEN_EXPIRES`| Refresh token TTL in days            | `7`                      |
| `BCRYPT_ROUNDS`            | bcrypt cost factor (min 10)          | `12`                     |
| `ENVIRONMENT`              | `development` / `production`         | `development`            |
| `REDIS_URL`                | Redis connection string              | `redis://localhost:6379/0`|

**Never commit `.env` with real credentials.** See `.gitignore`.

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=term-missing
```

Tests use SQLite in-memory — no external database required.

---

## Database Migrations (Alembic)

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description of change"

# Rollback one step
alembic downgrade -1
```

---

## API Overview

All endpoints versioned under `/api/v1/`. Full docs at `/docs`.

| Endpoint                          | Methods              | Auth      | Description                          |
|-----------------------------------|----------------------|-----------|--------------------------------------|
| `/auth/register`                  | POST                 | Public    | Register parent                      |
| `/auth/login`                     | POST                 | Public    | Login, receive JWT pair              |
| `/auth/logout`                    | POST                 | Parent    | Invalidate access token              |
| `/auth/refresh`                   | POST                 | Public    | Refresh access token                 |
| `/children`                       | GET, POST            | Parent    | List / create child profiles         |
| `/children/{id}`                  | GET, PUT, DELETE     | Parent    | Child CRUD                           |
| `/children/{id}/progress`         | GET                  | Parent    | Full learning history                |
| `/children/{id}/badges`           | GET                  | Parent    | Badges earned                        |
| `/units`                          | GET, POST            | Admin     | Curriculum unit management           |
| `/lessons`                        | GET, POST            | Admin     | Lesson management                    |
| `/lessons/{id}/exercises`         | GET, POST            | Admin     | Exercise management                  |
| `/lessons/{id}/complete`          | POST                 | Parent    | Complete lesson; awards XP + badges  |
| `/exercises/{id}/submit`          | POST                 | Parent    | Submit exercise answer               |
| `/notifications`                  | GET, PATCH           | Parent    | Fetch / mark notifications read      |
| `/leaderboard`                    | GET                  | Public    | XP leaderboard by age group          |
| `/admin/logs`                     | GET                  | Admin     | Audit log viewer                     |
| `/admin/stats`                    | GET                  | Admin     | Platform-wide statistics             |
| `/ws/notifications`               | WS                   | Parent    | Real-time notification stream        |

---

## Architecture

```
app/
├── main.py                  # FastAPI routes (request parsing + response only)
├── config.py                # Environment-based settings (pydantic-settings)
├── core/
│   └── security.py          # JWT creation/decoding, bcrypt password hashing
├── db/
│   ├── base.py              # DeclarativeBase, UUIDMixin, TimestampMixin
│   └── session.py           # Async engine + session factory
├── models/
│   ├── user.py              # Parent, Child, Badge, Notification, AuditLog
│   ├── curriculum.py        # Unit, Lesson, Exercise
│   └── progress.py          # LessonProgress
├── services/
│   └── gamification_service.py  # XP, levels, streaks, badges, notifications
migrations/
└── versions/
    └── 001_initial_schema.py
tests/
├── test_api.py              # Integration tests (41 tests, SQLite in-memory)
└── test_gamification.py     # Unit tests for gamification logic
```

---

## Security

- Passwords hashed with **bcrypt** (cost factor 12, configurable)
- JWT access tokens expire in 15 min; refresh tokens in 7 days
- `POST /auth/logout` adds token to blacklist (in-memory; replace with Redis in production)
- Child profiles strictly isolated by parent ownership
- All admin endpoints verify `role == "admin"`
- No secrets in Git — use `.env` (see `.gitignore`)

---

## Known Limitations & Future Improvements

- Token blacklist is in-memory — restarting the server clears it. **Production fix**: use Redis TTL-based blacklist.
- No scheduled jobs for daily streak evaluation (Celery Beat integration planned)
- No rate limiting on auth endpoints (SlowAPI/Redis integration planned)
- Leaderboard not Redis-cached yet (bonus feature)
