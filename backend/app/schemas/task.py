from typing import List, Optional
from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    task_type: str = "general"  # general|call|email|meeting|follow_up|verification
    priority: str = "medium"  # low|medium|high|urgent
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    provider_id: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None
    completed_at: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    task_type: str
    priority: str
    status: str
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    provider_id: Optional[str] = None
    completed_at: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
