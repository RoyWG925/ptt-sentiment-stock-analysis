# 部署指南

## 本地開發環境部署

### 1. 環境需求

- Python 3.8+
- pip (Python 套件管理工具)
- SQLite 3
- (選用) CUDA 11.8+ for GPU 加速

### 2. 安裝步驟

```bash
# 1. Clone 專案
git clone https://github.com/yourusername/ptt-sentiment-analysis.git
cd ptt-sentiment-analysis

# 2. 建立虛擬環境
python -m venv venv

# 3. 啟動虛擬環境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. 安裝依賴套件
pip install -r requirements.txt

# 5. 設定環境變數
cp .env.example .env
# 編輯 .env 檔案，填入你的設定

# 6. 初始化資料庫（如果需要）
python -c "from src.web_app.app import ensure_base_tables; ensure_base_tables()"
```

### 3. 執行應用程式

#### 方式一：使用啟動腳本（推薦）

```bash
# 執行資料處理 Pipeline
python run_pipeline.py

# 啟動 Web 標註系統
python run_web_app.py

# 啟動桌面標註工具
python run_desktop_app.py
```

#### 方式二：直接執行模組

```bash
# 資料處理
python src/pipeline/data_pipeline.py
python src/pipeline/thesis_stats.py

# Web 應用程式
python src/web_app/app.py

# 桌面應用程式
python src/desktop_app/advanced_label_tool.py
```

## 生產環境部署

### 使用 Gunicorn (Linux/Mac)

```bash
# 安裝 Gunicorn
pip install gunicorn

# 啟動應用程式
gunicorn -w 4 -b 0.0.0.0:8000 src.web_app.app:app
```

### 使用 Waitress (Windows)

```bash
# 安裝 Waitress
pip install waitress

# 啟動應用程式
waitress-serve --host=0.0.0.0 --port=8000 src.web_app.app:app
```

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Docker 部署（選用）

### 建立 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "run_web_app.py"]
```

### 建立 docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./database:/app/database
      - ./data:/app/data
    env_file:
      - .env
```

### 執行

```bash
docker-compose up -d
```

## 疑難排解

### 問題 1: ModuleNotFoundError

**解決方式**: 確保已啟動虛擬環境並安裝所有依賴套件

```bash
pip install -r requirements.txt
```

### 問題 2: 資料庫鎖定錯誤

**解決方式**: 確保 SQLite 使用 WAL 模式（程式碼已設定）

### 問題 3: Flask SECRET_KEY 錯誤

**解決方式**: 確認 `.env` 檔案中已設定 `FLASK_SECRET_KEY`

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# 將輸出的金鑰填入 .env
```

### 問題 4: 找不到資料檔案

**解決方式**: 確認檔案路徑正確，或在 `.env` 中調整路徑

```bash
# 檢查檔案是否存在
ls data/raw/taiex_open_close.csv
```

## 效能優化建議

1. **SQLite 優化**
   - 已啟用 WAL 模式
   - 已關閉 synchronous（提升寫入速度）

2. **Flask 優化**
   - 生產環境請設定 `FLASK_DEBUG=False`
   - 使用 Gunicorn/Waitress 而非內建伺服器

3. **資料處理優化**
   - 大量資料處理時使用批次處理
   - 考慮使用 PostgreSQL 替代 SQLite

## 監控與日誌

- 日誌檔案位置: `logs/`
- 建議使用 `tail -f logs/app.log` 監控即時日誌
- 生產環境建議整合 ELK Stack 或 Grafana

## 備份策略

```bash
# 備份資料庫
cp database/ptt_data.db database/backup/ptt_data_$(date +%Y%m%d).db

# 備份資料檔案
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/
```
