# TDM (澳廣視) API 參考文檔

> **最後更新**：2026-07-12
> **調研方法**：原有 Playwright 頁面抓取與直接 API 測試，加上 2026-07-12 公開頁面、網路請求及 HLS manifest 追加驗證
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

本文所列新聞、節目、直播、搜尋、專題與微視頻等公開內容 API 無需登入、無需 Cookie、無需 JS 渲染，可直接 HTTP GET。`member/*` 等會員功能例外，可能要求登入。

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

| Lang 值 | 語言 | 已確認的 `locale` |
|---------|------|-------------------|
| `zh` / `zh-hant` | 繁體中文（依端點及頁面用法而異） | `zh_TW` |
| `pt` | 葡萄牙文 | `pt_PT` |
| `en` | 英文 | `en` |

新聞 API 已實測上述語言與 `locale` 對應；全文搜尋 `/api/v1.0/search/` 的 `Lang` 控制行為尚未確認。

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
| `IsShowSevenDay` | string | 否 | — | `true` / `false` | 抽樣中設 `true` 會回傳較多近期資料；`false` 或不傳時結果較少，但 `true` 亦不代表可取得完整歷史。 |
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

> ⚠️ 2026-07-09 抽樣中，`IsShowSevenDay=false` 或不傳時回傳數量明顯少於 `true`；此參數只能描述抽樣窗口差異，不能視為完整歷史資料開關。

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
| `item.video` | 空字串 = 無影片；非空 = API 回傳的影片播放或 HLS URL。官方 manifest 可使用 `playelist.m3u8` 拼字。 |
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

取得單篇新聞完整內容，可能同時包含影片、音訊及多張圖片。

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
      "id": 1218429,
      "title": "新聞標題",
      "content": "<p>HTML 格式完整內文</p>",
      "date": "07/09/2026 10:53:00",
      "category": 27,
      "video": "",
      "audio": "https://vod3.tdm.com.mo/newweb/_definist_/mp3:.../playelist.m3u8",
      "images": [
        {
          "file": "https://cdn2.tdm.com.mo/...",
          "title": "圖片標題或說明"
        }
      ],
      "iconIndicator": {
        "isAudio": true,
        "isImage": true,
        "isVideo": false
      },
      "videoLength": 0,
      "videoThumb": "",
      "shareUrl": "https://www.tdm.com.mo/zh-hant/sharelink/news/1218429",
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

**媒體欄位判定**：

| 欄位 | 說明 |
|------|------|
| `video` | 非空時為新聞影片 HLS URL。官方路徑可使用拼字 `playelist.m3u8`。 |
| `audio` | 非空時為新聞音訊 HLS URL；實測新聞 `1218429` 使用 TDM `vod3` 的 MP3 HLS `.../playelist.m3u8`。 |
| `images[]` | 完整圖片集合；每項至少可見 `file`（圖片 URL）與 `title`（標題或說明）。 |
| `cover` | 卡片或內容封面，不等於 `images[]` 的完整圖片集合。 |
| `iconIndicator.isAudio` | 是否含音訊。 |
| `iconIndicator.isImage` | 是否含圖片集合。 |
| `iconIndicator.isVideo` | 是否含影片。 |

同一新聞可同時包含多種媒體，不能以單一 `type` 或只檢查 `cover` 判定。實測新聞 `1218429` 同時有 `audio` 與 `images[]`，屬 mixed media。

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

#### 回應結構與分頁

```json
{
  "code": 0,
  "data": {
    "count": 126438,
    "pageCount": 8429,
    "items": []
  }
}
```

`data.count` 是符合條件的總數，`data.pageCount` 是總頁數；實際 item 欄位隨 `SelectType` 改變。

#### 四類搜尋結果差異

| `SelectType` | 已確認的結果特徵 |
|--------------|------------------|
| `search_news` | `type=news`；包含 `id/title/content/date/video/audio/cover/iconIndicator/viewCount` 等新聞欄位。 |
| `search_program` | 包含 `slug`、`video`、`audio`、`programType`、`channelType`；詳情應使用節目 slug 契約。 |
| `search_short_video` | `type=SHORTVIDEO`，item 直接回傳 `video`。 |
| `search_pressrelease` | `type=PRESSRELEASE`，包含 `cover/title/content/date/viewCount`。 |

`search_news` item 已自帶 `video`，過濾影片新聞時可直接檢查是否非空，無需逐項再請求 `/news/{id}`。但四類結果的 ID、slug 與資源契約不同，item URL 或 ID **不能一律拼成** `/news-detail/{id}`。全文搜尋的 `Lang` 控制行為尚未確認。

---

## 5. 節目

### 5.1 `GET /api/v1.0/program` — 節目列表

#### 官網實際請求

```text
# 節目入口 — 全部節目
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
| `PageSize` | `13` | 1~N（首頁 TV=6、Radio=4） |
| `Lang` | `zh` | 語言 |
| `CategoryType` | `""` | 子分類 |
| `Slug` | `program_list` | 頁面標識 |
| `PreRecordAd` | `6` | 前置廣告 |

回應使用 `header/newsList/adIds/total/currentItemCount/currentPage` 容器；節目 item 可包含 slug，後續詳情應以 slug 為主。

### 5.2 節目 slug 詳情契約

`/api/v1.0/program/{numeric_id}` **不是目前可靠的主要詳情契約**：2026-07-12 抽樣實測會回 `data: null`，對應舊頁亦可能 404。現行節目頁應使用下列 slug 端點；已以電視節目 `good_morning_macau` 與電台節目 `ChillClass_Radio` 驗證。

#### 5.2.1 `GET /api/v1.0/program/{slug}/details` — 節目主檔

```text
GET /api/v1.0/program/good_morning_macau/details
GET /api/v1.0/program/ChillClass_Radio/details
```

| 路徑參數 | 說明 |
|----------|------|
| `slug` | 節目永久識別字；大小寫依 API 回傳值使用。 |

`data` 已確認的主要欄位：

| 欄位 | 說明 |
|------|------|
| `id` | 節目主檔 ID。 |
| `slug` | 節目 slug。 |
| `title` | 節目名稱。 |
| `cover` | 節目封面。 |
| `content` | 節目介紹，可能為 HTML。 |
| `playDesc` | 播出說明。 |
| `channels` | 所屬電視或電台頻道資訊。 |
| `programHosts` | 主持人陣列。 |
| `hasReview` | 是否有節目重溫。 |
| `isCanReview` | 目前是否允許重溫。 |
| `interVerLimit` | 國際版或地區觀看限制標記。 |
| `interVerDeadline` | 國際版觀看期限。 |
| `noLive` | 不提供直播的限制標記。 |
| `remark` | 其他備註或限制說明。 |

#### 5.2.2 `GET /api/v1.0/program/{slug}/feature` — 節目特色內容

```text
GET /api/v1.0/program/good_morning_macau/feature?slug=good_morning_macau
GET /api/v1.0/program/ChillClass_Radio/feature?slug=ChillClass_Radio
```

| 參數 | 必填 | 說明 |
|------|------|------|
| path `slug` | 是 | 節目 slug。 |
| query `slug` | 官網有傳 | 與 path slug 相同。 |

回應為該節目的 feature 資料；內容與數量依節目配置，可能為空。

#### 5.2.3 `GET /api/v1.0/program/{slug}/review` — 節目重溫

```text
GET /api/v1.0/program/good_morning_macau/review?resource=good_morning_macau&Page=1&DateDesc=true&ViewTotalDesc=false&preRecordAd=0&Date=
GET /api/v1.0/program/ChillClass_Radio/review?resource=ChillClass_Radio&Page=1&DateDesc=true&ViewTotalDesc=false&preRecordAd=0&Date=
```

| 參數 | 預設/實測值 | 說明 |
|------|-------------|------|
| path `slug` | 必填 | 節目 slug。 |
| `resource` | 同 slug | 官網請求使用的節目資源識別字。 |
| `Page` | `1` | 頁碼。 |
| `DateDesc` | `true` | 按日期遞減。 |
| `ViewTotalDesc` | `false` | 是否按觀看數遞減。 |
| `preRecordAd` | `0` | 前置廣告配置。 |
| `Date` | `""` | 日期過濾。 |

#### review 回應層級

```json
{
  "code": 0,
  "data": {
    "count": 980,
    "page": 1,
    "pageCount": 82,
    "items": [
      {
        "date": "2026-07-11",
        "shareUrl": "https://www.tdm.com.mo/zh-hant/sharelink/program/good_morning_macau?s=pc&type=all&category=video&date=2026-07-11",
        "items": [
          {
            "id": 407929,
            "images": [],
            "items": [
              {
                "id": 569716,
                "video": "https://vod3.tdm.com.mo/.../Hand20260711.mp4/playelist.m3u8",
                "radio": "",
                "cover": "https://cdn2.tdm.com.mo/...",
                "episodeId": 407929,
                "programHosts": [],
                "radioLength": 0
              }
            ]
          }
        ]
      }
    ]
  }
}
```

實際容器層級是 `data.items[]`（日期群組）→ `items[]`（集數）→ `items[]`（可播放片段）：

- 日期群組：`date`、`shareUrl`。
- 集數：`id`、`images[]`。
- 片段：`id`、`video`、`radio`、`cover`、`episodeId`、`programHosts[]`、`radioLength`。

ID 語義必須區分：

- **節目主檔 ID**：`details.id`，識別整個節目。
- **集數 ID**：第二層 `items[].id`。
- **片段 ID**：第三層 `items[].id`；其 `episodeId` 指回所屬集數。

三者不是同一 ID，不能互相替代。電台節目的同一結構會以 `radio` 提供音訊 HLS；實測 `ChillClass_Radio` 音訊 manifest 使用 `mp3:attachment/...mp3/playelist.m3u8`。

### 5.3 `GET /api/v1.0/program/categories` — 節目分類

```text
GET /api/v1.0/program/categories?Type=all
```

### 5.4 現行節目表 API（`program-list`）

#### 5.4.1 `GET /api/v1.0/program-list/Channel` — 頻道清單

```text
GET /api/v1.0/program-list/Channel?type=tv
GET /api/v1.0/program-list/Channel?type=radio
```

| 參數 | 可選值 | 說明 |
|------|--------|------|
| `type` | `tv` / `radio` | 頻道類型。 |

#### 5.4.2 `GET /api/v1.0/program-list/categories` — 節目表分類

```text
GET /api/v1.0/program-list/categories?channelId=0
```

| 參數 | 實測值 | 說明 |
|------|--------|------|
| `channelId` | `0` | `0` 表示未限定特定頻道。 |

回應提供可查日期，已確認欄位包括：

```json
{
  "day": 12,
  "week": "日",
  "title": "12/7 (星期日)",
  "date": "2026-07-12"
}
```

#### 5.4.3 `GET /api/v1.0/program-list/{date}` — 指定日期節目表

```text
# 澳視澳門 91 台
GET /api/v1.0/program-list/2026-07-12?date=2026-07-12&type=tv&channelId=1

# 澳門電台 FM100.7
GET /api/v1.0/program-list/2026-07-12?date=2026-07-12&type=radio&channelId=3
```

| 參數 | 說明 |
|------|------|
| path `date` | `YYYY-MM-DD`。 |
| query `date` | 官網同時傳入的 `YYYY-MM-DD`。 |
| `type` | `tv` 或 `radio`。 |
| `channelId` | 頻道 ID；空值表示未限定。 |

節目表 item 已確認欄位：`id`、`programmeId`、`slug`、`episodeId`、`type`、`programType`、`date`、`title`、`isLive`、`isReview`、`onlineFeed`、`isNews`、`episodeItemId`、`livePhoto`、`channelBackground`、`programLang`。

`date` 表示節目開始時間。API item **沒有原始 `end` 欄位**；結束時間可由下一節目的開始時間推導，但推導值不屬於 API 原始回應。

---

## 6. 直播

### 6.1 `GET /api/v1.0/live/categories` — 直播分類

回傳電視與電台分類及完整頻道資訊。實測電視頻道包括「澳視澳門 91台」，電台包括「澳門電台 FM100.7」。

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
        "logo": "https://cdn2.tdm.com.mo/...png",
        "title": "澳視澳門 91台",
        "intro": "<p>頻道簡介 HTML</p>",
        "onlineFeed": "https://live3.tdm.com.mo/ch1/ch1.live/playlist.m3u8",
        "liveProgramName": "目前直播節目名稱",
        "slug": "ctvp",
        "chatUUID": "聊天室識別字",
        "appKey": "聊天室應用識別字"
      }
    ]
  }
]
```

`channelInfo` 已確認欄位包括 `onlineFeed/liveProgramName/slug/chatUUID/appKey`；`onlineFeed` 是頻道目前提供的直播 HLS URL。電台樣本 `id=3`、`title=澳門電台 FM100.7`、`slug=fm1007`，串流為 `https://live3.tdm.com.mo/live/rch2a.live/playlist.m3u8`。

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

2026-07-12 公開 API 的 `channelInfo.onlineFeed` 實測以 `live3.tdm.com.mo` URL 為準，例如：

```text
https://live3.tdm.com.mo/.../playlist.m3u8
```

`/api/v1/common/get-domain` 仍可回傳 `live3` 至其他直播域名的映射；實際播放入口應優先採用當次 API 回傳的 `onlineFeed`，而不是硬編固定域名。

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

### 9.6 分享 URL

API 物件可直接回傳 `shareUrl`，已確認格式包括：

```text
# 新聞
https://www.tdm.com.mo/zh-hant/sharelink/news/1218429

# 電視節目重溫
https://www.tdm.com.mo/zh-hant/sharelink/program/good_morning_macau?s=pc&type=all&category=video&date=2026-07-11

# 電台節目重溫
https://www.tdm.com.mo/zh-hant/sharelink/program/ChillClass_Radio?s=pc&type=all&category=radio&date=2026-07-10
```

節目分享 URL 以節目 slug、媒體類型及日期定位，不應自行改拼成 numeric item URL。分享入口應優先使用各 API item 實際回傳的 `shareUrl`；分享頁 HTML 並非取得資源詳情或媒體 URL 的穩定契約。

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

### 11.1 微視頻（short-video）

#### 11.1.1 `GET /api/v1.0/short-video/category` — 微視頻分類

```text
GET /api/v1.0/short-video/category
```

已確認分類 ID：

| ID | 名稱 |
|----|------|
| `441` | 即日要聞 |
| `407` | 故事 |
| `410` | 新知 |
| `413` | 潮玩 |
| `415` | 特派員 |

#### 11.1.2 `GET /api/v1.0/short-video` — 微視頻列表

```text
GET /api/v1.0/short-video?Page=1&PageSize=3&Category=&Lang=zh
GET /api/v1.0/short-video?Page=1&PageSize=3&Category=441&Lang=zh
```

| 參數 | 預設/實測值 | 說明 |
|------|-------------|------|
| `Page` | `1` | 頁碼。 |
| `PageSize` | `3` | 每頁筆數。 |
| `Category` | `""` | 空值為全部，或傳分類 ID。 |
| `Lang` | `zh` | 語言。 |

```json
{
  "code": 0,
  "data": {
    "newsList": [],
    "total": 0,
    "currentPage": 1,
    "currentItemCount": 0
  }
}
```

`GET /api/v1.0/short-video/{id}` 抽樣回 404；獨立 detail 契約尚未確認，不能假定列表 ID 可套用該路徑。

### 11.2 專題（special）

#### 11.2.1 `GET /api/v1.0/special` — 專題列表

```text
GET /api/v1.0/special?Slug=special_site1
```

回應包含 `data.lists[]` 與 `data.total`；列表 item 已確認欄位包括 `id/title/slug/cover/banner/openVote/openComments/tags/activityStartAt/activityEndAt`。

已以專題 slug `FIFA2026` 驗證現行專題頁與下列關聯 API。

#### 11.2.2 `GET /api/v1.0/special/{slug}` — 專題主檔

```text
GET /api/v1.0/special/FIFA2026
```

| 路徑參數 | 說明 |
|----------|------|
| `slug` | 專題 slug，例如 `FIFA2026`。 |

回傳指定 slug 的專題主檔；新聞、關聯節目與節目重溫分別使用下列獨立端點。專題列表中已確認的 `id/title/slug/cover/banner/openVote/openComments/tags/activityStartAt/activityEndAt` 可用於定位及展示主檔。

#### 11.2.3 `GET /api/v1.0/special/{slug}/related-program` — 關聯節目

```text
GET /api/v1.0/special/FIFA2026/related-program
```

回傳專題關聯節目資料；節目識別與詳情仍依第 5 章的 slug 契約。

#### 11.2.4 `GET /api/v1.0/special/{slug}/program-review` — 專題節目重溫

```text
GET /api/v1.0/special/FIFA2026/program-review?Page=1&PageSize=16
```

| 參數 | 實測值 | 說明 |
|------|--------|------|
| `Page` | `1` | 頁碼。 |
| `PageSize` | `16` | 每頁筆數。 |

#### 11.2.5 `GET /api/v1.0/special/{slug}/news` — 專題新聞

```text
GET /api/v1.0/special/FIFA2026/news?id=FIFA2026&Tag=&Page=1&PageSize=16
```

| 參數 | 實測值 | 說明 |
|------|--------|------|
| `id` | 同 slug | 官網以專題 slug 傳入。 |
| `Tag` | `""` | 標籤過濾。 |
| `Page` | `1` | 頁碼。 |
| `PageSize` | `16` | 每頁筆數。 |

專題新聞 item 已確認可包含 `video`、`audio`、`images`、`tags`、`shareUrl`、`iconIndicator`；同樣應依欄位組合判定 mixed media。

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

### 13.3 官方 URL 拼字與使用原則

TDM 實際回傳的 HLS URL 可包含 `playelist.m3u8`。`playelist` 是官方現行 URL 的實際拼字，不能未經驗證自行改成 `playlist`。新聞、節目、音訊與直播均應優先使用當次 API 回傳的完整 URL；只有回應明確提供非 manifest 播放路徑時，才可依同一資源已驗證的 manifest 規則處理。

---

## 14. 已知限制與行為

| # | 限制 | 說明 |
|----|------|------|
| 1 | **`IsShowSevenDay=true` 不是歷史全量開關** | `false` 或不傳的抽樣結果較少；`true` 可取得較多近期資料，但不代表可取得全站歷史全量。 |
| 2 | **`IsVideo` 僅在 `Type=all_detail` 時生效** | `Type=image` 模式下 `IsVideo` 參數被忽略。 |
| 3 | **`Category` 是數字 ID** | 傳字串值（如 `"local"`）無效，必須傳數字（如 `"27"`）。 |
| 4 | **`Date` 參數效果有限** | `Date` 在 `Type=image` 時有一定效果，在 `Type=all_detail` 時效果不明顯。 |
| 5 | **歷史日期需要跨頁檢查** | 單頁只含部分結果，且 `IsShowSevenDay` 不能視為歷史全量保證。 |
| 6 | **`searchbar` API 已失效（404）** | TDM 網站搜尋欄目前不再使用此端點。 |
| 7 | **公開與會員端點權限不同** | 本文主要公開內容 API 無需登入；`member/*` 等會員功能仍可能要求登入。 |
| 8 | **搜尋四類契約不同** | 搜尋 item URL、ID 或 slug 不能一律當成新聞詳情；搜尋 `Lang` 控制尚未確認。 |
| 9 | **numeric program endpoint 不可靠** | `/api/v1.0/program/{numeric_id}` 實測可回 `data:null`，舊 numeric 頁亦可能 404；主要契約是 `/program/{slug}/details|feature|review`。 |
| 10 | **節目觀看受欄位限制** | `interVerLimit`、`interVerDeadline`、`noLive` 可能限制地區、期限、直播或重溫可用性。 |
| 11 | **節目表只有開始時間** | item 的 `date` 是開始時間；`end` 可由下一筆開始時間推導，但不是原始 API 欄位。 |
| 12 | **short-video detail 未確認** | `/short-video/{id}` 抽樣 404，不能宣稱存在穩定獨立詳情端點。 |
| 13 | **字幕狀態未確認** | 目前未在抽樣 API 欄位發現字幕資料，抽樣 HLS manifest 亦未見 `SUBTITLES`；僅代表抽樣未發現，不能宣稱全站沒有字幕。 |
| 14 | **官方 HLS 拼字不可任改** | `playelist.m3u8` 是已實測的官方 URL 拼字，不可自行正規化為 `playlist.m3u8`。 |
| 15 | **媒體可混合存在** | `video/audio/images[]` 可同時出現；`cover` 不等於完整圖片集合，應配合 `iconIndicator` 與各媒體欄位判定。 |
| 16 | **分頁可見資料有限** | 部分列表在較後頁面回空或受內容窗口限制，不能只憑單次分頁推定全站總可取範圍。 |

---

## 15. 頁面與 API 對照

| 頁面 | URL 模式 | 調用的現行 API |
|------|----------|----------------|
| 首頁 | `/zh-hant` | `news`（Type=image, Slug=web_news_homepage, PageSize=12）、`program`（Type=tv/radio）、`special-live`、`weather-notify`、`advertisement` |
| 新聞列表 | `/zh-hant/news-list?type=image&category=all&date=YYYY-MM-DD` | `news`（Type=image, Slug=news_list, PageSize=40）、`news/categories`、`advertisement` |
| 新聞詳情 | `/zh-hant/news-detail/{id}` | `news/{id}`、`news/{id}/comment`、`news/{id}/relation`、側欄 `news`（Type=all_detail） |
| 搜尋 | `/zh-hant/search?q=KEYWORD&type=...` | `search/?Keywords=...&SelectType=...`、`search/fitler` |
| 直播 | `/zh-hant/live?Channel={id}&type=tv|radio` | `live/categories`、`live/{id}/playlist`、`program-list/Channel` |
| 節目入口 | `/zh-hant/program/all_program` | `program`（Type=all, Slug=program_list）、`program/categories` |
| 電視節目 slug 頁 | `/zh-hant/program/playitem_video/{slug}?langarea=zh` | `program/{slug}/details`、`program/{slug}/feature`、`program/{slug}/review` |
| 電台節目 slug 頁 | 站內電台節目頁（以頁面實際 slug 為準） | `program/{slug}/details`、`program/{slug}/feature`、`program/{slug}/review` |
| 節目表 | 指定日期、類型與頻道的節目表頁 | `program-list/Channel?type=tv|radio`、`program-list/categories?channelId=0`、`program-list/{date}?date=&type=&channelId=` |
| 微視頻 | `/zh-hant/short-video`（分類可由頁面狀態指定） | `short-video/category`、`short-video?Page=&PageSize=&Category=&Lang=` |
| 專題 | `/zh-hant/special/{slug}` | `special/{slug}`、`special/{slug}/related-program`、`special/{slug}/program-review`、`special/{slug}/news` |

---

## 附錄：變更記錄

| 日期 | 變更 |
|------|------|
| 2026-07-12 | 追加公開頁面、網路請求與 HLS manifest 驗證：新聞 audio/images/iconIndicator 與 mixed media；四類搜尋差異；節目 slug details/feature/review；現行 program-list；直播 channelInfo/live3；微視頻分類與列表；FIFA2026 專題 API；分享 URL、語言 locale、字幕與各項限制。修正 numeric program 詳情、`IsShowSevenDay`、節目表 end 與 `playelist` 拼字等舊說法。 |
| 2026-07-09 | 初始版本。Playwright 實測 6 頁面 + API 直測。Type=image/all_detail 差異、IsShowSevenDay 行為、Category 數字 ID、search API video 欄位、program/live/CMS/ad/common API 完整目錄。 |
