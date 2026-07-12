# TDMDO — 澳廣視（TDM）新聞／影片工具

[![Python](https://img.shields.io/badge/Python-≥3.9-3776AB)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000)](https://flask.palletsprojects.com)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-green)](https://ffmpeg.org)

> **使用說明同步：2026-07-12**
>
> TDMDO 以澳廣視（TDM）公開內容 API 為核心，提供 Web UI、CLI 與 Claude Code Skill，可查詢新聞、全文搜尋、下載及裁剪新聞影片，並支援 Telegram／WebDAV 推送與遠端模式。

## 實作邊界

- **現行 CLI 的 TDM API 解析只支援新聞**：由 6–7 位新聞 ID，或含該 ID 的 TDM 新聞 URL，查詢 `/api/v1.0/news/{id}`，並只消費 `data.detail.video`。
- **Web UI 的主要下載流程同樣以新聞 ID／新聞 URL 為準**。Web 後端對其他 URL 沒有專用 TDM API 解析；沒有抽出新聞 ID 時才會交由伺服器上的 `yt-dlp`／`ffmpeg` 嘗試處理。非 TDM URL 若路徑恰含 6–7 位數字段，仍可能被誤判為新聞 ID；因此不代表支援任何 URL，也不保證能下載。
- TDM 網站已確認節目、新聞音訊與圖片、直播、節目表、微視頻及專題 API，但現行 CLI **沒有**對應的 `program`、`audio`、`images`、`live`、`schedule` 或 `special` 命令。
- 本文只概述 API。唯一詳細且持續更新的正式文件是 [`docs/TDMDO/reference/TDM_API_Reference.md`](docs/TDMDO/reference/TDM_API_Reference.md)。

---

## 系統架構（主要現行檔案）

下列為目前主線所需檔案的節錄；根目錄另有已廢棄的 `TDM/` 歷史版本及其他報告／協作文件，不作現行實作依據。

```text
TDMDO/
├── app/
│   └── tdm_web.py                   # 獨立 Flask Web UI／遠端 Server
├── .claude/skills/tdm/
│   ├── SKILL.md                     # Claude Code Skill 定義與現行能力
│   ├── .env.example                 # Skill／Server 環境變數範例
│   ├── scripts/
│   │   ├── tdm_core.py              # CLI／Web 共用核心
│   │   ├── tdm_tool.py              # CLI 入口
│   │   ├── tdm_remote.py            # 遠端 CLI 客戶端
│   │   ├── push_manager.py          # Telegram 等推送通道
│   │   └── requirements.txt         # Python 依賴
│   ├── references/
│   │   └── tdm-site-reference.md    # TDM 網站 API 快速導讀
│   └── examples/
│       └── example-usage.md         # 現行可執行範例
├── docs/TDMDO/reference/
│   └── TDM_API_Reference.md         # 唯一詳細 TDM API 正式 Reference
├── CLAUDE.md
└── README.md
```

> 專案根目錄目前沒有 `.env.example`；可複製 `.claude/skills/tdm/.env.example` 為 `.claude/skills/tdm/.env`。

---

## 功能總覽

### 已接入

- 新聞列表：頁碼、筆數、日期、分類及僅影片篩選。
- 全文搜尋：新聞、微視頻、節目三種 parser choice；目前只查 TDM 搜尋 API 第一頁。
- 新聞影片：由新聞 ID／新聞 URL 解析 `video` HLS，下載完整影片或直接裁剪。
- 現有影片裁剪：支援純秒、`MM:SS.sss`、`HH:MM:SS.sss`。
- Web UI：新聞瀏覽／搜尋、新聞影片查詢與下載、裁剪、下載檔案管理及推送。
- 推送：WebDAV 自動歸檔，以及 Telegram 文字、影片、圖片、文件推送。
- 遠端模式：由輕量 CLI 客戶端操作常駐 TDMDO Web Server。
- SQLite：新聞、下載版本與推送狀態。

### 網站已確認、尚未接入

以下是網站/API 能力，不是現行 CLI 命令：

- 節目 slug 的 `details`、`feature`、`review`，以及電台節目音訊。
- 新聞詳情的 `audio`、`images[]`、`iconIndicator` 與 mixed media。
- `live/categories` 直播、`program-list` 節目表。
- `short-video` 分類／列表與 `search_pressrelease`。
- `special` 專題主檔、關聯節目、節目重溫及專題新聞。

完整端點、參數、官網請求、回應結構與限制請查閱[正式 Reference](docs/TDMDO/reference/TDM_API_Reference.md)，不要自行虛構對應命令。

---

## 安裝與環境

### 依賴

| 依賴 | 用途 |
|---|---|
| Python ≥ 3.9 | 執行 CLI／Web |
| `requests>=2.32.0` | TDM API 與遠端客戶端 |
| `beautifulsoup4>=4.12.0` | 目前保留在 requirements；現行主線程式未直接使用，待依賴整理 |
| `yt-dlp>=2024.0` | 可選下載器；通用 URL fallback |
| `flask>=3.0.0` | 獨立 Web Server |
| ffmpeg（系統工具） | 影片下載 fallback 與裁剪 |
| `python-telegram-bot` | Telegram 推送，需另外安裝 |

```bash
python --version
pip install -r .claude/skills/tdm/scripts/requirements.txt
pip install python-telegram-bot
ffmpeg -version
```

遠端客戶端只需 Python 與 `requests`，不需本機 Flask、SQLite 或 ffmpeg。

### `.env`

```bash
cp .claude/skills/tdm/.env.example .claude/skills/tdm/.env
```

| 變數 | 預設值 | 適用範圍 | 說明 |
|---|---|---|---|
| `TDM_DOWNLOAD_DIR` | `<skill>/downloads` | CLI／Web core | 下載目錄 |
| `TDM_DB_PATH` | `<skill>/scripts/tdm_news.db` | CLI／Web core | SQLite 路徑 |
| `TDM_SERVER` | 無 | CLI | 遠端 Server URL |
| `TDM_SERVER_PASSWORD` | 無 | 遠端 CLI | 必須匹配 Server `WEB_AUTH_PASSWORDS` 其中之一 |
| `TDM_REMOTE_POLL_TIMEOUT` | `600` | 遠端 CLI | 下載進度輪詢總逾時秒數，必須大於 0 |
| `WEBDAV_ENABLED` | `false` | CLI／Web core | 啟用 WebDAV 自動推送 |
| `WEBDAV_URL` | 無 | CLI／Web core | WebDAV Server URL |
| `WEBDAV_USERNAME` | 無 | CLI／Web core | WebDAV 帳號 |
| `WEBDAV_PASSWORD` | 無 | CLI／Web core | WebDAV 密碼 |
| `WEBDAV_PATH` | `/` | CLI／Web core | WebDAV 目標目錄 |
| `PUSH_ENABLED` | `true` | CLI／Web | 啟用通用推送 |
| `PUSH_DEFAULT_TARGET` | `tg` | CLI／Web | 預設通道，可用逗號分隔 |
| `TG_TOKEN` | 無 | CLI／Web | Telegram Bot Token |
| `TG_CHATID` | 無 | CLI／Web | Telegram Chat ID |
| `WEB_AUTH_ENABLED` | `false` | Web Server | 啟用 TDMDO 頁面與 API 密碼保護 |
| `WEB_AUTH_PASSWORDS` | 無 | Web Server | 一個或多個逗號分隔密碼 |

系統環境變數優先於 `.env`。CLI 與核心模組會可靠載入 `.claude/skills/tdm/.env`。

`app/tdm_web.py` 也會讀取**啟動時工作目錄**的 `.env`（不一定是專案根目錄），但它目前是**先 import `tdm_core`，再讀該 `.env`**；因此其中的 `TDM_DOWNLOAD_DIR`、`TDM_DB_PATH`、WebDAV 及通用推送配置在該次程序中不會改變已初始化的 core／push-manager 常數。請將這些配置放在 `.claude/skills/tdm/.env`。工作目錄 `.env` 只適合之後才讀取的 Web 認證等配置。

---

## Web UI

### 啟動

```bash
# 僅本機
python app/tdm_web.py --host 127.0.0.1 --port 8080

# 允許內網訪問
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

瀏覽器開啟 `http://127.0.0.1:8080`。使用 `0.0.0.0` 時，請處理防火牆並啟用認證或只在可信任內網使用。

### 實際 UI 行為

Web UI 有「新聞」、「下載」、「已下載」三個標籤：

- **新聞列表**：可選分類、日期及僅影片，呼叫 `GET /api/news` 的新聞列表流程。
- **關鍵字搜尋**：有關鍵字時，`GET /api/news?search=...&stype=...` 會改走 `query_search`，不是對目前列表做本地過濾。搜尋類型 UI 提供 `search_news`、`search_program`；搜尋底層只取 TDM 全文搜尋第一頁。頁碼 UI 不代表會取得 TDM 搜尋後續頁。
- **節目搜尋限制**：`search_program` 結果結構、網址顯示與下載銜接仍以新聞模型呈現，尚非完整節目支援。
- **下載查詢**：輸入 6–7 位新聞 ID 或含該 ID 的 TDM 新聞 URL，查詢新聞詳情的 `video`。
- **其他 URL**：UI 查詢階段通常無法建立新聞資訊。直接呼叫 Web 下載 API 時，沒有可解析新聞 ID 的 URL 才會交由 Server 的 `yt-dlp`／ffmpeg fallback 嘗試；若非 TDM URL 路徑恰含 6–7 位數字段，現行 `extract_id()` 仍可能先把它誤判為新聞 ID，因此其他 URL 不屬於保證支援範圍。
- **時間格式**：開始、結束或 duration 後端均接受純秒、`MM:SS.sss`、`HH:MM:SS.sss`，包括小數秒。播放器「擷取時間」按鈕目前填入整秒，但可手動輸入毫秒。
- **檔案管理**：可播放、下載、裁剪、刪除、推送 WebDAV／Telegram，並按新聞 ID 顯示原片與裁剪版本。

### Web 密碼保護

```env
WEB_AUTH_ENABLED=true
WEB_AUTH_PASSWORDS=password_one,password_two
```

啟用後，頁面與業務 API 由 Flask 後端驗證 Cookie。Cookie 最長 30 天。這是 **TDMDO Web/API 認證層**，與 TDM 公開內容 API 是否登入無關。

### 檔案服務

```text
http://127.0.0.1:8080/api/download-file/<檔名>
http://127.0.0.1:8080/api/download-file/<檔名>?dl=1
```

---

## CLI

```bash
python .claude/skills/tdm/scripts/tdm_tool.py <命令> [參數]
```

### `news` — 新聞列表

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --page 2 --limit 20
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --date 2026-07-12 --limit 20

# 分類可用別名或數字
python .claude/skills/tdm/scripts/tdm_tool.py news --category local --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --category 42 --limit 10
```

| CLI 別名 | API `Category` | 類別 |
|---|---:|---|
| `all` | 空值 | 全部 |
| `local` | `27` | 本地 |
| `world` | `41` | 要聞 |
| `sport` | `42` | 體育 |
| `feature` | `143` | 特稿 |

API 原生分類是數字；別名由 CLI 轉換。

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --search "暴雨" --limit 20
```

- **本地模式**：先取得指定 `/news` 列表頁，再在當頁結果過濾關鍵字，不是全站搜尋。
- **遠端模式**：Server 的 `/api/news?search=` 會改走 `query_search` 全文搜尋，而且只查第一頁。
- 需要明確全文搜尋時，使用 `search`。

### `search` — 全文搜尋

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 政府 --limit 15
python .claude/skills/tdm/scripts/tdm_tool.py search 暴雨 警告 --type search_news --video-only --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 --type search_short_video --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 --type search_program --limit 10
```

現行 parser 只有：

- `search_news`（預設）
- `search_short_video`
- `search_program`

`query_search` 固定請求 TDM 搜尋 API 的 `Page=1`，不會自動跨頁。CLI 沒有 `search_pressrelease` choice。`search_program` 與 `search_short_video` 的 item 契約不同於新聞；現行輸出仍會以新聞 URL 模式顯示，後續下載解析不完整，不要假定能直接交給 `download`。

### `download` — 下載新聞影片

只接受 6–7 位新聞 ID，或現行 `extract_id()` 可辨識、以路徑形式包含該 ID 的標準 TDM 新聞 URL。不要假定 query 參數中的任意數字都能解析：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true"

# 輸出、覆蓋、下載後推送
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --output "downloads/news.mp4"
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --output "downloads/news.mp4" --overwrite
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --push --push-target tg
```

現行流程：提取新聞 ID → `GET /api/v1.0/news/{id}` → 讀取 `data.detail.video` → 以 yt-dlp 或 ffmpeg 下載。不要使用節目 slug、節目主檔 ID、集數 ID 或片段 ID 代替新聞 ID。

`--cut` 固定是 `START,DURATION`，第二值是**持續時間**，不是結束時間：

```bash
# 從 20 秒開始，持續 30 秒
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 00:00:20,00:00:30

# 從 10.500 秒開始，持續 2.250 秒
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 10.500,2.250
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 00:10.500,00:02.250 --output "downloads/clip.mp4"
```

### `trim` — 裁剪現有影片

`--start` 必填；`--end` 與 `--duration` 必須二選一。

| 格式 | 範例 |
|---|---|
| 純秒 | `10.500` |
| `MM:SS.sss` | `00:10.500` |
| `HH:MM:SS.sss` | `00:00:10.500` |

```bash
# 10.500 至 13.125 秒，長度 2.625 秒
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input "downloads/news.mp4" --start 10.500 --end 13.125 \
  --output "downloads/clip_ms.mp4"

# 同一範圍，以 duration 表示
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input "downloads/news.mp4" --start 00:00:10.500 --duration 00:00:02.625 \
  --output "downloads/clip_ms.mp4"
```

小數秒會轉成浮點秒數交給 ffmpeg。實際精度受來源時間戳、影格率、關鍵幀、音訊取樣及 ffmpeg 對輸入編碼的處理影響，不保證逐幀或逐毫秒完全一致。

### `push` — Telegram／通用通道推送

Telegram 需要 `python-telegram-bot`、`TG_TOKEN` 與 `TG_CHATID`。四類內容互斥，必須擇一；`--target` 指定目標通道。

```bash
python .claude/skills/tdm/scripts/tdm_tool.py push --text "新聞更新了" --target tg
python .claude/skills/tdm/scripts/tdm_tool.py push --video "downloads/news.mp4" --caption "新聞影片" --target tg
python .claude/skills/tdm/scripts/tdm_tool.py push --image "downloads/photo.jpg" --caption "新聞截圖" --target tg
python .claude/skills/tdm/scripts/tdm_tool.py push --file "downloads/report.pdf" --caption "新聞資料" --target tg
```

支援文字、影片、圖片、文件。圖片推送是發送既有本機圖片，不代表 CLI 能下載新聞 `images[]`。Telegram 通道會依檔案類型使用 `sendVideo`、`sendPhoto` 或 `sendDocument`，並受 Bot API 與實作中的大小限制約束。

### `db` 與 `push-log`

```bash
python .claude/skills/tdm/scripts/tdm_tool.py db init
python .claude/skills/tdm/scripts/tdm_tool.py db stats
python .claude/skills/tdm/scripts/tdm_tool.py db sync --pages 3
python .claude/skills/tdm/scripts/tdm_tool.py db sync --pages 3 --force
python .claude/skills/tdm/scripts/tdm_tool.py push-log --limit 20
```

parser 雖然存在 `db sync --all-days`，但它對應的上游 `IsShowSevenDay` 語義不可靠：`false` 或省略在抽樣中可能反而取得更少資料，且不代表全歷史。因此本文不推薦以 `--all-days` 作「全歷史同步」範例。

`push-log` 的真實資料來源是 SQLite `news` 表的 `push_url`、`push_time`；查詢中的 `downloaded` 只是 `push_time` 的欄位別名，不是下載時間。現行資料不來自 `webdav_push_log` 表；初始化會清理舊版遺留的同名表。

---

## 遠端模式

遠端 CLI 將命令轉成 TDMDO Web Server HTTP 請求。Server 執行 API、SQLite、下載、裁剪與推送；客戶端只需 `requests`。

### 啟動與連線

```bash
# Server
python app/tdm_web.py --host 0.0.0.0 --port 8080

# Client：--server 可放在子命令前或後
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 news --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --server http://192.168.1.100:8080 --limit 10
```

也可配置：

```env
TDM_SERVER=http://192.168.1.100:8080
TDM_SERVER_PASSWORD=your_client_password
TDM_REMOTE_POLL_TIMEOUT=600
```

### 真實路由

| CLI | 遠端路由 |
|---|---|
| `news` | `GET /api/news` |
| `search` | `GET /api/news?search=...&stype=...` |
| `download` | `POST /api/download`，輪詢 `GET /api/progress/{id}` |
| `trim` | `POST /api/trim` |
| `push --text` | `POST /api/push-text` |
| `push` 媒體 | `POST /api/push-to-tg` |
| `db stats` | `GET /api/db-stats` |
| `db sync` | `POST /api/db-sync` |
| `push-log` | `GET /api/push-log` |

沒有 `/api/search` 路由；遠端 `search` 仍走 `/api/news?search=`，Server 再呼叫 `query_search`，同樣只查 TDM 搜尋第一頁。遠端 `db init` 由 Server 管理，客戶端只顯示提示。

### 認證

Server 設定：

```env
WEB_AUTH_ENABLED=true
WEB_AUTH_PASSWORDS=password_one,password_two
```

Client 的 `TDM_SERVER_PASSWORD` 必須匹配 `WEB_AUTH_PASSWORDS` 其中之一。客戶端收到 401 後會呼叫 `POST /auth` 取得 Cookie，再重試請求。建議僅透過 HTTPS 或可信任內網傳送密碼。

TDM 公開內容 API 與 TDMDO Server 是不同認證層：前者一般免登入；`member/*` 等會員 API 是例外；後者可由上述配置保護。

### 遠端檔案限制

- `download` 的輸出位於 Server；自訂 `output` 只允許 `TDM_DOWNLOAD_DIR` 的直屬檔名，不能寫入子目錄或目錄外路徑。
- `trim --input` 是 Server `TDM_DOWNLOAD_DIR` 中的檔名；不會上傳 Client 檔案。`trim --output` 同樣只能是該目錄的直屬檔名。
- `push --video/--image/--file` 只取 Client 參數的 basename，並在 Server `TDM_DOWNLOAD_DIR` 找同名檔；不會上傳 Client 檔案。
- 下載每 2 秒輪詢一次，預設總逾時 600 秒。逾時或 Client 中止只停止輪詢，**不會取消 Server 任務**。

```bash
# Server 的下載目錄須已存在 1217791_news.mp4
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 \
  trim --input "1217791_news.mp4" --start 10.500 --duration 2.625 --output "clip.mp4"

python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 \
  push --video "1217791_news.mp4" --caption "新聞影片" --target tg
```

---

## WebDAV 自動推送

在 `.claude/skills/tdm/.env` 設定：

```env
WEBDAV_ENABLED=true
WEBDAV_URL=http://192.168.1.100:5244
WEBDAV_USERNAME=tdmdo
WEBDAV_PASSWORD=your_password_here
WEBDAV_PATH=/TDM新聞/
```

Alist／OpenAlist 帳號需有 WebDAV 讀寫權限，目標目錄亦須存在。成功下載會嘗試自動上傳；推送失敗不會把已完成下載改判為失敗。

---

## Claude Code Skill

Skill 位於 `.claude/skills/tdm/`。在對話中提及 TDM、澳廣視、澳門新聞、新聞搜尋、新聞影片下載、裁剪或遠端模式，可觸發現行流程。

```text
使用者：查詢最新的 TDM 影片新聞
→ 執行 tdm_tool.py news --video-only

使用者：搜尋關於「颱風」的新聞
→ 執行 tdm_tool.py search 颱風

使用者：下載 https://www.tdm.com.mo/zh-hant/news-detail/1217791
→ 提取新聞 ID，執行 download 命令

使用者：把 video.mp4 從 10.500 秒裁到 13.125 秒
→ 執行 tdm_tool.py trim --input video.mp4 --start 10.500 --end 13.125
```

對話式裁剪應執行現行 `trim` CLI 命令，不應描述成直接呼叫某個未展示的「函數」。

---

## TDM API 簡表

基礎 URL：`https://www.tdm.com.mo/api/v1.0`

| API | 正確端點／範例 | 現行消費範圍 |
|---|---|---|
| 新聞列表 | `/news?Page=1&PageSize=40&Lang=zh` | `news` 使用；分類、日期、影片篩選 |
| 新聞詳情 | `/news/{id}` | 回應可含 `video`、`audio`、`images[]`、`iconIndicator`；Skill 只消費 `video` |
| 全文搜尋 | `/search/?Keywords=澳門&SelectType=search_news&Page=1&PageSize=15&FullSearch=true&DateSort=true` | `search` 使用，但只查第一頁 |
| 搜尋建議 | `/searchbar?query=澳門&Lang=zh` | 目前 404，網站搜尋欄也不再使用，不可依賴 |

TDM 新聞、節目、直播、搜尋、專題與微視頻等公開內容一般免登入、Cookie 與瀏覽器 JS；`member/*` 等會員功能例外。TDMDO Web 認證是獨立層，不可混為一談。

### 分類

| 類別 | API 數字 | CLI 別名 |
|---|---:|---|
| 本地 | `27` | `local` |
| 要聞 | `41` | `world` |
| 體育 | `42` | `sport` |
| 特稿 | `143` | `feature` |

---

## 典型工作流

### 查詢、下載並以毫秒裁剪

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --category local --video-only --page 1 --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --output "downloads/news.mp4"
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input "downloads/news.mp4" --start 10.500 --end 13.125 \
  --output "downloads/news_highlight.mp4"
```

### 下載時直接裁剪並推送

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download \
  --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791" \
  --cut 00:10.500,00:02.250 \
  --output "downloads/highlight.mp4" \
  --push --push-target tg
```

### 搜尋後下載

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 交通 --type search_news --video-only --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
```

### 啟動 Web Server

```bash
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

---

## 已知限制

1. CLI 的 TDM API 下載解析只接受新聞 ID／新聞 URL，並只消費新聞詳情 `video`。
2. 搜尋固定只查第一頁；`search_program`、`search_short_video` 的顯示、URL 與下載解析不完整。
3. 本地與遠端 `news --search` 語義不同：本地過濾當頁列表，遠端改走全文搜尋。
4. 節目 slug、新聞音訊／圖片、直播、節目表與專題已在網站 API 確認，但沒有對應 CLI 流程。
5. `/api/v1.0/searchbar` 目前 404；不可作搜尋建議依據。
6. `IsShowSevenDay=true` 不是完整歷史開關；`false` 或省略可能取得更少資料。
7. `/short-video/{id}` 獨立詳情契約尚未確認；抽樣回 404。
8. 字幕欄位與 HLS 字幕軌尚未確認，不能宣稱已支援或全站不存在。
9. 遠端媒體推送與裁剪不會上傳 Client 本機檔案。
10. Web UI／後端對非新聞 URL 只依賴 yt-dlp／ffmpeg fallback，成功與否取決於來源及工具能力。
11. 遠端輪詢逾時不取消 Server 下載任務。
12. 裁剪精度受來源時間戳、影格率、關鍵幀、音訊取樣及 ffmpeg 行為影響。

---

## 疑難排解

### 下載失敗

確認至少有 ffmpeg 或 yt-dlp，並可由目前 PATH 執行：

```bash
ffmpeg -version
yt-dlp --version
```

若是新聞下載，另確認 ID 為 6–7 位、新聞存在且 `data.detail.video` 非空。節目頁、直播頁或任意公開影片 URL 不屬於 CLI 已保證的新聞解析範圍。

### 裁剪不精確

程式先執行包含 `-ss`、`-t`、`-avoid_negative_ts make_zero` 的 ffmpeg 命令；失敗後的 fallback 仍使用 `-ss` 與 `-t`。兩條命令都**沒有顯式指定 codec**，因此不要假定一定重新編碼、一定 stream copy，或一定精確到幀。實際輸出由來源格式、時間戳、影格率、取樣邊界及 ffmpeg 預設選擇決定。

### Telegram 推送失敗

```text
1. 確認已安裝 python-telegram-bot
2. 確認 PUSH_ENABLED、TG_TOKEN、TG_CHATID
3. 確認 Bot 有目標群組／頻道權限
4. 遠端媒體推送時，確認同名檔案已在 Server TDM_DOWNLOAD_DIR
```

### WebDAV 推送失敗

```text
1. 確認 WEBDAV_ENABLED=true 且 URL／帳密完整
2. 確認帳號有 WebDAV 讀寫權限
3. 確認目標目錄存在
4. 優先把配置放在 .claude/skills/tdm/.env
```

### 遠端 401

確認 Server 的 `WEB_AUTH_ENABLED=true`、`WEB_AUTH_PASSWORDS` 已配置，且 Client `TDM_SERVER_PASSWORD` 精確匹配其中一個值。請勿把 TDM 網站會員密碼用作這項配置。

---

## 參考資料

- [TDM API 正式 Reference（唯一詳細文件）](docs/TDMDO/reference/TDM_API_Reference.md)
- [TDM 網站 API 快速導讀](.claude/skills/tdm/references/tdm-site-reference.md)
- [現行 CLI／遠端使用範例](.claude/skills/tdm/examples/example-usage.md)
- [TDM Skill 定義](.claude/skills/tdm/SKILL.md)

---

## 授權

專案為私有工具，僅供學習與個人使用。使用時請遵守 TDM 網站服務條款與內容授權規範。
