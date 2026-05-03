"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    Query,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.base import Base
from app.db.session import get_db, engine
from app.db.app.models.progress import LessonProgress
from app.models.curriculum import Exercise, Lesson, Unit
from app.models.user import AuditLog, Badge, Child, Notification, Parent
from app.services.gamification_service import GamificationService

settings = get_settings()
security = HTTPBearer()
active_ws_connections: Dict[str, List[WebSocket]] = {}
service = GamificationService

# In-memory token blacklist for logout.
# In production, replace with Redis: https://redis.io/
_token_blacklist: set[str] = set()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ParentUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ChildCreateRequest(BaseModel):
    name: str
    age: int
    avatar_url: Optional[str] = None
    learning_level: Optional[str] = None


class ChildUpdateRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    avatar_url: Optional[str] = None
    learning_level: Optional[str] = None


class UnitCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int = 0
    published: bool = False


class UnitUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    published: Optional[bool] = None


class LessonCreateRequest(BaseModel):
    unit_id: str
    title: str
    exercise_type: str
    order_index: int = 0
    published: bool = False
    difficulty: int = 1


class LessonUpdateRequest(BaseModel):
    title: Optional[str] = None
    exercise_type: Optional[str] = None
    order_index: Optional[int] = None
    published: Optional[bool] = None
    difficulty: Optional[int] = None


class ExerciseCreateRequest(BaseModel):
    content: str
    type: str
    order_index: int = 0
    difficulty: int = 1


class ExerciseUpdateRequest(BaseModel):
    content: Optional[str] = None
    type: Optional[str] = None
    order_index: Optional[int] = None
    difficulty: Optional[int] = None


class LessonCompleteRequest(BaseModel):
    child_id: str
    correct_answers: int = Field(ge=0)
    total_questions: int = Field(gt=0)
    duration_seconds: int = Field(ge=0)


class ExerciseSubmitRequest(BaseModel):
    child_id: str
    correct_answers: int = Field(ge=0)
    total_questions: int = Field(gt=0)
    duration_seconds: int = Field(ge=0)


def pagination_meta(total: int, page: int, page_size: int) -> Dict[str, int]:
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


async def get_access_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
    token = credentials.credentials
    if token in _token_blacklist:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    return payload


async def get_current_parent(
    payload: Dict[str, Any] = Depends(get_access_payload),
    db: AsyncSession = Depends(get_db),
) -> Parent:
    user = await db.get(Parent, payload.get("sub"))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(current_user: Parent = Depends(get_current_parent)) -> Parent:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def authorize_child(
    child_id: str,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Child:
    child = await db.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    if not current_user.is_admin and child.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return child


def serialize_parent(parent: Parent) -> Dict[str, Any]:
    return {
        "id": parent.id,
        "email": parent.email,
        "first_name": parent.first_name,
        "last_name": parent.last_name,
        "role": parent.role,
        "created_at": parent.created_at.isoformat() if parent.created_at else None,
    }


def serialize_child(child: Child) -> Dict[str, Any]:
    return {
        "id": child.id,
        "name": child.name,
        "age": child.age,
        "avatar_url": child.avatar_url,
        "learning_level": child.learning_level,
        "xp_total": child.xp_total,
        "level_number": child.level_number,
        "streak_current": child.streak_current,
        "streak_best": child.streak_best,
        "streak_last_activity_date": child.streak_last_activity_date,
        "lessons_completed": child.lessons_completed,
        "accuracy_rate": child.accuracy_rate,
        "last_activity_at": child.last_activity_at.isoformat() if child.last_activity_at else None,
        "parent_id": child.parent_id,
    }


def serialize_unit(unit: Unit) -> Dict[str, Any]:
    return {
        "id": unit.id,
        "title": unit.title,
        "description": unit.description,
        "order_index": unit.order_index,
        "published": unit.published,
        "created_at": unit.created_at.isoformat() if unit.created_at else None,
    }


def serialize_lesson(lesson: Lesson) -> Dict[str, Any]:
    return {
        "id": lesson.id,
        "unit_id": lesson.unit_id,
        "title": lesson.title,
        "exercise_type": lesson.exercise_type,
        "order_index": lesson.order_index,
        "published": lesson.published,
        "difficulty": lesson.difficulty,
        "exercise_count": len(lesson.exercises) if lesson.exercises else 0,
    }


def serialize_exercise(exercise: Exercise) -> Dict[str, Any]:
    return {
        "id": exercise.id,
        "lesson_id": exercise.lesson_id,
        "content": exercise.content,
        "type": exercise.type,
        "order_index": exercise.order_index,
        "difficulty": exercise.difficulty,
    }


def serialize_progress(progress: LessonProgress) -> Dict[str, Any]:
    return {
        "id": progress.id,
        "child_id": progress.child_id,
        "lesson_id": progress.lesson_id,
        "completed": progress.completed,
        "correct_answers": progress.correct_answers,
        "total_questions": progress.total_questions,
        "score": progress.score,
        "duration_seconds": progress.duration_seconds,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
    }


def serialize_badge(badge: Badge) -> Dict[str, Any]:
    return {
        "id": badge.id,
        "child_id": badge.child_id,
        "name": badge.name,
        "description": badge.description,
        "awarded_at": badge.awarded_at.isoformat() if badge.awarded_at else None,
    }


def serialize_notification(notification: Notification) -> Dict[str, Any]:
    return {
        "id": notification.id,
        "parent_id": notification.parent_id,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
    }


async def create_audit_log(
    user: Parent,
    action: str,
    resource: str,
    details: Optional[str],
    db: AsyncSession,
) -> None:
    log = AuditLog(user_id=user.id, action=action, resource=resource, details=details or "")
    db.add(log)
    await db.commit()


async def broadcast_notification(parent_id: str, payload: Dict[str, Any]) -> None:
    connections = active_ws_connections.get(parent_id, [])
    for websocket in list(connections):
        try:
            await websocket.send_json(payload)
        except Exception:
            connections.remove(websocket)


async def create_notification(
    parent_id: str,
    title: str,
    message: str,
    db: AsyncSession,
) -> Notification:
    notification = Notification(parent_id=parent_id, title=title, message=message)
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    await broadcast_notification(parent_id, serialize_notification(notification))
    return notification


async def award_badges(child: Child, db: AsyncSession, parent: Parent) -> List[Badge]:
    existing = await db.execute(select(Badge.name).where(Badge.child_id == child.id))
    existing_names = {row[0] for row in existing.all()}
    candidates = [
        ("first_lesson", "First Lesson", "Completed the first lesson", child.lessons_completed >= 1),
        ("xp_100", "100 XP Earned", "Earned 100 XP", child.xp_total >= 100),
        ("streak_3", "3-Day Streak", "Maintained 3-day streak", child.streak_current >= 3),
        ("streak_7", "7-Day Streak", "Maintained 7-day streak", child.streak_current >= 7),
        ("lessons_10", "10 Lessons", "Completed 10 lessons", child.lessons_completed >= 10),
    ]
    awarded: List[Badge] = []
    for name, title, description, condition in candidates:
        if condition and name not in existing_names:
            badge = Badge(child_id=child.id, name=name, description=description)
            db.add(badge)
            await db.flush()
            await db.refresh(badge)
            awarded.append(badge)
            await create_notification(
                parent_id=child.parent_id,
                title=f"Badge unlocked: {title}",
                message=f"{child.name} earned the '{title}' badge.",
                db=db,
            )
    if awarded:
        await db.commit()
    return awarded


async def get_child_progress(child: Child, db: AsyncSession) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(LessonProgress)
        .where(LessonProgress.child_id == child.id)
        .order_by(LessonProgress.completed_at.desc())
    )
    return [serialize_progress(item) for item in result.scalars().all()]


async def get_leaderboard(
    db: AsyncSession,
    page: int,
    page_size: int,
    min_age: Optional[int],
    max_age: Optional[int],
) -> Dict[str, Any]:
    filters = []
    if min_age is not None:
        filters.append(Child.age >= min_age)
    if max_age is not None:
        filters.append(Child.age <= max_age)
    query = select(Child).where(*filters).order_by(Child.xp_total.desc())
    total = await db.scalar(select(func.count()).select_from(Child).where(*filters))
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return {
        "items": [serialize_child(item) for item in result.scalars().all()],
        "pagination": pagination_meta(total, page, page_size),
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Children's Literacy Learning Platform",
    docs_url="/docs",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/app", response_class=FileResponse)
async def app_ui() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(Parent).where(Parent.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    parent = Parent(
        email=request.email,
        password_hash=get_password_hash(request.password),
        first_name=request.first_name,
        last_name=request.last_name,
        role="parent",
    )
    db.add(parent)
    await db.commit()
    await db.refresh(parent)

    access_token = create_access_token(subject=parent.id, email=parent.email, role=parent.role)
    refresh_token = create_refresh_token(subject=parent.id, email=parent.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(Parent).where(Parent.email == request.email))
    parent = result.scalar_one_or_none()
    if not parent or not verify_password(request.password, parent.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(subject=parent.id, email=parent.email, role=parent.role)
    refresh_token = create_refresh_token(subject=parent.id, email=parent.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    parent = await db.get(Parent, payload.get("sub"))
    if not parent:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(subject=parent.id, email=parent.email, role=parent.role)
    refresh_token = create_refresh_token(subject=parent.id, email=parent.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _: Parent = Depends(get_current_parent),
) -> None:
    """
    Invalidate the current access token.
    Token is added to an in-memory blacklist; it will be rejected on
    subsequent requests even before it expires naturally.
    """
    _token_blacklist.add(credentials.credentials)


@app.get("/api/v1/auth/me")
async def auth_me(current_user: Parent = Depends(get_current_parent)) -> Dict[str, Any]:
    return serialize_parent(current_user)


@app.get("/api/v1/parents/{parent_id}")
async def get_parent(parent_id: str, current_user: Parent = Depends(get_current_parent), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    parent = await db.get(Parent, parent_id)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    if not current_user.is_admin and current_user.id != parent.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return serialize_parent(parent)


@app.get("/api/v1/parents")
async def list_parents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    total = await db.scalar(select(func.count()).select_from(Parent))
    result = await db.execute(select(Parent).order_by(Parent.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return {
        "items": [serialize_parent(parent) for parent in result.scalars().all()],
        "pagination": pagination_meta(total, page, page_size),
    }


@app.put("/api/v1/parents/{parent_id}")
async def update_parent(
    parent_id: str,
    payload: ParentUpdateRequest,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    parent = await db.get(Parent, parent_id)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    if not current_user.is_admin and current_user.id != parent.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if payload.first_name is not None:
        parent.first_name = payload.first_name
    if payload.last_name is not None:
        parent.last_name = payload.last_name

    db.add(parent)
    await db.commit()
    await db.refresh(parent)
    await create_audit_log(current_user, "update", "parent", f"Updated parent {parent_id}", db)
    return serialize_parent(parent)


@app.get("/api/v1/parents/{parent_id}/children")
async def get_parent_children(
    parent_id: str,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    parent = await db.get(Parent, parent_id)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    if not current_user.is_admin and current_user.id != parent.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    await db.refresh(parent)
    return {"children": [serialize_child(child) for child in parent.children]}


@app.get("/api/v1/children")
async def list_children(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    if current_user.is_admin:
        total = await db.scalar(select(func.count()).select_from(Child))
        query = select(Child).order_by(Child.name.asc())
    else:
        total = await db.scalar(select(func.count()).select_from(Child).where(Child.parent_id == current_user.id))
        query = select(Child).where(Child.parent_id == current_user.id).order_by(Child.name.asc())
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return {
        "items": [serialize_child(child) for child in result.scalars().all()],
        "pagination": pagination_meta(total, page, page_size),
    }


@app.post("/api/v1/children")
async def create_child(
    payload: ChildCreateRequest,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    child = Child(
        parent_id=current_user.id,
        name=payload.name,
        age=payload.age,
        avatar_url=payload.avatar_url,
        learning_level=payload.learning_level,
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)
    await create_audit_log(current_user, "create", "child", f"Created child {child.id}", db)
    return serialize_child(child)


@app.get("/api/v1/children/{child_id}")
async def get_child(child: Child = Depends(authorize_child)) -> Dict[str, Any]:
    return serialize_child(child)


@app.put("/api/v1/children/{child_id}")
async def update_child(
    payload: ChildUpdateRequest,
    child: Child = Depends(authorize_child),
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    if payload.name is not None:
        child.name = payload.name
    if payload.age is not None:
        child.age = payload.age
    if payload.avatar_url is not None:
        child.avatar_url = payload.avatar_url
    if payload.learning_level is not None:
        child.learning_level = payload.learning_level
    db.add(child)
    await db.commit()
    await db.refresh(child)
    await create_audit_log(current_user, "update", "child", f"Updated child {child.id}", db)
    return serialize_child(child)


@app.delete("/api/v1/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_child(
    child: Child = Depends(authorize_child),
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.delete(child)
    await db.commit()
    await create_audit_log(current_user, "delete", "child", f"Deleted child {child.id}", db)


@app.get("/api/v1/children/{child_id}/progress")
async def child_progress(child: Child = Depends(authorize_child), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    return {"progress": await get_child_progress(child, db)}


@app.get("/api/v1/children/{child_id}/badges")
async def child_badges(child: Child = Depends(authorize_child), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    await db.refresh(child)
    return {"badges": [serialize_badge(badge) for badge in child.badges]}


@app.get("/api/v1/units")
async def list_units(
    title: Optional[str] = Query(None),
    published: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    query = select(Unit).order_by(Unit.order_index.asc())
    count_query = select(func.count()).select_from(Unit)
    if title:
        query = query.where(Unit.title.ilike(f"%{title}%"))
        count_query = count_query.where(Unit.title.ilike(f"%{title}%"))
    if published is not None:
        query = query.where(Unit.published == published)
        count_query = count_query.where(Unit.published == published)
    total = await db.scalar(count_query)
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return {
        "items": [serialize_unit(item) for item in result.scalars().all()],
        "pagination": pagination_meta(total, page, page_size),
    }


@app.post("/api/v1/units")
async def create_unit(
    payload: UnitCreateRequest,
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    unit = Unit(
        title=payload.title,
        description=payload.description,
        order_index=payload.order_index,
        published=payload.published,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    await create_audit_log(admin, "create", "unit", f"Created unit {unit.id}", db)
    return serialize_unit(unit)


@app.get("/api/v1/units/{unit_id}")
async def get_unit(unit_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    return serialize_unit(unit)


@app.put("/api/v1/units/{unit_id}")
async def update_unit(
    unit_id: str,
    payload: UnitUpdateRequest,
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    if payload.title is not None:
        unit.title = payload.title
    if payload.description is not None:
        unit.description = payload.description
    if payload.order_index is not None:
        unit.order_index = payload.order_index
    if payload.published is not None:
        unit.published = payload.published
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    await create_audit_log(admin, "update", "unit", f"Updated unit {unit.id}", db)
    return serialize_unit(unit)


@app.delete("/api/v1/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(unit_id: str, admin: Parent = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> None:
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    await db.delete(unit)
    await db.commit()
    await create_audit_log(admin, "delete", "unit", f"Deleted unit {unit.id}", db)


@app.get("/api/v1/lessons")
async def list_lessons(
    unit_id: Optional[str] = Query(None),
    exercise_type: Optional[str] = Query(None),
    published: Optional[bool] = Query(None),
    difficulty: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    query = select(Lesson).order_by(Lesson.order_index.asc())
    count_query = select(func.count()).select_from(Lesson)
    if unit_id:
        query = query.where(Lesson.unit_id == unit_id)
        count_query = count_query.where(Lesson.unit_id == unit_id)
    if exercise_type:
        query = query.where(Lesson.exercise_type.ilike(f"%{exercise_type}%"))
        count_query = count_query.where(Lesson.exercise_type.ilike(f"%{exercise_type}%"))
    if published is not None:
        query = query.where(Lesson.published == published)
        count_query = count_query.where(Lesson.published == published)
    if difficulty is not None:
        query = query.where(Lesson.difficulty == difficulty)
        count_query = count_query.where(Lesson.difficulty == difficulty)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return {
        "items": [serialize_lesson(item) for item in result.scalars().all()],
        "pagination": pagination_meta(total, page, page_size),
    }


@app.post("/api/v1/lessons")
async def create_lesson(
    payload: LessonCreateRequest,
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    unit = await db.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    lesson = Lesson(
        unit_id=payload.unit_id,
        title=payload.title,
        exercise_type=payload.exercise_type,
        order_index=payload.order_index,
        published=payload.published,
        difficulty=payload.difficulty,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    await create_audit_log(admin, "create", "lesson", f"Created lesson {lesson.id}", db)
    return serialize_lesson(lesson)


@app.get("/api/v1/lessons/{lesson_id}")
async def get_lesson(lesson_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return serialize_lesson(lesson)


@app.put("/api/v1/lessons/{lesson_id}")
async def update_lesson(
    lesson_id: str,
    payload: LessonUpdateRequest,
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if payload.title is not None:
        lesson.title = payload.title
    if payload.exercise_type is not None:
        lesson.exercise_type = payload.exercise_type
    if payload.order_index is not None:
        lesson.order_index = payload.order_index
    if payload.published is not None:
        lesson.published = payload.published
    if payload.difficulty is not None:
        lesson.difficulty = payload.difficulty
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    await create_audit_log(admin, "update", "lesson", f"Updated lesson {lesson.id}", db)
    return serialize_lesson(lesson)


@app.delete("/api/v1/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(lesson_id: str, admin: Parent = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> None:
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    await db.delete(lesson)
    await db.commit()
    await create_audit_log(admin, "delete", "lesson", f"Deleted lesson {lesson.id}", db)


@app.get("/api/v1/lessons/{lesson_id}/exercises")
async def list_lesson_exercises(lesson_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    await db.refresh(lesson)
    return {"items": [serialize_exercise(exercise) for exercise in lesson.exercises]}


@app.post("/api/v1/lessons/{lesson_id}/exercises")
async def create_exercise(
    lesson_id: str,
    payload: ExerciseCreateRequest,
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    exercise = Exercise(
        lesson_id=lesson_id,
        content=payload.content,
        type=payload.type,
        order_index=payload.order_index,
        difficulty=payload.difficulty,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    await create_audit_log(admin, "create", "exercise", f"Created exercise {exercise.id}", db)
    return serialize_exercise(exercise)


@app.get("/api/v1/exercises/{exercise_id}")
async def get_exercise(exercise_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return serialize_exercise(exercise)


@app.put("/api/v1/exercises/{exercise_id}")
async def update_exercise(
    exercise_id: str,
    payload: ExerciseUpdateRequest,
    admin: Parent = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    if payload.content is not None:
        exercise.content = payload.content
    if payload.type is not None:
        exercise.type = payload.type
    if payload.order_index is not None:
        exercise.order_index = payload.order_index
    if payload.difficulty is not None:
        exercise.difficulty = payload.difficulty
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    await create_audit_log(admin, "update", "exercise", f"Updated exercise {exercise.id}", db)
    return serialize_exercise(exercise)


@app.delete("/api/v1/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(exercise_id: str, admin: Parent = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> None:
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    await db.delete(exercise)
    await db.commit()
    await create_audit_log(admin, "delete", "exercise", f"Deleted exercise {exercise.id}", db)


@app.post("/api/v1/lessons/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: str,
    payload: LessonCompleteRequest,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    # --- Input validation only (no business logic here) ---
    lesson = await db.get(Lesson, lesson_id)
    if not lesson or not lesson.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published lesson not found")
    child = await db.get(Child, payload.child_id)
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    if not current_user.is_admin and child.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # --- Delegate ALL logic to service layer ---
    svc = GamificationService(db)
    result = await svc.process_lesson_complete(
        child=child,
        lesson_id=lesson_id,
        lesson_difficulty=lesson.difficulty,
        correct=payload.correct_answers,
        total=payload.total_questions,
        duration_seconds=payload.duration_seconds,
    )

    # Award badges via service
    new_badges = await svc.award_badges(child)
    result["badges_earned"] = [b.name for b in new_badges]

    # Notify parent via service
    await svc.create_notification(
        parent_id=child.parent_id,
        title="Lesson completed",
        message=f"{child.name} completed '{lesson.title}' and earned {result['xp_earned']} XP.",
    )
    for badge in new_badges:
        await svc.create_notification(
            parent_id=child.parent_id,
            title="Badge unlocked!",
            message=f"{child.name} earned the '{badge.name}' badge.",
        )
        await broadcast_notification(
            child.parent_id,
            {"type": "badge", "badge": badge.name, "child": child.name},
        )

    await db.commit()
    await db.refresh(child)

    # Broadcast lesson completion via WebSocket
    await broadcast_notification(
        child.parent_id,
        {"type": "lesson_complete", "child": child.name, "lesson": lesson.title, **result},
    )

    return {"gamification": result, "child": serialize_child(child)}


@app.post("/api/v1/exercises/{exercise_id}/submit")
async def submit_exercise(
    exercise_id: str,
    payload: ExerciseSubmitRequest,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    child = await db.get(Child, payload.child_id)
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    if not current_user.is_admin and child.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    score = round((payload.correct_answers / payload.total_questions) * 100.0, 2) if payload.total_questions > 0 else 0.0
    lesson = await db.get(Lesson, exercise.lesson_id)
    if lesson and lesson.published:
        svc = GamificationService(db)
        await svc.create_notification(
            parent_id=child.parent_id,
            title="Exercise submitted",
            message=f"{child.name} submitted an exercise for '{lesson.title}' — score: {score:.0f}%.",
        )
        await db.commit()
    return {
        "exercise_id": exercise.id,
        "correct_answers": payload.correct_answers,
        "total_questions": payload.total_questions,
        "score": score,
        "duration_seconds": payload.duration_seconds,
    }


@app.get("/api/v1/notifications")
async def list_notifications(
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    result = await db.execute(select(Notification).where(Notification.parent_id == current_user.id).order_by(Notification.sent_at.desc()))
    return {"items": [serialize_notification(item) for item in result.scalars().all()]}


@app.patch("/api/v1/notifications/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    current_user: Parent = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    notification = await db.get(Notification, notification_id)
    if not notification or notification.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return serialize_notification(notification)


@app.get("/api/v1/leaderboard")
async def leaderboard(
    min_age: Optional[int] = Query(None, ge=1),
    max_age: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await get_leaderboard(db, page, page_size, min_age, max_age)


@app.get("/api/v1/admin/logs")
async def admin_logs(admin: Parent = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))
    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource": log.resource,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in result.scalars().all()
        ]
    }


@app.get("/api/v1/admin/stats")
async def admin_stats(admin: Parent = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    total_parents = await db.scalar(select(func.count()).select_from(Parent))
    total_children = await db.scalar(select(func.count()).select_from(Child))
    total_lessons = await db.scalar(select(func.count()).select_from(Lesson))
    total_completed = await db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.completed == True))
    return {
        "total_parents": total_parents,
        "total_children": total_children,
        "total_lessons": total_lessons,
        "total_completed_lessons": total_completed,
    }


@app.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    parent_id = str(payload.get("sub"))
    active_ws_connections.setdefault(parent_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_ws_connections[parent_id].remove(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
