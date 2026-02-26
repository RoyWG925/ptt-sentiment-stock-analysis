# 檔案名稱: ultimate_data_manager.py
# (✅ V4 - 終極版：可管理 Train, Validation, Test 三個資料集)

import tkinter as tk
from tkinter import messagebox, font, Toplevel, Listbox
import sqlite3
import pandas as pd
import os
import sys
from tkinter import ttk 

# --- 全域設定 ---
DB_PATH = "ptt_data_m.db"

# 模式 1: 訓練集
TABLE_TRAIN = {
    "name": "v2_training_set_master",
    "title": "管理「完整訓練集 (Train)」",
    "json_base": None 
}

# 模式 2: 驗證集 (新)
TABLE_VAL = {
    "name": "v2_validation_set_master",
    "title": "管理「完整驗證集 (Val)」",
    "json_base": None
}

# 模式 3: 黃金測試集
TABLE_TEST = {
    "name": "manual_test_set",
    "title": "管理「黃金測試集 (Test)」",
    "json_base": None,
    "export_path": "./ptt_gold_standard/test.json" 
}
# --- (其餘程式碼 99% 相同) ---

# ... (顏色和標籤定義)...
COLORS = {0: "#FFE4E1", 1: "#FFFACD", 2: "#E0FFD4"}; LABEL_MAP = {0: "Negative", 1: "Neutral", 2: "Positive"}

# --- 資料庫處理邏輯 (完全不變) ---
def db_fix_label(table_name, text, new_label_id):
    if not text: return "error", "錯誤：文本不能為空。"
    try:
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute(f"INSERT OR REPLACE INTO {table_name} (text, label_id) VALUES (?, ?)", (text, new_label_id))
        conn.commit()
        msg = f"成功「新增/更新」: '{text}'" if cursor.rowcount == 1 else f"成功「覆蓋/更新」: '{text}'"
        conn.close(); return "success_fix", msg
    except Exception as e: return "error", f"資料庫錯誤: {e}"

def db_delete_label(table_name, text):
    if not text: return "error", "錯誤：文本不能為空。"
    try:
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE text = ?", (text,))
        conn.commit()
        status, msg = ("success_delete", f"成功「刪除」: '{text}'") if cursor.rowcount > 0 else ("warning", f"警告：在 DB 中找不到 '{text}'")
        conn.close(); return status, msg
    except Exception as e: return "error", f"資料庫錯誤: {e}"

def db_check_if_exists(table_name, text):
    try:
        conn = sqlite3.connect(DB_PATH); query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE text = ? LIMIT 1)"
        cursor = conn.cursor(); cursor.execute(query, (text,)); result = cursor.fetchone()[0]; conn.close()
        return bool(result)
    except Exception: return False

def fetch_combined_stats(db_table_name, json_base_file):
    stats = {0: 0, 1: 0, 2: 0, "total": 0}
    df_json = pd.DataFrame(columns=['text', 'label_id'])
    if json_base_file: 
        if not os.path.exists(json_base_file): print(f"警告: 找不到共識檔案 {json_base_file}")
        else:
            try:
                df_json = pd.read_json(json_base_file, orient='records')
                if 'labels' in df_json.columns: df_json.rename(columns={'labels': 'label_id'}, inplace=True)
                df_json = df_json[['text', 'label_id']]
            except Exception as e: print(f"讀取 {json_base_file} 失敗: {e}")
    df_db = pd.DataFrame(columns=['text', 'label_id'])
    try:
        conn = sqlite3.connect(DB_PATH); df_db = pd.read_sql_query(f"SELECT text, label_id FROM {db_table_name}", conn); conn.close()
    except Exception as e: print(f"讀取 {db_table_name} 失敗: {e}")
    df_all = pd.concat([df_json, df_db]); df_all.drop_duplicates(subset=['text'], keep='last', inplace=True)
    counts = df_all['label_id'].value_counts()
    for label_id, count in counts.items():
        if label_id in stats: stats[label_id] = count
    stats["total"] = len(df_all)
    return stats

def db_fetch_history(table_name, limit=10):
    try:
        conn = sqlite3.connect(DB_PATH); query = f"SELECT text, label_id FROM {table_name} ORDER BY id DESC LIMIT {limit}"; rows = conn.execute(query).fetchall(); conn.close()
        return rows
    except Exception: return []

# --- UI 應用程式 (不變, 除了標題) ---

class LabelApp:
    def __init__(self, root, mode_config):
        self.root = root
        self.db_table_name = mode_config["name"]
        self.json_base_file = mode_config["json_base"]
        self.export_path = mode_config.get("export_path")
        self.is_test_mode = (self.export_path is not None) 
        
        root.title(mode_config["title"]) # 標題會自動變
        root.geometry("800x530") 
        
        self.font_default = font.Font(family="Arial", size=11); self.font_bold = font.Font(family="Arial", size=10, weight="bold"); self.font_status = font.Font(family="Arial", size=10); self.font_stats_title = font.Font(family="Arial", size=12, weight="bold"); self.font_stats = font.Font(family="Monospace", size=12)
        self.count_var_0 = tk.StringVar(value="..."); self.count_var_1 = tk.StringVar(value="..."); self.count_var_2 = tk.StringVar(value="..."); self.total_var = tk.StringVar(value="..."); self.status_var = tk.StringVar(value=f"準備就緒。請管理 [{self.db_table_name}]...")
        
        main_frame = tk.Frame(root, padx=10, pady=10); main_frame.pack(fill=tk.BOTH, expand=True)
        left_frame = tk.Frame(main_frame, width=450); left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        tk.Label(left_frame, text="輸入文本:", font=self.font_default).pack(anchor="w", pady=(0, 5))
        self.text_entry = tk.Entry(left_frame, width=60, font=self.font_default); self.text_entry.pack(fill=tk.X, ipady=5, pady=5)
        tk.Label(left_frame, text="執行動作:", font=self.font_default).pack(anchor="w", pady=(10, 5))
        
        btn_neg = tk.Button(left_frame, text="✅ 新增 / 修正為 Negative (0)", bg=COLORS[0], fg="black", font=self.font_bold, command=lambda: self.on_submit_fix(0)); btn_neg.pack(fill=tk.X, ipady=4, pady=2)
        btn_neu = tk.Button(left_frame, text="✅ 新增 / 修正為 Neutral (1)", bg=COLORS[1], fg="black", font=self.font_bold, command=lambda: self.on_submit_fix(1)); btn_neu.pack(fill=tk.X, ipady=4, pady=2)
        btn_pos = tk.Button(left_frame, text="✅ 新增 / 修正為 Positive (2)", bg=COLORS[2], fg="black", font=self.font_bold, command=lambda: self.on_submit_fix(2)); btn_pos.pack(fill=tk.X, ipady=4, pady=2)
        btn_del = tk.Button(left_frame, text="❌ 刪除此文本", bg="#FF6347", fg="white", font=self.font_bold, command=self.on_submit_delete); btn_del.pack(fill=tk.X, ipady=4, pady=(10, 2))
        
        if self.is_test_mode and self.export_path:
            ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=15)
            self.btn_export = tk.Button(left_frame, text=f"🚀 匯出 (Export) 至 test.json 🚀", bg="#28a745", fg="white", font=self.font_bold, command=self.on_submit_export)
            self.btn_export.pack(fill=tk.X, ipady=8, pady=5)
        
        self.status_label = tk.Label(left_frame, textvariable=self.status_var, font=self.font_status, wraplength=430, pady=10, fg="grey"); self.status_label.pack(side=tk.BOTTOM, anchor="w")
        
        right_frame = tk.Frame(main_frame); right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        stats_frame_title = f" 📊「{mode_config['title']}」統計 "
        stats_frame = tk.LabelFrame(right_frame, text=stats_frame_title, font=self.font_stats_title, padx=10, pady=10); stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(stats_frame, text="Negative (0):", font=self.font_stats).grid(row=0, column=0, sticky="w", padx=5); tk.Label(stats_frame, textvariable=self.count_var_0, font=self.font_stats).grid(row=0, column=1, sticky="w")
        tk.Label(stats_frame, text="Neutral (1): ", font=self.font_stats).grid(row=1, column=0, sticky="w", padx=5); tk.Label(stats_frame, textvariable=self.count_var_1, font=self.font_stats).grid(row=1, column=1, sticky="w")
        tk.Label(stats_frame, text="Positive (2):", font=self.font_stats).grid(row=2, column=0, sticky="w", padx=5); tk.Label(stats_frame, textvariable=self.count_var_2, font=self.font_stats).grid(row=2, column=1, sticky="w")
        tk.Label(stats_frame, text="-"*20, font=self.font_stats).grid(row=3, column=0, columnspan=2, sticky="w", padx=5)
        tk.Label(stats_frame, text="Total:       ", font=self.font_stats).grid(row=4, column=0, sticky="w", padx=5); tk.Label(stats_frame, textvariable=self.total_var, font=self.font_stats).grid(row=4, column=1, sticky="w")
        
        history_frame = tk.LabelFrame(right_frame, text=f" 🕓 最近 10 筆 (來自 {self.db_table_name}) ", font=self.font_stats_title, padx=10, pady=10); history_frame.pack(fill=tk.BOTH, expand=True)
        self.history_listbox = Listbox(history_frame, height=10, font=self.font_default); self.history_listbox.pack(fill=tk.BOTH, expand=True)
        
        self.text_entry.focus_set(); self.refresh_stats_and_history()

    def on_submit_fix(self, new_label_id):
        text = self.text_entry.get().strip();
        if not text: self.status_var.set("錯誤：文本不能為空。"); self.status_label.config(fg="red"); return
        if self.is_test_mode: 
            if db_check_if_exists(TABLE_TRAIN["name"], text):
                self.status_var.set(f"錯誤：該文本已存在於「訓練集」！\n為防止資料洩露，已拒絕新增。"); self.status_label.config(fg="red"); return
        
        status, message = db_fix_label(self.db_table_name, text, new_label_id)
        self.status_var.set(f"({LABEL_MAP[new_label_id]}) {message}")
        if status == "success_fix": self.status_label.config(fg="blue"); self.text_entry.delete(0, tk.END); self.refresh_stats_and_history()
        elif status == "error": self.status_label.config(fg="red");
        if "致命錯誤" in message: messagebox.showerror("啟動錯誤", message); self.root.destroy()
        self.text_entry.focus_set()
        
    def on_submit_delete(self):
        text = self.text_entry.get().strip();
        if not text: self.status_var.set("錯誤：文本不能為空。"); self.status_label.config(fg="red"); return
        if not messagebox.askyesno("確認刪除", f"你確定要從 '{self.db_table_name}' 中\n永久刪除以下文本嗎？\n\n{text}"): return
        status, message = db_delete_label(self.db_table_name, text)
        self.status_var.set(message)
        if status == "success_delete": self.status_label.config(fg="red"); self.text_entry.delete(0, tk.END); self.refresh_stats_and_history()
        elif status == "warning": self.status_label.config(fg="#E69B00")
        elif status == "error": self.status_label.config(fg="red")
        self.text_entry.focus_set()

    def on_submit_export(self):
        print(f"--- 正在匯出「黃金測試集」至 {self.export_path} ---")
        try: conn = sqlite3.connect(DB_PATH); df = pd.read_sql_query(f"SELECT text, label_id FROM {self.db_table_name}", conn); conn.close()
        except Exception as e: messagebox.showerror("匯出失敗", f"讀取資料庫時發生錯誤: {e}"); return
        if len(df) == 0: messagebox.showwarning("匯出警告", "資料庫中沒有資料，匯出的 test.json 將會是空的。")
        try:
            os.makedirs(os.path.dirname(self.export_path), exist_ok=True)
            df.to_json(self.export_path, orient="records", force_ascii=False)
            messagebox.showinfo("匯出成功", f"✅ 匯出成功！\n\n共 {len(df)} 筆資料已儲存至：\n{self.export_path}")
            self.status_var.set(f"匯出成功！共 {len(df)} 筆資料。"); self.status_label.config(fg="green")
        except Exception as e: messagebox.showerror("匯出失敗", f"儲存 JSON 檔案時發生錯誤: {e}")

    def refresh_stats_and_history(self):
        print("--- (正在刷新「完整」統計...) ---")
        stats = fetch_combined_stats(self.db_table_name, self.json_base_file)
        self.count_var_0.set(f"{stats[0]:>5}"); self.count_var_1.set(f"{stats[1]:>5}"); self.count_var_2.set(f"{stats[2]:>5}"); self.total_var.set(f"{stats['total']:>5}")
        print("--- (刷新完畢) ---")
        history = db_fetch_history(self.db_table_name, limit=10); self.history_listbox.delete(0, tk.END)
        for text, label_id in history:
            display_text = f"[{LABEL_MAP.get(label_id, '?')}] {text}"; self.history_listbox.insert(tk.END, display_text)
            if label_id in COLORS: self.history_listbox.itemconfig(tk.END, {'bg': COLORS[label_id]})

# --- 啟動器 (✅ 已修改：加入第三個按鈕) ---

class StartupWindow:
    def __init__(self, root):
        self.root = root; self.root.title("啟動資料管理器"); self.root.geometry("350x250") # 加高
        tk.Label(root, text="你要管理哪一份資料？", font=("Arial", 14)).pack(pady=20)
        
        btn_train = tk.Button(root, text="訓練集 (Train Set)", font=("Arial", 12), height=2, command=lambda: self.launch_app(TABLE_TRAIN))
        btn_train.pack(fill=tk.X, padx=30, pady=5)
        
        # ✅ (新) 驗證集按鈕
        btn_val = tk.Button(root, text="驗證集 (Validation Set)", font=("Arial", 12), height=2, command=lambda: self.launch_app(TABLE_VAL))
        btn_val.pack(fill=tk.X, padx=30, pady=5)
        
        btn_test = tk.Button(root, text="黃金測試集 (Test Set)", font=("Arial", 12), height=2, command=lambda: self.launch_app(TABLE_TEST))
        btn_test.pack(fill=tk.X, padx=30, pady=5)

    def launch_app(self, mode_config):
        self.root.destroy(); main_window = tk.Tk(); app = LabelApp(main_window, mode_config); main_window.mainloop()

# --- 主程式 (✅ 已修改：確保三個表格都存在) ---
if __name__ == "__main__":
    try:
        conn = sqlite3.connect(DB_PATH)
        # (新) 訓練集 (沒有 PRIMARY KEY，因為 text 是 UNIQUE 的)
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE_TRAIN['name']} (text TEXT NOT NULL UNIQUE, label_id INTEGER NOT NULL);""")
        # (新) 驗證集
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE_VAL['name']} (text TEXT NOT NULL UNIQUE, label_id INTEGER NOT NULL);""")
        # (舊) 測試集 (有 ID 和 added_at)
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE_TEST['name']} (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL UNIQUE, label_id INTEGER NOT NULL, added_at DATETIME DEFAULT (datetime('now','localtime')));""")
        conn.close()
    except Exception as e: print(f"檢查資料庫時出錯: {e}"); sys.exit()
    
    startup_root = tk.Tk(); app = StartupWindow(startup_root); startup_root.mainloop()