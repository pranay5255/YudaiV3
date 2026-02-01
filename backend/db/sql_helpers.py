"""
SQL utility functions for vanilla SQL queries using psycopg3
"""

from typing import Optional, List, Any, Dict
from psycopg import Connection


def execute_query(conn: Connection, query: str, params: tuple = None) -> List[Dict]:
    """
    Execute SELECT query and return all results as dicts

    Args:
        conn: Database connection
        query: SQL query string with %s placeholders
        params: Tuple of parameters for query

    Returns:
        List of dict rows
    """
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def execute_one(conn: Connection, query: str, params: tuple = None) -> Optional[Dict]:
    """
    Execute SELECT query and return single result

    Args:
        conn: Database connection
        query: SQL query string with %s placeholders
        params: Tuple of parameters for query

    Returns:
        Single dict row or None if no result
    """
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchone()


def execute_scalar(conn: Connection, query: str, params: tuple = None) -> Any:
    """
    Execute query and return single value

    Args:
        conn: Database connection
        query: SQL query string with %s placeholders
        params: Tuple of parameters for query

    Returns:
        Single value (first column of first row) or None
    """
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        row = cur.fetchone()
        return list(row.values())[0] if row else None


def execute_write(conn: Connection, query: str, params: tuple = None) -> int:
    """
    Execute INSERT/UPDATE/DELETE and return affected rows

    Args:
        conn: Database connection
        query: SQL query string with %s placeholders
        params: Tuple of parameters for query

    Returns:
        Number of affected rows
    """
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.rowcount
