---
name: tdm
description: TDM (澳廣視 tdm.com.mo) news query, video download/trim via API+m3u8+ffmpeg, keyword search. Trigger when mentioning TDM, 澳廣視, 澳門新聞, tdm.com.mo, 新聞查詢, 關鍵字搜索, 新聞下載, 影片下載, 裁剪影片, 剪片, m3u8, tdm_tool. (Web UI 已剝離為獨立 app/tdm_web.py)
argument-hint: "[command] [options]"
---

# TDMDO — 澳廣視新聞/影片一站式工具

以 TDM 官方 API 為核心（不需瀏覽器 JS 渲染），整合新聞查詢、關鍵字搜索、影片下載、裁剪、網頁端。

## 遠端模式（多機共用一台 Server）

設定 `TDM_SERVER` 環境變數後，CLI 所有操作自動走遠端 HTTP 調用，不需本機 SQLite / ffmpeg：

```bash
# 方式一：環境變數（永久生效）
set TDM_SERVER=http://192.168.1.100:8080

# 方式二：命令列參數（一次性；--server 可置於子命令前或後）
python tdm_tool.py --server http://192.168.1.100:8080 news --limit 10
python tdm_tool.py news --server http://192.168.1.100:8080 --limit 10
```

| 命令 | 遠端行為 |
|---|---|
| `news` | HTTP GET `/api/news` |
| `search` | HTTP GET `/api/news?search=` |
| `download` | HTTP POST `/api/download` + 輪詢進度 |
| `trim` | HTTP POST `/api/trim`（伺服器端檔案） |
| `push` | HTTP POST `/api/push-text` 或 `/api/push-to-tg` |
| `db stats` | HTTP GET `/api/db-stats` |
| `db sync` | HTTP POST `/api/db-sync` |
| `push-log` | HTTP GET `/api/push-log` |

**客戶端只需要**：`pip install requests`（不需 ffmpeg / SQLite / flask）。

> Server 端需執行 `python app/tdm_web.py --host 0.0.0.0 --port 8080`。
> 若 Server 設定 `WEB_AUTH_ENABLED=true`，客戶端需設定相同的 `TDM_SERVER_PASSWORD`；建議僅在 HTTPS 或可信任內網使用。

## 環境檢查

```bash
python --version           # ≥ 3.9
ffmpeg -version            # 必須在 PATH 中
pip install requests flask # 基礎依賴
```

## 環境變數配置（可選）

複製 `.env.example` 為 `.env` 即可自訂路徑：

```bash
cp .env.example .env
```

| 變數 | 預設值 | 說明 |
|---|---|---|
| `TDM_DOWNLOAD_DIR` | `<skill>/downloads` | 影片下載目錄 |
| `TDM_DB_PATH` | `<skill>/scripts/tdm_news.db` | SQLite 資料庫路徑 |
| `TDM_SERVER` | (無) | 遠端伺服器 URL，設定後 CLI 走 HTTP 遠端模式 |
| `TDM_SERVER_PASSWORD` | (無) | Server 啟用 Web 密碼保護時，CLI 自動登入使用的密碼 |
| `TDM_REMOTE_POLL_TIMEOUT` | `600` | 遠端下載進度輪詢總逾時秒數 |
| `WEBDAV_ENABLED` | `false` | 是否啟用 WebDAV 自動推送 |
| `WEBDAV_URL` | (無) | WebDAV 伺服器 URL |
| `WEBDAV_USERNAME` | (無) | WebDAV 上傳帳號 |
| `WEBDAV_PASSWORD` | (無) | WebDAV 上傳密碼 |
| `WEBDAV_PATH` | `/` | WebDAV 上傳目標目錄 |

> 載入順序：系統環境變數 > `.env` > 預設值。CLI 工具會自動載入 skill 目錄下的 `.env`。

## 核心命令

### 1. 查詢新聞列表

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news [OPTIONS]

選項:
  --category {all,local,world,sport,feature,27,41,42,143}  分類名稱或 ID (預設: all)
  --limit N                                    篇數 (預設: 10)
  --page N                                     頁碼 (預設: 1)
  --search KEYWORD                             搜尋關鍵字
  --video-only                                 僅顯示有影片的新聞
```

**URL 規則**：新聞列表頁 `?Page=1&PageSize=40`，直接 GET 即可，無需 JS。

### 2. 下載影片（從新聞 ID 或 URL）

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true"
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/video/program-detail/850015"
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 00:00:20,00:00:30
```

`--cut` 格式固定為 `START,DURATION`，第二值是持續時間而非結束時間。

**原理**：自動從 URL 提取 6-7 位 ID → 調用 `api/v1.0/news/{id}` 取得 m3u8 → ffmpeg 下載。不需要瀏覽器。

### 3. 裁剪影片

```bash
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input video.mp4 --start 00:00:20 --end 00:00:50 --output clip.mp4
```

### 4. 關鍵字搜索新聞

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門 政府"
```

支援多關鍵字（空格分隔），自動在多頁中搜尋。

### 5. 網頁端（獨立部署）

```bash
# 僅本機訪問
python app/tdm_web.py --host 127.0.0.1 --port 8080

# 允許內網其他機器訪問
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

訪問 http://127.0.0.1:8080 或 `http://<本機IP>:8080`，貼上任何 TDM URL 即可下載影片。

> **注意**：`app/tdm_web.py` 是獨立的 Flask 網頁服務，不屬於 skill 本體。如需在 QClaw 中使用網頁端，需將 `app/tdm_web.py` 一併複製到目標工作區。
> 使用 `0.0.0.0` 時請確保 **Windows 防火牆** 放行 8080 埠，否則內網其他機器無法連入。

### 6. 通用推送（Telegram / 可擴展多通道）

```bash
# 推純文字
python .claude/skills/tdm/scripts/push_manager.py --text "下載完成：世界盃16強"
python .claude/skills/tdm/scripts/tdm_tool.py push --text "新聞更新了"

# 推影片
python .claude/skills/tdm/scripts/push_manager.py --video video.mp4 --caption "新聞影片"

# 推圖片
python .claude/skills/tdm/scripts/push_manager.py --image photo.jpg --caption "截圖"

# 推文件
python .claude/skills/tdm/scripts/push_manager.py --file report.pdf --caption "今日報表"

# 下載後自動推送（--push）
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --push
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --push --push-target "tg"
```

**推送配置** (`.env`)：

| 變數 | 預設值 | 說明 |
|---|---|---|
| `PUSH_ENABLED` | `true` | 是否啟用推送 |
| `PUSH_DEFAULT_TARGET` | `tg` | 預設推送通道（逗號分隔） |
| `TG_TOKEN` | (無) | Telegram Bot Token（@BotFather） |
| `TG_CHATID` | (無) | Telegram Chat ID（個人/群組/頻道） |

**支援內容類型**：文字、影片 (`.mp4/.mkv/.webm` ≤50MB)、圖片 (`.jpg/.png/.gif/.webp` ≤10MB)、文件 (任意格式 ≤50MB)

**智慧發送**：根據副檔名自動選擇 `sendVideo` / `sendPhoto` / `sendDocument`，超限自動降級。

**獨立使用**（不依賴 TDM 模組）：
```python
from push_manager import push_text, push_video, push_image, push_media

# 一行推送
push_text("Hello Telegram!")
push_video("video.mp4", "新聞影片")
push_media("photo.jpg", "截圖")  # 自動判斷類型
```

**新增通道**：在 `push_manager.py` 中繼承 `BaseChannel`，加入 `CHANNEL_REGISTRY` 即可。

## TDM API 架構

| API | URL | 說明 |
|---|---|---|
| 新聞列表 | `api/v1.0/news?Page=1&PageSize=40&Lang=zh` | 分頁新聞 |
| 新聞詳情+影片 | `api/v1.0/news/{id}` | `data.detail.video` = m3u8 URL |
| 全文搜尋 | `api/v1.0/news?Page=1&PageSize=40&query=關鍵字&Lang=zh` | API 全文檢索 |
| 搜尋建議 | `api/v1.0/searchbar?query=關鍵字&Lang=zh` | 搜尋自動完成 |

**無需登入，無需 Cookie，無需 JS 渲染。**

## 新聞分類對照

| 前端顯示 | API Category 參數 | 說明 |
|---|---|---|
| 全部 | (空/default) | 所有新聞 |
| 本地 | local | 澳門本地新聞 |
| 要聞 | world? | 國際要聞 |
| 體育 | sport | 體育新聞 |
| 特稿 | feature | 專題報導 |

## 常見工作流

### A: 查詢今日有影片的新聞並下載

```bash
# 找出有影片的新聞
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 5
# 下載指定 ID
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
```

### B: 從新聞連結一鍵下載裁剪

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true"
python .claude/skills/tdm/scripts/tdm_tool.py trim --input "1217791_世界盃16強.mp4" --start 00:00:20 --end 00:00:50
```

### C: 搜索特定主題新聞

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search "暴雨 警告"
```

### D: 啟動網頁端分享給非技術用戶

```bash
python app/tdm_web.py --port 8080
```

## 相依性

- Python ≥ 3.9, requests, flask
- ffmpeg（系統 PATH 中）

## 其他資源

- TDM 網站/API 詳解：`references/tdm-site-reference.md`
- 使用範例：`examples/example-usage.md`
- 參考專案：`TDM/`（完整的新聞監控+影片處理系統，含 SQLite、通知、青龍面板整合）
- `.env` 設定範例：`.env.example`（含 WebDAV 自動推送配置）

## WebDAV 自動推送

下載完成後透過 **WebDAV 協議**（HTTP Basic Auth）自動上傳到 Alist / OpenAlist，無 JWT、穩定可靠。

在 `.env` 中配置：

```env
WEBDAV_ENABLED=true
WEBDAV_URL=http://192.168.1.100:5244
WEBDAV_USERNAME=tdmdo
WEBDAV_PASSWORD=your_password_here
WEBDAV_PATH=/TDM新聞/
```

### 前置步驟

1. Alist 後台 → **用戶** → 新增或編輯專用帳號
2. 勾選 **「WebDAV 讀寫」** 權限
3. 確保目標目錄存在

配置完成後每次 `download` 自動推送。推送失敗不影響下載結果。

### 查看推送記錄

```bash
python .claude/skills/tdm/scripts/tdm_tool.py push-log --limit 20
```

記錄自動寫入 SQLite（`webdav_push_log` 表），包含檔案名、大小、推送狀態。
