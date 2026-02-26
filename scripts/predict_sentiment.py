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
FINETUNED_MODEL_PATH = "./nlptown-finetuned-on-ptt" 
DB_PATH = "ptt_data_m.db" # 讀取 ptt_data_m.db
OUTPUT_CSV_PATH = "full_sentiment_predictions.csv" # CSV 備份

# ✅✅✅ 關鍵修改 ✅✅✅
# 我們將 AI 模型的預測結果儲存到一個全新的表格，
# 這樣就 100% 不會覆蓋你的人工標註或共識表格。
TABLE_NAME = "ai_model_predictions" 

BATCH_SIZE = 32 

# ===================================================================
# 0. 前置檢查
# ===================================================================
print("--- 步驟 0/7: 正在進行前置檢查... ---") 
if not os.path.isdir(FINETUNED_MODEL_PATH):
    print(f"錯誤：模型資料夾不存在於 '{FINETUNED_MODEL_PATH}'")
    print("請確認您已成功執行微調腳本，並將模型儲存於正確的路徑。")
    sys.exit(1) 
print("前置檢查通過，模型資料夾存在。")

# ===================================================================
# 2. 載入模型與建立 Pipeline
# ===================================================================
print("--- 步驟 1/7: 正在載入微調後的模型... ---")
DEVICE = 0 if torch.cuda.is_available() else -1
classifier = pipeline(
    "sentiment-analysis",
    model=FINETUNED_MODEL_PATH,
    tokenizer=FINETUNED_MODEL_PATH,
    device=DEVICE
)
print(f"模型已載入，將使用 {'GPU' if DEVICE == 0 else 'CPU'} 進行計算。")

# ===================================================================
# 3. 從資料庫讀取所有需要分析的文本
# ===================================================================
print("--- 步驟 2/7: 正在從資料庫讀取資料... ---")
# 程式會從 ptt_data_m.db 讀取原始文本
conn = sqlite3.connect(DB_PATH) 

# 讀取推文
push_query = "SELECT id, push_content AS text, push_time AS timestamp FROM push_comments WHERE text IS NOT NULL AND text != ''"
df_pushes = pd.read_sql_query(push_query, conn)
df_pushes['type'] = 'push'

# 讀取標題
title_query = "SELECT id, title AS text, timestamp FROM sentiments WHERE text IS NOT NULL AND text != ''"
df_titles = pd.read_sql_query(title_query, conn)
df_titles['type'] = 'title'

# 讀取內文
content_query = "SELECT id, content AS text, timestamp FROM sentiments WHERE text IS NOT NULL AND text != ''"
df_contents = pd.read_sql_query(content_query, conn)
df_contents['type'] = 'content'

# 保持資料庫連線開啟，稍後寫入新表格

df_all = pd.concat([df_pushes, df_titles, df_contents], ignore_index=True)
print(f"資料讀取完成，共 {len(df_all)} 筆文本待分析。")
print(f"   (來源: {DB_PATH})")

# ===================================================================
# 4. 執行大規模預測
# ===================================================================
print("--- 步驟 3/7: 正在執行大規模情緒預測 (這會需要一段時間)... ---")
all_texts = list(df_all['text'].astype(str)) 
predictions_raw = []

for out in tqdm(classifier(all_texts, batch_size=BATCH_SIZE, truncation=True), total=len(all_texts)):
    predictions_raw.append(out)
    
# ===================================================================
# 5. 整理結果
# ===================================================================
print("--- 步驟 4/7: 正在整理預測結果... ---")
df_all['predicted_label'] = [p['label'] for p in predictions_raw]
df_all['predicted_score'] = [p['score'] for p in predictions_raw]

label_map = {"negative": 0, "neutral": 1, "positive": 2}
df_all['label_id'] = df_all['predicted_label'].map(label_map)

# ===================================================================
# 6. 儲存結果至資料庫 (新表格)
# ===================================================================
print(f"--- 步驟 5/7: 正在將結果寫入資料庫新表格 '{TABLE_NAME}'... ---")
try:
    # 使用 if_exists='replace'
    # 這只會「替換」ai_model_predictions 這張表，不會動到你其他的表。
    # 這能確保你每次執行，拿到的都是最新、最完整的 AI 預測結果。
    df_all.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
    print(f"成功將 {len(df_all)} 筆結果寫入資料庫: {DB_PATH}, 表格: {TABLE_NAME}")
    print("   (註: 這 '不會' 覆蓋 consensus_articles 或 manual_labels 等表格)")
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

print("\n🎉🎉🎉 任務完成！🎉🎉🎉")
print(f"所有預測結果已成功儲存至: {OUTPUT_CSV_PATH}")
print(f"所有預測結果已成功儲存至資料庫的 '{TABLE_NAME}' 表格。") 
print(f"\n--- 步驟 7/7: 結果預覽 (前 5 筆) ---")
print(df_all.head())