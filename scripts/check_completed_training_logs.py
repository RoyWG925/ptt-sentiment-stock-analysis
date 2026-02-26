# check_completed_training_logs.py
"""
檢查已完成的訓練，提取每輪 Loss 變化
"""
import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def analyze_training_history(model_dir="./ptt_raw_model"):
    """分析已完成訓練的 Loss 歷史"""
    model_path = Path(model_dir)
    
    # 尋找 trainer_state.json（包含完整訓練歷史）
    state_file = model_path / "trainer_state.json"
    if not state_file.exists():
        print("❌ 未找到 trainer_state.json，檢查 checkpoint 資料夾")
        checkpoints = [d for d in model_path.glob("checkpoint-*") if d.is_dir()]
        if checkpoints:
            state_file = checkpoints[-1] / "trainer_state.json"  # 最後一個 checkpoint
        else:
            print("❌ 沒有找到訓練狀態檔案")
            return
    
    # 載入訓練歷史
    with open(state_file) as f:
        state = json.load(f)
    
    print("=== 已完成訓練摘要 ===")
    print(f"總 epochs: {state.get('num_train_epochs', 'N/A')}")
    print(f"總步數: {state.get('global_step', 'N/A')}")
    print(f"最佳模型步數: {state.get('best_model_checkpoint', 'N/A')}")
    
    # 提取 log_history（每 logging_steps 的記錄）
    log_history = state.get('log_history', [])
    if not log_history:
        print("⚠️ 沒有詳細 log 歷史，可能 logging_steps 設定過大")
        return
    
    print(f"\n📈 找到 {len(log_history)} 筆訓練記錄")
    
    # 整理每輪 Loss
    epoch_losses = {}
    eval_results = {}
    
    for log in log_history:
        step = log.get('step', 0)
        epoch = log.get('epoch', 0)
        
        # 訓練 loss
        if 'loss' in log:
            if epoch not in epoch_losses:
                epoch_losses[epoch] = []
            epoch_losses[epoch].append(log['loss'])
        
        # 驗證結果
        if 'eval_loss' in log:
            eval_results[epoch] = {
                'loss': log['eval_loss'],
                'f1': log.get('eval_f1', 'N/A'),
                'accuracy': log.get('eval_accuracy', 'N/A')
            }
    
    # 顯示每輪平均 Loss
    print("\n=== 每輪訓練 Loss ===")
    for epoch in sorted(epoch_losses.keys()):
        avg_loss = np.mean(epoch_losses[epoch])
        print(f"Epoch {epoch:.1f}: 平均 Loss = {avg_loss:.4f} "
              f"(樣本數: {len(epoch_losses[epoch])})")
    
    print("\n=== 每輪驗證結果 ===")
    for epoch in sorted(eval_results.keys()):
        result = eval_results[epoch]
        print(f"Epoch {epoch}: eval_loss={result['loss']:.4f}, "
              f"F1={result['f1']:.4f if result['f1'] != 'N/A' else 'N/A'}")
    
    # 繪製 Loss 曲線
    epochs = sorted(epoch_losses.keys())
    avg_losses = [np.mean(epoch_losses[e]) for e in epochs]
    
    plt.figure(figsize=(10, 6))
    plt.plot(epochs, avg_losses, 'b-o', label='Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Average Loss')
    plt.title('PTT Consensus Model Training Loss')
    plt.legend()
    plt.grid(True)
    plt.savefig('training_loss_curve.png')
    plt.show()
    
    print("\n✅ Loss 曲線已保存為 training_loss_curve.png")

if __name__ == "__main__":
    analyze_training_history()