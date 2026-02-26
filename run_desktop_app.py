#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌面標註工具啟動腳本
"""
import sys
import os

# 將專案根目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 正在啟動桌面標註工具...")
    
    # 執行桌面應用程式
    from src.desktop_app.advanced_label_tool import StartupWindow
    import tkinter as tk
    
    startup_root = tk.Tk()
    app = StartupWindow(startup_root)
    startup_root.mainloop()
