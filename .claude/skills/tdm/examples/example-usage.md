# TDMDO 使用範例

## 環境設定

```bash
# 安裝 Python 依賴
pip install -r .claude/skills/tdm/scripts/requirements.txt

# 確認依賴
python -c "import requests, bs4, flask; print('OK')"
yt-dlp --version
ffmpeg -version
```

## 範例 1：查看今日要聞

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --limit 5 --video-only
```

預期輸出：
```
TDM 新聞 (顯示 5/40 篇):
   1. [VIDEO] 古巴再次全國大停電近千萬人受影響
      ID:1217808 | 2026-07-06 | https://www.tdm.com.mo/zh-hant/news-detail/1217808
   2. [TEXT] 王毅倡盡早簽訂中挪自貿協定
      ID:1217799 | 2026-07-06 | https://www.tdm.com.mo/zh-hant/news-detail/1217799
  ...
```

## 範例 2：搜尋特定新聞

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --search "暴雨" --limit 10
```

## 範例 3：下載 TDM 節目影片

```bash
python .claude/skills/tdm/scripts/tdm_tool.py download \
  --url "https://www.tdm.com.mo/zh-hant/video/program-playlist/568509"
```

## 範例 4：下載並裁剪精華

```bash
# 先下載完整影片
python .claude/skills/tdm/scripts/tdm_tool.py download \
  --url "https://www.tdm.com.mo/zh-hant/video/program-playlist/568509" \
  --output full.mp4

# 裁剪 5:30 到 6:30 的片段
python .claude/skills/tdm/scripts/tdm_tool.py trim \
  --input full.mp4 \
  --start 00:05:30 \
  --duration 00:01:00 \
  --output highlight.mp4
```

## 範例 5：啟動網頁端

```bash
python app/tdm_web.py --port 8080
```

然後在瀏覽器中打開 http://127.0.0.1:8080，貼上新聞 URL 即可下載。

## 範例 6：從 YouTube 下載（澳廣視頻道）

```bash
yt-dlp "https://www.youtube.com/watch?v=ia1dS-_1Ojg"
```

## 疑難排解

### yt-dlp 下載失敗

部分網站可能需要瀏覽器 Cookie：
```bash
yt-dlp --cookies-from-browser chrome "URL"
```

### TDM API 無回應

TDM API 無需登入/Cookie，若無回應請確認網路可訪問 `https://www.tdm.com.mo`。

### ffmpeg 裁剪不精確

裁剪預設走重新編碼以確保精確到幀。若需極速無損裁剪（僅關鍵幀級別），可手動加 `-c copy`。
