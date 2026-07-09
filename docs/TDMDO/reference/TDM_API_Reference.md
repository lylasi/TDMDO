# TDM (澳廣視) API 參考文檔

> **最後更新**：2026-07-09
> **調研方法**：Playwright 瀏覽器實際抓取 6 個頁面 + 直接 API 測試驗證
> **基準網站**：`https://www.tdm.com.mo/zh-hant/`

---

## 目錄

1. [通用說明](#1-通用說明)
2. [核心 API：新聞](#2-核心-api新聞)
3. [新聞詳情與關聯](#3-新聞詳情與關聯)
4. [全文搜索](#4-全文搜索)
5. [節目](#5-節目)
6. [直播](#6-直播)
7. [搜尋輔助](#7-搜尋輔助)
8. [CMS 與頁面](#8-cms-與頁面)
9. [通用功能](#9-通用功能)
10. [廣告](#10-廣告)
11. [其他 API](#11-其他-api)
12. [V1 API（非 v1.0）](#12-v1-api非-v10)
13. [影片 m3u8 處理](#13-影片-m3u8-處理)
14. [已知限制與行為](#14-已知限制與行為)
15. [頁面與 API 對照](#15-頁面與-api-對照)

---

## 1. 通用說明

### 1.1 認證

**全部 API 無需登入、無需 Cookie、無需 JS 渲染**。直接 HTTP GET 即可。

### 1.2 基礎 URL

```
https://www.tdm.com.mo/api/v1.0
```

### 1.3 通用請求頭

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
```

### 1.4 通用回應格式

```json
{
  "code": 0,          // 0 或 200 = 成功
  "type": "Success",  // "Success" | "Info" | "Error"
  "message": "OK",
  "data": { ... }     // 各 API 不同
}
```

### 1.5 語言參數

| Lang 值 | 語言 |
|---------|------|
| `zh` | 簡體中文（部分頁面預設） |
| `zh-hant` | 繁體中文（詳情頁、側欄） |
| `pt` | 葡萄牙文 |
| `en` | 英文 |

### 1.6 新聞分類 ID

> 來源：`GET /api/v1.0/news/categories`

| ID | 名稱 | 說明 |
|----|------|------|
| `27` | 本地 | 澳門本地新聞 |
| `41` | 要聞 | 國際要聞 |
| `42` | 體育 | 體育新聞 |
| `143` | 特稿 | 專題報導 |

---

## 2. 核心 API：新聞

### 2.1 `GET /api/v1.0/news` — 新聞列表

最重要的 API，用於取得分頁新聞列表。

#### 完整參數表

| 參數 | 型別 | 必填 | 預設值 | 可選值 | 說明 |
|------|------|------|--------|--------|------|
| `Type` | string | 否 | — | `image` / `all_detail` / `all` | **關鍵參數**。`image`=卡片模式(含縮圖)；`all_detail`=列表細節模式，**`IsVideo` 過濾僅在此模式生效** |
| `IsShowSevenDay` | string | 否 | — | `true` / `false` | ⚠️ **僅設 `true` 才有完整結果**。設 `false` 或不傳反而更少（只回當天） |
| `IsVideo` | string | 否 | — | `true` / `false` | 僅 `Type=all_detail` 時生效。`true`=僅影片、`false`=僅文字、不傳=全部 |
| `Category` | string | 否 | `""` | `""` / `27` / `41` / `42` / `143` | 分類 ID（數字） |
| `Date` | string | 否 | `""` | `YYYY-MM-DD` | 日期過濾 |
| `Page` | int | 否 | `1` | ≥1 | 頁碼 |
| `PageSize` | int | 否 | `40` | 1~100 | 每頁筆數（首頁用 `12`） |
| `Lang` | string | 否 | `zh` | `zh` / `zh-hant` / `pt` / `en` | 語言 |
| `SpecialId` | string | 否 | `""` | — | 特殊專題 ID（僅 `Type=all_detail` 時用） |
| `Slug` | string | 否 | — | `web_news_homepage` / `news_list` | 頁面標識（僅 `Type=image` 時用） |
| `PreRecordAd` | int | 否 | `5` | 0~N | 前置廣告數（僅 `Type=image` 時用） |
| `adIds` | string | 否 | `[]` | JSON array | 廣告 ID（僅 `Type=all_detail` 時用） |

#### 官網實際請求範例

```text
# 首頁 — 卡片模式，12 篇
GET /api/v1.0/news?Type=image&IsShowSevenDay=true&Category=&Page=1&PreRecordAd=5&Slug=web_news_homepage&PageSize=12&Lang=zh

# 新聞列表頁 — 卡片模式，40 篇，含日期
GET /api/v1.0/news?IsShowSevenDay=true&Type=image&Category=&Date=2026-07-09&Page=1&PageSize=40&Lang=zh&PreRecordAd=5&Slug=news_list

# 新聞列表頁 — 分類過濾（本地）
GET /api/v1.0/news?IsShowSevenDay=true&Type=image&Category=27&Date=2026-07-09&Page=1&PageSize=40&Lang=zh&PreRecordAd=5&Slug=news_list

# 詳情頁側欄 — 細節模式，不含影片
GET /api/v1.0/news?IsShowSevenDay=true&Type=all_detail&IsVideo=false&SpecialId=&Page=1&PageSize=40&Lang=zh-hant

# 影片新聞 — 細節模式，僅影片
GET /api/v1.0/news?IsShowSevenDay=true&Type=all_detail&IsVideo=true&SpecialId=&Category=&Page=1&PageSize=40&Lang=zh
```

#### 各模式回傳數量對比（實測 2026-07-09）

| Type | IsVideo | Category | IsShowSevenDay | total |
|------|---------|----------|----------------|-------|
| `image` | (不傳) | — | `true` | **448** |
| `image` | (不傳) | — | (不傳) | 72 ⚠️ |
| `all_detail` | `true` | — | `true` | **210** |
| `all_detail` | `true` | — | `false` | 39 ⚠️ |
| `all_detail` | `true` | `27` | `true` | 135 |
| `all_detail` | `false` | — | `true` | 238 |

> ⚠️ `IsShowSevenDay` 設 `false` 或不傳時，回傳數量反而比 `true` 少（只回今天），這是 TDM API 的已知行為。

#### 回應結構

```json
{
  "code": 0,
  "type": "Success",
  "data": {
    "header": { "topItem": null },
    "newsList": [
      {
        "type": "news",
        "section": null,
        "data": [
          {
            "id": 1218364,
            "title": "新聞標題",
            "content": "<p>HTML 內容</p>",
            "date": "07/09/2026 10:53:00",
            "category": 27,
            "video": "",                           // 空字串=純文字
            "videoLength": 0,
            "videoThumb": "",
            "shareUrl": "https://www.tdm.com.mo/zh-hant/sharelink/news/1218364",
            "cover": "https://cdn2.tdm.com.mo/...",
            "tags": [],
            "viewCount": 0,
            "likeCount": 0,
            "commentCount": 0,
            "isTop": false,
            "isLike": false,
            "isCollect": false,
            "isAddList": false,
            "openComment": true,
            "newWindow": false,
            "channelId": null,
            "playlistId": null,
            "audio": null,
            "images": [],
            "iconIndicator": null,
            "headTitle": null,
            "type": "news",
            "createdAt": "2026-07-09T10:53:00",
            "path": null,
            "url": null,
            "urlTxt": null,
            "locale": "zh_TW"
          }
        ]
      }
    ],
    "adIds": [],
    "total": 651,              // ← 真實總數，必須用此值而非 len(items)
    "currentItemCount": 40,
    "currentPage": 1,
    "firstPageNewsNum": 1,
    "pageTime": 1783566768441
  }
}
```

**關鍵欄位說明**：

| 欄位 | 說明 |
|------|------|
| `data.total` | **API 回傳的總篇數** — 分頁計算必須以此為準 |
| `data.newsList[]` | 新聞容器陣列，每個容器有 `type`、`section`、`data[]` |
| `data.newsList[].data[]` | 實際新聞物件陣列 |
| `item.id` | 6-7 位新聞 ID |
| `item.title` | 新聞標題 |
| `item.content` | HTML 格式內文 |
| `item.date` | 格式 `MM/DD/YYYY HH:MM:SS` |
| `item.category` | 數字分類 ID |
| `item.video` | 空字串 = 純文字；非空 = m3u8 URL（含 `/play` 而非 `/playelist`） |
| `item.shareUrl` | 分享連結 |
| `item.cover` | 縮圖 URL |

---

### 2.2 `GET /api/v1.0/news/categories` — 新聞分類

回傳可用分類 ID 映射。

```text
GET /api/v1.0/news/categories
```

```json
[
  { "id": 27,  "title": "本地" },
  { "id": 41,  "title": "要聞" },
  { "id": 42,  "title": "體育" },
  { "id": 143, "title": "特稿" }
]
```

---

## 3. 新聞詳情與關聯

### 3.1 `GET /api/v1.0/news/{id}` — 新聞詳情

取得單篇新聞完整內容（含影片 m3u8）。

#### 官網實際請求

```text
GET /api/v1.0/news/1218364?SpecialId=&id=1218364&Lang=zh-hant&Date=&Category=&Type=all
```

#### 參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `SpecialId` | `""` | 特殊專題 |
| `id` | (同 path) | 新聞 ID |
| `Lang` | `zh-hant` | 語言。網站詳情頁用 `zh-hant` |
| `Date` | `""` | 日期關聯 |
| `Category` | `""` | 分類關聯 |
| `Type` | `all` | 回應類型 |

#### 回應結構（關鍵欄位）

```json
{
  "code": 200,
  "data": {
    "detail": {
      "id": 1218364,
      "title": "14個8年期的士牌開標  最快料明年次季分批投運",
      "content": "<p>HTML 格式完整內文</p>",
      "date": "07/09/2026 10:53:00",
      "category": 27,
      "video": "https://vod3.tdm.com.mo/newweb/_definist_/mp4:news_cn_20260709/xxx.mp4/playelist.m3u8",
      "videoLength": 0,
      "videoThumb": "https://cdn2.tdm.com.mo/...",
      "shareUrl": "https://www.tdm.com.mo/zh-hant/sharelink/news/1218364",
      "createdAt": "2026-07-09T10:53:00",
      "cover": "https://cdn2.tdm.com.mo/...",
      "tags": [],
      "viewCount": 0,
      "likeCount": 0,
      "commentCount": 0,
      "newWindow": false,
      "openComment": true,
      "locale": "zh_TW"
    }
  }
}
```

> **m3u8 轉換規則**：若 `video` 欄位含 `/play` 而非 `/playelist`，需替換為 `/playelist.m3u8`。例如 `/xxx.mp4/play` → `/xxx.mp4/playelist.m3u8`

### 3.2 `GET /api/v1.0/news/{id}/relation` — 相關新聞

```text
GET /api/v1.0/news/1218364/relation?id=1218364
```

回傳相關新聞列表（結構同 news 列表的 items）。

### 3.3 `GET /api/v1.0/news/{id}/comment` — 新聞評論

```text
GET /api/v1.0/news/1218364/comment
```

回傳該新聞的用戶評論。

---

## 4. 全文搜索

### 4.1 `GET /api/v1.0/search/` — 全文搜索

#### 官網實際請求

```text
GET /api/v1.0/search/?Keywords=澳門&SelectType=search_news&Page=1&PageSize=15&FullSearch=true&DateSort=true
```

#### 參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `Keywords` | (必填) | 搜尋關鍵字，支援多詞空格分隔 |
| `SelectType` | `search_news` | `search_news`(新聞) / `search_short_video`(微視頻) / `search_program`(節目) / `search_pressrelease`(公司動態) |
| `Page` | `1` | ≥1 |
| `PageSize` | `15` | 網站預設 15 |
| `FullSearch` | `true` | 全文搜索 |
| `DateSort` | `true` | 按日期排序 |

#### 回應結構

```json
{
  "code": 0,
  "data": {
    "count": 126438,
    "items": [
      {
        "id": 1218384,
        "title": "新聞標題",
        "content": "HTML 內容",
        "date": "07/09/2026 12:03:00",
        "video": "",                    // ← 自帶 video 欄位！
        "cover": "https://cdn...",
        "type": "news",
        "path": null,
        "url": null,
        "channelType": null,
        "programType": null,
        "playlistId": null,
        "slug": null,
        "newWindow": false,
        "infoId": null,
        "headTitle": null,
        "iconIndicator": null,
        "collectCount": 0,
        "likeCount": 0,
        "commentCount": 0,
        "viewCount": 0,
        "audio": null
      }
    ]
  }
}
```

> ⚠️ **重要**：search API 回傳的每條 item **已自帶 `video` 欄位**。過濾影片新聞時直接檢查 `item.video` 是否非空即可，**不需要**再對每個 ID 調用 `/news/{id}` 檢查。

---

## 5. 節目

### 5.1 `GET /api/v1.0/program` — 節目列表

#### 官網實際請求

```text
# 節目表頁 — 全部節目
GET /api/v1.0/program?Type=all&Page=1&Lang=zh&CategoryType=&PageSize=13&PreRecordAd=6&Slug=program_list

# 首頁 — TV 節目
GET /api/v1.0/program?Type=tv&PreRecordAd=4&PageSize=6

# 首頁 — 電台節目
GET /api/v1.0/program?Type=radio&PreRecordAd=4&PageSize=4
```

#### 參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `Type` | `all` | `tv` / `radio` / `all` |
| `Page` | `1` | ≥1 |
| `PageSize` | `13` | 1~N（首頁 TV=6, Radio=4） |
| `Lang` | `zh` | 語言 |
| `CategoryType` | `""` | 子分類 |
| `Slug` | `program_list` | 頁面標識 |
| `PreRecordAd` | `6` | 前置廣告 |

#### 回應結構

```json
{
  "code": 0,
  "data": {
    "header": { ... },
    "newsList": [ ... ],
    "adIds": [],
    "total": 381,
    "currentItemCount": 13,
    "currentPage": 1
  }
}
```

結構與新聞列表相同（共用 `newsList` 容器格式）。

### 5.2 `GET /api/v1.0/program/{id}` — 節目詳情

```text
GET /api/v1.0/program/850015
```

回應結構與 `GET /api/v1.0/news/{id}` 相同（`data.detail.*`），含 `video` 欄位。

### 5.3 `GET /api/v1.0/program/categories` — 節目分類

```text
GET /api/v1.0/program/categories?Type=all
```

### 5.4 `GET /api/v1.0/program-list/Channel` — 頻道清單

```text
GET /api/v1.0/program-list/Channel?type=tv
```

回傳頻道列表（直播頁使用）。

---

## 6. 直播

### 6.1 `GET /api/v1.0/live/categories` — 直播分類

回傳直播頻道分類與頻道資訊（含 logo、簡介）。

```text
GET /api/v1.0/live/categories
```

```json
[
  {
    "id": 1,
    "title": "電視",
    "channelInfo": [
      {
        "id": 1,
        "logo": "https://cdn2.tdm.com.mo/uploads/attachment/2021-03/...png",
        "title": "澳視澳門 91台",
        "intro": "<p>頻道簡介 HTML</p>"
      }
    ]
  }
]
```

### 6.2 `GET /api/v1.0/live/{id}/playlist` — 直播播放清單

```text
GET /api/v1.0/live/1/playlist
```

回傳當前頻道 m3u8 節目時間表（含 `startTime`, `endTime`, `title` 等）。

### 6.3 `GET /api/v1.0/common/special-live` — 特別直播

```text
GET /api/v1.0/common/special-live?slug=web_home&type=web
```

回傳 `data: null` 若無特別直播。

### 6.4 直播 m3u8 URL

```
https://globallive.tdm.com.mo/ch1/ch1.live/playlist.m3u8
```

域名可透過 `/api/v1/common/get-domain` 動態獲取。

---

## 7. 搜尋輔助

### 7.1 `GET /api/v1.0/search/fitler` — 搜尋類型選項

回傳搜尋頁的類型下拉選單。

```text
GET /api/v1.0/search/fitler
```

```json
[
  { "title": "新聞",   "type": "search_news" },
  { "title": "微視頻", "type": "search_short_video" },
  { "title": "節目",   "type": "search_program" },
  { "title": "公司動態","type": "search_pressrelease" }
]
```

### 7.2 `GET /api/v1.0/searchbar` — 搜尋建議

> ⚠️ **已失效**：`/api/v1.0/searchbar?query=test&Lang=zh` 目前回傳 **404**。TDM 網站搜尋欄不再呼叫此 API。

---

## 8. CMS 與頁面

### 8.1 `GET /api/v1.0/cms/common` — 全域 CMS 設定

全站每個頁面載入時呼叫，回傳網站導航、footer 等全域內容。

```text
GET /api/v1.0/cms/common
```

### 8.2 `GET /api/v1.0/cms/notice` — 全域公告

```text
GET /api/v1.0/cms/notice
```

### 8.3 `GET /api/v1.0/cms/page/item` — 頁面 Meta/SEO

回傳指定頁面的 meta 描述、header banner 等。

```text
GET /api/v1.0/cms/page/item?path=home
GET /api/v1.0/cms/page/item?path=news-list
GET /api/v1.0/cms/page/item?path=news-detail
GET /api/v1.0/cms/page/item?path=live
GET /api/v1.0/cms/page/item?path=search
GET /api/v1.0/cms/page/item?path=program%2Fall_program
```

### 8.4 `GET /api/v1.0/cms/common/setting` — 系統開關

```text
GET /api/v1.0/cms/common/setting?Identify=_system&ck=enable_gray_style
GET /api/v1.0/cms/common/setting?Identify=common&ck=logo
```

---

## 9. 通用功能

### 9.1 `GET /api/v1.0/common/weather` — 天氣

全站 header 天氣資訊。

```text
GET /api/v1.0/common/weather
```

```json
{
  "data": {
    "id": 0,
    "cover": "https://cdn2.tdm.com.mo/uploads/images/weather/02.png",
    "title": "天氣",
    "date": "2026-07-09",
    "content": "天氣描述",
    "t": "30",        // 當前溫度
    "h": "77",        // 濕度
    "maxT": "...",
    "minT": "..."
  }
}
```

### 9.2 `GET /api/v1.0/common/weather-notify` — 天氣警告

```text
GET /api/v1.0/common/weather-notify
```

### 9.3 `GET /api/v1.0/common/chinese-lunisolar` — 農曆

```text
GET /api/v1.0/common/chinese-lunisolar?date=2026-07-09
```

```json
{
  "data": {
    "date": "2026-07-09",
    "year": 2026,
    "month": 5,
    "day": 25,
    ...
  }
}
```

### 9.4 `GET /api/v1.0/common/banner` — 橫幅/選單

```text
GET /api/v1.0/common/banner?slug=menu_program         // 選單橫幅
GET /api/v1.0/common/banner?slug=homepage_TV_slider   // 首頁 TV 輪播
GET /api/v1.0/common/banner?slug=home_program         // 首頁節目
```

### 9.5 `GET /api/v1.0/common/message-template` — 訊息模板

```text
GET /api/v1.0/common/message-template?slug=cookies_content
```

Cookie 同意彈窗內容。

---

## 10. 廣告

### 10.1 `GET /api/v1.0/advertisement` — 廣告位

全站統一廣告 API，透過 `slug` 區分位置。

```text
GET /api/v1.0/advertisement?slug=homepagetop          // 首頁頂部
GET /api/v1.0/advertisement?slug=news_static_top      // 新聞頁固定廣告
GET /api/v1.0/advertisement?slug=news_detail          // 新聞詳情
GET /api/v1.0/advertisement?slug=news_detail_video    // 新聞詳情影片區
GET /api/v1.0/advertisement?slug=live_bottom          // 直播頁底部
GET /api/v1.0/advertisement?slug=live_pop_ctvp        // 直播彈窗
GET /api/v1.0/advertisement?slug=home_program_1       // 首頁節目 1
GET /api/v1.0/advertisement?slug=home_program_2       // 首頁節目 2
GET /api/v1.0/advertisement?slug=home_program_3       // 首頁節目 3
```

---

## 11. 其他 API

### 11.1 `GET /api/v1.0/short-video/category` — 微視頻分類

```text
GET /api/v1.0/short-video/category
```

### 11.2 `GET /api/v1.0/special` — 專題頁面

```text
GET /api/v1.0/special?Slug=special_site1
```

### 11.3 `GET /api/v1.0/member/playlist` — 會員播放清單

```text
GET /api/v1.0/member/playlist
```

需登入，未登入回傳空或錯誤。

---

## 12. V1 API（非 v1.0）

### 12.1 `GET /api/v1/common/get-domain` — CDN 域名映射

動態獲取當前 CDN 域名。

```text
GET https://www.tdm.com.mo/api/v1/common/get-domain
```

```json
{
  "message": "OK",
  "data": {
    "domains": {
      "https://vod3.tdm.com.mo": "https://vod5.tdm.com.mo",
      "https://live3.tdm.com.mo": "https://live5.tdm.com.mo",
      "https://locallive.tdm.com.mo": "https://globallive.tdm.com.mo",
      "https://localvod.tdm.com.mo": "https://globalvod.tdm.com.mo"
    },
    "videoDomain": "https://vod3.tdm.com.mo"
  }
}
```

---

## 13. 影片 m3u8 處理

### 13.1 m3u8 URL 格式

TDM 影片使用 HLS (m3u8) 格式，h264/AAC 編碼，最高 720p。

```
https://vod3.tdm.com.mo/newweb/_definist_/mp4:news_cn_20260709/xxx.mp4/playelist.m3u8
```

### 13.2 CDN 域名

```
vod1.tdm.com.mo ~ vod5.tdm.com.mo
cdn1.tdm.com.mo / cdn2.tdm.com.mo
globallive.tdm.com.mo       (直播)
globalvod.tdm.com.mo        (點播)
```

建議透過 `/api/v1/common/get-domain` 動態獲取最新域名映射。

### 13.3 URL 轉換規則

從 `GET /api/v1.0/news/{id}` 取得的 `video` 欄位，若含 `/play` 而非 `/playelist`：

```python
if m3u8 and "/play" in m3u8 and "/playelist" not in m3u8:
    m3u8 = m3u8.replace("/play", "/playelist.m3u8")
```

### 13.4 下載

```bash
# yt-dlp (優先)
yt-dlp --no-playlist -o output.mp4 "https://vod3.tdm.com.mo/.../playelist.m3u8"

# ffmpeg (備用)
ffmpeg -y -i "https://vod3.tdm.com.mo/.../playelist.m3u8" output.mp4
```

---

## 14. 已知限制與行為

| # | 限制 | 說明 |
|----|------|------|
| 1 | **`IsShowSevenDay` 必須為 `true`** | 設 `false` 或不傳時回傳數量反而更少（只回今天）。這是 TDM API 的已知行為，無法透過 API 參數突破。 |
| 2 | **`IsVideo` 僅在 `Type=all_detail` 時生效** | `Type=image` 模式下 `IsVideo` 參數被忽略。 |
| 3 | **`Category` 是數字 ID** | 傳字串值（如 `"local"`）無效，必須傳數字（如 `"27"`）。 |
| 4 | **Date 參數效果有限** | `Date` 參數在 `Type=image` 時有一定效果，但在 `Type=all_detail` 時效果不明顯。**
| 5 | **歷史日期需要跨頁掃描** | 查詢歷史日期時，API 單頁只含少量結果，需跨多頁收集。 |
| 6 | **`searchbar` API 已失效(404)** | TDM 網站搜尋欄不再使用此端點。 |
| 7 | **無需認證** | 所有 API 均為公開，無需 Cookie、Token 或 JS 渲染。 |
| 8 | **分頁上限** | API 約第 8-10 頁後回傳空資料，實際可取得約 300-400 篇。 |

---

## 15. 頁面與 API 對照

| 頁面 | URL 模式 | 調用的 API |
|------|----------|-----------|
| 首頁 | `/zh-hant` | `news`(Type=image,Slug=web_news_homepage,PageSize=12), `program`(Type=tv+radio), `special-live`, `weather-notify`, `advertisement`×N |
| 新聞列表 | `/zh-hant/news-list?type=image&category=all&date=YYYY-MM-DD` | `news`(Type=image,Slug=news_list,PageSize=40), `news/categories`, `advertisement` |
| 新聞詳情 | `/zh-hant/news-detail/{id}` | `news/{id}`(Type=all,Lang=zh-hant), `news/{id}/comment`, `news/{id}/relation`, `news`(側欄 Type=all_detail,IsVideo=false) |
| 搜尋 | `/zh-hant/search?q=KEYWORD&type=news` | SSR 渲染，`search/?Keywords=...`, `search/fitler` |
| 直播 | `/zh-hant/live?Channel=1&type=tv` | `live/categories`, `live/{id}/playlist`, `program-list/Channel` |
| 節目表 | `/zh-hant/program/all_program` | `program`(Type=all,Slug=program_list), `program/categories` |

---

## 附錄 A：本機程式碼映射

| API | 代碼位置 |
|-----|---------|
| `api_news_list()` | `.claude/skills/tdm/scripts/tdm_core.py` |
| `api_news_detail()` / `get_video_info()` | `.claude/skills/tdm/scripts/tdm_core.py` |
| `api_search()` | `.claude/skills/tdm/scripts/tdm_core.py` |
| `query_news_list()` | `.claude/skills/tdm/scripts/tdm_core.py` |
| `query_search()` | `.claude/skills/tdm/scripts/tdm_core.py` |
| `download_video()` / `trim_video()` | `.claude/skills/tdm/scripts/tdm_core.py` |
| CLI 入口 | `.claude/skills/tdm/scripts/tdm_tool.py` |
| Web 端 Flask 路由 | `app/tdm_web.py` |
| 舊版採集器 | `TDM/data_collector.py` |
| 舊版 URL 模板 | `TDM/config.py` |
| Skill 定義 | `.claude/skills/tdm/` |

## 附錄 B：變更記錄

| 日期 | 變更 |
|------|------|
| 2026-07-09 | 初始版本。Playwright 實測 6 頁面 + API 直測。Type=image/all_detail 差異、IsShowSevenDay 行為、Category 數字 ID、search API video 欄位、program/live/CMS/ad/common API 完整目錄 |
