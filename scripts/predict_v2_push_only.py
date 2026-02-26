# 檔案名稱: predict_v2_push_only.py
#
# 目的：
# 1. 載入你最強的 V2 特化模型
# 2. 讀取資料庫中「所有推文」
# 3. (關鍵) 排除所有 'http' 開頭的推文
# 4. 執行預測
# 5. 儲存到「最終」的 v2 專用表格

import torch
import pandas as pd
import sqlite3
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from tqdm import tqdm
import os
import sys

# ===================================================================
# 1. 設定區
# ===================================================================
# ✅ 1. 使用你最強的 V2 (特化) 模型
FINETUNED_MODEL_PATH = "./nlptown-finetuned-v2-push-extra" 
DB_PATH = "ptt_data_m.db"

# ✅ 3. 儲存到全新的表格和 CSV
OUTPUT_CSV_PATH = "v2_push_only_predictions.csv" 
TABLE_NAME = "ai_model_predictions_v2_push_only" 

BATCH_SIZE = 32 

# ===================================================================
# 0. 前置檢查
# ===================================================================
print("--- 步驟 0/7: 正在進行前置檢查... ---") 
if not os.path.isdir(FINETUNED_MODEL_PATH):
    print(f"錯誤：模型資料夾不存在於 '{FINETUNED_MODEL_PATH}'")
    print("請確認您已成功執行 'finetune_v2_push_extra.py' 腳本。")
    sys.exit(1) 
print(f"前置檢查通過，將使用 v2 模型: {FINETUNED_MODEL_PATH}")

# ===================================================================
# 2. 載入 v2 模型與建立 Pipeline
# ===================================================================
print("--- 步驟 1/7: 正在載入 v2 (特化) 模型... ---")
DEVICE = 0 if torch.cuda.is_available() else -1
classifier = pipeline(
    "sentiment-analysis",
    model=FINETUNED_MODEL_PATH,
    tokenizer=FINETUNED_MODEL_PATH,
    device=DEVICE
)
print(f"v2 模型已載入，將使用 {'GPU' if DEVICE == 0 else 'CPU'} 進行計算。")

# ===================================================================
# 3. 從資料庫讀取「已過濾的推文」
# ===================================================================
print("--- 步驟 2/7: 正在從資料庫讀取「已過濾的推文」... ---")
conn = sqlite3.connect(DB_PATH) 

# ✅ 2. (關鍵) SQL 查詢
#  - 只讀取 push_comments
#  - 排除 push_content IS NULL 或 ''
#  - (你的要求) 排除 push_content LIKE 'http%'
push_query = """
SELECT 
    id, 
    push_content AS text, 
    push_time AS timestamp 
FROM 
    push_comments 
WHERE 
    push_content IS NOT NULL 
    AND push_content != '' 
    AND push_content NOT LIKE 'http%'
"""

df_pushes = pd.read_sql_query(push_query, conn)
df_pushes['type'] = 'push' # (為未來擴充保留)

df_all = df_pushes

print(f"資料讀取完成，共 {len(df_all)} 筆「乾淨推文」待分析。")
print(f"   (來源: {DB_PATH}, 已排除 http 連結)")

# ===================================================================
# 4. 執行大規模預測 (使用 v2 模型)
# ===================================================================
print("--- 步驟 3/7: 正在執行大規模情緒預測 (這會需要一段時間)... ---")
all_texts = list(df_all['text'].astype(str)) 
predictions_raw = []

# 使用 tqdm 顯示進度條
for out in tqdm(classifier(all_texts, batch_size=BATCH_SIZE, truncation=True), total=len(all_texts)):
    predictions_raw.append(out)
    
# ===================================================================
# 5. 整理結果
# ===================================================================
print("--- 步驟 4/7: 正在整理預測結果... ---")
df_all['predicted_label'] = [p['label'] for p in predictions_raw]
df_all['predicted_score'] = [p['score'] for p in predictions_raw]

# 你的 v2 模型的標籤也是 0/1/2
label_map = {"negative": 0, "neutral": 1, "positive": 2}
df_all['label_id'] = df_all['predicted_label'].map(label_map)

# ===================================================================
# 6. 儲存結果至資料庫 (新表格)
# ===================================================================
print(f"--- 步驟 5/7: 正在將結果寫入資料庫新表格 '{TABLE_NAME}'... ---")
try:
    # 使用 if_exists='replace'
    # 這只會「替換」ai_model_predictions_v2_push_only 這張表
    # 不會動到你 v1 的 ai_model_predictions 或其他任何表
    df_all.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
    print(f"成功將 {len(df_all)} 筆結果寫入資料庫: {DB_PATH}, 表格: {TABLE_NAME}")
except Exception as e:
    print(f"寫入資料庫時發生錯誤: {e}")
finally:
    # 在所有資料庫操作完成後，才關閉連線
    conn.close()
    print("資料庫連線已關閉。")

# ===================================================================
# 7. 儲存結果至 CSV (備份)
# ===================================================================
print("--- 步驟 6/7: 正在將結果儲存至 CSV 檔案 (備份)... ---")
df_all.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')

print("\n🎉🎉🎉 v2 最終預測任務完成！🎉🎉🎉")
print(f"所有「乾淨推文」的 v2 預測結果已成功儲存至: {OUTPUT_CSV_PATH}")
print(f"所有「乾淨推文」的 v2 預測結果已成功儲存至資料庫的 '{TABLE_NAME}' 表格。") 
print(f"\n--- 步驟 7/7: 結果預覽 (前 5 筆) ---")
print(df_all.head())