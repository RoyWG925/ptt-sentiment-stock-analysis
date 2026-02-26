# 🔧 專案重構執行清單

> **預計總時間**: 4-6 小時  
> **建議執行順序**: 依照編號順序執行，每完成一項就打勾 ✅

---

## 階段一：安全性修復（立即執行）⚠️

### 1. 生成安全的 SECRET_KEY
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
- [ ] 複製生成的金鑰
- [ ] 貼到 `.env` 檔案中的 `FLASK_SECRET_KEY=`

### 2. 設定環境變數檔案
```bash
# .env 檔案已經有範本了，填入真實值
```
- [ ] 編輯 `.env` 檔案
- [ ] 填入 `FLASK_SECRET_KEY`（步驟 1 生成的）
- [ ] 填入 `PG_PASSWORD`（如果有使用 PostgreSQL）
- [ ] 確認 `.env` 已在 `.gitignore` 中

### 3. 安裝環境變數管理套件
```bash
pip install python-dotenv
```
- [ ] 執行安裝指令
- [ ] 確認安裝成功

---

## 階段二：建立目錄結構（30 分鐘）

### 4. 建立所有必要資料夾
```bash
mkdir -p src/web_app
mkdir -p src/desktop_app
mkdir -p src/pipeline
mkdir -p src/utils
mkdir -p scripts
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/outputs
mkdir -p assets/charts
mkdir -p logs
mkdir -p database
mkdir -p docs
mkdir -p tests
```
- [ ] 執行所有 mkdir 指令
- [ ] 確認資料夾已建立

### 5. 建立 Python Package 標記檔案
```bash
touch src/__init__.py
touch src/web_app/__init__.py
touch src/desktop_app/__init__.py
touch src/pipeline/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
```
- [ ] 執行所有 touch 指令（Windows 用 `type nul >` 代替）
- [ ] 確認檔案已建立

---

## 階段三：移動檔案到正確位置（30 分鐘）

### 6. 移動核心應用程式
```bash
mv app.py src/web_app/
mv advanced_label_tool.py src/desktop_app/
```
- [ ] 移動 `app.py`
- [ ] 移動 `advanced_label_tool.py`

### 7. 移動資料處理 Pipeline
```bash
mv 01_data_pipeline.py src/pipeline/data_pipeline.py
mv 02_thesis_stats.py src/pipeline/thesis_stats.py
```
- [ ] 移動並重新命名 `01_data_pipeline.py`
- [ ] 移動並重新命名 `02_thesis_stats.py`

### 8. 移動實驗性腳本
```bash
mv analyze_v1_json_dist.py scripts/
mv analyze_v2_final_distribution.py scripts/
mv arbitrate_and_insert.py scripts/
mv audit_v2_training_set.py scripts/
mv audit_v2_validation_set.py scripts/
mv calc_synchronicity_stats.py scripts/
```
- [ ] 移動所有 `analyze_*.py`
- [ ] 移動 `arbitrate_and_insert.py`
- [ ] 移動所有 `audit_*.py`
- [ ] 移動 `calc_synchronicity_stats.py`

### 9. 移動資料檔案
```bash
mv aligned_timeseries.csv data/raw/
mv taiex_open_close.csv data/raw/
# 如果有 thesis_final_data.csv
mv thesis_final_data.csv data/processed/
```
- [ ] 移動 CSV 檔案到 `data/raw/`
- [ ] 移動處理後的資料到 `data/processed/`

### 10. 移動輸出檔案
```bash
mv advanced_metrics_stats.txt data/outputs/
mv THESIS_FULL_TABLES.txt data/outputs/
```
- [ ] 移動所有 `.txt` 輸出檔案

### 11. 移動圖表檔案
```bash
mv chart_*.png assets/charts/
```
- [ ] 移動所有 `chart_*.png` 檔案

### 12. 移動日誌檔案
```bash
mv auto_crawler.log logs/
```
- [ ] 移動所有 `.log` 檔案

### 13. 移動資料庫檔案（如果存在）
```bash
mv ptt_data.db database/
mv ptt_data_m.db database/
```
- [ ] 移動所有 `.db` 檔案
- [ ] 確認資料庫檔案不會被 commit（已在 `.gitignore`）

---

## 階段四：程式碼重構（1-2 小時）

### 14. 建立共用資料庫工具模組
- [ ] 建立 `src/utils/db_utils.py`
- [ ] 複製以下程式碼：

```python
# src/utils/db_utils.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def get_conn(db_path=None):
    """統一的資料庫連線函式"""
    if db_path is None:
        db_path = os.getenv("DB_PATH", "database/ptt_data.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    return conn
```

### 15. 修改 `src/web_app/app.py` 使用環境變數
- [ ] 在檔案開頭加入：
```python
from dotenv import load_dotenv
import os

load_dotenv()
```
- [ ] 修改設定區塊：
```python
DB_PATH = os.getenv("DB_PATH", "database/ptt_data.db")
HOST = os.getenv("FLASK_HOST", "0.0.0.0")
PORT = int(os.getenv("FLASK_PORT", "8000"))
DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("請在 .env 檔案中設定 FLASK_SECRET_KEY")
```

### 16. 修改 `src/desktop_app/advanced_label_tool.py` 使用環境變數
- [ ] 在檔案開頭加入：
```python
from dotenv import load_dotenv
import os

load_dotenv()
```
- [ ] 修改 DB_PATH：
```python
DB_PATH = os.getenv("DB_PATH_M", "database/ptt_data_m.db")
```

### 17. 修改 `src/pipeline/data_pipeline.py` 使用環境變數
- [ ] 在檔案開頭加入：
```python
from dotenv import load_dotenv
import os

load_dotenv()
```
- [ ] 修改路徑設定：
```python
DB_PATH = os.getenv("DB_PATH_M", "database/ptt_data_m.db")
STOCK_CSV = os.getenv("STOCK_CSV", "data/raw/taiex_open_close.csv")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "data/processed/thesis_final_data.csv")
```

### 18. 修改 `src/pipeline/thesis_stats.py` 使用環境變數
- [ ] 在檔案開頭加入：
```python
from dotenv import load_dotenv
import os

load_dotenv()
```
- [ ] 修改路徑設定：
```python
INPUT_CSV = os.getenv("OUTPUT_CSV", "data/processed/thesis_final_data.csv")
OUTPUT_FILE = os.getenv("STATS_OUTPUT", "data/outputs/THESIS_FULL_TABLES.txt")
```

### 19. 修改爬蟲檔案（如果有 crawler_auto.py 和 crawler_gossi.py）
- [ ] 在檔案開頭加入環境變數載入
- [ ] 修改 PostgreSQL 密碼為：
```python
PG_PASSWORD = os.getenv("PG_PASSWORD")
```

---

## 階段五：測試與驗證（1 小時）

### 20. 測試資料處理 Pipeline
```bash
python src/pipeline/data_pipeline.py
```
- [ ] 執行成功
- [ ] 檢查 `data/processed/thesis_final_data.csv` 是否生成
- [ ] 檢查資料內容是否正確

### 21. 測試統計分析
```bash
python src/pipeline/thesis_stats.py
```
- [ ] 執行成功
- [ ] 檢查 `data/outputs/THESIS_FULL_TABLES.txt` 是否生成
- [ ] 檢查統計結果是否正確

### 22. 測試 Flask Web App
```bash
python src/web_app/app.py
```
- [ ] 啟動成功
- [ ] 開啟瀏覽器訪問 `http://localhost:8000`
- [ ] 測試登入功能
- [ ] 測試標註功能
- [ ] 測試後台儀表板

### 23. 測試桌面標註工具
```bash
python src/desktop_app/advanced_label_tool.py
```
- [ ] 啟動成功
- [ ] 測試訓練集標註
- [ ] 測試測試集標註（含資料洩露防護）
- [ ] 檢查統計數據更新

---

## 階段六：文件與版本控制（1 小時）

### 24. 檢查 Git 狀態
```bash
git status
```
- [ ] 確認 `.env` 不在追蹤清單中
- [ ] 確認 `*.db` 不在追蹤清單中
- [ ] 確認 `venv/` 不在追蹤清單中

### 25. 建立 Git Commit
```bash
git add .
git commit -m "refactor: 重構專案結構，提升可維護性與安全性

- 建立標準化目錄結構 (src/, scripts/, data/, docs/)
- 移除硬編碼密碼，改用環境變數管理
- 更新 .gitignore 防止敏感資料外洩
- 完善 README.md 與專案文件
- 更新 requirements.txt 包含所有依賴套件"
```
- [ ] 執行 git add
- [ ] 執行 git commit
- [ ] 確認 commit 成功

### 26. 建立 GitHub Repository（如果還沒有）
```bash
# 在 GitHub 網站上建立新 Repository
# 然後執行：
git remote add origin https://github.com/你的帳號/ptt-sentiment-analysis.git
git branch -M main
git push -u origin main
```
- [ ] 在 GitHub 建立 Repository
- [ ] 設定 remote
- [ ] Push 到 GitHub
- [ ] 確認檔案已上傳

### 27. 撰寫技術文件（選用）
- [ ] 建立 `docs/architecture.md`（系統架構說明）
- [ ] 建立 `docs/api.md`（API 文件）
- [ ] 建立 `docs/deployment.md`（部署指南）

---

## 階段七：進階優化（選用）

### 28. 建立單元測試
- [ ] 建立 `tests/test_db_utils.py`
- [ ] 建立 `tests/test_pipeline.py`
- [ ] 執行測試：`pytest tests/`

### 29. 設定 CI/CD
- [ ] 建立 `.github/workflows/test.yml`
- [ ] 設定自動測試
- [ ] 設定程式碼品質檢查（flake8, black）

### 30. 建立 Docker 容器（選用）
- [ ] 建立 `Dockerfile`
- [ ] 建立 `docker-compose.yml`
- [ ] 測試容器化部署

---

## ✅ 完成檢查清單

### 最終驗證
- [x] 所有測試通過
- [x] README.md 完整且清晰
- [x] 沒有硬編碼的密碼或 API Keys
- [x] `.gitignore` 正確設定
- [x] 專案可以在新環境中重新部署
- [x] 目錄結構標準化
- [x] 環境變數配置完成
- [x] 啟動腳本已建立
- [x] 技術文件已完成

### 慶祝 🎉
- [x] 專案重構完成！
- [ ] 在 LinkedIn 分享你的專案
- [ ] 更新履歷表
- [ ] Push 到 GitHub

---

**備註**：
- Windows 使用者請將 `mv` 改為 `move`，`touch` 改為 `type nul >`
- 如果遇到問題，請參考 `README.md` 的疑難排解章節
- 建議使用 Git 分支進行重構，避免影響主分支：`git checkout -b refactor/project-structure`
