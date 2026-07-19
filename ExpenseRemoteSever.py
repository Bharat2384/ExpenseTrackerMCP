# IMPORTS EXPLANATION:
# - sqlite3: Standard library for SYNCHRONOUS database operations
#   ISSUE: Used for synchronous init to avoid asyncio.run() conflicts
# - aiosqlite: Async wrapper around sqlite3 for non-blocking database calls
#   ISSUE: The original code was missing this dependency (>= 0.22.1)
# - aiofiles: Async file I/O operations (previously used blocking open())
#   ISSUE: Original code used synchronous open() in an async function which blocks the event loop
import os
import json
import sqlite3
import aiosqlite
import aiofiles
from fastmcp import FastMCP

DB_PATH = os.path.join(os.path.dirname(__file__), "expense.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("Expense Tracker")


# ---------------------------
# INIT DB (sync) - CHANGED FROM ASYNC TO SYNC
# ---------------------------
# PROBLEM #1 (Original code used async init_db):
#   - Original: Used "async def init_db()" with asyncio.run(init_db())
#   - Error: RuntimeError - asyncio.run() cannot be called from a running event loop
#   - Why: FastMCP runs its own event loop. Calling asyncio.run() during module import
#     tries to create a nested event loop, which Python doesn't allow.
#
# SOLUTION: Use synchronous sqlite3 for database initialization
#   - sqlite3 is part of Python standard library
#   - No event loop conflicts
#   - Database setup only happens once on module load
#   - Actual tool operations still use async aiosqlite for non-blocking I/O

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # FIX #5: Enable WAL (Write-Ahead Logging) mode
    # - WAL mode improves concurrency and write performance
    # - Allows readers and writers to work together without blocking
    # - Creates -wal and -shm files, so directory must have write permissions
    c.execute("PRAGMA journal_mode=WAL")

    # Create table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS EXPENSES_V1 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


# Initialize database on module load (happens once when server starts)
# PROBLEM #2 (Original: Database was never initialized when FastMCP runs):
#   - Original: init_db() only called if __name__ == "__main__"
#   - Error: "unable to open database file" when using FastMCP as a server
#   - Why: When FastMCP imports the module as a server, it skips the main block,
#     so the database was never created. Then add_expense() couldn't find the table.
#
# SOLUTION: Call init_db() at module level (outside the if __name__ block)
#   - Ensures database is created whenever module is imported
#   - Works with both direct execution and FastMCP server import

# PROBLEM #5 (SQLite readonly database error):
#   - Error: "attempt to write a readonly database"
#   - Cause: SQLite needs write access to directory for temp files (-wal, -shm)
#   - Solution: Enable WAL mode and ensure proper permissions
init_db()


# ---------------------------
# DATABASE CONNECTION HELPER
# ---------------------------
# FIX #5: Configure aiosqlite connections for proper write access
# - timeout=30: Wait up to 30 seconds if database is locked (retry mechanism)
# - isolation_level=None: Use autocommit mode so we control transactions explicitly
async def get_db():
    """Open a configured database connection with proper settings."""
    db = await aiosqlite.connect(DB_PATH, timeout=30)
    db.isolation_level = None  # Autocommit mode
    return db


# ---------------------------
# ADD EXPENSE (async)
# ---------------------------
@mcp.tool
async def add_expense(date, amount, category, subcategory, note):
    """Add a new expense entry to the database."""
    # FIX #5: Use configured connection with timeout and proper transaction handling
    try:
        async with await get_db() as c:
            cur = await c.execute(
                "INSERT INTO EXPENSES_V1(date, category, amount, subcategory, note) VALUES (?, ?, ?, ?, ?)",
                (date, category, amount, subcategory, note)
            )
            await c.commit()
            return {"status": "ok", "id": cur.lastrowid}
    except Exception as e:
        # Better error reporting for debugging
        return {"status": "error", "message": f"Database error: {str(e)}"}


# ---------------------------
# LIST EXPENSES (async)
# ---------------------------
@mcp.tool
async def list_expenses(start_date: str | None = None,
                        end_date: str | None = None,
                        category: str | None = None):
    """List expenses filtered by date range and category."""

    query = """
        SELECT date, amount, category, subcategory, note
        FROM EXPENSES_V1
        WHERE 1 = 1
    """

    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    if category:
        query += " AND category = ?"
        params.append(category)

    # FIX #5: Use configured connection with timeout
    try:
        async with await get_db() as c:
            cur = await c.execute(query, params)
            rows = await cur.fetchall()

        expenses = [
            {
                "date": r[0],
                "amount": r[1],
                "category": r[2],
                "subcategory": r[3],
                "note": r[4],
            }
            for r in rows
        ]

        return {"status": "ok", "count": len(expenses), "expenses": expenses}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}


# ---------------------------
# DELETE EXPENSES (async)
# ---------------------------
@mcp.tool
async def delete_expenses(id: int | None = None,
                          frmdate: str | None = None,
                          category: str | None = None):
    """Delete specific expenses from the database."""

    if not any([id, frmdate, category]):
        raise ValueError("At least one filter must be provided.")

    query = "DELETE FROM EXPENSES_V1 WHERE 1 = 1"
    params = []

    if id:
        query += " AND id = ?"
        params.append(id)

    if frmdate:
        query += " AND date < ?"
        params.append(frmdate)

    if category:
        query += " AND category = ?"
        params.append(category)

    # FIX #5: Use configured connection with timeout
    try:
        async with await get_db() as c:
            cur = await c.execute(query, params)
            await c.commit()
            deleted_count = cur.rowcount

        return {"status": "ok", "deleted": deleted_count}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}


# ---------------------------
# UPDATE EXPENSE (async)
# ---------------------------
@mcp.tool
async def update_expense(id: int | None = None,
                         date: str | None = None,
                         amount: float | None = None,
                         category: str | None = None,
                         subcategory: str | None = None,
                         note: str | None = None):
    """Update an existing expense entry."""

    if not id:
        raise ValueError("An 'id' must be provided to update an expense.")

    if not any([date, amount, category, subcategory, note]):
        raise ValueError("At least one field must be provided to update.")

    update_clause = []
    params = []

    if date:
        update_clause.append("date = ?")
        params.append(date)

    if amount is not None:
        update_clause.append("amount = ?")
        params.append(amount)

    if category:
        update_clause.append("category = ?")
        params.append(category)

    if subcategory:
        update_clause.append("subcategory = ?")
        params.append(subcategory)

    if note:
        update_clause.append("note = ?")
        params.append(note)

    query = f"""
        UPDATE EXPENSES_V1
        SET {", ".join(update_clause)}
        WHERE id = ?
    """

    params.append(id)

    # FIX #5: Use configured connection with timeout
    try:
        async with await get_db() as c:
            cur = await c.execute(query, params)
            await c.commit()
            updated_count = cur.rowcount

        return {"status": "ok", "updated": updated_count}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}


# ---------------------------
# GET ID (async)
# ---------------------------
@mcp.tool
async def get_id(date: str | None = None,
                 amount: float | None = None,
                 category: str | None = None,
                 subcategory: str | None = None,
                 note: str | None = None):
    """Retrieve expense IDs matching the given filters."""

    if not any([date, amount, category, subcategory, note]):
        raise ValueError("At least one filter must be provided.")

    query = "SELECT id FROM EXPENSES_V1 WHERE 1 = 1"
    params = []

    if date:
        query += " AND date = ?"
        params.append(date)

    if amount is not None:
        query += " AND amount = ?"
        params.append(amount)

    if category:
        query += " AND category = ?"
        params.append(category)

    if subcategory:
        query += " AND subcategory = ?"
        params.append(subcategory)

    if note:
        query += " AND note LIKE ?"
        params.append(f"%{note}%")

    # FIX #5: Use configured connection with timeout
    try:
        async with await get_db() as c:
            cur = await c.execute(query, params)
            rows = await cur.fetchall()

        ids = [r[0] for r in rows]

        return {"status": "ok", "count": len(ids), "ids": ids}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}


# ---------------------------
# RESOURCE (async) - CHANGED TO USE aiofiles
# ---------------------------
# PROBLEM #3 (Original used blocking open() in async function):
#   - Original: Used "with open(...)" inside async function
#   - Issue: open() is BLOCKING (synchronous), not async
#   - Why it's bad: When async function awaits on blocking I/O, it BLOCKS the entire
#     event loop, preventing other tools from running concurrently
#   - Symptom: Server becomes unresponsive during file reads
#
# SOLUTION: Use aiofiles for non-blocking file I/O
#   - aiofiles.open() returns an awaitable file object
#   - Doesn't block the event loop
#   - Other async operations can run while reading files
#   - Added aiofiles>=23.0.0 to pyproject.toml dependencies

@mcp.resource("expense://categories", mime_type="application/json")
async def categories():
    async with aiofiles.open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return await f.read()


# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
