from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.task_service import create_task, get_task, list_tasks, update_task, delete_task
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/tasks", tags=["Tasks"])

def _fmt(doc: dict) -> dict:
    for f in ("created_at", "updated_at", "due_date", "completed_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc

@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_tasks_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    lead_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    overdue_only: bool = False,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_tasks(db, skip, limit, lead_id, assigned_to, status_filter, priority, overdue_only)
    return paginate([_fmt(i) for i in items], total, page, limit)

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_task_route(
    data: TaskCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await create_task(db, data.model_dump(), str(user.get("_id", "")))
    return _fmt(doc)

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_route(
    task_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_task(db, task_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return _fmt(doc)

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_route(
    task_id: str,
    data: TaskUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await update_task(db, task_id, updates)
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return _fmt(doc)

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_route(
    task_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    success = await delete_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
