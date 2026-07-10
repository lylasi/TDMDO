# TDMDO — 澳廣視（TDM）新聞/影片一站式工具

[![Python](https://img.shields.io/badge/Python-≥3.9-3776AB)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000)](https://flask.palletsprojects.com)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-green)](https://ffmpeg.org)

> **TDMDO** 是以 [澳廣視（TDM）官方 API](https://www.tdm.com.mo) 為核心的新聞查詢與影片下載工具，提供 **網頁端（Web UI）** 與 **指令列（CLI）** 兩種使用方式，並可整合到 **Claude Code 作為 Skill** 使用。不需瀏覽器 JS 渲染，不需登入 Cookie。

---

## 📦 系統架構

```
TDMDO/
├── app/
│   └── tdm_web.py              # Web 端（Flask 網頁服務）
├── .claude/skills/tdm/
│   ├── SKILL.md                 # Claude Code Skill 定義
│   ├── .env.example             # 環境變數範例
│   ├── scripts/
│   │   ├── tdm_core.py          # 核心模組（CLI/Web 共用）
│   │   ├── tdm_tool.py          # CLI 工具（命令列）
│   │   ├── push_manager.py      # 通用推送模組（Telegram）
│   │   ├── tdm_news.db          # SQLite 資料庫（自動建立）
│   │   └── requirements.txt     # Python 依賴
│   ├── references/
│   │   └── tdm-site-reference.md # TDM API 參考文件
│   └── examples/
│       └── example-usage.md     # 使用範例
├── docs/
│   └── TDMDO/
│       ├── reference/
│       │   └── TDM_API_Reference.md  # TDM API 調研檔案
│       ├── plan/                    # 計劃文件
│       ├── meeting/                 # 會議材料
│       ├── research/                # 調研文件
│       ├── spec/                    # 需求規格
│       ├── report/                  # 報告
│       ├── decision/                # 決策記錄
│       └── release/                 # 發佈記錄
├── CLAUDE.md                    # Claude Code 專案指令
├── .env.example                 # 專案根目錄環境變數範例
└── README.md                    # 本文件
```

---

## ✨ 功能總覽

### 新聞瀏覽與搜尋
- 瀏覽 TDM 新聞列表（支援分類篩選：本地、要聞、體育、特稿）
- 關鍵字全文檢索（支援多關鍵字搜尋）
- 僅顯示有影片的新聞（自動過濾純文字新聞）
- 按日期篩選新聞
- 每則新聞標示 `[影片]` / `[純文字]` 類型

### 影片下載與裁剪
- 從新聞頁面 URL 或 6-7 位數字 ID 自動提取 m3u8 串流連結
- 支援 ffmpeg 精確到幀的裁剪（指定開始/結束時間）
- 支援 yt-dlp 快速下載（無裁剪時自動選用）
- 支援任何 m3u8 / 公開影片 URL
- 即時顯示下載進度

### 推送功能
- **WebDAV 自動推送**：下載/裁剪完成後自動上傳到 Alist / OpenAlist
- **Telegram 推送**：手動或自動推送影片/圖片/文件/文字到 Telegram
- **智能發送**：依副檔名自動選擇 `sendVideo` / `sendPhoto` / `sendDocument`
- **自動降級**：超過限制大小時自動切換發送方式（如 >50MB 影片改用 sendDocument）
- **可擴展架構**：繼承 `BaseChannel` 即可新增推送通道

### 資料庫管理
- SQLite 本地資料庫，記錄下載歷史與推送狀態
- 增量同步最新新聞
- 按新聞 ID 歸類所有下載版本（原片 + 裁剪版）
- 標記已刪除檔案（顯示為「遺失」）

---

## 🚀 Web 端安裝與使用

### 前置需求

| 依賴 | 版本要求 | 用途 |
|---|---|---|
| Python | ≥ 3.9 | 執行程式 |
| ffmpeg | 任何版本（需在系統 PATH） | 下載與裁剪影片 |
| yt-dlp | 建議安裝 | 快速下載 m3u8 |

### 安裝步驟

```bash
# 1. 確認 ffmpeg 可用
ffmpeg -version

# 2. 安裝 Python 依賴
pip install -r .claude/skills/tdm/scripts/requirements.txt

# 3. （可選）複製環境變數設定檔
cp .claude/skills/tdm/.env.example .claude/skills/tdm/.env
```

### 啟動 Web 服務

```bash
# 僅本機訪問（開發用）
python app/tdm_web.py --host 127.0.0.1 --port 8080

# 允許內網其他機器訪問
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

啟動後終端會顯示：

```
  TDMDO  http://0.0.0.0:8080
  下載目錄: D:\CODE\TDMDO\.claude\skills\tdm\downloads
```

在瀏覽器打開 `http://127.0.0.1:8080` 即可使用。

### Web UI 功能詳解

網頁端分為三個主標籤頁：

#### 📰 新聞標籤

| 功能 | 說明 |
|---|---|
| **關鍵字搜尋** | 輸入關鍵字搜尋新聞，支援全文檢索 |
| **分類篩選** | 切換全部/本地/要聞/體育/特稿分類 |
| **日期篩選** | 指定日期瀏覽當日新聞 |
| **僅影片模式** | 勾選後只顯示含影片的新聞 |
| **搜尋類型** | 可切換搜尋「全部新聞」或「節目」 |
| **一鍵下載** | 點擊「下載」按鈕直接跳轉到下載頁 |

#### ⬇️ 下載標籤

| 功能 | 說明 |
|---|---|
| **輸入 ID/URL** | 貼上 TDM 新聞 URL 或 6-7 位數字 ID |
| **自動查詢** | 自動取得影片資訊（標題、時長、縮圖、文字內容） |
| **HLS 預覽** | 使用 hls.js 直接在瀏覽器預覽影片 |
| **時間裁剪** | 輸入開始/結束時間（HH:MM:SS），從預覽畫面擷取當前時間 |
| **下載/重新下載** | 下載完整影片或裁剪片段 |
| **已下載版本列表** | 顯示該新聞所有已下載版本（原片 + 裁剪） |
| **播放已下載影片** | 點擊 ▶ 按鈕播放已下載的影片 |
| **推送 WebDAV** | 推送單一檔案到 WebDAV |
| **推送 Telegram** | 推送單一檔案到 Telegram |
| **刪除** | 刪除已下載的影片 |

#### 📁 已下載標籤

| 功能 | 說明 |
|---|---|
| **群組檢視** | 按新聞 ID 歸類顯示所有已下載影片 |
| **播放/裁剪/推送** | 每個影片皆可播放、裁剪、推送或刪除 |
| **狀態標示** | 顯示推送狀態（☁️=已推送、📤=待推送、⚠️=檔案遺失） |

### 密碼保護

Web 端支援簡單的密碼保護層。在 `.env` 中設定：

```env
WEB_AUTH_ENABLED=true
WEB_AUTH_PASSWORDS=your_password_here  # 多個密碼用逗號分隔
```

啟用後訪問頁面需輸入密碼，密碼存儲在瀏覽器 Cookie（30 天有效）。

### 檔案服務

所有已下載的影片可透過 `http://127.0.0.1:8080/api/download-file/<檔名>` 直接訪問或下載，方便分享給內網其他用戶。

---

## 🛠️ CLI 工具安裝與使用

### 安裝

同 Web 端前置需求，安裝 Python 依賴即可。

### 命令參考

```bash
python .claude/skills/tdm/scripts/tdm_tool.py <命令> [參數]
```

#### `news` — 查詢新聞列表

```bash
# 顯示 10 篇最新新聞
python .claude/skills/tdm/scripts/tdm_tool.py news --limit 10

# 僅顯示有影片的新聞
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 5

# 按分類查詢（27=本地、41=要聞、42=體育、143=特稿）
python .claude/skills/tdm/scripts/tdm_tool.py news --category 27 --limit 10

# 指定日期
python .claude/skills/tdm/scripts/tdm_tool.py news --date 2026-07-09 --limit 20

# 過濾關鍵字
python .claude/skills/tdm/scripts/tdm_tool.py news --search "颱風" --limit 5
```

#### `search` — 關鍵字全文搜索

```bash
# 基本搜尋
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門 政府"

# 僅搜尋影片新聞
python .claude/skills/tdm/scripts/tdm_tool.py search "世界盃" --video-only

# 搜尋節目
python .claude/skills/tdm/scripts/tdm_tool.py search "澳視新聞" --type search_program

# 指定顯示數量
python .claude/skills/tdm/scripts/tdm_tool.py search "暴雨" --limit 30
```

搜尋類型 (`--type`)：
| 值 | 說明 |
|---|---|
| `search_news`（預設） | 全部新聞 |
| `search_program` | 節目 |
| `search_short_video` | 微視頻 |

#### `download` — 下載影片

```bash
# 從新聞 ID 下載
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791

# 從 URL 下載（自動提取 ID）
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791"

# 下載節目影片
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/video/program-detail/850015"

# 下載後自動推送到 Telegram
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --push

# 下載時裁剪（參數：開始時間,持續時間）
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut "00:00:20,00:00:30"

# 強制覆蓋已存在的檔案
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --overwrite

# 指定輸出路徑
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --output D:/Videos/news.mp4
```

#### `trim` — 裁剪已下載的影片

```bash
# 裁剪指定時間範圍
python .claude/skills/tdm/scripts/tdm_tool.py trim --input video.mp4 --start 00:00:20 --end 00:00:50

# 指定持續時間
python .claude/skills/tdm/scripts/tdm_tool.py trim --input video.mp4 --start 00:05:30 --duration 00:01:00

# 指定輸出路徑
python .claude/skills/tdm/scripts/tdm_tool.py trim --input video.mp4 --start 00:00:10 --end 00:00:20 --output clip.mp4
```

#### `push` — 獨立推送命令

```bash
# 推送文字
python .claude/skills/tdm/scripts/tdm_tool.py push --text "下載完成：世界盃16強"

# 推送影片（自動判斷類型）
python .claude/skills/tdm/scripts/tdm_tool.py push --video video.mp4 --caption "新聞影片"

# 推送圖片
python .claude/skills/tdm/scripts/tdm_tool.py push --image photo.jpg --caption "截圖"

# 推送文件
python .claude/skills/tdm/scripts/tdm_tool.py push --file report.pdf --caption "今日報表"
```

#### `db` — 資料庫管理

```bash
# 初始化資料庫
python .claude/skills/tdm/scripts/tdm_tool.py db init

# 查看資料庫統計
python .claude/skills/tdm/scripts/tdm_tool.py db stats

# 增量同步最新新聞到本地資料庫
python .claude/skills/tdm/scripts/tdm_tool.py db sync

# 強制同步（更新已有新聞）
python .claude/skills/tdm/scripts/tdm_tool.py db sync --force

# 不限 7 天，同步更早的新聞
python .claude/skills/tdm/scripts/tdm_tool.py db sync --all-days --pages 5
```

#### `push-log` — 查看推送記錄

```bash
python .claude/skills/tdm/scripts/tdm_tool.py push-log --limit 20
```

---

## 🌐 遠端模式（多機共用一台 Server）

設定 `TDM_SERVER` 後，CLI 所有操作自動走 HTTP 調用遠端 Flask 伺服器。客戶端**只需 `pip install requests`**，不需要 SQLite / ffmpeg / flask。

### 架構

```
┌─────────────────────┐
│ Server 機（常駐）     │
│ flask + ffmpeg       │
│ + SQLite + 影片儲存   │  ← 所有重裝備都在這裡
└────────┬────────────┘
         │ HTTP API (:8080)
    ┌────┴────┬────────┐
    │         │        │
┌───┴──┐ ┌───┴──┐ ┌───┴──┐
│ A 機  │ │ B 機  │ │ C 機  │  ← 只有 requests
└──────┘ └──────┘ └──────┘
```

### 使用方法

**步驟 1** — Server 機啟動 Web 服務：

```bash
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

**步驟 2** — 客戶端設定遠端伺服器（二選一）：

```bash
# 方式一：環境變數（永久生效，寫在 .env）
TDM_SERVER=http://192.168.1.100:8080

# 方式二：命令列參數（一次性）
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 news --limit 10
```

**步驟 3** — 照常使用所有 CLI 命令：

```bash
# 查詢新聞（走遠端）
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 10

# 搜尋新聞
python .claude/skills/tdm/scripts/tdm_tool.py search "颱風" --video-only

# 下載影片（由 Server 機執行 ffmpeg，完成後提供下載連結）
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791

# 裁剪影片（Server 機上已有檔案）
python .claude/skills/tdm/scripts/tdm_tool.py trim --input 1217791_新聞.mp4 --start 00:00:20 --end 00:00:50

# 查看遠端資料庫統計
python .claude/skills/tdm/scripts/tdm_tool.py db stats

# 觸發遠端同步
python .claude/skills/tdm/scripts/tdm_tool.py db sync --all-days --pages 5

# 推送文字到 Telegram（透過 Server 機）
python .claude/skills/tdm/scripts/tdm_tool.py push --text "下載完成"
```

### 遠端模式支援的命令

| 命令 | 遠端行為 | 備註 |
|---|---|---|
| `news` | HTTP GET `/api/news` | 完整支援參數 |
| `search` | HTTP GET `/api/news?search=` | 完整支援參數 |
| `download` | HTTP POST `/api/download` + 輪詢進度 | 影片儲存在 Server 機 |
| `trim` | HTTP POST `/api/trim` | 針對 Server 機既有檔案 |
| `push` | HTTP POST `/api/push-text` 或 `/api/push-to-tg` | 透過 Server 機推送 |
| `db stats` | HTTP GET `/api/db-stats` | |
| `db sync` | HTTP POST `/api/db-sync` | 觸發 Server 機同步 |
| `push-log` | HTTP GET `/api/push-log` | |
| `db init` | ⚠️ 不支援（由 Server 端管理） | 顯示提示訊息 |

> **注意**：遠端模式下 `download` / `trim` 的影片儲存在 Server 機的 `TDM_DOWNLOAD_DIR`，完成後終端會顯示下載連結。

### 遠端模式的 .env 配置

在客戶端的 `.env` 中只需設定：

```env
# 遠端伺服器 URL
TDM_SERVER=http://192.168.1.100:8080

# Server 啟用 WEB_AUTH_ENABLED 時，CLI 自動登入使用
TDM_SERVER_PASSWORD=your_server_password

# 遠端下載進度輪詢總逾時秒數
TDM_REMOTE_POLL_TIMEOUT=600
```

Server 機的 `.env` 保持原有完整配置即可（Telegram / WebDAV / Web 密碼保護等）。若啟用密碼保護，建議只在 HTTPS 或可信任內網傳送 CLI 登入密碼。

---

## 🤖 Claude Code Skill 安裝與使用

TDMDO 可作為 **Claude Code 的 Skill** 整合，讓你在對話中直接操作 TDM 新聞與影片。

### 安裝方式

Skill 已預置於專案中，路徑為 `.claude/skills/tdm/`。當你在 TDMDO 專案目錄中使用 Claude Code 時，Skill 已自動可用。

若要在其他專案中使用，請將 `.claude/skills/tdm/` 目錄複製到該專案的 `.claude/skills/` 下。

### 觸發關鍵字

在對話中提及以下關鍵字時，Skill 會自動觸發：

| 關鍵字 | 觸發功能 |
|---|---|
| TDM、澳廣視、澳門新聞、tdm.com.mo | 載入 TDMDO Skill |
| 新聞查詢、關鍵字搜索、新聞搜索 | 啟動新聞查詢流程 |
| 影片下載、下載影片、m3u8 | 啟動影片下載流程 |
| 裁剪影片、剪片、trim | 啟動裁剪流程 |

### 可用對話範例

```
使用者: 查詢最新的 TDM 新聞
→ Claude 自動執行 tdm_tool.py news 顯示最新新聞

使用者: 搜索關於「颱風」的新聞
→ Claude 自動執行 tdm_tool.py search 颱風

使用者: 下載這個影片 https://www.tdm.com.mo/zh-hant/news-detail/1217791
→ Claude 自動提取 ID，執行 download 命令

使用者: 裁剪 video.mp4 從 00:00:20 到 00:00:50
→ Claude 自動執行 trim_video 函數
```

### 推送管理器獨立使用

`push_manager.py` 可獨立匯入使用，不依賴 TDM 模組：

```python
from push_manager import push_text, push_video, push_image, push_media

# 一行推送
push_text("Hello Telegram!")
push_video("video.mp4", "新聞影片")
push_image("photo.jpg", "截圖")
push_media("report.pdf", "文件")  # 自動判斷類型
```

### 核心模組獨立使用

```python
from tdm_core import (
    query_news_list,    # 查詢新聞列表
    query_search,       # 關鍵字搜尋
    get_video_info,     # 取得影片資訊
    download_video,     # 下載影片
    trim_video,         # 裁剪影片
    push_to_webdav,     # WebDAV 推送
    init_db,            # 初始化資料庫
    get_grouped_videos, # 取得已下載影片（歸類）
)
```

---

## ⚙️ 環境變數配置

### 完整變數表

| 變數 | 預設值 | 適用範圍 | 說明 |
|---|---|---|---|
| **基本路徑** | | | |
| `TDM_DOWNLOAD_DIR` | `<skill>/downloads` | CLI+Web | 影片下載目錄 |
| `TDM_DB_PATH` | `<skill>/scripts/tdm_news.db` | CLI+Web | SQLite 資料庫路徑 |
| `TDM_SERVER` | (無) | CLI | 遠端伺服器 URL，設定後 CLI 走 HTTP 遠端模式（見[遠端模式](#-遠端模式多機共用一台-server)） |
| `TDM_SERVER_PASSWORD` | (無) | CLI | Server 啟用 Web 密碼保護時，CLI 自動登入使用的密碼 |
| `TDM_REMOTE_POLL_TIMEOUT` | `600` | CLI | 遠端下載進度輪詢總逾時秒數 |
| **WebDAV 推送** | | | |
| `WEBDAV_ENABLED` | `false` | CLI+Web | 啟用 WebDAV 自動推送 |
| `WEBDAV_URL` | (無) | CLI+Web | WebDAV 伺服器 URL（含埠號） |
| `WEBDAV_USERNAME` | (無) | CLI+Web | WebDAV 上傳帳號 |
| `WEBDAV_PASSWORD` | (無) | CLI+Web | WebDAV 上傳密碼 |
| `WEBDAV_PATH` | `/` | CLI+Web | WebDAV 上傳目標目錄 |
| **Telegram 推送** | | | |
| `PUSH_ENABLED` | `true` | CLI+Web | 啟用推送功能 |
| `PUSH_DEFAULT_TARGET` | `tg` | CLI+Web | 預設推送通道 |
| `TG_TOKEN` | (無) | CLI+Web | Telegram Bot Token（@BotFather 取得） |
| `TG_CHATID` | (無) | CLI+Web | Telegram Chat ID（個人/群組/頻道） |
| **Web 密碼保護** | | | |
| `WEB_AUTH_ENABLED` | `false` | Web 端 | 啟用頁面密碼保護 |
| `WEB_AUTH_PASSWORDS` | (無) | Web 端 | 允許的密碼（多個用逗號分隔） |

### 配置載入順序

1. 系統環境變數（最高優先級）
2. `.env` 檔案（`<skill>/.env` 或專案根目錄 `.env`）
3. 程式內建預設值（最低優先級）

### 設定檔位置

- **Skill 層級**：`.claude/skills/tdm/.env`（CLI 工具啟動時自動載入）
- **專案根目錄**：`.env`（Web 端啟動時自動載入）

### WebDAV 配置範例

```env
WEBDAV_ENABLED=true
WEBDAV_URL=http://192.168.1.100:5244
WEBDAV_USERNAME=tdmdo
WEBDAV_PASSWORD=your_password_here
WEBDAV_PATH=/TDM新聞/
```

> Alist 後台 → 用戶 → 新增或編輯專用帳號，勾選「WebDAV 讀寫」權限。

### Telegram 配置範例

```env
PUSH_ENABLED=true
PUSH_DEFAULT_TARGET=tg
TG_TOKEN=1234567890:ABCdefGHIJklmNOPqrStuVWXyz
TG_CHATID=-1001234567890
```

取得方式：
- **TG_TOKEN**：在 Telegram 中搜尋 [@BotFather](https://t.me/BotFather)，建立 Bot 後取得 Token
- **TG_CHATID**：將 Bot 加入頻道/群組，發送一條訊息後訪問 `https://api.telegram.org/bot<TG_TOKEN>/getUpdates` 取得 Chat ID

---

## 🔄 典型工作流

### 1. 查詢今日有影片的新聞並下載

```bash
# 找出有影片的新聞
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 10

# 下載指定 ID
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
```

### 2. 從新聞連結一鍵下載並剪輯精華

```bash
# 下載並裁剪（下載時只下載需要的片段）
python .claude/skills/tdm/scripts/tdm_tool.py download \
  --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791" \
  --cut "00:00:20,00:00:30"

# 或先下載完整影片，再裁剪
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input "1217791_世界盃16強.mp4" \
  --start 00:00:20 --end 00:00:50
```

### 3. Web 端圖形化操作

```bash
# 啟動 Web 服務
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

1. 在瀏覽器打開 `http://<你的IP>:8080`
2. 切換到 **📰 新聞** 標籤瀏覽新聞
3. 找到有影片的新聞，點擊「下載」自動跳轉
4. 在 **⬇️ 下載** 標籤確認資訊後點「下載/裁剪」
5. 下載完成後切換到 **📁 已下載** 查看所有影片

### 4. 搜尋特定主題並推送到 Telegram

```bash
# 搜尋新聞
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門 交通" --video-only

# 下載影片並推送
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1218239 --push

# 或推送已下載的檔案
python .claude/skills/tdm/scripts/tdm_tool.py push \
  --video "1218239_南灣地段.mp4" \
  --caption "澳門南灣地段新聞"
```

### 5. 全自動 WebDAV 歸檔

配置 `.env` 後，每次執行 `download` 或 `trim` 都會自動將檔案上傳到 WebDAV 伺服器（如 Alist），不再需要手動搬運檔案。

---

## 📚 新聞分類對照

| 前端顯示 | API Category 參數 | 分類 ID |
|---|---|---|
| 全部 | (不指定) | — |
| 本地 | `local` | 27 |
| 要聞 | `world` | 41 |
| 體育 | `sport` | 42 |
| 特稿 | `feature` | 143 |

## 🌐 TDM API 架構（簡要）

所有 API 為公開 RESTful，**無需認證**。

| API | URL | 說明 |
|---|---|---|
| 新聞列表 | `api/v1.0/news?Page=1&PageSize=40&Lang=zh` | 分頁新聞 |
| 新聞詳情+影片 | `api/v1.0/news/{id}` | `data.detail.video` = m3u8 URL |
| 全文搜尋 | `api/v1.0/search/?Keywords=關鍵字` | 全文檢索 |
| 搜尋建議 | `api/v1.0/searchbar?query=關鍵字&Lang=zh` | 搜尋自動完成 |

詳細 API 文件請見：[TDM API 參考文件](docs/TDMDO/reference/TDM_API_Reference.md)

---

## 📋 依賴清單

| 套件 | 用途 |
|---|---|
| `requests` | HTTP API 呼叫 |
| `flask` | Web 服務 |
| `yt-dlp` | m3u8 影片下載加速 |
| `ffmpeg`（系統工具） | 影片下載與裁剪 |
| `python-telegram-bot`（可選） | Telegram 推送 |
| `beautifulsoup4`（可選） | HTML 解析 |

安裝所有依賴：
```bash
pip install -r .claude/skills/tdm/scripts/requirements.txt
# （可選）Telegram 推送
pip install python-telegram-bot
```

---

## 🧪 疑難排解

### 下載失敗

```
請確認 ffmpeg 或 yt-dlp 已安裝且在系統 PATH 中
```

### 影片無回應

TDM API 無需登入，若無回應請確認網路可訪問 `https://www.tdm.com.mo`。

### Telegram 推送失敗

```
確認已安裝 python-telegram-bot
確認 .env 中 TG_TOKEN 和 TG_CHATID 正確
Bot 需要是目標群組/頻道的管理員
```

### WebDAV 推送失敗

```
確認 Alist 後台用戶已勾選「WebDAV 讀寫」權限
確認 WEBDAV_URL 可正常訪問
```

### 裁剪不精確

裁剪預設走重新編碼以確保精確到幀。若需極速無損裁剪（僅關鍵幀級別），可手動使用 `-c copy` 參數。

---

## 📁 已下載目錄結構

所有影片儲存在 `TDM_DOWNLOAD_DIR`（預設 `downloads/`）：
```
downloads/
├── 1217791_世界盃16強_葡萄牙_0-1_西班牙.mp4    # 原片
├── 1217791_世界盃16強_葡萄牙_0-1_西班牙_cut_00-00-20.000_00-00-50.000.mp4  # 裁剪版
├── 1217866_氣象局料今明兩日仍有大驟雨及雷暴.mp4
└── ...
```

---

## 📄 授權

專案為私有工具，僅供學習與個人使用。使用時請遵守 TDM 網站服務條款。

---

> 更多細節請參閱：
> - [CLI 使用範例](.claude/skills/tdm/examples/example-usage.md)
> - [TDM API 參考](.claude/skills/tdm/references/tdm-site-reference.md)
> - [TDM API 調研檔案](docs/TDMDO/reference/TDM_API_Reference.md)
