from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
import models
from auth import CurrentUser, hash_password
from database import get_db
from schemas import TaskResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter()


# Create User
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):

    #Create a new user in the same tenant as the currently authenticated user
    tenant_id = current_user.tenant_id

    #Check username uniqueness within tenant
    existing = db.execute(select(models.User).where(models.User.username == user.username,models.User.tenant_id == tenant_id)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username already exists in this tenant")

    #Check email uniqueness within tenant
    existing_email = db.execute(select(models.User).where(models.User.email == user.email,models.User.tenant_id == tenant_id)).scalars().first()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Email already registered in this tenant")

    new_user = models.User(username=user.username,email=user.email,password_hash=hash_password(user.password),tenant_id=tenant_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# Get User by ID
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):
    
    tenant_id = current_user.tenant_id
     #Tenant isolation — can only see users in your tenant
    user = db.execute(select(models.User).where(models.User.id == user_id,models.User.tenant_id == tenant_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    return user

# Get User's Tasks
@router.get("/{user_id}/tasks", response_model=list[TaskResponse])
def get_user_tasks(user_id: int,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser):
    
    tenant_id = current_user.tenant_id
    # Verify user exists in this tenant first
    user = db.execute(select(models.User).where(models.User.id == user_id,models.User.tenant_id == tenant_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")

    tasks = db.execute(select(models.Task).where(models.Task.assignee_id == user_id,models.Task.tenant_id == tenant_id,models.Task.is_deleted == False)).scalars().all()
    return tasks

# Update User (Partial)
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int,user_update: UserUpdate,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser,):
   
    tenant_id = current_user.tenant_id
    user = db.execute(select(models.User).where(models.User.id == user_id,models.User.tenant_id == tenant_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")

    #Only validate uniqueness if value is actually changing
    if user_update.username and user_update.username != user.username:
        existing = db.execute(select(models.User).where(models.User.username == user_update.username,models.User.tenant_id == tenant_id)).scalars().first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username already exists in this tenant")
        user.username = user_update.username

    if user_update.email and user_update.email != user.email:
        existing = db.execute(select(models.User).where(models.User.email == user_update.email,models.User.tenant_id == tenant_id)).scalars().first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Email already registered in this tenant")
        user.email = user_update.email

    if user_update.password:
        user.password_hash = hash_password(user_update.password)

    db.commit()
    db.refresh(user)
    return user

# Delete User
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int,db: Annotated[Session, Depends(get_db)],current_user: CurrentUser,):
    
    tenant_id = current_user.tenant_id
    # Prevent user from deleting themselves
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="You cannot delete your own account")
    
    user = db.execute(select(models.User).where(models.User.id == user_id,models.User.tenant_id == tenant_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")

    db.delete(user)
    db.commit()