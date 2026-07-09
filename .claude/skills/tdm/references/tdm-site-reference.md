# 澳廣視 (TDM) 網站架構與 API 詳解

> 更新：2026-07-07（新增 API 架構）

## API 總覽

TDM 提供公開 RESTful API，**無需登入、無需 Cookie、無需 JS 渲染**。

### 核心 API 端點

| 端點 | URL | 方法 | 說明 |
|---|---|---|---|
| 新聞列表 | `api/v1.0/news?Page=1&PageSize=40&Lang=zh` | GET | 分頁新聞資料，含 JSON |
| 新聞詳情 | `api/v1.0/news/{id}` | GET | 含 `data.detail.video` = m3u8 |
| 搜尋建議 | `api/v1.0/searchbar?query=關鍵字&Lang=zh` | GET | 搜尋自動完成 |
| 全文搜索 | `api/v1.0/news?query=關鍵字&Lang=zh` | GET | API 全文檢索 |

### 新聞詳情 API 回應格式

```json
GET /api/v1.0/news/1217791
{
  "code": 200,
  "data": {
    "detail": {
      "id": 1217791,
      "title": "世界盃16強：葡萄牙 0-1 西班牙",
      "content": "<p>...</p>",
      "date": "07/07/2026 08:02:00",
      "video": "https://vod3.tdm.com.mo/newweb/_definist_/mp4:news_cn_20260707/20260707_372.mp4/playelist.m3u8",
      "videoLength": 117.0,
      "videoThumb": "https://...",
      "shareUrl": "https://www.tdm.com.mo/zh-hant/sharelink/news/1217791",
      "category": "..."
    }
  }
}
```

**關鍵欄位**：
- `data.detail.video` — 直接的 m3u8 下載連結，可直接傳給 ffmpeg
- `data.detail.videoLength` — 影片長度（秒）
- `data.detail.content` — HTML 格式的內文

### 新聞列表 API 回應格式

```json
GET /api/v1.0/news?Page=1&PageSize=10&Lang=zh
{
  "code": 200,
  "data": {
    "totalCount": 12345,
    "newsList": [
      {
        "type": "news",
        "data": [
          {
            "id": 1217791,
            "title": "...",
            "content": "<p>...</p>",
            "date": "07/07/2026 08:02:00",
            "createdAt": "2026-07-07T08:02:00",
            "video": "https://vod3.tdm.com.mo/...m3u8",
            "shareUrl": "https://...",
            "thumbnail": "https://..."
          }
        ]
      }
    ]
  }
}
```

## 頁面 URL 結構對照

| 頁面 | URL 模式 | 可提取 ID? |
|---|---|---|
| 新聞詳情 | `/zh-hant/news-detail/{id}?isvideo=true&...` | ✅ 6-7 位數字 |
| 節目播放 | `/zh-hant/video/program-playlist/{id}` | ✅ |
| 節目詳情 | `/zh-hant/video/program-detail/{id}` | ✅ |
| 新聞列表 | `/zh-hant/news-list?type=image&category=all&page=1&date=YYYY-MM-DD` | ❌ 需從 API 取得 |
| 直播 | `/zh-hant/live` | ❌ |
| 搜尋 | `/zh-hant/search` | ❌ (前端 JS) |

## ID 提取規則

TDM 使用 6-7 位數字 ID，可從以下 URL 模式提取：

- `https://www.tdm.com.mo/zh-hant/news-detail/1217791?isvideo=true` → `1217791`
- `https://www.tdm.com.mo/zh-hant/video/program-playlist/568509` → `568509`
- `https://www.tdm.com.mo/zh-hant/video/program-detail/850015` → `850015`

Regex: `/(\d{6,7})(?:/|\?|$|&)`

## 影片 CDN 域名

TDM 影片使用多個 CDN 域名：
- `vod1.tdm.com.mo` ~ `vod5.tdm.com.mo`
- `cdn1.tdm.com.mo` / `cdn2.tdm.com.mo`

所有影片皆為 HLS (m3u8) 格式，h264/AAC 編碼，最高 720p。

## 搜尋

TDM 支援兩種搜尋模式：

1. **API 全文搜尋**：`api/v1.0/news?query=關鍵字`
2. **搜尋建議 API**：`api/v1.0/searchbar?query=關鍵字`
3. **本機搜尋**：取得多頁新聞 → 本地關鍵字匹配（參考 TDM/ content_matcher.py）

## 語言切換

| 語言 | 路徑前綴 |
|---|---|
| 繁體中文 | `/zh-hant/` |
| 簡體中文 | `/zh-cn/` |
| 葡萄牙文 | `/pt/` |
| 英文 | `/en/` |

## 新聞分類

首頁新聞區塊切換：電台新聞 / 電視新聞 / 微視頻

分類選單：全部 / 本地 / 要聞 / 體育 / 特稿

## 參考專案

本機已 clone 參考專案 `TDM/`，包含：
- 完整 SQLite 新聞資料庫 + 增量採集
- 關鍵字匹配 + 通知系統
- 影片下載/裁剪 CLI
- Telegram/微信/青龍面板整合
