import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import text
from src.database.connection import init_db, get_engine

async def check():
    load_dotenv(override=True)
    init_db()
    engine = get_engine()
    async with engine.connect() as conn:
        # Check current database and user
        db_info = await conn.execute(text("SELECT current_database(), current_user, current_schema()"))
        info = db_info.fetchone()
        print(f"Connected to: DB={info[0]}, User={info[1]}, Schema={info[2]}")
        
        # Check tables
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = res.fetchall()
        print(f"Tables in 'public' schema: {[t[0] for t in tables]}")

if __name__ == "__main__":
    asyncio.run(check())
