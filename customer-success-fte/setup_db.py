import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from src.database.connection import init_db, create_all_tables, get_engine
from sqlalchemy import text

async def setup_db():
    print("Initialising database...")
    init_db()
    
    engine = get_engine()
    
    # Check for pgvector extension
    async with engine.begin() as conn:
        print("Checking/Creating pgvector extension...")
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            print("pgvector extension ready.")
        except Exception as e:
            print(f"Warning: Could not create pgvector extension: {e}")
            print("Ensure your database user has sufficient permissions.")

    # Step 1: Drop everything for a clean slate
    print("Cleaning existing schema...")
    async with engine.begin() as conn:
        try:
            # Drop views first
            await conn.execute(text("DROP VIEW IF EXISTS v_daily_metrics CASCADE"))
            await conn.execute(text("DROP VIEW IF EXISTS v_customer_open_tickets CASCADE"))
            
            # Drop tables
            tables = [
                "agent_metrics", "knowledge_base", "tickets", 
                "messages", "conversations", "customer_identifiers", "customers"
            ]
            for table in tables:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            
            # Drop types
            types = ["channel_type", "ticket_status", "ticket_priority", "message_role", "identifier_type"]
            for t in types:
                await conn.execute(text(f"DROP TYPE IF EXISTS {t} CASCADE"))
                
            print("Schema cleaned.")
        except Exception as e:
            print(f"Warning during cleaning: {e}")

    # Dispose engine to ensure fresh connection pool for create step
    await engine.dispose()
    
    # Step 2: Fresh connect and apply schema.sql
    print("Applying schema.sql...")
    engine = get_engine() # Re-gets the singleton (or we should call create_engine again)
    # Actually get_engine might return the same object. Let's just use create_engine
    from src.database.connection import create_engine as _create_engine
    engine = _create_engine()

    try:
        schema_path = os.path.join("src", "database", "schema.sql")
        with open(schema_path, "r") as f:
            sql = f.read()
            
        # Robust SQL splitter for PostgreSQL
        statements = []
        current_stmt = []
        in_dollar_block = False
        
        for line in sql.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                continue
            
            # Simple dollar block tracking (matches $$)
            if '$$' in line:
                in_dollar_block = not in_dollar_block
            
            current_stmt.append(line)
            
            if ';' in line and not in_dollar_block:
                # This might still be naive if there are multiple ; on a line 
                # but it's better than before.
                statements.append('\n'.join(current_stmt))
                current_stmt = []
        
        async with engine.begin() as conn:
            print("Applying schema statements...")
            for stmt in statements:
                if not stmt.strip(): continue
                # print(f"Executing: {stmt[:50].strip()}...")
                await conn.execute(text(stmt))
        print("Schema applied successfully from schema.sql.")
    except Exception as e:
        print(f"Error applying schema.sql: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
    finally:
        await engine.dispose()

    # print("Creating tables...")
    # try:
    #     await create_all_tables()
    #     print("Tables created successfully.")
    # except Exception as e:
    #     print(f"Error creating tables: {e}")

if __name__ == "__main__":
    asyncio.run(setup_db())
