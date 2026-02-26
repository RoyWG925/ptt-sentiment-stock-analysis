import os
import torch
import numpy as np
from datasets import load_dataset
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
# ✅ 基礎模型：指定為 nlptown
MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment" 
DATA_DIR = "./ptt_raw_consensus" 
# ✅ 輸出資料夾：指定一個乾淨、合法的本地路徑
OUTPUT_DIR = "./nlptown-finetuned-on-ptt" 
LOGGING_DIR = "./logs"

# =================================================================
# 2. 載入資料集
# =================================================================
print("--- 1/7: 正在載入資料集... ---")
data_files = {
    "train": os.path.join(DATA_DIR, "train.json"),
    "validation": os.path.join(DATA_DIR, "validation.json"),
    "test": os.path.join(DATA_DIR, "test.json"),
}
raw_datasets = load_dataset("json", data_files=data_files)

print("原始資料集欄位：")
print(raw_datasets["train"].column_names)

# ✅ 重命名 label_id → labels
raw_datasets = raw_datasets.rename_column("label_id", "labels")

# ✅ 只移除不需要的欄位，保留 text 和 labels
columns_to_remove = [col for col in raw_datasets["train"].column_names 
                    if col not in ["text", "labels"]]
print(f"移除欄位：{columns_to_remove}")
raw_datasets = raw_datasets.remove_columns(columns_to_remove)

print("清理後資料集：")
print(raw_datasets["train"].column_names)
print(raw_datasets)

# =================================================================
# 3. 分詞（保留 labels）
# =================================================================
print("\n--- 2/7: 正在載入分詞器並進行分詞... ---")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def tokenize_function(examples):
    # 只對 text 進行分詞，labels 保持不變
    result = tokenizer(examples["text"], truncation=True, max_length=256)
    # 確保 labels 被保留
    result["labels"] = examples["labels"]
    return result

# ✅ 關鍵修正：只移除 text 欄位，保留 labels
tokenized_datasets = raw_datasets.map(
    tokenize_function, 
    batched=True,
    remove_columns=["text"]  # 只移除 text，保留 labels
)

print("分詞完成！確認 labels 存在：")
print("訓練集欄位：", tokenized_datasets["train"].column_names)
print("驗證集欄位：", tokenized_datasets["validation"].column_names)
print(tokenized_datasets)

# 驗證 labels 資料類型
print(f"訓練集 labels 範例：{tokenized_datasets['train']['labels'][:5]}")
print(f"Labels 資料類型：{type(tokenized_datasets['train']['labels'][0])}")

# =================================================================
# 4. 載入模型
# =================================================================
print("\n--- 3/7: 正在載入預訓練模型... ---")
labels = ["negative", "neutral", "positive"]
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME, 
    num_labels=len(labels),
    id2label={i: label for i, label in enumerate(labels)},
    label2id={label: i for i, label in enumerate(labels)},
    ignore_mismatched_sizes=True
)

# =================================================================
# 5. 評估指標
# =================================================================
print("\n--- 4/7: 設定評估指標... ---")
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average='weighted'
    )
    acc = accuracy_score(labels, predictions)
    
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }

# =================================================================
# 6. 訓練參數
# =================================================================
print("\n--- 5/7: 設定訓練參數... ---")
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    warmup_steps=50,
    weight_decay=0.01,
    
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    save_total_limit=2,
    
    logging_dir=LOGGING_DIR,
    logging_steps=10,
    
    # CPU 優化
    dataloader_num_workers=0,
    dataloader_pin_memory=False,
    
    report_to="none",
)

# =================================================================
# 7. 建立 Trainer
# =================================================================
print("\n--- 6/7: 建立 Trainer... ---")
data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["validation"],
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
)

print("\n--- 7/7: ✨✨✨ 開始微調模型 ✨✨✨ ---")
trainer.train()
print("\n--- ✅ 模型微調完成 ---")

# =================================================================
# 最終評估
# =================================================================
print("\n--- 正在使用『測試集』進行最終評估 ---")
final_results = trainer.evaluate(eval_dataset=tokenized_datasets["test"])

print("\n======== 最終評估結果 (測試集) ========")
print(f"  Accuracy:  {final_results['eval_accuracy']:.4f}")
print(f"  F1-Score:  {final_results['eval_f1']:.4f}")
print(f"  Precision: {final_results['eval_precision']:.4f}")
print(f"  Recall:    {final_results['eval_recall']:.4f}")

# 儲存模型
trainer.save_model(OUTPUT_DIR)
print(f"\n🏆 模型已儲存至：{OUTPUT_DIR}")