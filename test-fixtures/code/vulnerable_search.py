"""User search module — INTENTIONALLY VULNERABLE for TB-3 testing.

This file contains a SQL injection vulnerability (CWE-89) that bandit
will flag as B608 (hardcoded_sql_expressions). The security gate should
catch this, and the agent should fix it to use parameterized queries.
"""

import sqlite3


def search_users(db_path: str, query: str) -> list[dict]:
    """Search users by name.

    Args:
        db_path: Path to the SQLite database.
        query: Search term for user name.

    Returns:
        List of matching user dicts with 'id' and 'name' keys.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # VULNERABILITY: String formatting in SQL query — SQL injection (CWE-89)
    cursor.execute(f"SELECT id, name FROM users WHERE name LIKE '%{query}%'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row[0], "name": row[1]} for row in rows]


def get_user_by_id(db_path: str, user_id: str) -> dict | None:
    """Get a single user by ID.

    Args:
        db_path: Path to the SQLite database.
        user_id: The user ID to look up.

    Returns:
        User dict or None if not found.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # VULNERABILITY: String formatting in SQL query — SQL injection (CWE-89)
    cursor.execute(f"SELECT id, name, email FROM users WHERE id = '{user_id}'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "email": row[2]}
    return None
