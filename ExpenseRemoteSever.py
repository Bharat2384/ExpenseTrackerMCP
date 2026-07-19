import os
import json
import aiosqlite
from fastmcp import FastMCP

DB_PATH = os.path.join(os.path.dirname(__file__), "expense.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("Expense Tracker")


# ---------------------------
# INIT DB (async)
# ---------------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as c:
        await c.execute("""
            CREATE TABLE IF NOT EXISTS EXPENSES_V1 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)
        await c.commit()


# ---------------------------
# ADD EXPENSE (async)
# ---------------------------
@mcp.tool
async def add_expense(date, amount, category, subcategory, note):
    """Add a new expense entry to the database."""
    async with aiosqlite.connect(DB_PATH) as c:
        cur = await c.execute(
            "INSERT INTO EXPENSES_V1(date, category, amount, subcategory, note) VALUES (?, ?, ?, ?, ?)",
            (date, category, amount, subcategory, note)
        )
        await c.commit()
        return {"status": "ok", "id": cur.lastrowid}


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

    async with aiosqlite.connect(DB_PATH) as c:
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

    async with aiosqlite.connect(DB_PATH) as c:
        cur = await c.execute(query, params)
        await c.commit()
        deleted_count = cur.rowcount

    return {"status": "ok", "deleted": deleted_count}


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

    async with aiosqlite.connect(DB_PATH) as c:
        cur = await c.execute(query, params)
        await c.commit()
        updated_count = cur.rowcount

    return {"status": "ok", "updated": updated_count}


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

    async with aiosqlite.connect(DB_PATH) as c:
        cur = await c.execute(query, params)
        rows = await cur.fetchall()

    ids = [r[0] for r in rows]

    return {"status": "ok", "count": len(ids), "ids": ids}


# ---------------------------
# RESOURCE (async)
# ---------------------------
@mcp.resource("expense://categories", mime_type="application/json")
async def categories():
    async with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return await f.read()


# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    mcp.run(transport="http", host="0.0.0.0", port=8000)
