import aiosqlite
import os

class DatabaseManager:
    _db_file = "database.db"

    @classmethod
    async def get_connection(cls):
        conn = await aiosqlite.connect(cls._db_file)
        conn.row_factory = aiosqlite.Row
        return conn

    @staticmethod
    async def execute(query, *args):
        """For queries that don't return data (INSERT, UPDATE, DELETE)."""
        async with aiosqlite.connect(DatabaseManager._db_file) as db:
            await db.execute(query, args)
            await db.commit()

    @staticmethod
    async def fetch(query, *args):
        """For queries that return multiple records."""
        async with aiosqlite.connect(DatabaseManager._db_file) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, args) as cursor:
                return await cursor.fetchall()

    @staticmethod
    async def fetchrow(query, *args):
        """For queries that return a single record."""
        async with aiosqlite.connect(DatabaseManager._db_file) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, args) as cursor:
                return await cursor.fetchone()

    @staticmethod
    async def fetchval(query, *args):
        """For queries that return a single value from a single record."""
        async with aiosqlite.connect(DatabaseManager._db_file) as db:
            async with db.execute(query, args) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    @staticmethod
    async def log_event(event_type: str, actor_id: str, trace_id: str, payload: dict):
        """Log a system trace event to the database."""
        import json
        query = """
            INSERT INTO sys_trace_stream (event_type, actor_id, trace_id, payload)
            VALUES (?, ?, ?, ?)
        """
        await DatabaseManager.execute(query, event_type, actor_id, trace_id, json.dumps(payload))

    @staticmethod
    async def get_recent_logs(limit: int = 30):
        """Fetch the most recent logs from the database, sorted by id descending."""
        query = """
            SELECT id, event_type, actor_id, trace_id, created_at, payload
            FROM sys_trace_stream
            ORDER BY id DESC
            LIMIT ?
        """
        rows = await DatabaseManager.fetch(query, limit)
        import json
        logs = []
        for row in rows:
            try:
                payload_data = json.loads(row["payload"])
            except Exception:
                payload_data = {"raw": row["payload"]}
            logs.append({
                "id": row["id"],
                "event_type": row["event_type"],
                "actor_id": row["actor_id"],
                "trace_id": row["trace_id"],
                "created_at": row["created_at"],
                "payload": payload_data
            })
        return logs

    @staticmethod
    async def get_new_logs(last_id: int, limit: int = 50):
        """Fetch new logs newer than the specified last_id."""
        query = """
            SELECT id, event_type, actor_id, trace_id, created_at, payload
            FROM sys_trace_stream
            WHERE id > ?
            ORDER BY id ASC
            LIMIT ?
        """
        rows = await DatabaseManager.fetch(query, last_id, limit)
        import json
        logs = []
        for row in rows:
            try:
                payload_data = json.loads(row["payload"])
            except Exception:
                payload_data = {"raw": row["payload"]}
            logs.append({
                "id": row["id"],
                "event_type": row["event_type"],
                "actor_id": row["actor_id"],
                "trace_id": row["trace_id"],
                "created_at": row["created_at"],
                "payload": payload_data
            })
        return logs

# Add a function to be called during bot startup and shutdown
async def connect_database():
    # Initialize schema if needed
    if not os.path.exists(DatabaseManager._db_file):
        print("Creating new database file...")
    
    try:
        with open('database/schema.sql', 'r') as f:
            schema = f.read()
        
        async with aiosqlite.connect(DatabaseManager._db_file) as db:
            await db.executescript(schema)
            await db.commit()
        print("Database schema initialized/verified.")
    except Exception as e:
        print(f"Error initializing database: {e}")

async def disconnect_database():
    # No persistent pool to close with aiosqlite in this simple implementation
    pass