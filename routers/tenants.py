from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas import TenantCreate, TenantResponse

router = APIRouter()

# Create Tenant
@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(tenant: TenantCreate,db: Annotated[Session, Depends(get_db)]):
    # Prevent duplicate tenant names
    existing = db.execute(select(models.Tenant).where(models.Tenant.name == tenant.name)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Tenant with this name already exists")

    new_tenant = models.Tenant(name=tenant.name)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return new_tenant

# Get Tenant by ID
@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: int,db: Annotated[Session, Depends(get_db)]):
    tenant = db.execute(select(models.Tenant).where(models.Tenant.id == tenant_id)).scalars().first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant