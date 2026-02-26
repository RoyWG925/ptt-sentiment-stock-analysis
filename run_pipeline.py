#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
資料處理 Pipeline 執行腳本
"""
import sys
import os

# 將專案根目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 PTT 情緒分析資料處理 Pipeline")
    print("=" * 60)
    
    # Step 1: 資料清洗與特徵工程
    print("\n[Step 1/2] 執行資料清洗與特徵工程...")
    from src.pipeline.data_pipeline import main as pipeline_main
    pipeline_main()
    
    # Step 2: 統計分析
    print("\n[Step 2/2] 執行統計分析...")
    from src.pipeline.thesis_stats import main as stats_main
    stats_main()
    
    print("\n" + "=" * 60)
    print("✅ Pipeline 執行完成！")
    print("=" * 60)
