# TDM 網站與 API 快速導讀

> **最後同步**：2026-07-12
>
> 本文件只提供精簡導讀；完整端點參數、回應結構、實測範例與限制，以專案根目錄的 `docs/TDMDO/reference/TDM_API_Reference.md` 為準。

## 使用邊界

- **網站 API 已確認**：代表 TDM 公開網站目前有對應端點及實測行為。
- **Skill 已實作**：代表現行 TDM Skill／CLI 已有可用流程；網站已有 API 不等於 Skill 已提供命令。
- 新聞、搜尋、節目、直播、節目表、微視頻與專題等公開內容通常免登入、Cookie 與瀏覽器 JS；`member/*` 會員端點例外，可能要求登入。

基礎 URL：`https://www.tdm.com.mo/api/v1.0`

## 網站 API 快覽

### 新聞

| 用途 | 端點 | 重點 |
|---|---|---|
| 新聞列表 | `GET /api/v1.0/news` | 支援分頁、分類、日期及列表模式；總數欄位為 `data.total`。 |
| 新聞分類 | `GET /api/v1.0/news/categories` | 已確認分類：本地 `27`、要聞 `41`、體育 `42`、特稿 `143`。 |
| 新聞詳情 | `GET /api/v1.0/news/{id}` | `data.detail` 可同時包含 `video`、`audio`、`images[]`、`iconIndicator`。 |
| 相關新聞 | `GET /api/v1.0/news/{id}/relation` | 取得關聯新聞。 |
| 新聞評論 | `GET /api/v1.0/news/{id}/comment` | 取得公開評論資料。 |

實際例子：

- 列表：`https://www.tdm.com.mo/api/v1.0/news?Type=image&IsShowSevenDay=true&Category=27&Page=1&PageSize=40&Lang=zh&Slug=news_list`
- 詳情：`https://www.tdm.com.mo/api/v1.0/news/1218429?Lang=zh-hant&Type=all`

`video`、`audio` 與 `images[]` 可能混合存在；`cover` 不等於完整圖片集合，應配合各媒體欄位與 `iconIndicator` 判斷。

### 全文搜尋

端點：`GET /api/v1.0/search/`

例子：`https://www.tdm.com.mo/api/v1.0/search/?Keywords=澳門&SelectType=search_news&Page=1&PageSize=15&FullSearch=true&DateSort=true`

| `SelectType` | 類型 | 識別特徵 |
|---|---|---|
| `search_news` | 新聞 | 新聞 ID 及 `video`、`audio`、`cover` 等欄位。 |
| `search_short_video` | 微視頻 | `type=SHORTVIDEO`，結果可直接含 `video`。 |
| `search_program` | 節目 | 以 `slug` 及節目契約為主。 |
| `search_pressrelease` | 公司動態 | `type=PRESSRELEASE`。 |

四類結果的 ID、slug 與 URL 契約不同，不可一律拼成新聞詳情 URL。`GET /api/v1.0/search/fitler` 可取得四類選項；`/api/v1.0/searchbar` 目前回傳 404，不可依賴。

### 節目與節目表

| 用途 | 端點 | 重點 |
|---|---|---|
| 節目列表 | `GET /api/v1.0/program` | 可依 `Type=tv|radio|all` 查詢。 |
| 節目主檔 | `GET /api/v1.0/program/{slug}/details` | 現行可靠詳情契約，以 slug 為主。 |
| 節目特色 | `GET /api/v1.0/program/{slug}/feature` | 內容可能為空。 |
| 節目重溫 | `GET /api/v1.0/program/{slug}/review` | 含日期群組、集數及可播放片段。 |
| 頻道清單 | `GET /api/v1.0/program-list/Channel?type=tv|radio` | 取得電視或電台頻道。 |
| 可查日期 | `GET /api/v1.0/program-list/categories?channelId=0` | 回傳節目表日期選項。 |
| 指定日期節目表 | `GET /api/v1.0/program-list/{date}` | 同時傳 `date`、`type`、`channelId`。 |

Slug 例子：`https://www.tdm.com.mo/api/v1.0/program/good_morning_macau/review?resource=good_morning_macau&Page=1&DateDesc=true&ViewTotalDesc=false&preRecordAd=0&Date=`

節目 review 的資源位於三層：`data.items[]`（日期群組）→ `items[]`（集數）→ `items[]`（片段）。節目主檔 ID、集數 ID、片段 ID 是不同識別值，不可互換。

### 直播

| 用途 | 端點 | 重點 |
|---|---|---|
| 直播分類與頻道 | `GET /api/v1.0/live/categories` | `channelInfo.onlineFeed` 提供當次直播 HLS URL。 |
| 頻道播放清單 | `GET /api/v1.0/live/{id}/playlist` | 可含節目開始、結束時間及標題。 |
| 特別直播 | `GET /api/v1.0/common/special-live` | 無特別直播時可回 `data: null`。 |

例子：`https://www.tdm.com.mo/api/v1.0/live/categories`

### 微視頻

| 用途 | 端點 | 重點 |
|---|---|---|
| 分類 | `GET /api/v1.0/short-video/category` | 回傳微視頻分類 ID。 |
| 列表 | `GET /api/v1.0/short-video` | 支援 `Page`、`PageSize`、`Category`、`Lang`。 |

例子：`https://www.tdm.com.mo/api/v1.0/short-video?Page=1&PageSize=3&Category=441&Lang=zh`

獨立 `/api/v1.0/short-video/{id}` detail 契約尚未確認，抽樣回傳 404。

### 專題

| 用途 | 端點 |
|---|---|
| 專題列表 | `GET /api/v1.0/special?Slug=special_site1` |
| 專題主檔 | `GET /api/v1.0/special/{slug}` |
| 關聯節目 | `GET /api/v1.0/special/{slug}/related-program` |
| 節目重溫 | `GET /api/v1.0/special/{slug}/program-review` |
| 專題新聞 | `GET /api/v1.0/special/{slug}/news` |

例子：`https://www.tdm.com.mo/api/v1.0/special/FIFA2026/news?id=FIFA2026&Tag=&Page=1&PageSize=16`

### CDN 域名映射

`GET https://www.tdm.com.mo/api/v1/common/get-domain` 使用 **v1**（不是 v1.0），可取得 VOD／直播域名映射。實際播放應優先使用各內容 API 當次回傳的完整 URL，不要硬編固定 CDN。

## Skill 現況

| 能力 | 現況 |
|---|---|
| 新聞列表 | 已實作 `news`。 |
| 全文搜尋 | 已實作 `search`，目前只查第一頁；CLI 類型包含新聞、微視頻及節目，不含 `search_pressrelease`。 |
| 新聞影片 | 已實作以 6–7 位新聞 ID 查詢詳情、讀取 `video`、下載及裁剪。 |
| 推送 | 已實作文字與本機媒體推送，以及下載後推送流程。 |
| 遠端模式 | 已實作透過 TDMDO Server 執行新聞、搜尋、下載、裁剪與推送等既有能力。 |

Skill **沒有** program slug、新聞 `audio`、新聞 `images[]`、live、schedule／program-list、special 的專用查詢或下載命令。網站搜尋結果中出現這些內容，不代表可直接交給新聞下載流程。

## 必要限制

1. `/api/v1.0/program/{numeric_id}` 不是可靠的節目詳情契約，實測可回 `data: null`；應使用 slug 的 `details`、`feature`、`review`。
2. `/api/v1.0/searchbar` 目前為 404；正式全文搜尋使用 `/api/v1.0/search/`。
3. 微視頻分類與列表已確認，但獨立 short-video detail 尚未確認。
4. `IsShowSevenDay=true` 只在抽樣中取得較多近期資料，不代表全歷史或全量資料。
5. 字幕欄位及 HLS 字幕軌尚未確認；不可宣稱支援，也不可斷言全站沒有字幕。
6. 官方 HLS URL 可使用 `playelist.m3u8` 拼字，必須保留 API 回傳值，不可擅自改成 `playlist.m3u8`。
7. 新聞 ID、節目主檔 ID、集數 ID、片段 ID 的用途不同；新聞下載流程不可接受其他種類 ID 作替代。
8. 節目 review 必須依 `data.items[] → items[] → items[]` 三層解析，不能把上層容器當成可播放片段。
9. 公開內容一般免登入，但 `member/*` 等會員端點例外。
10. 搜尋四類與各內容端點的回應結構不同；不要假定共同欄位或共同詳情 URL。

完整資料請查閱：`docs/TDMDO/reference/TDM_API_Reference.md`。
