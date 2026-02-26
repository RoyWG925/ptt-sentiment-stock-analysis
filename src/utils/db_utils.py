# -*- coding: utf-8 -*-
"""
資料庫連線工具模組
提供統一的資料庫連線介面
"""
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def get_conn(db_path=None):
    """
    統一的資料庫連線函式
    
    Args:
        db_path: 資料庫檔案路徑，若為 None 則使用環境變數 DB_PATH
        
    Returns:
        sqlite3.Connection: 資料庫連線物件
    """
    if db_path is None:
        db_path = os.getenv("DB_PATH", "database/ptt_data.db")
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    return conn
