from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


db_url = "postgresql://postgres:97135@localhost:5432/tasksdb"
engine = create_engine(db_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
       yield session