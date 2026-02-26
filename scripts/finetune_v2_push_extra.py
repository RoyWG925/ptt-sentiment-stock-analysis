# 檔案名稱: finetune_v2_push_extra.py
# (✅ V3 - 系統升級：Train 和 Validation 都從 DB 讀取)

import os
import torch
import numpy as np
import pandas as pd
import sqlite3
from datasets import load_dataset, Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding
)
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# =================================================================
# 1. 基本設定 
# =================================================================
MODEL_NAME = "./nlptown-finetuned-on-ptt" 
OUTPUT_DIR = "./nlptown-finetuned-v2-push-extra" 
LOGGING_DIR = "./logs-v2"
DB_PATH = "ptt_data_m.db"

# ✅ (新) 你的三個「主要」資料來源
MASTER_TRAIN_TABLE = "v2_training_set_master" 
MASTER_VAL_TABLE = "v2_validation_set_master"
GOLD_TEST_DIR = "./ptt_gold_standard"

print(f"--- 準備訓練 v2 (Push-Only) 模型 ---")
print(f"  基礎模型 (v1): {MODEL_NAME}")
print(f"  輸出模型 (v2): {OUTPUT_DIR}")
print(f"  訓練集 (Train): {DB_PATH} -> [{MASTER_TRAIN_TABLE}]")
print(f"  驗證集 (Val): {DB_PATH} -> [{MASTER_VAL_TABLE}]")
print(f"  最終評估集: {GOLD_TEST_DIR}/test.json")
print("-" * 40)

# =================================================================
# 2. 載入資料集 (✅ 關鍵修改處)
# =================================================================
raw_datasets = {} # 建立一個空的 dict

# --- 步驟 2a: 從 DB 載入「主要訓練集」 ---
print(f"--- 1/7: 正在從資料庫 [{MASTER_TRAIN_TABLE}] 載入主要訓練集... ---")
def load_dataset_from_db(table_name):
    """(新) 統一的 DB 載入函式"""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT text, label_id FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if len(df) == 0:
            print(f"錯誤：表格 {table_name} 是空的！")
            return None
        print(f"  > 成功載入 {len(df)} 筆 (來自 {table_name})")
        return Dataset.from_pandas(df)
    except Exception as e:
        print(f"讀取資料庫 {table_name} 時發生錯誤: {e}")
        return None

raw_datasets["train"] = load_dataset_from_db(MASTER_TRAIN_TABLE)
if raw_datasets["train"] is None: exit(1) 

# --- 步驟 2b: 從 DB 載入「主要驗證集」 ---
print(f"--- 正在從資料庫 [{MASTER_VAL_TABLE}] 載入主要驗證集... ---")
raw_datasets["validation"] = load_dataset_from_db(MASTER_VAL_TABLE)
if raw_datasets["validation"] is None: exit(1) 

# --- 步驟 2c: 清理欄位 ---
print("--- 正在清理所有資料集的欄位... ---")
from datasets import DatasetDict
raw_datasets = DatasetDict(raw_datasets) # 轉換為 DatasetDict

raw_datasets = raw_datasets.rename_column("label_id", "labels")
columns_to_keep = ["text", "labels"]
for split in raw_datasets:
    all_cols = raw_datasets[split].column_names
    cols_to_remove = [col for col in all_cols if col not in columns_to_keep]
    if cols_to_remove:
        raw_datasets[split] = raw_datasets[split].remove_columns(cols_to_remove)
print("清理後資料集：")
print(raw_datasets) # 你會看到 train, validation


# =================================================================
# 3. 分詞 (不變)
# =================================================================
print("\n--- 2/7: 正在載入分詞器並進行分詞... ---")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME) 
def tokenize_function(examples):
    result = tokenizer(examples["text"], truncation=True, max_length=256)
    result["labels"] = examples["labels"]
    return result
tokenized_datasets = raw_datasets.map(tokenize_function, batched=True, remove_columns=["text"])
print("分詞完成！")

# =================================================================
# 4. 載入模型 (不變)
# =================================================================
print(f"\n--- 3/7: 正在載入『v1 模型』({MODEL_NAME})... ---")
labels = ["negative", "neutral", "positive"]
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME, num_labels=len(labels), 
    id2label={i: label for i, label in enumerate(labels)},
    label2id={label: i for i, label in enumerate(labels)}
)
print(f"成功從 {MODEL_NAME} 載入 v1 模型。")

# =================================================================
# 5. 評估指標 (不變)
# =================================================================
print("\n--- 4/7: 設定評估指標... ---")
def compute_metrics(eval_pred):
    logits, labels = eval_pred; predictions = np.argmax(logits, axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='weighted', zero_division=0)
    acc = accuracy_score(labels, predictions)
    return {'accuracy': acc, 'f1': f1, 'precision': precision, 'recall': recall}

# =================================================================
# 6. 訓練參數 (不變)
# =================================================================
print("\n--- 5/7: 設定訓練參數... ---")
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR, num_train_epochs=8, learning_rate=2e-5,
    per_device_train_batch_size=32, per_device_eval_batch_size=32,
    warmup_steps=50, weight_decay=0.01, eval_strategy="epoch",
    save_strategy="epoch", load_best_model_at_end=True, save_total_limit=2,
    logging_dir=LOGGING_DIR, logging_steps=10, report_to="none",
)

# =================================================================
# 7. 建立 Trainer (不變)
# =================================================================
print("\n--- 6/7: 建立 Trainer... ---")
data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
trainer = Trainer(
    model=model, args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["validation"],
    tokenizer=tokenizer, data_collator=data_collator,
    compute_metrics=compute_metrics,
)

print("\n--- 7/7: ✨✨✨ 開始訓練 v2 (Push-Only) 模型 ✨✨✨ ---")
trainer.train()
print("\n--- ✅ v2 模型訓練完成 ---")

# =================================================================
# 最終評估 (不變)
# =================================================================
print("\n--- 正在載入「黃金標準測試集」進行最終評估 ---")
GOLD_TEST_FILE = os.path.join(GOLD_TEST_DIR, "test.json")
eval_title = "黃金標準測試集"
if not os.path.exists(GOLD_TEST_FILE):
    print(f"警告：找不到黃金測試集 {GOLD_TEST_FILE}！")
    final_eval_dataset = None
else:
    gold_test_raw = load_dataset("json", data_files={"test": GOLD_TEST_FILE})["test"]
    if "label_id" not in gold_test_raw.column_names:
        print(f"錯誤：黃金測試集 {GOLD_TEST_FILE} 缺少 'label_id' 欄位。")
        final_eval_dataset = None
    else:
        gold_test_raw = gold_test_raw.rename_column("label_id", "labels")
        tokenized_gold_test = gold_test_raw.map(tokenize_function, batched=True, remove_columns=["text"])
        final_eval_dataset = tokenized_gold_test
if final_eval_dataset is not None:
    final_results = trainer.evaluate(eval_dataset=final_eval_dataset)
    print(f"\n======== 最終評估結果 ({eval_title}) ========")
    print(f"   Accuracy:  {final_results['eval_accuracy']:.4f}")
    print(f"   F1-Score:  {final_results['eval_f1']:.4f}")
    print(f"   Precision: {final_results['eval_precision']:.4f}")
    print(f"   Recall:    {final_results['eval_recall']:.4f}")
else:
    print("--- 由於黃金測試集載入失敗，已跳過最終評估 ---")

trainer.save_model(OUTPUT_DIR)
print(f"\n🏆 v2 模型已儲存至：{OUTPUT_DIR}")