#!/usr/bin/env python3
"""
Base Repository - Common database operations
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config import DB_CONFIG


class BaseRepository:
    """Base class for all repositories with common DB operations"""

    def __init__(self):
        self._connection = None

    def get_connection(self):
        """Create a new database connection"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except Exception as e:
            print(f"Database connection error: {e}")
            return None

    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """Context manager for database cursor"""
        conn = self.get_connection()
        if not conn:
            yield None
            return

        try:
            cursor_factory = RealDictCursor if dict_cursor else None
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                yield cur
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def execute_query(
        self,
        query: str,
        params: tuple = None,
        fetch_one: bool = False,
        fetch_all: bool = True
    ) -> Optional[Any]:
        """Execute a query and return results"""
        with self.get_cursor() as cur:
            if cur is None:
                return None

            cur.execute(query, params)

            if fetch_one:
                return cur.fetchone()
            elif fetch_all:
                return cur.fetchall()
            return None

    def execute_insert(self, query: str, params: tuple = None) -> bool:
        """Execute an insert/update query"""
        with self.get_cursor() as cur:
            if cur is None:
                return False

            cur.execute(query, params)
            return True

    @classmethod
    def check_db_available(cls) -> bool:
        """Check if database is available"""
        repo = cls()
        conn = repo.get_connection()
        if conn:
            conn.close()
            return True
        return False
