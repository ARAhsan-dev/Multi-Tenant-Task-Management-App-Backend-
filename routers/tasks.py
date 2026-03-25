from typing import Annotated, Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session
import models
from auth import CurrentUser
from database import get_db
from schemas import TaskCreate, TaskUpdate, TaskResponse,PaginatedTaskResponse, BulkTaskCreate, BulkTaskUpdate

router = APIRouter()

# Helper: fetch task with tenant isolation
def get_task_or_404(task_id: int,tenant_id: int,db: Session,include_deleted: bool = False) -> models.Task:
    filters = [
        models.Task.id == task_id,
        models.Task.tenant_id == tenant_id,
    ]
    if not include_deleted:
        filters.append(models.Task.is_deleted == False)

    task = db.execute(select(models.Task).where(and_(*filters))).scalars().first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Task not found")
    return task

# Helper: validate assignee belongs to tenant
def validate_assignee(assignee_id: int, tenant_id: int, db: Session) -> models.User:
    user = db.execute(select(models.User).where(models.User.id == assignee_id,models.User.tenant_id == tenant_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Assignee {assignee_id} does not belong to this tenant")
    return user

# Valid status transitions
VALID_TRANSITIONS = {
    models.TaskStatus.todo: [models.TaskStatus.in_progress],
    models.TaskStatus.in_progress: [models.TaskStatus.todo, models.TaskStatus.done],
    models.TaskStatus.done: [models.TaskStatus.in_progress],
}

def validate_status_transition(current: models.TaskStatus, new: models.TaskStatus):
    if new != current and new not in VALID_TRANSITIONS.get(current, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: '{current}' → '{new}'. "
                   f"Allowed: {[s.value for s in VALID_TRANSITIONS[current]]}"
        )


# List tasks with filters & pagination
@router.get("", response_model=PaginatedTaskResponse)
def get_tasks(
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
    assignee_id: Optional[int] = None,
    status: Optional[models.TaskStatus] = None,
    priority: Optional[models.TaskPriority] = None,
    due_start: Optional[date] = None,
    due_end: Optional[date] = None,
    search: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    tenant_id = current_user.tenant_id

    # Always scope to current tenant, never show deleted
    filters = [models.Task.is_deleted == False,models.Task.tenant_id == tenant_id]

    if assignee_id:
        validate_assignee(assignee_id, tenant_id, db)
        filters.append(models.Task.assignee_id == assignee_id)
    if status:
        filters.append(models.Task.status == status)
    if priority:
        filters.append(models.Task.priority == priority)
    if due_start and due_end:
        filters.append(models.Task.due_date.between(due_start, due_end))
    elif due_start:
        filters.append(models.Task.due_date >= due_start)
    elif due_end:
        filters.append(models.Task.due_date <= due_end)

    if search:
        filters.append(
            or_(
                models.Task.title.ilike(f"%{search}%"),
                models.Task.description.ilike(f"%{search}%")
            )
        )

    # Get total count for pagination metadata
    total = db.execute(select(func.count()).select_from(models.Task).where(and_(*filters))).scalar()

    tasks = db.execute(select(models.Task).where(and_(*filters)).limit(limit).offset(offset)).scalars().all()

    # Build next/prev links
    next_link = f"/api/tasks?limit={limit}&offset={offset + limit}" \
        if offset + limit < total else None
    prev_link = f"/api/tasks?limit={limit}&offset={max(offset - limit, 0)}" \
        if offset > 0 else None

    return PaginatedTaskResponse(
        total=total,
        limit=limit,
        offset=offset,
        next=next_link,
        previous=prev_link,
        data=tasks,
    )

# Get Soft Deleted Tasks
@router.get("/deleted", response_model=PaginatedTaskResponse)
def get_deleted_tasks(
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get all soft deleted tasks for current tenant."""
    tenant_id = current_user.tenant_id

    filters = [
        models.Task.is_deleted == True,
        models.Task.tenant_id == tenant_id,
    ]

    total = db.execute(select(func.count()).select_from(models.Task).where(and_(*filters))).scalar()
    tasks = db.execute(select(models.Task).where(and_(*filters)).limit(limit).offset(offset)).scalars().all()

    return PaginatedTaskResponse(
        total=total,
        limit=limit,
        offset=offset,
        next=None,
        previous=None,
        data=tasks,
    )


# Bulk create tasks
@router.post("/bulk", response_model=List[TaskResponse], status_code=status.HTTP_201_CREATED)
def create_tasks_bulk(payload: BulkTaskCreate,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):
    tenant_id = current_user.tenant_id
    created_tasks = []

    for task in payload.tasks:
        # Validate each assignee before inserting anything
        validate_assignee(task.assignee_id, tenant_id, db)

        new_task = models.Task(
            title=task.title,
            description=task.description,
            status=task.status or models.TaskStatus.todo,
            priority=task.priority or models.TaskPriority.medium,
            due_date=task.due_date,
            labels=task.labels,
            attachments=task.attachments,
            assignee_id=task.assignee_id,
            tenant_id=tenant_id,
            created_by=current_user.id,
            updated_by=None,
        )
        db.add(new_task)
        created_tasks.append(new_task)

    # Single commit for all tasks 
    db.commit()
    for t in created_tasks:
        db.refresh(t)
    return created_tasks


# Bulk update tasks
@router.patch("/bulk", response_model=List[TaskResponse])
def update_tasks_bulk(payload: List[BulkTaskUpdate],db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):
   
    tenant_id = current_user.tenant_id
    updated_tasks = []

    for item in payload:
        task = get_task_or_404(item.task_id, tenant_id, db)
        update_data = item.updates.model_dump(exclude_unset=True)

        if "status" in update_data:
            validate_status_transition(task.status, update_data["status"])

        if "assignee_id" in update_data:
            validate_assignee(update_data["assignee_id"], tenant_id, db)

        for field, value in update_data.items():
            setattr(task, field, value)

        task.updated_by = current_user.id
        updated_tasks.append(task)

    #Single commit for all updates
    db.commit()
    for t in updated_tasks:
        db.refresh(t)
    return updated_tasks


# Get single task
@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):
    return get_task_or_404(task_id, current_user.tenant_id, db)

# Create single task
@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):
    tenant_id = current_user.tenant_id

    # Validate assignee belongs to tenant
    validate_assignee(task.assignee_id, tenant_id, db)

    new_task = models.Task(
        title=task.title,
        description=task.description,
        status=task.status or models.TaskStatus.todo,
        priority=task.priority or models.TaskPriority.medium,
        due_date=task.due_date,
        labels=task.labels,
        attachments=task.attachments,
        assignee_id=task.assignee_id,
        tenant_id=tenant_id,
        # Audit trail to track who created it
        created_by=current_user.id,
        updated_by=None,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

   
# Partial update task
@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int,task_data: TaskUpdate,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):

    tenant_id = current_user.tenant_id
    task = get_task_or_404(task_id, tenant_id, db)
    update_data = task_data.model_dump(exclude_unset=True)

    #Validate status transition before applying
    if "status" in update_data:
        validate_status_transition(task.status, update_data["status"])

    #Validate new assignee belongs to tenant
    if "assignee_id" in update_data:
        validate_assignee(update_data["assignee_id"], tenant_id, db)

    for field, value in update_data.items():
        setattr(task, field, value)

    #Track who last updated the task
    task.updated_by = current_user.id

    db.commit()
    db.refresh(task)
    return task

# Soft delete task
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser,):
    task = get_task_or_404(task_id, current_user.tenant_id, db)
    task.is_deleted = True
    task.updated_by = current_user.id
    db.commit()


# Restore soft-deleted task
@router.patch("/restore/{task_id}", response_model=TaskResponse)
def restore_task(task_id: int,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser,):
    
    # include_deleted=True so we can find and restore it
    task = get_task_or_404(task_id, current_user.tenant_id, db, include_deleted=True)

    if not task.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Task is not deleted")

    task.is_deleted = False
    task.updated_by = current_user.id
    db.commit()
    db.refresh(task)
    return task