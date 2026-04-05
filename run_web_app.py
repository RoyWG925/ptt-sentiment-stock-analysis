#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask Web 標註系統啟動腳本
"""
import sys
import os

# 將專案根目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 執行 Flask 應用程式
if __name__ == "__main__":
    from src.web_app.app import app, ensure_base_tables, build_queue, get_conn, HOST, PORT, DEBUG

    print("🚀 正在啟動 PTT 情緒標註系統...")

    # 初始化資料庫
    ensure_base_tables()

    # 建立固定順序 queue
    conn = get_conn()
    build_queue(conn)
    conn.close()

    print("✅ 資料庫初始化完成")
    print(f"🌐 請開啟瀏覽器訪問: http://localhost:{PORT}")

    # 啟動應用程式
    app.run(host=HOST, port=PORT, debug=DEBUG)
