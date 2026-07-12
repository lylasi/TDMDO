---
name: tdm
description: TDM（澳廣視 tdm.com.mo）新聞查詢與搜尋、新聞影片下載/裁剪、內容推送及遠端模式工具。Trigger when mentioning TDM, 澳廣視, 澳門新聞, tdm.com.mo, 新聞查詢, 關鍵字搜索, 新聞下載, 新聞影片下載, 裁剪影片, 剪片, m3u8, 推送, 遠端模式, tdm_tool.（Web UI 已剝離為獨立 app/tdm_web.py）
argument-hint: "[command] [options]"
---

# TDMDO — 澳廣視新聞/影片一站式工具

以 TDM 公開內容 API 為核心（不需瀏覽器 JS 渲染），目前整合新聞查詢、全文搜尋、新聞影片下載與裁剪、Telegram/WebDAV 推送及遠端模式。

> **實作邊界**：目前 CLI 的 TDM API 解析路徑只支援以 6–7 位新聞 ID 查詢 `/api/v1.0/news/{id}` 並消費 `video` 欄位。TDM 網站已確認的節目、直播、節目表、新聞音訊及圖片等 API，不代表 Skill 已提供對應查詢或下載命令；詳見「TDM 網站已確認、尚未接入 Skill」。

## 遠端模式（多機共用一台 Server）

設定 `TDM_SERVER` 環境變數後，CLI 操作自動走遠端 HTTP 調用，不需本機 SQLite / ffmpeg：

```bash
# 方式一：環境變數（Windows cmd，目前工作階段生效）
set TDM_SERVER=http://192.168.1.100:8080

# 方式二：命令列參數（一次性；--server 可置於子命令前或後）
python tdm_tool.py --server http://192.168.1.100:8080 news --limit 10
python tdm_tool.py news --server http://192.168.1.100:8080 --limit 10
```

| 命令 | 現行遠端行為 |
|---|---|
| `news` | HTTP GET `/api/news` |
| `search` | HTTP GET `/api/news?search=...&stype=...` |
| `download` | HTTP POST `/api/download` + 輪詢 `/api/progress/{id}` |
| `trim` | HTTP POST `/api/trim`（伺服器端檔案） |
| `push` | HTTP POST `/api/push-text` 或 `/api/push-to-tg` |
| `db stats` | HTTP GET `/api/db-stats` |
| `db sync` | HTTP POST `/api/db-sync` |
| `push-log` | HTTP GET `/api/push-log` |

> 遠端 `search` 的真實契約仍是 `/api/news?search=`，目前沒有 `/api/search` 路由。Server 會轉調同一個 `query_search`，因此也只查 TDM 全文搜尋 API 的第一頁。

**客戶端只需要**：`pip install requests`（不需 ffmpeg / SQLite / flask）。

> Server 端需執行 `python app/tdm_web.py --host 0.0.0.0 --port 8080`。
> TDM 公開內容 API 本身免登入；這不等於 TDMDO Web Server 必須公開。Server 可設定 `WEB_AUTH_ENABLED=true`，並以 `WEB_AUTH_PASSWORDS` 提供一個或多個逗號分隔密碼；遠端客戶端的 `TDM_SERVER_PASSWORD` 必須匹配其中一個密碼。建議僅在 HTTPS 或可信任內網使用。TDM `member/*` 會員 API 另屬例外，可能要求登入。

## 環境檢查

```bash
python --version
ffmpeg -version
pip install requests flask
pip install yt-dlp python-telegram-bot
```

- Python ≥ 3.9。
- `requests`：核心與遠端客戶端必需。
- `ffmpeg`：裁剪必需；本地下載可使用 ffmpeg 或 yt-dlp。
- `flask`：僅獨立 Web Server 使用。
- `yt-dlp`：可選的下載器。
- `python-telegram-bot`：Telegram 推送必需。

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
| `TDM_SERVER_PASSWORD` | (無) | 遠端客戶端自動登入密碼；需匹配 Server `WEB_AUTH_PASSWORDS` 其中之一 |
| `TDM_REMOTE_POLL_TIMEOUT` | `600` | 遠端下載進度輪詢總逾時秒數 |
| `WEB_AUTH_ENABLED` | `false` | Server 是否啟用 TDMDO Web/API 密碼保護 |
| `WEB_AUTH_PASSWORDS` | (無) | Server 允許的密碼，支援逗號分隔多個值 |
| `WEBDAV_ENABLED` | `false` | 是否啟用 WebDAV 自動推送 |
| `WEBDAV_URL` | (無) | WebDAV 伺服器 URL |
| `WEBDAV_USERNAME` | (無) | WebDAV 上傳帳號 |
| `WEBDAV_PASSWORD` | (無) | WebDAV 上傳密碼 |
| `WEBDAV_PATH` | `/` | WebDAV 上傳目標目錄 |

> 載入順序：系統環境變數 > `.env` > 預設值。CLI 工具會自動載入 skill 目錄下的 `.env`。

## 核心命令（目前程式已實作）

### 1. 查詢新聞列表

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news [OPTIONS]

選項:
  --category {all,local,world,sport,feature,27,41,42,143}  分類名稱或 ID（預設: all）
  --limit N                                                篇數（預設: 10）
  --page N                                                 頁碼（預設: 1）
  --search KEYWORD                                         在本次新聞列表結果中過濾關鍵字
  --date YYYY-MM-DD                                        指定日期
  --video-only                                             僅顯示有影片的新聞
```

**URL 規則**：新聞列表 API 使用 `/api/v1.0/news` 及 `Page`、`PageSize` 等參數，直接 GET 即可，無需 JS。

> 本地 `news --search` 是對當次 `/news` 列表頁結果做客戶端過濾；遠端模式的 `/api/news?search=` 則會切換到全文搜尋 `query_search`。兩者語義不同。

### 2. 下載新聞影片（從新聞 ID 或新聞 URL）

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true"
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 00:00:20,00:00:30
```

`--cut` 格式固定為 `START,DURATION`，第二值是持續時間而非結束時間。時間支援小數秒（毫秒），例如：

```bash
# 從 10.500 秒開始，裁剪 2.250 秒
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 10.500,2.250

# 等價時間格式
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 00:10.500,00:02.250
```

**現行原理**：從參數或 URL 提取 6–7 位新聞 ID → 調用 `/api/v1.0/news/{id}` → 讀取 `data.detail.video` 的 HLS URL → 使用 ffmpeg 或 yt-dlp 下載。

> 現行 slug 節目頁及其 `/program/{slug}/details|feature|review` 資料尚未接入下載流程。不要把節目 slug、節目主檔 ID、集數 ID或片段 ID 當作新聞 ID 使用。

### 3. 裁剪影片

```bash
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input video.mp4 --start 00:00:20 --end 00:00:50 --output clip.mp4
```

亦可用 `--duration` 代替 `--end`；兩者不可同時使用。所有時間參數均支援以下格式，秒數部分可帶小數：

- 純秒數：`10.500`（10 秒 500 毫秒）
- `MM:SS.sss`：`00:10.500`
- `HH:MM:SS.sss`：`00:00:10.500`

```bash
# 10.500 秒至 13.125 秒（長度 2.625 秒）
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input video.mp4 --start 10.500 --end 13.125 --output clip.mp4

# 同一範圍，改用持續時間
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input video.mp4 --start 00:00:10.500 --duration 00:00:02.625 --output clip.mp4
```

小數秒會以浮點秒數傳給 ffmpeg；實際可達精度仍受來源影片時間戳、影格率及音訊取樣邊界影響。

### 4. 關鍵字全文搜尋

```bash
# 預設搜尋新聞
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門 政府"

# CLI 已實作的搜尋類型
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門" --type search_news
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門" --type search_short_video
python .claude/skills/tdm/scripts/tdm_tool.py search "澳門" --type search_program
```

支援多關鍵字（空格分隔）。目前 `query_search` 固定請求全文搜尋 API 的 `Page=1`，`PageSize=max(limit, 40)`，**不會自動搜尋多頁**。CLI parser 目前只有 `search_news`、`search_short_video`、`search_program` 三種 choice，尚未提供 `search_pressrelease`。

> `search_program` 與 `search_short_video` 的結果結構不同於新聞；現行 CLI 的網址顯示及後續下載解析仍以新聞為主，尚不完整。不可假定它們都能拼成 `/news-detail/{id}` 或直接交給 `download`。

### 5. 網頁端（獨立部署）

```bash
# 僅本機訪問
python app/tdm_web.py --host 127.0.0.1 --port 8080

# 允許內網其他機器訪問
python app/tdm_web.py --host 0.0.0.0 --port 8080
```

訪問 http://127.0.0.1:8080 或 `http://<本機IP>:8080`。含 6–7 位新聞 ID 的 TDM 新聞 URL 會走官方新聞 API；其他 URL 只能依賴伺服器上的 yt-dlp/ffmpeg 是否能解析，不代表已正式接入節目、直播或其他 TDM API。

> **注意**：`app/tdm_web.py` 是獨立的 Flask 網頁服務，不屬於 skill 本體。如需在 QClaw 中使用網頁端，需將 `app/tdm_web.py` 一併複製到目標工作區。
> 使用 `0.0.0.0` 時請確保 Windows 防火牆放行 8080 埠，並視需要設定 `WEB_AUTH_ENABLED=true` 與 `WEB_AUTH_PASSWORDS`；否則內網其他機器可能無法連入或服務可能未受保護。

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

> **遠端媒體推送限制**：設定 `TDM_SERVER` 後，`push --video/--image/--file` 不會把客戶端本機檔案上傳至 Server。參數會取 basename，Server 只會在自己的 `TDM_DOWNLOAD_DIR` 尋找同名檔案；因此檔案必須已存在於伺服器下載目錄。純文字 `push --text` 不受此限制。

**推送配置** (`.env`)：

| 變數 | 預設值 | 說明 |
|---|---|---|
| `PUSH_ENABLED` | `true` | 是否啟用推送 |
| `PUSH_DEFAULT_TARGET` | `tg` | 預設推送通道（逗號分隔） |
| `TG_TOKEN` | (無) | Telegram Bot Token（@BotFather） |
| `TG_CHATID` | (無) | Telegram Chat ID（個人/群組/頻道） |

**支援推送內容類型**：文字、影片 (`.mp4/.mkv/.webm` ≤50MB)、圖片 (`.jpg/.png/.gif/.webp` ≤10MB)、文件（任意格式 ≤50MB）。這裡的圖片支援是推送本機圖片，不是從 TDM 新聞下載 `images[]`。

**智慧發送**：根據副檔名自動選擇 `sendVideo` / `sendPhoto` / `sendDocument`，超限自動降級。

**獨立使用**（不依賴 TDM 模組）：

```python
from push_manager import push_text, push_video, push_image, push_media

push_text("Hello Telegram!")
push_video("video.mp4", "新聞影片")
push_media("photo.jpg", "截圖")  # 自動判斷類型
```

**新增通道**：在 `push_manager.py` 中繼承 `BaseChannel`，加入 `CHANNEL_REGISTRY` 即可。

## TDM API 架構與現行消費範圍

| API | TDM 網站 URL | Skill 現況 |
|---|---|---|
| 新聞列表 | `/api/v1.0/news?Page=1&PageSize=40&Lang=zh` | 已用於 `news`；支援分類、日期、影片過濾等現有參數 |
| 新聞詳情 | `/api/v1.0/news/{id}` | 已用於新聞影片解析；網站回應可含 `video`、`audio`、`images[]`、`iconIndicator`，Skill 現在只消費 `video` |
| 全文搜尋 | `/api/v1.0/search/?Keywords=關鍵字&SelectType=search_news&Page=1&PageSize=15&FullSearch=true&DateSort=true` | 已用於 `search`，但現行只請求第一頁 |
| 搜尋建議 | `/api/v1.0/searchbar?query=關鍵字&Lang=zh` | 目前回傳 404，不可依賴；網站搜尋欄亦不再使用 |

TDM 新聞、節目、直播、搜尋、專題與微視頻等公開內容 API 一般無需登入、Cookie 或 JS 渲染；`member/*` 等會員 API 例外。TDMDO 自己的 Web Server 可另外設定 `WEB_AUTH_ENABLED` 與 `WEB_AUTH_PASSWORDS`，兩者是不同認證層。

## 新聞分類對照

| 前端顯示 | API `Category` 數字值 | CLI `--category` 別名 |
|---|---:|---|
| 全部 | 空值/default | `all` |
| 本地 | `27` | `local` |
| 要聞 | `41` | `world` |
| 體育 | `42` | `sport` |
| 特稿 | `143` | `feature` |

> TDM API 的 `Category` 必須使用數字 ID；`local/world/sport/feature` 是 TDMDO CLI 在送出請求前轉換的便利別名，不是 API 原生值。

## TDM 網站已確認、尚未接入 Skill

以下能力已在 TDM 網站/API 調研中確認，但目前沒有對應的 Skill CLI 查詢或下載流程。完整端點、參數、回應結構與限制以 [`docs/TDMDO/reference/TDM_API_Reference.md`](../../../docs/TDMDO/reference/TDM_API_Reference.md) 為準：

- 節目 slug 契約：`/api/v1.0/program/{slug}/details`、`feature`、`review`；numeric `/program/{id}` 端點不可靠。
- 新聞 `audio`、`images[]` 及 video/audio/images mixed media；目前核心只消費 `video`。
- 直播分類及串流資訊：`/api/v1.0/live/categories`。
- 節目表：`/api/v1.0/program-list/Channel`、`program-list/categories`、`program-list/{date}`。
- 全文搜尋的 `search_pressrelease` 類型；CLI 尚未有此 choice。
- `short-video` 分類與列表端點已確認；但 `/short-video/{id}` 抽樣回 404，獨立 detail 契約尚未確認，不可宣稱可穩定下載。
- `special` 專題主檔、關聯節目、節目重溫及專題新聞端點。
- 語言參數 `Lang=zh-hant`、`zh`、`pt`、`en`，實際用法依端點而異。
- 字幕欄位與 HLS 字幕軌尚未確認；不可宣稱支援或全站不存在字幕。

> 本章只記錄網站能力，不提供不存在的 CLI 命令。

## 已知限制

1. **搜尋只查第一頁**：`query_search` 固定 `Page=1`，不會自動跨頁。
2. **本地與遠端 `news --search` 語義不同**：本地對當頁新聞列表做客戶端過濾；遠端 `/api/news?search=` 轉用全文搜尋。
3. **節目 slug 未支援下載**：新聞下載流程不能處理 `/program/{slug}` 或節目 review 的多層資源。
4. **新聞音訊/圖片未消費**：詳情 API 可回傳 `audio`、`images[]`、`iconIndicator`，目前下載只讀 `video`。
5. **`searchbar` 已失效**：目前回傳 404，不可作搜尋建議依據。
6. **`IsShowSevenDay=true` 不是全歷史開關**：抽樣中 `true` 只取得較多近期資料，不代表完整歷史；`false` 或不傳時抽樣結果較少。
7. **非新聞搜尋結果解析不完整**：`search_program`、`search_short_video` 的網址顯示與下載契約尚未完整接入。
8. **字幕未確認**：目前抽樣未發現穩定字幕欄位或 HLS `SUBTITLES` 軌，但不能據此斷言全站沒有字幕。

## 常見工作流

### A：查詢今日有影片的新聞並下載

```bash
# 找出有影片的新聞
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 5
# 下載指定新聞 ID
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
```

### B：從新聞連結一鍵下載裁剪

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true"
python .claude/skills/tdm/scripts/tdm_tool.py trim --input "1217791_世界盃16強.mp4" --start 00:00:20 --end 00:00:50
```

### C：搜尋特定主題新聞

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search "暴雨 警告"
```

### D：啟動網頁端分享給非技術用戶

```bash
python app/tdm_web.py --port 8080
```

## 相依性

- Python ≥ 3.9、requests
- ffmpeg 或 yt-dlp（本地影片下載；裁剪使用 ffmpeg）
- flask（僅獨立 Web Server）

## 其他資源

- 現行 TDM 網站 API 調研：`docs/TDMDO/reference/TDM_API_Reference.md`
- Skill 內歷史網站說明：`references/tdm-site-reference.md`（如與現行 API Reference 衝突，以現行 API Reference 為準）
- 使用範例：`examples/example-usage.md`
- `TDM/`：**已廢棄的歷史版本，不作現行實作依據**
- `.env` 設定範例：`.env.example`（含 WebDAV 自動推送配置）

## WebDAV 自動推送

下載完成後可透過 WebDAV 協議（HTTP Basic Auth）自動上傳到 Alist / OpenAlist。

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
2. 勾選「WebDAV 讀寫」權限
3. 確保目標目錄存在

配置完成後，每次成功下載會嘗試自動推送；推送失敗不影響下載結果。

### 查看推送記錄

```bash
python .claude/skills/tdm/scripts/tdm_tool.py push-log --limit 20
```

現行 `push-log` 從 SQLite `news` 表的 `push_url`、`push_time` 欄位查詢已推送記錄。不存在現行 `webdav_push_log` 表；`init_db()` 會刪除舊版遺留的同名表。
