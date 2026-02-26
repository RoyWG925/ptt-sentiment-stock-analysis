# 檔案名稱: audit_v2_training_set.py
#
# 目的：
# 1. 抓取「所有」V2 模型的訓練資料 (JSON + DB)。
# 2. 將它們合併成一個 CSV 檔案。
# 3. 統計完整的訓練集標籤分佈，並按來源分類。

import pandas as pd
import sqlite3
import os

# --- 設定區 ---
DB_PATH = "ptt_data_m.db"
MANUAL_TABLE = "manual_labels_extra"
CONSENSUS_FILE = "./ptt_raw_consensus_push_only/train.json"

OUTPUT_CSV = "v2_full_training_set_audit.csv"

LABEL_MAP = {
    0: 'Negative',
    1: 'Neutral',
    2: 'Positive'
}
# --- ---

def load_json_data(filepath):
    """從 V2 共識 train.json 載入資料"""
    print(f"--- 正在載入: {filepath} ---")
    if not os.path.exists(filepath):
        print(f"錯誤：找不到檔案 {filepath}，將會跳過。")
        return pd.DataFrame()
        
    df = pd.read_json(filepath, orient='records')
    
    # 統一欄位名稱
    if 'labels' in df.columns:
        df.rename(columns={'labels': 'label_id'}, inplace=True)
    
    if 'label_id' not in df.columns or 'text' not in df.columns:
        print(f"錯誤： {filepath} 缺少 'text' 或 'label_id' 欄位。")
        return pd.DataFrame()
        
    df['source'] = 'Consensus_JSON'
    print(f"  > 成功載入 {len(df)} 筆 (來自 JSON)")
    return df[['text', 'label_id', 'source']]

def load_db_data(db_path, table_name):
    """從 manual_labels_extra 資料庫表格載入資料"""
    print(f"--- 正在載入: {db_path} (表格: {table_name}) ---")
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(f"SELECT text, label_id FROM {table_name}", conn)
        conn.close()
        
        df['source'] = 'Manual_DB'
        print(f"  > 成功載入 {len(df)} 筆 (來自 DB)")
        return df[['text', 'label_id', 'source']]
    except Exception as e:
        print(f"錯誤：無法從資料庫讀取 {table_name}: {e}")
        return pd.DataFrame()

def print_stats(df, title):
    """輔助函式：印出標籤分佈"""
    print(f"\n{title}")
    total = len(df)
    if total == 0:
        print("  (無資料)")
        return
        
    counts = df['label_id'].map(LABEL_MAP).value_counts().sort_index()
    percents = (counts / total) * 100
    
    stats_df = pd.DataFrame({'Count': counts, 'Percent': percents.round(1)})
    print(stats_df.to_string())
    print(f"  Total: {total}")

# --- 主程式 ---
if __name__ == "__main__":
    print("🚀 正在抓取「所有」V2 訓練資料...")
    
    # 1. 載入兩個來源
    df_json = load_json_data(CONSENSUS_FILE)
    df_db = load_db_data(DB_PATH, MANUAL_TABLE)
    
    if df_json.empty and df_db.empty:
        print("\n錯誤：兩個資料來源均為空，無法執行。")
        exit()
        
    # 2. 合併
    df_all_train = pd.concat([df_json, df_db], ignore_index=True)
    
    total_raw_count = len(df_all_train)
    
    # 3. 檢查重複 (非常重要！)
    # 檢查是否有文本同時存在於 JSON 和 DB 中
    df_all_train.drop_duplicates(subset=['text'], keep='last', inplace=True)
    total_unique_count = len(df_all_train)
    
    num_duplicates = total_raw_count - total_unique_count
    
    # 4. 產生報告
    print("\n" + "="*50)
    print("      V2 完整訓練集 (Unique) 審計報告")
    print("="*50)
    print(f"  原始總筆數 (JSON + DB): {total_raw_count}")
    print(f"  重複文本數 (已移除): {num_duplicates}")
    print(f"  最終獨特訓練樣本數: {total_unique_count}")
    
    # 統計 1: 總體標籤分佈
    print_stats(df_all_train, "--- 1. 總體標籤分佈 (Unique) ---")
    
    # 統計 2: 按來源分類 (這就是你想要的)
    print("\n--- 2. 按來源分類 (Count) ---")
    # map 讓 0,1,2 變成可讀的 Negative, Neutral, Positive
    crosstab = pd.crosstab(
        df_all_train['source'], 
        df_all_train['label_id'].map(LABEL_MAP)
    )
    print(crosstab)
    
    # 5. 匯出 CSV 供你手動檢視
    try:
        df_all_train['label_name'] = df_all_train['label_id'].map(LABEL_MAP)
        # 排序，方便你檢視
        df_all_train = df_all_train.sort_values(by=['label_name', 'source'])
        
        df_all_train.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        
        print("\n\n🎉🎉🎉 匯出成功！🎉🎉🎉")
        print(f"所有 {total_unique_count} 筆獨特的訓練資料已儲存至:")
        print(f"{OUTPUT_CSV}")
        print("\n你可以用 Excel 或 VS Code 打開這個檔案，")
        print("來手動審查所有訓練資料的品質。")
        
    except Exception as e:
        print(f"\n錯誤：儲存 CSV 失敗: {e}")