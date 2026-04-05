# -*- coding: utf-8 -*-
"""Unit tests for src/utils/db_utils.py"""
import os
import sqlite3
import tempfile
import pytest

from src.utils.db_utils import get_conn


def test_get_conn_default_creates_connection(tmp_path, monkeypatch):
    """get_conn() should return a working sqlite3 connection."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)

    conn = get_conn()
    assert conn is not None
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_get_conn_explicit_path(tmp_path):
    """get_conn(db_path) should use the explicitly provided path."""
    db_file = str(tmp_path / "explicit.db")
    conn = get_conn(db_path=db_file)
    assert conn is not None
    conn.close()
    assert os.path.exists(db_file)


def test_get_conn_wal_mode(tmp_path):
    """get_conn() should enable WAL journal mode."""
    db_file = str(tmp_path / "wal_test.db")
    conn = get_conn(db_path=db_file)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_get_conn_supports_basic_query(tmp_path):
    """Connection returned by get_conn() should support basic SQL operations."""
    db_file = str(tmp_path / "query_test.db")
    conn = get_conn(db_path=db_file)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO t (val) VALUES (?)", ("hello",))
    conn.commit()
    row = conn.execute("SELECT val FROM t").fetchone()
    conn.close()
    assert row[0] == "hello"
