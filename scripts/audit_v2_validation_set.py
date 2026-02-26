# 檔案名稱: audit_v2_validation_set.py
#
# 目的：
# 1. 讀取「主要驗證集」 (v2_validation_set_master)
# 2. 將其匯出成 CSV，方便你手動審查 (Audit) 品質

import pandas as pd
import sqlite3
import os

# --- 設定區 ---
DB_PATH = "ptt_data_m.db"

# 你的「主要驗證集」表格
MASTER_VAL_TABLE = "v2_validation_set_master"

OUTPUT_CSV = "v2_validation_set_audit.csv"

LABEL_MAP = {
    0: 'Negative',
    1: 'Neutral',
    2: 'Positive'
}
# --- ---

def main():
    print(f"🚀 正在匯出「主要驗證集」({MASTER_VAL_TABLE}) ...")
    
    # 1. 載入資料庫
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT text, label_id FROM {MASTER_VAL_TABLE}", conn)
        conn.close()
    except Exception as e:
        print(f"錯誤：無法從資料庫讀取 {MASTER_VAL_TABLE}: {e}")
        print("你是否已經執行了「步驟二」的 import_validation_set_to_db.py 腳本？")
        return

    if len(df) == 0:
        print(f"警告：表格 {MASTER_VAL_TABLE} 中沒有資料。")
        return

    # 2. 增加可讀性
    df['label_name'] = df['label_id'].map(LABEL_MAP)
    
    # 3. 匯出 CSV 供你手動檢視
    try:
        # 排序，方便你檢視
        df = df.sort_values(by=['label_name'])
        
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        
        print("\n🎉🎉🎉 匯出成功！🎉🎉🎉")
        print(f"所有 {len(df)} 筆「驗證集」資料已儲存至:")
        print(f"{OUTPUT_CSV}")
        
        print("\n標籤分佈 (來自 v2_validation_set_master):")
        print(df['label_name'].value_counts().sort_index().to_string())

    except Exception as e:
        print(f"\n錯誤：儲存 CSV 失敗: {e}")

if __name__ == "__main__":
    main()