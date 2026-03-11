from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
import models
from auth import verify_password, create_access_token, hash_password
from database import get_db
from schemas import TokenResponse, RegisterRequest, RegisterResponse

router = APIRouter()

# Login Endpoint
@router.post("/login", response_model=TokenResponse)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],db: Annotated[Session, Depends(get_db)]):

    # Look up user by username
    user = db.execute(select(models.User).where(models.User.username == form_data.username)).scalars().first()
    
    #Doesn't reveal whether username or password was wrong
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password",headers={"WWW-Authenticate": "Bearer"})
    
    # Encode both user id AND tenant_id into the token
    access_token = create_access_token(data={"sub": str(user.id),"tenant_id": user.tenant_id})
    return TokenResponse(access_token=access_token)

# Register Tenant + Admin User
@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest,db: Annotated[Session, Depends(get_db)]):

    # Verify tenant exists
    tenant = db.execute(select(models.Tenant).where(models.Tenant.id == payload.tenant_id)).scalars().first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Tenant not found")
    
    # Check username uniqueness within tenant
    existing = db.execute(select(models.User).where(models.User.username == payload.username,models.User.tenant_id == payload.tenant_id)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username already taken in this tenant")

    # Check email uniqueness within tenant
    existing_email = db.execute(select(models.User).where(models.User.email == payload.email,models.User.tenant_id == payload.tenant_id)).scalars().first()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Email already registered in this tenant")

    user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        tenant_id=payload.tenant_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id),"tenant_id": user.tenant_id})

    return RegisterResponse(
        tenant_id=tenant.id,
        user_id=user.id,
        username=user.username,
        access_token=access_token
    )