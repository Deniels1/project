"""
Integration tests for API endpoints.
Uses in-memory SQLite via SQLAlchemy for isolated, DB-backed testing.
No external services required.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.session import get_db
from app.db.base import Base


# ------------------------------------------------------------------ #
# Test DB setup (SQLite in-memory, async)                              #
# ------------------------------------------------------------------ #

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

async def register_parent(client: AsyncClient, email="parent@test.com", password="password123"):
    resp = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "Parent",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def get_auth_headers(client: AsyncClient, email="parent@test.com", password="password123"):
    tokens = await register_parent(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ------------------------------------------------------------------ #
# Health                                                                #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ------------------------------------------------------------------ #
# Auth flow                                                             #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_register_parent(client: AsyncClient):
    tokens = await register_parent(client)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient):
    await register_parent(client)
    resp = await client.post("/api/v1/auth/register", json={
        "email": "parent@test.com",
        "password": "password123",
        "first_name": "Dupe",
        "last_name": "User",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await register_parent(client)
    resp = await client.post("/api/v1/auth/login", json={
        "email": "parent@test.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client: AsyncClient):
    await register_parent(client)
    resp = await client.post("/api/v1/auth/login", json={
        "email": "parent@test.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_token(client: AsyncClient):
    tokens = await register_parent(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    # Logout
    resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 204
    # Token should now be rejected
    resp2 = await client.get("/api/v1/auth/me", headers=headers)
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_auth_me(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "parent@test.com"


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    tokens = await register_parent(client)
    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# ------------------------------------------------------------------ #
# Child profile CRUD                                                    #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_create_child(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.post("/api/v1/children", headers=headers, json={
        "name": "Alice",
        "age": 6,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["age"] == 6
    assert data["xp_total"] == 0


@pytest.mark.asyncio
async def test_list_children(client: AsyncClient):
    headers = await get_auth_headers(client)
    await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})
    await client.post("/api/v1/children", headers=headers, json={"name": "Bob", "age": 8})
    resp = await client.get("/api/v1/children?page=1&page_size=10", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_get_child_by_id(client: AsyncClient):
    headers = await get_auth_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    resp = await client.get(f"/api/v1/children/{child['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == child["id"]


@pytest.mark.asyncio
async def test_update_child(client: AsyncClient):
    headers = await get_auth_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    resp = await client.put(f"/api/v1/children/{child['id']}", headers=headers, json={"name": "Alicia", "age": 7})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alicia"


@pytest.mark.asyncio
async def test_delete_child(client: AsyncClient):
    headers = await get_auth_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    resp = await client.delete(f"/api/v1/children/{child['id']}", headers=headers)
    assert resp.status_code == 204
    # Should be gone
    resp2 = await client.get(f"/api/v1/children/{child['id']}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_cannot_access_other_parents_child(client: AsyncClient):
    headers1 = await get_auth_headers(client, "parent1@test.com")
    headers2 = await get_auth_headers(client, "parent2@test.com")
    child = (await client.post("/api/v1/children", headers=headers1, json={"name": "Alice", "age": 6})).json()
    resp = await client.get(f"/api/v1/children/{child['id']}", headers=headers2)
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# Curriculum                                                            #
# ------------------------------------------------------------------ #

async def create_unit_and_lesson(client: AsyncClient, admin_headers: dict):
    unit = (await client.post("/api/v1/units", headers=admin_headers, json={
        "title": "Phonics Level 1",
        "published": True,
        "order_index": 1,
    })).json()
    lesson = (await client.post("/api/v1/lessons", headers=admin_headers, json={
        "unit_id": unit["id"],
        "title": "Letter A",
        "exercise_type": "phonics",
        "published": True,
        "difficulty": 1,
        "order_index": 1,
    })).json()
    return unit, lesson


async def get_admin_headers(client: AsyncClient):
    """Register a parent then manually set them as admin via DB."""
    from app.models.user import Parent
    tokens = await register_parent(client, "admin@test.com", "adminpass123")
    # Set role to admin via DB
    async with TestingSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(Parent).where(Parent.email == "admin@test.com"))
        parent = result.scalar_one()
        parent.role = "admin"
        await session.commit()
    # Re-login to get token with admin role
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "adminpass123"
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_unit_as_admin(client: AsyncClient):
    admin_headers = await get_admin_headers(client)
    resp = await client.post("/api/v1/units", headers=admin_headers, json={
        "title": "Phonics Level 1",
        "published": True,
        "order_index": 1,
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Phonics Level 1"


@pytest.mark.asyncio
async def test_create_unit_as_non_admin_fails(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.post("/api/v1/units", headers=headers, json={
        "title": "Phonics Level 1",
        "published": True,
        "order_index": 1,
    })
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# Lesson completion + gamification                                      #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_complete_lesson_awards_xp(client: AsyncClient):
    headers = await get_auth_headers(client)
    admin_headers = await get_admin_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    _, lesson = await create_unit_and_lesson(client, admin_headers)

    resp = await client.post(f"/api/v1/lessons/{lesson['id']}/complete", headers=headers, json={
        "child_id": child["id"],
        "correct_answers": 8,
        "total_questions": 10,
        "duration_seconds": 120,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["gamification"]["xp_earned"] == 100  # difficulty 1
    assert data["gamification"]["total_xp"] == 100
    assert data["gamification"]["new_streak"] == 1


@pytest.mark.asyncio
async def test_complete_lesson_awards_first_lesson_badge(client: AsyncClient):
    headers = await get_auth_headers(client)
    admin_headers = await get_admin_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    _, lesson = await create_unit_and_lesson(client, admin_headers)

    resp = await client.post(f"/api/v1/lessons/{lesson['id']}/complete", headers=headers, json={
        "child_id": child["id"],
        "correct_answers": 10,
        "total_questions": 10,
        "duration_seconds": 90,
    })
    assert resp.status_code == 200
    assert "first_lesson" in resp.json()["gamification"]["badges_earned"]


@pytest.mark.asyncio
async def test_child_progress_endpoint(client: AsyncClient):
    headers = await get_auth_headers(client)
    admin_headers = await get_admin_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    _, lesson = await create_unit_and_lesson(client, admin_headers)

    await client.post(f"/api/v1/lessons/{lesson['id']}/complete", headers=headers, json={
        "child_id": child["id"],
        "correct_answers": 5,
        "total_questions": 10,
        "duration_seconds": 60,
    })
    resp = await client.get(f"/api/v1/children/{child['id']}/progress", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "progress" in data


# ------------------------------------------------------------------ #
# Notifications                                                         #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_notifications_created_on_lesson_complete(client: AsyncClient):
    headers = await get_auth_headers(client)
    admin_headers = await get_admin_headers(client)
    child = (await client.post("/api/v1/children", headers=headers, json={"name": "Alice", "age": 6})).json()
    _, lesson = await create_unit_and_lesson(client, admin_headers)

    await client.post(f"/api/v1/lessons/{lesson['id']}/complete", headers=headers, json={
        "child_id": child["id"],
        "correct_answers": 10,
        "total_questions": 10,
        "duration_seconds": 90,
    })
    resp = await client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) > 0


# ------------------------------------------------------------------ #
# Unauthenticated access                                               #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_unauthenticated_request_fails(client: AsyncClient):
    resp = await client.get("/api/v1/children")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 403, explicit checks return 401
