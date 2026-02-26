from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# nlptown 模型路徑（微調後）
MODEL_PATH = "./bert-finetuned-ptt-sentiment"  # 或 "./bert-finetuned-nlptown"

# 載入模型和分詞器
print("🔄 正在載入模型...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

# nlptown 的 5星標籤
LABELS = {
    1: "1星 ⭐ (非常負面)",
    2: "2星 ⭐⭐ (負面)", 
    3: "3星 ⭐⭐⭐ (中性)",
    4: "4星 ⭐⭐⭐⭐ (正面)",
    5: "5星 ⭐⭐⭐⭐⭐ (非常正面)"
}

model.eval()
print("✅ 模型載入完成！")
print(f"標籤：{LABELS}\n")

# === 測試文字 ===
test_texts = [
    # 中文測試
    "這產品完全是垃圾，浪費我的錢！",
    "還可以，但品質不太穩定。",
    "普通啦，沒什麼特別的。",
    "很不錯，值得推薦給朋友！",
    "超級棒！完全超出預期！",
    
    # 英文測試
    "Terrible product, complete waste of money!",
    "It's okay, nothing special.",
    "Amazing! Best purchase ever!",
    
    # 日文測試
    "最悪です！全く使えません。",
    "最高！大満足です！"
]

print("=== 🧪 模型預測測試 ===")
print("-" * 60)

for i, text in enumerate(test_texts, 1):
    # 分詞
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256, padding=True)
    
    # 預測
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class_id = torch.argmax(logits, dim=-1).item()
        probabilities = torch.softmax(logits, dim=-1)
        confidence = probabilities[0][predicted_class_id].item()
    
    print(f"{i:2d}. '{text}'")
    print(f"   預測：{LABELS[predicted_class_id]} (信心度：{confidence:.1%})")
    print()