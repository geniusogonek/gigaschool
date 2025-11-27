from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


class Base(DeclarativeBase):
    pass


async def init_db(url: str):
    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
#        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    return engine


def get_session_maker(engine):
    return sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
