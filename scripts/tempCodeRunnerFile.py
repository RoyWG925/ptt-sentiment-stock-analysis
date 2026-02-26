# 檔案名稱: compare_v0_v1_v2.py
# (✅ 已修正：補上 import os)
# (✅ 已升級：包含混淆矩陣繪圖功能)

import pandas as pd
import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import warnings
import os # ✅✅✅ 修正：在這裡補上 import os ✅✅✅

# 匯入繪圖和矩陣所需的函式庫
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

# --- 1. 設定區 ---
warnings.filterwarnings("ignore", "Using a pipeline without")

V0_MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
V1_MODEL_PATH = "./nlptown-finetuned-on-ptt"
V2_MODEL_PATH = "./nlptown-finetuned-v2-push-extra" 
DATA_DIR = "./ptt_gold_standard" 
DEVICE = 0 if torch.cuda.is_available() else -1

print("="*60)
print("     模型效能對決: V0 (原始) vs V1 (泛用) vs V2 (特化)")
print("="*60)
print(f"V0 Model: {V0_MODEL_NAME}")
print(f"V1 Model: {V1_MODEL_PATH}")
print(f"V2 Model: {V2_MODEL_PATH}")
print(f"Test Set: {DATA_DIR}/test.json (黃金標準)")
print(f"Using Device: {'GPU' if DEVICE == 0 else 'CPU'}")


# --- 2. 載入「黃金標準測試集」 ---
print("\n--- 正在載入『黃金標準測試集』---")
# ⬇️⬇️ 這裡需要 os 模組 ⬇️⬇️
test_file_path = os.path.join(DATA_DIR, "test.json")
if not os.path.exists(test_file_path):
    print(f"錯誤：找不到黃金測試集 '{test_file_path}'")
    exit()

test_dataset = load_dataset("json", data_files={"test": test_file_path})["test"]

true_labels = list(test_dataset["label_id"])
texts = list(test_dataset["text"]) 
label_names = ["negative", "neutral", "positive"]
all_possible_labels = [0, 1, 2]
print(f"黃金測試集載入完成，共 {len(texts)} 筆資料。")


# --- 3. 輔助函式 (不變) ---
def map_stars_to_label_id(prediction):
    label_str = prediction['label']
    if label_str in ['1 star', '2 stars']: return 0
    elif label_str == '3 stars': return 1
    else: return 2

def map_ptt_label_to_id(prediction):
    label_str = prediction['label']
    label_map = {"negative": 0, "neutral": 1, "positive": 2}
    if label_str.startswith("LABEL_"):
        return int(label_str.split("_")[1])
    return label_map.get(label_str, -1)


# ===================================================================
# 4. 評估「V0 原始 nlptown 模型」
# ===================================================================
print("\n--- 正在評估『V0 原始 nlptown 模型』... ---")
try:
    v0_classifier = pipeline("sentiment-analysis", model=V0_MODEL_NAME, device=DEVICE)
    v0_preds_raw = v0_classifier(texts, truncation=True, max_length=256, batch_size=16)
    v0_preds = [map_stars_to_label_id(p) for p in v0_preds_raw]
    
    print("--- V0 Model (nlptown) Performance Report ---")
    report_v0 = classification_report(true_labels, v0_preds, target_names=label_names, labels=all_possible_labels, output_dict=True, zero_division=0)
    print(pd.DataFrame(report_v0).transpose().round(4))

    # 繪製 V0 混淆矩陣
    cm_v0 = confusion_matrix(true_labels, v0_preds, labels=all_possible_labels)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm_v0, annot=True, fmt='d', cmap='Reds', xticklabels=label_names, yticklabels=label_names)
    plt.title('Confusion Matrix: V0 (nlptown)')
    plt.xlabel('Predicted Label'); plt.ylabel('True Label')
    plt.savefig("confusion_matrix_v0.png")
    print("V0 混淆矩陣已儲存至 confusion_matrix_v0.png")

except Exception as e:
    print(f"評估 V0 時發生錯誤: {e}")
    report_v0 = {'weighted avg': {'precision': 0, 'recall': 0, 'f1-score': 0}, 'accuracy': 0, 'macro avg': {'f1-score': 0}}
    v0_preds = []


# ===================================================================
# 5. 評估「V1 泛用模型」
# ===================================================================
print("\n--- 正在評估『V1 泛用模型』... ---")
try:
    v1_classifier = pipeline("sentiment-analysis", model=V1_MODEL_PATH, tokenizer=V1_MODEL_PATH, device=DEVICE)
    v1_preds_raw = v1_classifier(texts, truncation=True, max_length=256, batch_size=16)
    v1_preds = [map_ptt_label_to_id(p) for p in v1_preds_raw]
    
    print("--- V1 Model (All Data) Performance Report ---")
    report_v1 = classification_report(true_labels, v1_preds, target_names=label_names, labels=all_possible_labels, output_dict=True, zero_division=0)
    print(pd.DataFrame(report_v1).transpose().round(4))

    # 繪製 V1 混淆矩陣
    cm_v1 = confusion_matrix(true_labels, v1_preds, labels=all_possible_labels)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm_v1, annot=True, fmt='d', cmap='Blues', xticklabels=label_names, yticklabels=label_names)
    plt.title('Confusion Matrix: V1 (PTT-All)')
    plt.xlabel('Predicted Label'); plt.ylabel('True Label')
    plt.savefig("confusion_matrix_v1.png")
    print("V1 混淆矩陣已儲存至 confusion_matrix_v1.png")

except Exception as e:
    print(f"評估 V1 時發生錯誤: {e}")
    report_v1 = {'weighted avg': {'precision': 0, 'recall': 0, 'f1-score': 0}, 'accuracy': 0, 'macro avg': {'f1-score': 0}}
    v1_preds = []


# ===================================================================
# 6. 評估「V2 特化模型」
# ===================================================================
print("\n--- 正在評估『V2 特化模型』(你最新的)... ---")
try:
    v2_classifier = pipeline("sentiment-analysis", model=V2_MODEL_PATH, tokenizer=V2_MODEL_PATH, device=DEVICE)
    v2_preds_raw = v2_classifier(texts, truncation=True, max_length=256, batch_size=16)
    v2_preds = [map_ptt_label_to_id(p) for p in v2_preds_raw]

    print("--- V2 Model (Push + Manual) Performance Report ---")
    report_v2 = classification_report(true_labels, v2_preds, target_names=label_names, labels=all_possible_labels, output_dict=True, zero_division=0)
    print(pd.DataFrame(report_v2).transpose().round(4))

    # 繪製 V2 混淆矩陣
    cm_v2 = confusion_matrix(true_labels, v2_preds, labels=all_possible_labels)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm_v2, annot=True, fmt='d', cmap='Greens', xticklabels=label_names, yticklabels=label_names)
    plt.title('Confusion Matrix: V2 (PTT-Push-Manual)')
    plt.xlabel('Predicted Label'); plt.ylabel('True Label')
    plt.savefig("confusion_matrix_v2.png")
    print("V2 混淆矩Z陣已儲存至 confusion_matrix_v2.png")

except Exception as e:
    print(f"評估 V2 時發生錯誤: {e}")
    report_v2 = {'weighted avg': {'precision': 0, 'recall': 0, 'f1-score': 0}, 'accuracy': 0, 'macro avg': {'f1-score': 0}}
    v2_preds = []


# ===================================================================
# 7. 生成最終的「V0 vs V1 vs V2 對比報告」
# ===================================================================
metrics_v0 = report_v0['weighted avg']
metrics_v1 = report_v1['weighted avg']
metrics_v2 = report_v2['weighted avg']

macro_v0 = report_v0.get('macro avg', {'f1-score': 0})['f1-score']
macro_v1 = report_v1.get('macro avg', {'f1-score': 0})['f1-score']
macro_v2 = report_v2.get('macro avg', {'f1-score': 0})['f1-score']

comparison_df = pd.DataFrame({
    'Metric': ['Accuracy', 'Macro F1-Score', 'Weighted F1-Score'],
    'V0 (nlptown)': [report_v0['accuracy'], macro_v0, metrics_v0['f1-score']],
    'V1 (PTT-All)': [report_v1['accuracy'], macro_v1, metrics_v1['f1-score']],
    'V2 (PTT-Push-Manual)': [report_v2['accuracy'], macro_v2, metrics_v2['f1-score']]
})

print("\n\n" + "="*60)
print("     Performance Comparison (on GOLD STANDARD Test Set)")
print("="*60)
print(comparison_df.round(4).to_string(index=False))

print("\n評估完成。正在顯示圖表...")
# 在腳本結束時，一次顯示所有圖表 (在 .ipynb 中)
plt.show()