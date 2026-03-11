from fastapi import FastAPI
from database import Base, engine
from routers import authentication, tasks, users, tenants


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(authentication.router, prefix="/api/auth", tags=['auth'])
app.include_router(tenants.router, prefix="/api/tenants", tags=["Tenants"])