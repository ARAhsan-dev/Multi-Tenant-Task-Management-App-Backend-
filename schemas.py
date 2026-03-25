from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from enum import Enum
from typing import Optional, List

# Enums (for Task fields)
class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"

class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

# Tenant Schemas
class TenantBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TenantCreate(TenantBase):
    pass


class TenantResponse(TenantBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

# User Schemas
class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)

class UserCreate(UserBase):
    password: str=Field(min_length=8)

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    tenant_id: int

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=1, max_length=50)
    email: Optional[EmailStr] = Field(default=None, max_length=120)
    password: Optional[str] = Field(default=None, min_length=8)

# Task Schemas
class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None

class TaskCreate(TaskBase):
    assignee_id: int 
    status: Optional[TaskStatus] = TaskStatus.todo
    priority: Optional[TaskPriority] = TaskPriority.medium
    due_date: date
    labels: Optional[List[str]] = None      
    attachments: Optional[List[str]] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None
    labels: Optional[str] = None
    attachments: Optional[str] = None
    is_deleted: Optional[bool] = None  

class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TaskStatus
    priority: TaskPriority
    due_date: date
    assignee_id: int
    assignee: UserResponse      
    created_by: int
    updated_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    labels: Optional[List[str]] = None
    attachments: Optional[List[str]] = None

# Pagination Wrapper
class PaginatedTaskResponse(BaseModel):
    total: int
    limit: int
    offset: int
    next: Optional[str] = None
    previous: Optional[str] = None
    data: List[TaskResponse]


# Bulk Schemas
class BulkTaskCreate(BaseModel):
    tasks: List[TaskCreate]


class BulkTaskUpdate(BaseModel):
    task_id: int
    updates: TaskUpdate

# Token Response Schema
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

#Register Schema
class RegisterRequest(BaseModel):
    tenant_id: int
    username: str
    email: str
    password: str

class RegisterResponse(BaseModel):
    tenant_id: int
    user_id: int
    username: str
    access_token: str
    token_type: str = "bearer"
