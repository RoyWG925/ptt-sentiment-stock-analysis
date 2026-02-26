# 系統架構說明

## 整體架構

```
┌─────────────────────────────────────────────────────────┐
│                    使用者介面層                          │
├──────────────────┬──────────────────┬──────────────────┤
│  Flask Web App   │  Desktop Tool    │  CLI Scripts     │
│  (多人協作標註)   │  (單人標註)       │  (資料分析)       │
└────────┬─────────┴────────┬─────────┴────────┬─────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                   ┌────────▼────────┐
                   │   業務邏輯層     │
                   │  (src/utils)    │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │   資料存取層     │
                   │  (SQLite DB)    │
                   └─────────────────┘
```

## 模組說明

### 1. Web 應用程式 (`src/web_app/`)

- **功能**: 多人協作標註系統
- **技術**: Flask + Jinja2 + SQLite
- **特色**:
  - 固定順序 queue 機制
  - 多使用者並行標註
  - 即時進度儀表板
  - 三分制情緒標註（負面/中性/正面）

### 2. 桌面應用程式 (`src/desktop_app/`)

- **功能**: 單人標註工具
- **技術**: Tkinter + SQLite
- **特色**:
  - 資料洩露防護（測試集不可包含訓練集資料）
  - 即時統計顯示
  - 歷史記錄查看

### 3. 資料處理 Pipeline (`src/pipeline/`)

#### 3.1 `data_pipeline.py`
- 資料清洗與特徵工程
- 情緒資料與股價資料整合
- 高階指標計算（動能、波動率、量能比）

#### 3.2 `thesis_stats.py`
- 描述性統計
- 卡方檢定（結構斷裂）
- Spearman 相關性分析
- Bootstrap 信賴區間

### 4. 工具模組 (`src/utils/`)

- `db_utils.py`: 統一資料庫連線管理

### 5. 實驗性腳本 (`scripts/`)

- 模型分佈分析
- 資料集稽核
- 同步性統計

## 資料流程

```
PTT 爬蟲
    ↓
原始文本 (SQLite)
    ↓
BERT 情緒分類
    ↓
人工標註驗證 (Web/Desktop)
    ↓
資料清洗 & 特徵工程
    ↓
統計分析 & 假設檢定
    ↓
論文表格 & 視覺化圖表
```

## 資料庫設計

### 主要資料表

1. **sentiments** - 文章情緒資料
   - id, timestamp, board, title, content, label_id

2. **push_comments** - 推文資料
   - id, article_id, push_content, push_tag

3. **manual_labels_articles_all** - 文章標註（多人）
   - article_id, annotator, gold_star_title, gold_star_content

4. **manual_labels_pushes_all** - 推文標註（多人）
   - push_id, annotator, article_id, gold_star

5. **labeling_queue** - 標註任務佇列
   - seq, period, task_type, article_id, push_id

## 環境變數設定

所有敏感資訊與路徑設定都透過 `.env` 檔案管理：

```bash
# 資料庫
DB_PATH=database/ptt_data.db
DB_PATH_M=database/ptt_data_m.db

# Flask
FLASK_SECRET_KEY=<隨機生成的金鑰>
FLASK_HOST=0.0.0.0
FLASK_PORT=8000

# PostgreSQL (選用)
PG_PASSWORD=<資料庫密碼>
```

## 安全性設計

1. **環境變數隔離**: 所有密碼與金鑰都在 `.env` 中
2. **資料洩露防護**: 測試集標註時自動檢查訓練集
3. **Git 忽略**: `.gitignore` 防止敏感檔案外洩
4. **WAL 模式**: SQLite 使用 WAL 提升並行效能

## 擴展性考量

- **資料庫抽象層**: 可輕鬆切換到 PostgreSQL
- **模組化設計**: 各功能獨立，方便單元測試
- **配置外部化**: 不需改程式碼即可調整設定
