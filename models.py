from __future__ import annotations
from datetime import UTC, datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Enum as SQLAEnum, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from schemas import TaskPriority, TaskStatus 


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    users: Mapped[list[User]] = relationship(back_populates="tenant")
    tasks: Mapped[list[Task]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    tasks: Mapped[list[Task]] = relationship(back_populates="assignee",foreign_keys="Task.assignee_id",cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Required fields
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SQLAEnum(TaskStatus), default=TaskStatus.todo, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(SQLAEnum(TaskPriority), default=TaskPriority.medium, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Audit fields
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Optional fields
    labels: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    attachments: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assignee: Mapped[User] = relationship(back_populates="tasks",foreign_keys=[assignee_id])
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])
    tenant: Mapped[Tenant] = relationship(back_populates="tasks")

    # Timestamps and soft delete
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)