# TDMDO 現行使用範例

> **與現行 Skill 同步日期：2026-07-12**
>
> 本文件只展示目前 `tdm_tool.py` 與 `tdm_remote.py` 已實作的能力。範例中的新聞 ID、日期、檔名及 Server 位址僅為格式示例；執行時請替換為實際值。

## 基本準備

從專案根目錄執行下列命令：

```bash
python --version
pip install requests
```

本地下載需要 `ffmpeg` 或可選的 `yt-dlp`；裁剪需要 `ffmpeg`。Telegram 推送另需安裝並設定：

```bash
pip install python-telegram-bot
ffmpeg -version
```

遠端客戶端只需 `requests`，不需在客戶端安裝 Flask、SQLite 或 ffmpeg。

## 1. 查詢新聞列表 `news`

### 筆數、頁碼與影片過濾

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --limit 5
python .claude/skills/tdm/scripts/tdm_tool.py news --page 2 --limit 20
python .claude/skills/tdm/scripts/tdm_tool.py news --video-only --limit 10
```

### 分類：別名或數字均可

```bash
# 別名：all / local / world / sport / feature
python .claude/skills/tdm/scripts/tdm_tool.py news --category local --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --category world --limit 10

# 對應數字：27 / 41 / 42 / 143
python .claude/skills/tdm/scripts/tdm_tool.py news --category 42 --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --category 143 --limit 10
```

| CLI 別名 | 數字分類 | 類別 |
|---|---:|---|
| `all` | 空值 | 全部 |
| `local` | `27` | 本地 |
| `world` | `41` | 要聞 |
| `sport` | `42` | 體育 |
| `feature` | `143` | 特稿 |

### 日期及組合條件

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --date 2026-07-12 --limit 20
python .claude/skills/tdm/scripts/tdm_tool.py news --date 2026-07-12 --category local --video-only --page 1 --limit 10
```

### `news --search` 的本地／遠端差異

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --search "暴雨" --limit 20
```

- **本地模式**：先取得指定新聞列表頁，再在該頁結果中過濾關鍵字，不是全站全文搜尋。
- **遠端模式**：Server 的 `/api/news?search=...` 會轉用全文搜尋 `query_search`，語義不同，而且仍只查第一頁。
- 需要明確的全文搜尋時，優先使用下一節的 `search` 命令。

## 2. 全文搜尋 `search`

關鍵字可分成多個位置參數；CLI 會以空格合併：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 政府 --limit 15
python .claude/skills/tdm/scripts/tdm_tool.py search 暴雨 警告 --type search_news --video-only --limit 10
```

目前 parser 只實作三種 `--type`：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 --type search_news --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 --type search_short_video --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py search 澳門 --type search_program --limit 10
```

重要限制：

- 搜尋固定只請求 `Page=1`，**不會自動跨頁**；`--limit` 控制顯示／請求筆數，不代表會搜尋後續頁。
- `search_program` 與 `search_short_video` 的結果顯示、網址組合及後續下載解析尚不完整；不要假設搜尋結果可直接交給 `download`。
- CLI 沒有實作 `search_pressrelease` choice，因此不要把它寫成 `search --type` 範例。

## 3. 下載新聞影片 `download`

下載入口只使用 **6–7 位新聞 ID** 或 **含 6–7 位新聞 ID 的 TDM 新聞 URL**：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true"
```

指定輸出、覆蓋既有檔案：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --output "downloads/news.mp4"
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --output "downloads/news.mp4" --overwrite
```

下載時直接裁剪；`--cut` 固定為 `START,DURATION`，第二值是持續時間，不是結束時間。支援小數秒（毫秒）：

```bash
# 整秒：從 20 秒開始，持續 30 秒
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 00:00:20,00:00:30

# 毫秒：從 10.500 秒開始，持續 2.250 秒
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --cut 10.500,2.250

# MM:SS.sss 格式與自訂輸出
python .claude/skills/tdm/scripts/tdm_tool.py download --url "https://www.tdm.com.mo/zh-hant/news-detail/1217791" --cut 00:10.500,00:02.250 --output "downloads/clip.mp4"
```

下載完成後推送：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download --id 1217791 --push
```

不要使用節目 slug、節目主檔 ID、集數 ID 或片段 ID 取代新聞 ID；現行下載流程只會查詢新聞詳情並消費其 `video` 欄位。

## 4. 裁剪現有影片 `trim`

`--start` 必填，並且必須在 `--end` 與 `--duration` 中二選一；兩者互斥，不可同時提供。

時間支援三種格式，秒數部分可使用小數：

| 格式 | 範例 | 意義 |
|---|---|---|
| 純秒數 | `10.500` | 10 秒 500 毫秒 |
| `MM:SS.sss` | `00:10.500` | 10 秒 500 毫秒 |
| `HH:MM:SS.sss` | `00:00:10.500` | 10 秒 500 毫秒 |

以結束時間裁剪：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py trim --input "downloads/news.mp4" --start 00:00:20 --end 00:00:50 --output "downloads/clip.mp4"
```

以持續時間裁剪：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py trim --input "downloads/news.mp4" --start 00:00:20 --duration 00:00:30 --output "downloads/clip.mp4"
```

毫秒精確裁剪：

```bash
# 由 10.500 秒裁至 13.125 秒，實際長度 2.625 秒
python .claude/skills/tdm/scripts/tdm_tool.py trim --input "downloads/news.mp4" --start 10.500 --end 13.125 --output "downloads/clip_ms.mp4"

# 同一範圍，以 HH:MM:SS.sss + duration 表示
python .claude/skills/tdm/scripts/tdm_tool.py trim --input "downloads/news.mp4" --start 00:00:10.500 --duration 00:00:02.625 --output "downloads/clip_ms.mp4"
```

小數秒會以浮點秒數交給 ffmpeg；實際可達精度仍受來源影片時間戳、影格率與音訊取樣邊界影響。

本地模式的 `--input` 是本機路徑。遠端模式的 `--input` 是 **Server 的 `TDM_DOWNLOAD_DIR` 內檔名**，不是客戶端路徑，也不會上傳客戶端檔案：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 trim --input "1217791_news.mp4" --start 00:00:20 --duration 00:00:30 --output "clip.mp4"
```

## 5. 遠端模式

### `--server` 可放在子命令前或後

```bash
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 news --limit 10
python .claude/skills/tdm/scripts/tdm_tool.py news --server http://192.168.1.100:8080 --limit 10
```

也可使用環境變數。Windows cmd：

```bat
set TDM_SERVER=http://192.168.1.100:8080
set TDM_SERVER_PASSWORD=your_client_password
set TDM_REMOTE_POLL_TIMEOUT=900
python .claude/skills/tdm/scripts/tdm_tool.py news --limit 10
```

PowerShell：

```powershell
$env:TDM_SERVER = "http://192.168.1.100:8080"
$env:TDM_SERVER_PASSWORD = "your_client_password"
$env:TDM_REMOTE_POLL_TIMEOUT = "900"
python .claude/skills/tdm/scripts/tdm_tool.py news --limit 10
```

Server 若設定 `WEB_AUTH_ENABLED=true`，其 `WEB_AUTH_PASSWORDS` 可包含一個或多個逗號分隔密碼；客戶端 `TDM_SERVER_PASSWORD` 必須匹配其中一個。密碼屬於 TDMDO Server 認證，不是 TDM 公開內容 API 的登入資訊。建議只在 HTTPS 或可信任內網傳送認證。

遠端命令的實際路由包括：

| CLI | 遠端路由 |
|---|---|
| `news` | `GET /api/news` |
| `search` | `GET /api/news?search=...&stype=...` |
| `download` | `POST /api/download`，再輪詢 `GET /api/progress/{id}` |
| `trim` | `POST /api/trim` |
| `push` 文字 | `POST /api/push-text` |
| `push` 媒體 | `POST /api/push-to-tg` |
| `db stats` | `GET /api/db-stats` |
| `db sync` | `POST /api/db-sync` |
| `push-log` | `GET /api/push-log` |

遠端 `search` 仍使用 `/api/news?search=...`，沒有 `/api/search` 路由，而且同樣只查全文搜尋第一頁。

遠端下載每 2 秒輪詢進度，預設總逾時 600 秒。可用正數秒數環境變數 `TDM_REMOTE_POLL_TIMEOUT` 調整；逾時只會停止客戶端輪詢，Server 任務仍可能繼續執行。

## 6. 推送 `push`

Telegram 推送需要 `python-telegram-bot`，並在 `.env` 或環境變數設定 `TG_TOKEN`、`TG_CHATID`。`--target` 可指定現行已配置的目標通道，例如 `tg`。

```bash
# 文字
python .claude/skills/tdm/scripts/tdm_tool.py push --text "新聞更新了" --target tg

# 影片
python .claude/skills/tdm/scripts/tdm_tool.py push --video "downloads/news.mp4" --caption "新聞影片" --target tg

# 圖片
python .claude/skills/tdm/scripts/tdm_tool.py push --image "downloads/photo.jpg" --caption "新聞截圖" --target tg

# 文件
python .claude/skills/tdm/scripts/tdm_tool.py push --file "downloads/report.pdf" --caption "新聞資料" --target tg
```

`--text`、`--video`、`--image`、`--file` 四者互斥，必須選一個。

> **遠端媒體限制**：遠端 `push --video/--image/--file` 只取參數的 basename，並在 Server 的 `TDM_DOWNLOAD_DIR` 尋找同名檔案；它不會上傳客戶端檔案。純文字推送不受此限制。

```bash
# Server 的下載目錄必須已存在 news.mp4
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 push --video "news.mp4" --caption "新聞影片" --target tg
```

## 7. 資料庫 `db` 與推送記錄 `push-log`

初始化本地 SQLite：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py db init
```

查看統計：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py db stats
```

同步近期新聞；`--pages` 每頁 40 篇，`--force` 會強制更新既有新聞的 detail 資料：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py db sync --pages 3
python .claude/skills/tdm/scripts/tdm_tool.py db sync --pages 3 --force
```

查看 WebDAV 推送記錄：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py push-log --limit 20
```

遠端例子：

```bash
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 db stats
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 db sync --pages 3
python .claude/skills/tdm/scripts/tdm_tool.py --server http://192.168.1.100:8080 push-log --limit 20
```

遠端 `db init` 由 Server 管理，CLI 只會提示無需手動執行。

parser 雖有 `db sync --all-days`，但上游 `IsShowSevenDay` 行為不可靠；關閉或省略該參數的抽樣結果可能反而更少，**不代表同步全歷史**，因此不作推薦命令範例。

## 8. WebDAV 自動推送

在 `.claude/skills/tdm/.env` 設定：

```env
WEBDAV_ENABLED=true
WEBDAV_URL=http://192.168.1.100:5244
WEBDAV_USERNAME=tdmdo
WEBDAV_PASSWORD=your_password_here
WEBDAV_PATH=/TDM新聞/
```

成功下載後會嘗試自動上傳至 WebDAV；推送失敗不會把已完成的下載改判為失敗。

`push-log` 的真實資料來源是 SQLite `news` 表中的 `push_url` 與 `push_time` 欄位，**不是** `webdav_push_log` 表。現行初始化流程會清理舊版遺留的 `webdav_push_log` 表。

## 9. 尚未實作，不要照抄為命令

以下是 TDM 網站／API 已知能力或待確認項目，但目前沒有對應的現行 CLI 命令或完整流程：

- 節目 slug 的 details／feature／review 查詢或下載。
- 新聞 `audio`、`images[]` 的下載；`push --image` 只推送既有圖片檔。
- `live` 直播與 `schedule`／節目表命令。
- `special` 專題命令。
- `search_pressrelease` CLI 搜尋類型。
- 字幕查詢、下載或燒錄。

不要自行創造 `program`、`audio`、`images`、`live`、`schedule`、`special`、`search_pressrelease` 或 `subtitle` 子命令。網站 API 的正式端點、參數、回應結構與已知限制，請查閱專案根目錄：

`docs/TDMDO/reference/TDM_API_Reference.md`
