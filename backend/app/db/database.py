from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=True,    
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
Base = declarative_base()

async_engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 의존성 주입용 함수 (FastAPI용)
async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session
        
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()