# 檔案名稱: advanced_label_tool.py
# (V2 - 新增「資料洩露防護」功能)
#
# 當標註「測試集」時，會自動檢查該文本是否已存在於「訓練集」。

import tkinter as tk
from tkinter import messagebox, font, Toplevel, Listbox
import sqlite3
import sys
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# --- 全域設定 ---
DB_PATH = os.getenv("DB_PATH_M", "database/ptt_data_m.db")

# 模式 1: 訓練集 (V2)
TABLE_TRAIN = {
    "name": "manual_labels_extra",
    "title": "標註「訓練集 (Train)」 (V2 手動資料)"
}

# 模式 2: 黃金測試集
TABLE_TEST = {
    "name": "manual_test_set",
    "title": "標註「黃金測試集 (Test)」"
}

# 顏色
COLORS = {
    0: "#FFE4E1", # 負面 (淡紅)
    1: "#FFFACD", # 中性 (淡黃)
    2: "#E0FFD4"  # 正面 (淡綠)
}
LABEL_MAP = {0: "Negative", 1: "Neutral", 2: "Positive"}

# --- 資料庫處理邏輯 ---

def db_add_label(table_name, text, label_id):
    """將一筆標註寫入指定的表格"""
    if not text:
        return "error", "錯誤：文本不能為空。"
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            INSERT OR IGNORE INTO {table_name} (text, label_id)
            VALUES (?, ?)
        """, (text, label_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            status = "success"
            message = f"成功新增: '{text}'"
        else:
            status = "warning"
            message = f"警告：文本 '{text}' 已存在，未重複新增。"
            
        conn.close()
        return status, message
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return "error", f"致命錯誤：找不到表格 '{table_name}'！\n請先用 SQL Browser 建立它。"
        else:
            return "error", f"資料庫錯誤: {e}"
    except Exception as e:
        return "error", f"發生未知錯誤: {e}"

# ✅✅✅ --- 新增功能：資料庫檢查 --- ✅✅✅
def db_check_if_exists(table_name, text):
    """
    檢查指定文本是否存在於指定表格中。
    返回 True 或 False。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 使用 EXISTS (效能最好)
        query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE text = ? LIMIT 1)"
        cursor.execute(query, (text,))
        
        result = cursor.fetchone()[0] # 獲取 (1,) 或 (0,) 中的 1 或 0
        conn.close()
        
        return bool(result) # 轉換為 True 或 False
        
    except Exception as e:
        print(f"檢查資料庫時出錯 ({table_name}): {e}")
        return False # 發生錯誤時，保守地返回 False

def db_fetch_stats(table_name):
    """從指定表格獲取統計數據"""
    stats = {0: 0, 1: 0, 2: 0, "total": 0}
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = f"SELECT label_id, COUNT(*) FROM {table_name} GROUP BY label_id"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        conn.close()
        
        for label_id, count in rows:
            if label_id in stats:
                stats[label_id] = count
        
        stats["total"] = sum(stats[label_id] for label_id in [0, 1, 2])
        return stats
        
    except sqlite3.OperationalError:
        return stats
    except Exception as e:
        print(f"讀取統計時出錯: {e}")
        return stats

def db_fetch_history(table_name, limit=10):
    """獲取最近 10 筆標註歷史"""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT text, label_id FROM {table_name} ORDER BY id DESC LIMIT {limit}"
        rows = conn.execute(query).fetchall()
        conn.close()
        return rows
    except Exception:
        return []

# --- UI 應用程式 ---

class LabelApp:
    def __init__(self, root, mode_config):
        self.root = root
        self.table_name = mode_config["name"]
        self.title = mode_config["title"]
        
        root.title(self.title)
        root.geometry("800x450") 
        
        # --- (字體定義... 和之前相同) ---
        self.font_default = font.Font(family="Arial", size=11)
        self.font_bold = font.Font(family="Arial", size=10, weight="bold")
        self.font_status = font.Font(family="Arial", size=10)
        self.font_stats_title = font.Font(family="Arial", size=12, weight="bold")
        self.font_stats = font.Font(family="Monospace", size=12) 
        
        # --- (統計變數... 和之前相同) ---
        self.count_var_0 = tk.StringVar(value="...")
        self.count_var_1 = tk.StringVar(value="...")
        self.count_var_2 = tk.StringVar(value="...")
        self.total_var = tk.StringVar(value="...")
        self.status_var = tk.StringVar(value=f"準備就緒。請標註 [{self.table_name}]...")
        
        # --- (佈局... 和之前相同) ---
        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- 左側：標註區 ---
        left_frame = tk.Frame(main_frame, width=450)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        tk.Label(left_frame, text="請輸入要標註的文本:", font=self.font_default).pack(anchor="w", pady=(0, 5))
        
        self.text_entry = tk.Entry(left_frame, width=60, font=self.font_default)
        self.text_entry.pack(fill=tk.X, ipady=5, pady=5)
        
        button_frame = tk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        btn_neg = tk.Button(button_frame, text="Negative (0)", width=15, bg=COLORS[0], fg="black", font=self.font_bold, command=lambda: self.on_submit(0))
        btn_neg.pack(fill=tk.X, ipady=4, pady=2)
        
        btn_neu = tk.Button(button_frame, text="Neutral (1)", width=15, bg=COLORS[1], fg="black", font=self.font_bold, command=lambda: self.on_submit(1))
        btn_neu.pack(fill=tk.X, ipady=4, pady=2)
        
        btn_pos = tk.Button(button_frame, text="Positive (2)", width=15, bg=COLORS[2], fg="black", font=self.font_bold, command=lambda: self.on_submit(2))
        btn_pos.pack(fill=tk.X, ipady=4, pady=2)
        
        self.status_label = tk.Label(left_frame, textvariable=self.status_var, font=self.font_status, wraplength=430, pady=10, fg="grey")
        self.status_label.pack(side=tk.BOTTOM, anchor="w")
        
        # --- 右側：統計與歷史 ---
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        stats_frame = tk.LabelFrame(right_frame, text=" 📊 資料庫即時統計 ", font=self.font_stats_title, padx=10, pady=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(stats_frame, text="Negative (0):", font=self.font_stats).grid(row=0, column=0, sticky="w", padx=5)
        tk.Label(stats_frame, textvariable=self.count_var_0, font=self.font_stats).grid(row=0, column=1, sticky="w")
        tk.Label(stats_frame, text="Neutral (1): ", font=self.font_stats).grid(row=1, column=0, sticky="w", padx=5)
        tk.Label(stats_frame, textvariable=self.count_var_1, font=self.font_stats).grid(row=1, column=1, sticky="w")
        tk.Label(stats_frame, text="Positive (2):", font=self.font_stats).grid(row=2, column=0, sticky="w", padx=5)
        tk.Label(stats_frame, textvariable=self.count_var_2, font=self.font_stats).grid(row=2, column=1, sticky="w")
        tk.Label(stats_frame, text="-"*20, font=self.font_stats).grid(row=3, column=0, columnspan=2, sticky="w", padx=5)
        tk.Label(stats_frame, text="Total:       ", font=self.font_stats).grid(row=4, column=0, sticky="w", padx=5)
        tk.Label(stats_frame, textvariable=self.total_var, font=self.font_stats).grid(row=4, column=1, sticky="w")
        
        history_frame = tk.LabelFrame(right_frame, text=" 🕓 最近 10 筆 ", font=self.font_stats_title, padx=10, pady=10)
        history_frame.pack(fill=tk.BOTH, expand=True)
        
        self.history_listbox = Listbox(history_frame, height=10, font=self.font_default)
        self.history_listbox.pack(fill=tk.BOTH, expand=True)
        
        self.text_entry.focus_set()
        self.refresh_stats_and_history()

    # ✅✅✅ --- on_submit 方法已更新 --- ✅✅✅
    def on_submit(self, label_id):
        """當按鈕被點擊時的處理函式"""
        text = self.text_entry.get().strip()
        
        # 檢查文本是否為空
        if not text:
            self.status_var.set("錯誤：文本不能為空。")
            self.status_label.config(fg="red")
            return

        # --- 💥 新增的防護邏輯 💥 ---
        # 1. 檢查是否為「測試集」模式
        if self.table_name == TABLE_TEST["name"]:
            
            # 2. 檢查該文本是否已存在於「訓練集」
            is_in_train_set = db_check_if_exists(TABLE_TRAIN["name"], text)
            
            if is_in_train_set:
                # 3. 如果存在，拒絕新增
                error_msg = f"錯誤：該文本已存在於「訓練集」({TABLE_TRAIN['name']})！\n為防止資料洩露，已拒絕新增至測試集。"
                self.status_var.set(error_msg)
                self.status_label.config(fg="red")
                self.text_entry.focus_set()
                return # 立刻停止，不執行後續
        # --- 💥 防護邏輯結束 💥 ---
        
        # (如果檢查通過，或現在是訓練集模式，則正常執行)
        
        # 呼叫資料庫函式
        status, message = db_add_label(self.table_name, text, label_id)
        
        # 更新狀態標籤
        self.status_var.set(f"({LABEL_MAP[label_id]}) {message}")
        if status == "success":
            self.status_label.config(fg="green") 
            self.text_entry.delete(0, tk.END)
            self.refresh_stats_and_history() 
        elif status == "warning":
            self.status_label.config(fg="#E69B00") # 橘色
            self.text_entry.delete(0, tk.END)
        elif status == "error":
            self.status_label.config(fg="red")
            if "致命錯誤" in message:
                messagebox.showerror("啟動錯誤", message)
                self.root.destroy()
        
        self.text_entry.focus_set()
        
    def refresh_stats_and_history(self):
        """從資料庫取得更新的統計和歷史，並更新 UI"""
        # 1. 更新統計
        stats = db_fetch_stats(self.table_name)
        self.count_var_0.set(f"{stats[0]:>5}")
        self.count_var_1.set(f"{stats[1]:>5}")
        self.count_var_2.set(f"{stats[2]:>5}")
        self.total_var.set(f"{stats['total']:>5}")
        
        # 2. 更新歷史
        history = db_fetch_history(self.table_name, limit=10)
        self.history_listbox.delete(0, tk.END)
        
        for text, label_id in history:
            display_text = f"[{LABEL_MAP.get(label_id, '?')}] {text}"
            self.history_listbox.insert(tk.END, display_text)
            
            if label_id in COLORS:
                self.history_listbox.itemconfig(tk.END, {'bg': COLORS[label_id]})

# --- 啟動器 ---

class StartupWindow:
    """啟動時的模式選擇視窗"""
    def __init__(self, root):
        self.root = root
        self.root.title("啟動標註工具")
        self.root.geometry("350x200")
        self.choice = None
        
        tk.Label(root, text="你要標註哪一份資料？", font=("Arial", 14)).pack(pady=20)
        
        btn_train = tk.Button(
            root, text="訓練集 (Train Set)", 
            font=("Arial", 12), height=2,
            command=lambda: self.launch_app(TABLE_TRAIN)
        )
        btn_train.pack(fill=tk.X, padx=30, pady=5)
        
        btn_test = tk.Button(
            root, text="黃金測試集 (Test Set)", 
            font=("Arial", 12), height=2,
            command=lambda: self.launch_app(TABLE_TEST)
        )
        btn_test.pack(fill=tk.X, padx=30, pady=5)

    def launch_app(self, mode_config):
        self.root.destroy() 
        
        main_window = tk.Tk()
        app = LabelApp(main_window, mode_config)
        main_window.mainloop()

# --- 主程式 ---
if __name__ == "__main__":
    # 確保表格存在
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_TRAIN['name']} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                label_id INTEGER NOTICAL_NULL,
                added_at DATETIME DEFAULT (datetime('now','localtime'))
            );""")
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_TEST['name']} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                label_id INTEGER NOT NULL,
                added_at DATETIME DEFAULT (datetime('now','localtime'))
            );""")
        conn.close()
    except Exception as e:
        print(f"檢查資料庫時出錯: {e}")
        sys.exit()

    # 啟動模式選擇視窗
    startup_root = tk.Tk()
    app = StartupWindow(startup_root)
    startup_root.mainloop()