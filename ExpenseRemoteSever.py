from fastmcp import FastMCP
import os
import sqlite3

DB_PATH= os.path.join(os.path.dirname(__file__),'expense.db')
CATEGORIES_PATH=os.path.join(os.path.dirname(__file__),'categories.json')

#initiate mcp server
mcp=FastMCP('Expense tracker')



#create connection
def init_db():
    with sqlite3.connect(DB_PATH) as c:
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

init_db()


@mcp.tool
def add_expense(date, amount, category, subcategory, note):
    """Add a new expense entry to the database."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT INTO EXPENSES_V1(date, category, amount, subcategory, note) VALUES (?, ?, ?, ?, ?)",
            (date, category,amount , subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}

@mcp.tool
def list_expenses(start_date: str | None = None,
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

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)
        rows = cur.fetchall()

    # Convert rows → list of dicts
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

    return {
        "status": "ok",
        "count": len(expenses),
        "expenses": expenses
    }

@mcp.tool
def delete_expenses(
    id: int ,
    frmdate: str | None = None,
    category: str | None = None
):
    """Delete specific expenses from the database."""

    query = """
        DELETE FROM EXPENSES_V1
        WHERE 1 = 1
    """

    params = []

    if not(id) and not(frmdate) and not(category):
         raise ValueError("At least one filter must be provided.")

    if id:
        query += " AND id = ?"
        params.append(id)

    if frmdate:
        # delete entries older than frmdate
        query += " AND date < ?"
        params.append(frmdate)

    if category:
        query += " AND category = ?"
        params.append(category)

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)
        deleted_count = cur.rowcount

    return {
        "status": "ok",
        "deleted": deleted_count
    }

@mcp.tool
def update_expense(
    id: int | None = None,
    date: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None
):
    """Update an existing expense entry."""

    # Require at least one filter
    if not id:
        raise ValueError("An 'id' must be provided to update an expense.")

    # Require at least one field to update
    if not any([date, amount, category, subcategory, note]):
        raise ValueError("At least one field must be provided to update.")

    # Build UPDATE clause
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

    # Build final SQL
    query = f"""
        UPDATE EXPENSES_V1
        SET {", ".join(update_clause)}
        WHERE id = ?
    """

    params.append(id)

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)
        updated_count = cur.rowcount

    return {
        "status": "ok",
        "updated": updated_count
    }

@mcp.tool
def get_id(
    date: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None
):
    """Retrieve expense IDs matching the given filters."""

    # Require at least one filter
    if not any([date, amount, category, subcategory, note]):
        raise ValueError("At least one filter must be provided to search for IDs.")

    query = """
        SELECT id
        FROM expenses
        WHERE 1 = 1
    """

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
        params.append(f"%{note}%")   # partial match

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)
        rows = cur.fetchall()

    ids = [r[0] for r in rows]

    return {
        "status": "ok",
        "count": len(ids),
        "ids": ids
    }

@mcp.resource("expense://categories",mime_type='application/json')
def categories():
    with open(CATEGORIES_PATH,"r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
  mcp.run(transport="http",host="0.0.0.0",port=8000)