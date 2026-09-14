# -*- coding: utf-8 -*-
"""
TDMDO Core — 共用核心模組（CLI & Web 共用）。
不依賴 argparse / Flask，只做純邏輯。

用法:
  from tdm_core import load_env, query_news_list, get_video_info,
                        download_video, trim_video, push_to_webdav,
                        init_db, get_push_log, get_db_stats,
                        get_pushed_filenames

環境變數（透過 load_env 或 .env 自動載入）:
  TDM_DOWNLOAD_DIR, TDM_DB_PATH
  WEBDAV_ENABLED, WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD, WEBDAV_PATH
"""

import concurrent.futures
import html as _html_lib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from urllib.parse import urlsplit, urlunsplit

try:
    import requests as _requests
except ImportError:
    _requests = None

# ── 推送模組（可選依賴）──
try:
    from push_manager import (
        PUSH_ENABLED, PushManager, PushResult, push_media, push_text,
    )
    PUSH_MANAGER_AVAILABLE = True
except ImportError:
    PUSH_ENABLED = False
    PushManager = None
    PushResult = None
    push_media = None
    push_text = None
    PUSH_MANAGER_AVAILABLE = False


# ═══════════════════════════════════════════════════════════
# 初始化：路徑 + .env
# ═══════════════════════════════════════════════════════════

_CORE_FILE = Path(__file__).resolve()
SKILL_DIR  = _CORE_FILE.parent.parent          # .claude/skills/tdm
_PROJECT_ROOT = SKILL_DIR.parent.parent.parent  # 專案根（4層上）


def refresh_paths():
    """根據當前環境變數重新計算並建立路徑。"""
    global DB_PATH, DOWNLOAD_DIR
    _raw_db = os.environ.get("TDM_DB_PATH", "").strip()
    if _raw_db:
        _db_p = Path(_raw_db)
        DB_PATH = _db_p if _db_p.is_absolute() else (_PROJECT_ROOT / _db_p).resolve()
    else:
        DB_PATH = (SKILL_DIR / "scripts" / "tdm_news.db").resolve()

    _raw_dl = os.environ.get("TDM_DOWNLOAD_DIR", "").strip()
    if _raw_dl:
        _dl_p = Path(_raw_dl)
        DOWNLOAD_DIR = _dl_p if _dl_p.is_absolute() else (_PROJECT_ROOT / _dl_p).resolve()
    else:
        DOWNLOAD_DIR = (SKILL_DIR / "downloads").resolve()
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def load_env(env_dir: Path = None, override: bool = False):
    """載入 .env 到 os.environ。
    優先順序：系統環境變數 > 專案根目錄 .env > Skill 目錄 .env > 當前工作目錄 .env
    override: 是否強制用檔案設定覆蓋當前 os.environ
    """
    targets = []
    if env_dir is not None:
        targets.append(Path(env_dir) / ".env")
    else:
        for candidate in [_PROJECT_ROOT / ".env", SKILL_DIR / ".env", Path.cwd() / ".env"]:
            if candidate not in targets:
                targets.append(candidate)

    loaded_keys = set()
    for env_file in targets:
        if not env_file.exists():
            continue
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if not k:
                        continue
                    if override:
                        if k not in loaded_keys:
                            os.environ[k] = v
                            loaded_keys.add(k)
                    else:
                        if k not in os.environ:
                            os.environ[k] = v
        except OSError:
            pass

    refresh_paths()


# 初始化路徑與基本常數
TDM_BASE   = "https://www.tdm.com.mo"
API_BASE   = f"{TDM_BASE}/api/v1.0"
DB_PATH = (SKILL_DIR / "scripts" / "tdm_news.db").resolve()
DOWNLOAD_DIR = (SKILL_DIR / "downloads").resolve()

# 自動按優先順序載入 .env 並解析路徑
load_env()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

ID_REGEX = re.compile(r'/(\d{6,7})(?:/|\?|$|&)')

# WebDAV 配置
_WEBDAV_ENABLED  = os.environ.get("WEBDAV_ENABLED", "").lower() in ("true", "1", "yes")
_WEBDAV_URL      = os.environ.get("WEBDAV_URL", "").rstrip("/")
_WEBDAV_USERNAME = os.environ.get("WEBDAV_USERNAME", "")
_WEBDAV_PASSWORD = os.environ.get("WEBDAV_PASSWORD", "")
_WEBDAV_PATH     = os.environ.get("WEBDAV_PATH", "/")


# ═══════════════════════════════════════════════════════════
# 輔助函數
# ═══════════════════════════════════════════════════════════

def extract_id(s: str) -> Optional[str]:
    """從 TDM URL 或純數字字串中提取 6-7 位 ID。"""
    if s.isdigit() and 6 <= len(s) <= 7:
        return s
    m = ID_REGEX.search(s)
    return m.group(1) if m else None


def safe_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", re.sub(r"\s+", "_", s))[:120]


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = _html_lib.unescape(raw)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_time(t: str) -> float:
    """解析非負的 HH:MM:SS、MM:SS 或純秒數 → float。"""
    raw = str(t).strip()
    try:
        if ":" in raw:
            parts = raw.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
                if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
                    raise ValueError
                return hours * 3600 + minutes * 60 + seconds
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), float(parts[1])
                if minutes < 0 or not 0 <= seconds < 60:
                    raise ValueError
                return minutes * 60 + seconds
        value = float(raw)
        if value < 0:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ValueError(
            f"無法解析時間: '{raw}' (需要非負的 HH:MM:SS、MM:SS 或純秒數)"
        ) from None


def fmt_time(sec: float) -> str:
    h, m = int(sec // 3600), int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}" if s == int(s) else f"{h:02d}:{m:02d}:{s:06.3f}"


def normalize_m3u8_url(url: str) -> str:
    """將 TDM 的精確 /play 端點轉成播放清單 URL，不改壞既有 playlist URL。"""
    if not url:
        return ""
    return re.sub(r"/play(?=$|[?#])", "/playelist.m3u8", url, count=1)


def fmt_cut_time(sec: float) -> str:
    """秒數 → HH-MM-SS.sss（用於裁剪檔名）。"""
    h, r = divmod(abs(sec), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}-{int(m):02d}-{s:06.3f}"


def check_cmd(cmd: str) -> bool:
    """檢查命令是否存在。"""
    try:
        parts = cmd.split()
        if not parts:
            return False
        if len(parts) == 1:
            return shutil.which(parts[0]) is not None
        if len(parts) >= 3 and parts[0] == "python" and parts[1] == "-m":
            return importlib.util.find_spec(parts[2]) is not None
        res = subprocess.run([parts[0], "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        return res.returncode == 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# TDM API 層
# ═══════════════════════════════════════════════════════════

def _api_get(url: str, params: dict = None, timeout: int = 30) -> Optional[dict]:
    try:
        resp = _requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _m3u8_candidates(url: str) -> List[str]:
    """保留原始 HLS URL，並追加 TDM API 提供的影片 CDN 後備 URL。"""
    if not url:
        return []

    candidates = [url]
    try:
        parsed = urlsplit(url)
        current_origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return candidates
        if "tdm.com.mo" not in hostname or "vod" not in hostname:
            return candidates
    except Exception:
        return candidates

    domain_response = _api_get(f"{TDM_BASE}/api/v1/common/get-domain") or {}
    domain_data = domain_response.get("data", {})
    if not isinstance(domain_data, dict):
        return candidates

    domains = domain_data.get("domains", {})
    if not isinstance(domains, dict):
        domains = {}

    origins = []

    def add_origin(origin: Any):
        if not isinstance(origin, str) or not origin.strip():
            return
        origin = origin.strip().rstrip("/")
        try:
            origin_parts = urlsplit(origin)
            origin_host = (origin_parts.hostname or "").lower()
            if origin_parts.scheme not in ("http", "https") or not origin_parts.netloc:
                return
            if "tdm.com.mo" not in origin_host or "vod" not in origin_host:
                return
        except Exception:
            return
        if origin not in origins:
            origins.append(origin)

    mapped_origin = domains.get(current_origin)
    add_origin(mapped_origin)
    add_origin(domain_data.get("videoDomain"))
    add_origin(domain_data.get("sourceVideoDomain"))
    for source_origin, target_origin in domains.items():
        add_origin(source_origin)
        add_origin(target_origin)

    for origin in origins:
        try:
            origin_parts = urlsplit(origin)
            replacement = urlunsplit((
                origin_parts.scheme,
                origin_parts.netloc,
                parsed.path,
                parsed.query,
                parsed.fragment,
            ))
        except Exception:
            continue
        if replacement not in candidates:
            candidates.append(replacement)
    return candidates


def api_news_list(page: int = 1, page_size: int = 40,
                  show_seven_day: str = "true",
                  category: str = "", date: str = "",
                  lang: str = "zh", slug: str = "news_list",
                  is_video: str = "") -> Optional[dict]:
    """取得新聞列表 — 預設參數與 TDM 官網一致。

    官網原始請求範例:
      首頁:   Type=image&IsShowSevenDay=true&Page=1&PreRecordAd=5&Slug=web_news_homepage&PageSize=12
      列表頁: Type=image&IsShowSevenDay=true&Category=&Date=2026-07-09&Page=1&PageSize=40&PreRecordAd=5&Slug=news_list
      詳情頁: Type=all_detail&IsShowSevenDay=true&IsVideo=false&Page=1&PageSize=40&Lang=zh-hant
      影片區: Type=all_detail&IsShowSevenDay=true&IsVideo=true&Page=1&PageSize=40

    Args:
        page: 頁碼
        page_size: 每頁筆數 (網站預設 40，首頁 12)
        show_seven_day: 'true'=僅7天內 (網站預設), ''=不限
        category: 分類 ID (空=全部, 27=本地, 41=要聞, 42=體育, 143=特稿)
        date: 日期 YYYY-MM-DD (空=不限)
        lang: 語言 (zh/zh-hant/pt/en)
        slug: 頁面標識 (web_news_homepage/news_list)
        is_video: ''=全部, 'true'=僅影片, 'false'=僅文字 (僅 Type=all_detail 時有效)
    """
    # 影片過濾只在 Type=all_detail 時生效，需自動切換 Type
    news_type = "all_detail" if is_video else "image"
    params = {
        "Type": news_type,
        "Page": page,
        "PageSize": page_size,
        "Lang": lang,
        "Category": category,
    }
    # IsShowSevenDay: 只在不為空時才傳（空 = 不限制天數，等同官網不傳此參數）
    if show_seven_day:
        params["IsShowSevenDay"] = show_seven_day
    if is_video:
        params["IsVideo"] = is_video
        params["SpecialId"] = ""
    else:
        params["PreRecordAd"] = "5"
        params["Slug"] = slug
    if date:
        params["Date"] = date
    return _api_get(f"{API_BASE}/news", params)


def api_news_detail(news_id: str) -> Optional[dict]:
    return _api_get(f"{API_BASE}/news/{news_id}")


def api_search_suggest(query: str) -> Optional[dict]:
    return _api_get(f"{API_BASE}/searchbar", {"query": query, "Lang": "zh"})


def api_search(query: str, stype: str = "search_news",
               page: int = 1, page_size: int = 15) -> Optional[dict]:
    """全文搜索 — 與官網 search 頁面一致。
    官網請求例: /api/v1.0/search/?Keywords=澳門&SelectType=search_news&Page=1&PageSize=15&FullSearch=true&DateSort=true
    """
    return _api_get(f"{API_BASE}/search/", {
        "Keywords": query, "SelectType": stype,
        "Page": page, "PageSize": page_size,
        "FullSearch": "true", "DateSort": "true",
    })


def extract_items(data: dict) -> List[dict]:
    """從新聞列表 API 回應中提取所有新聞項目。"""
    if not data or data.get("code") != 0:
        return []
    items = []
    for container in data.get("data", {}).get("newsList", []):
        for item in container.get("data", []):
            if isinstance(item, dict) and item.get("id"):
                items.append(item)
    return items


def extract_total(data: dict, fallback: int = 0) -> int:
    """從新聞列表 API 回應中提取總篇數（data.total）。"""
    if not data or data.get("code") != 0:
        return fallback
    return data.get("data", {}).get("total", fallback)


def check_video_batch(ids: list) -> dict:
    """並發查詢多個 ID 是否含影片。"""
    def _check(nid):
        try:
            r = _requests.get(f"{API_BASE}/news/{nid}", headers=HEADERS, timeout=10)
            d = r.json()
            v = d.get("data", {}).get("detail", {}).get("video")
            return nid, {"video": bool(v),
                         "title": d.get("data", {}).get("detail", {}).get("title", ""),
                         "date":  d.get("data", {}).get("detail", {}).get("date", ""),
                         "m3u8":  v}
        except Exception:
            return nid, {"video": False, "title": "", "date": "", "m3u8": None}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return dict(ex.map(_check, ids))


def get_video_info(news_id: str) -> Optional[dict]:
    """獲取單一新聞影片資訊（含 m3u8、縮圖、文字摘要）。"""
    data = api_news_detail(news_id)
    if not data or data.get("code") != 0:
        return None
    d = data.get("data", {}).get("detail", {})
    m3u8 = normalize_m3u8_url(d.get("video", ""))
    raw = d.get("content", "") or ""
    try:
        content_text = re.sub(r'<[^>]+>', '', _html_lib.unescape(raw)).strip()
    except Exception:
        content_text = raw
    return {
        "id": d.get("id"), "title": d.get("title", f"tdm_{news_id}"),
        "m3u8": m3u8, "m3u8_full": m3u8,
        "length": d.get("videoLength"), "date": d.get("date", ""),
        "thumbnail": d.get("videoThumb", ""), "content": content_text,
    }


# ═══════════════════════════════════════════════════════════
# 新聞查詢（結構化回傳）
# ═══════════════════════════════════════════════════════════

def query_news_list(page: int = 1, size: int = 40,
                    search: str = "", video_only: bool = False,
                    category: str = "", date_filter: str = "") -> dict:
    """回傳: {items: [...], total: int, page: int, page_size: int}

    Args:
        page: 頁碼（1-based）
        size: 每頁顯示筆數
        search: 關鍵字過濾（客戶端）
        video_only: True=僅影片 (API IsVideo=true)
        category: 分類數字 ID（空=全部, 27=本地, 41=要聞, 42=體育, 143=特稿）
        date_filter: 日期 YYYY-MM-DD — 指定日期時自動跨 API 頁掃描
                     （TDM API 只支援 IsShowSevenDay=true 才有完整結果，
                      歷史日期需跨頁收集）
    """
    is_video = "true" if video_only else ""

    if date_filter:
        # 日期模式：跨 API 頁掃描收集指定日期新聞
        # API 永遠帶 IsShowSevenDay=true 以獲取每頁最大範圍
        try:
            parts = date_filter.split("-")
            mmddyyyy = f"{parts[1]}/{parts[2]}/{parts[0]}" if len(parts) == 3 else date_filter
        except Exception:
            mmddyyyy = date_filter
        all_items = []
        for api_pg in range(1, 11):
            data = api_news_list(api_pg, 40, show_seven_day="true",
                                 is_video=is_video)
            if not data or data.get("code") != 0:
                break
            batch = extract_items(data)
            if not batch:
                break
            for it in batch:
                if (it.get("date", "") or "").startswith(mmddyyyy):
                    all_items.append(it)
            if (batch[-1].get("date", "") or "")[:10] < mmddyyyy:
                break
        if category:
            c = str(category)
            all_items = [i for i in all_items if str(i.get("category", "")) == c]
        if search:
            kw = search.lower()
            all_items = [i for i in all_items
                         if kw in i.get("title", "").lower()
                         or kw in strip_html(i.get("content", "")).lower()]
        total = len(all_items)
        offset = (page - 1) * size
        return {"items": all_items[offset:offset + size], "total": total,
                "page": page, "page_size": size}

    # 一般模式：API 端 IsVideo/Category/Date（IsShowSevenDay 預設 true）
    data = api_news_list(page, size, show_seven_day="true",
                         category=category, date=date_filter,
                         is_video=is_video)
    if not data or data.get("code") != 0:
        return {"items": [], "total": 0, "page": page, "page_size": size,
                "error": "API 無回應"}
    items = extract_items(data)
    api_total = extract_total(data, len(items))

    # 客戶端過濾（僅 API 不支援的部分 — 關鍵字）
    if search:
        kw = search.lower()
        items = [i for i in items
                 if kw in i.get("title", "").lower()
                 or kw in strip_html(i.get("content", "")).lower()]

    return {"items": items, "total": api_total, "page": page, "page_size": size}


def query_search(keywords: List[str], stype: str = "search_news",
                 limit: int = 20, video_only: bool = False) -> dict:
    """回傳: {items: [...], total: int, checked: int, range: str}

    search API 自帶 video 欄位，video_only 時直接過濾，不需批次檢查。
    """
    query = " ".join(keywords)
    data = api_search(query, stype, 1, max(limit, 40))
    if not data or data.get("code") != 0:
        return {"items": [], "total": 0, "error": "搜尋失敗"}
    raw_items = data.get("data", {}).get("items", [])
    total_count = data.get("data", {}).get("count", 0)

    if not raw_items:
        return {"items": [], "total": total_count, "checked": 0,
                "range": f"搜尋庫共 {total_count} 篇，未找到匹配"}

    # 影片過濾：直接用 search API 自帶的 video 欄位
    if video_only:
        matched = [{"id": it["id"],
                    "title": it.get("title", ""),
                    "date": it.get("date", ""),
                    "video": True}
                   for it in raw_items if it.get("video")]
    else:
        matched = raw_items

    dates = [it.get("date", "") for it in raw_items if it.get("date")]
    range_str = ""
    if len(dates) > 1:
        range_str = f"時間: {dates[-1][:10]} ~ {dates[0][:10]}"
    return {"items": matched[:limit], "total": len(matched),
            "checked": 0,
            "range": range_str or f"全文搜尋 — {total_count} 篇"}


# ═══════════════════════════════════════════════════════════
# SQLite 資料庫層
# ═══════════════════════════════════════════════════════════

def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _db_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id              INTEGER PRIMARY KEY,
            title           TEXT    NOT NULL,
            content         TEXT,
            date            TEXT,
            video_url       TEXT,
            share_url       TEXT,
            raw_json        TEXT,
            fetched         TEXT    NOT NULL,
            created         TEXT,
            push_url        TEXT,
            push_time       TEXT,
            download_method TEXT,
            download_dir    TEXT
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_news_date ON news (date)")
    for col, col_type in [("push_url", "TEXT"), ("push_time", "TEXT"),
                          ("download_method", "TEXT"), ("download_dir", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE news ADD COLUMN {col} {col_type}")
        except Exception:
            pass
    # 刪除舊版獨立推送記錄表
    c.execute("DROP TABLE IF EXISTS webdav_push_log")

    # ── videos 表：獨立於 news，追蹤所有下載/裁剪的影片 ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id         TEXT,
            title           TEXT,
            filename        TEXT NOT NULL,
            filepath        TEXT NOT NULL,
            file_size       INTEGER,
            duration_sec    REAL,
            source_type     TEXT DEFAULT 'download',
            source_filename TEXT,
            cut_start       REAL,
            cut_end         REAL,
            push_url        TEXT,
            push_time       TEXT,
            push_status     TEXT DEFAULT 'pending',
            created_at      TEXT NOT NULL
        )""")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_filename ON videos (filename)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_videos_news_id ON videos (news_id)")

    conn.commit()
    conn.close()


def record_download(news_id: str, title: str, filepath: str,
                    push_ok: bool = False, push_url: str = "",
                    duration_sec: float = 0, source_url: str = "",
                    download_method: str = "", download_dir: str = ""):
    """更新 news 表：記錄下載資訊與推送狀態。"""
    conn = _db_conn()
    fp = Path(filepath)
    now = datetime.now().isoformat()
    nid = int(news_id) if news_id and news_id.isdigit() else 0
    if nid:
        existing = conn.execute("SELECT id FROM news WHERE id = ?", (nid,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE news SET title=?, video_url=?, share_url=?, fetched=?, push_url=?, push_time=?, download_method=?, download_dir=? WHERE id=?",
                (title, source_url, "", now, push_url, now if push_ok else None, download_method, download_dir, nid))
        else:
            conn.execute(
                "INSERT INTO news (id,title,video_url,share_url,fetched,push_url,push_time,download_method,download_dir) VALUES (?,?,?,?,?,?,?,?,?)",
                (nid, title, source_url, "", now, push_url, now if push_ok else None, download_method, download_dir))
    conn.commit()
    conn.close()


def get_push_log(limit: int = 20) -> list:
    conn = _db_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT id as news_id, title, push_url, push_time as downloaded, video_url FROM news WHERE push_url IS NOT NULL AND push_url != '' ORDER BY push_time DESC LIMIT ?", (limit,))]
    conn.close()
    return rows


def get_pushed_filenames() -> set:
    """回傳已推送的檔名集合（從 news 表 push_url 推斷檔名）。"""
    try:
        if not DB_PATH.exists():
            return set()
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT push_url FROM news WHERE push_url IS NOT NULL AND push_url != ''").fetchall()
        pushed = set()
        for r in rows:
            fname = r[0].split("/")[-1] if r[0] else ""
            if fname:
                pushed.add(fname)
        conn.close()
        return pushed
    except Exception:
        return set()


def get_db_stats() -> dict:
    conn = _db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM news")
    total_news = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM news WHERE video_url IS NOT NULL AND video_url != ''")
    video_count = c.fetchone()[0]
    c.execute("SELECT MAX(date) FROM news")
    latest = c.fetchone()[0] or "N/A"
    c.execute("SELECT COUNT(*) FROM news WHERE push_url IS NOT NULL AND push_url != ''")
    push_total = c.fetchone()[0]
    conn.close()
    return {"total_news": total_news, "video_count": video_count,
            "latest_date": latest, "push_total": push_total, "push_ok": push_total}


# ── videos 表操作 ─────────────────────────────────────────

def record_video(news_id: str = "", title: str = "", filepath: str = "",
                 source_type: str = "download", source_filename: str = "",
                 cut_start: float = None, cut_end: float = None,
                 duration_sec: float = 0, download_method: str = ""):
    """寫入/更新 videos 表。若 filename 已存在則更新，否則新增。"""
    fp = Path(filepath)
    if not fp.exists():
        return
    conn = _db_conn()
    now = datetime.now().isoformat()
    file_size = fp.stat().st_size
    fname = fp.name

    existing = conn.execute("SELECT id FROM videos WHERE filename = ?", (fname,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE videos SET news_id=?, title=?, filepath=?, file_size=?, duration_sec=?,"
            " source_type=?, source_filename=?, cut_start=?, cut_end=? WHERE filename=?",
            (str(news_id) if news_id else "", title, str(fp), file_size, duration_sec,
             source_type, source_filename, cut_start, cut_end, fname))
    else:
        conn.execute(
            "INSERT INTO videos (news_id, title, filename, filepath, file_size, duration_sec,"
            " source_type, source_filename, cut_start, cut_end, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(news_id) if news_id else "", title, fname, str(fp), file_size, duration_sec,
             source_type, source_filename, cut_start, cut_end, now))
    conn.commit()
    conn.close()


def update_video_push_status(filename: str, push_ok: bool, push_url: str = ""):
    """更新 videos 表的推送狀態。"""
    conn = _db_conn()
    now = datetime.now().isoformat()
    status = "pushed" if push_ok else "failed"
    conn.execute(
        "UPDATE videos SET push_status=?, push_url=?, push_time=? WHERE filename=?",
        (status, push_url, now if push_ok else None, filename))
    conn.commit()
    conn.close()


def get_video_by_id(video_id: int):
    """根據 videos 表 ID 取得單一影片記錄。"""
    try:
        conn = _db_conn()
        r = conn.execute("SELECT * FROM videos WHERE id = ?", (int(video_id),)).fetchone()
        conn.close()
        if not r:
            return None
        d = dict(r)
        fp = Path(d.get("filepath", ""))
        if fp.exists():
            kb = fp.stat().st_size / 1024
            d["size"] = f"{kb/1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"
            d["missing"] = False
        else:
            d["size"] = "已遺失"
            d["missing"] = True
        return d
    except Exception:
        return None


def get_videos_by_news_id(news_id: str) -> list:
    """回傳某新聞的所有影片版本（原片 + 裁剪版），按 source_type 排序。"""
    conn = _db_conn()
    rows = conn.execute(
        "SELECT * FROM videos WHERE news_id = ? ORDER BY "
        "CASE source_type WHEN 'download' THEN 0 ELSE 1 END, created_at DESC",
        (str(news_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_grouped_videos() -> list:
    """回傳按 news_id 歸類的影片群組。title 優先用原片（download）的。"""
    conn = _db_conn()
    rows = conn.execute(
        "SELECT * FROM videos ORDER BY "
        "CASE WHEN news_id IS NULL OR news_id = '' THEN 1 ELSE 0 END, "
        "CASE source_type WHEN 'download' THEN 0 ELSE 1 END, "
        "created_at DESC").fetchall()
    conn.close()

    groups = {}
    ungrouped = []
    # 先從 news 表拿真正的標題
    news_titles = {}
    try:
        conn2 = _db_conn()
        nr = conn2.execute("SELECT id, title FROM news WHERE title IS NOT NULL AND title != ''").fetchall()
        for r2 in nr:
            news_titles[str(r2["id"])] = r2["title"]
        conn2.close()
    except Exception:
        pass

    for r in rows:
        d = dict(r)
        fp = Path(d.get("filepath", ""))
        if fp.exists():
            kb = fp.stat().st_size / 1024
            d["size"] = f"{kb/1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"
            d["bytes"] = fp.stat().st_size
            d["missing"] = False
        else:
            d["size"] = "已遺失"
            d["bytes"] = d.get("file_size", 0)
            d["missing"] = True

        nid = d.get("news_id", "").strip()
        if nid:
            if nid not in groups:
                # 優先用 news 表的標題
                clean_title = news_titles.get(nid, "")
                if not clean_title:
                    # fallback: 從原片 filename 去掉 news_id 前綴
                    raw = d.get("title", "")
                    clean_title = re.sub(r'^\d{6,7}_', '', raw) if raw else ""
                groups[nid] = {"news_id": nid, "title": clean_title or d.get("title", ""), "videos": []}
            groups[nid]["videos"].append(d)
        else:
            ungrouped.append(d)

    result = sorted(groups.values(), key=lambda g: g["videos"][0].get("created_at", ""), reverse=True)
    if ungrouped:
        result.append({"news_id": None, "title": "未歸類", "videos": ungrouped})
    return result


def upsert_news(item: dict):
    """寫入/更新新聞。會先調 detail API 拿完整資料（m3u8、content、raw_json）。"""
    conn = _db_conn()
    now = datetime.now().isoformat()
    nid = str(item.get("id", ""))
    if not nid or not nid.isdigit():
        conn.close()
        return

    nid_int = int(nid)
    existing = conn.execute("SELECT id FROM news WHERE id = ?", (nid_int,)).fetchone()

    # 拿完整 detail（含 m3u8、content）
    detail_data = api_news_detail(nid)
    detail = (detail_data or {}).get("data", {}).get("detail", {})
    m3u8 = normalize_m3u8_url(detail.get("video", "") or "")
    content_html = detail.get("content", "") or ""
    content_text = strip_html(content_html)
    share_url = detail.get("shareUrl", "") or item.get("shareUrl", "") or ""

    title = detail.get("title") or item.get("title", "")
    date = detail.get("date") or item.get("date", "")
    raw_json = json.dumps(detail_data, ensure_ascii=False) if detail_data else json.dumps(item, ensure_ascii=False)

    try:
        if existing:
            conn.execute(
                "UPDATE news SET title=?, content=?, date=?, video_url=?, share_url=?, raw_json=?, fetched=? WHERE id=?",
                (title, content_text, date, m3u8, share_url, raw_json, now, nid_int))
        else:
            conn.execute(
                "INSERT INTO news (id,title,content,date,video_url,share_url,raw_json,fetched,created) VALUES (?,?,?,?,?,?,?,?,?)",
                (nid_int, title, content_text, date, m3u8, share_url, raw_json, now, item.get("createdAt", "")))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def sync_latest_news(force_update: bool = False, pages: int = 3,
                     all_days: bool = False) -> int:
    """增量同步最新新聞到本地 DB（預設只新增，--force 更新全部）。

    Args:
        force_update: 強制更新既有新聞的 detail 資料
        pages: 同步頁數 (每頁 40 篇)
        all_days: True=不限天數
    回傳新增/更新篇數。"""
    show_seven_day = "" if all_days else "true"
    count = 0
    for pg in range(1, pages + 1):
        data = api_news_list(pg, 40, show_seven_day=show_seven_day)
        items = extract_items(data)
        if not items:
            break
        for item in items:
            nid = item.get("id")
            if not nid:
                continue
            if force_update:
                upsert_news(item)
                count += 1
            else:
                conn = _db_conn()
                if not conn.execute("SELECT id FROM news WHERE id = ?", (int(nid),)).fetchone():
                    conn.close()
                    upsert_news(item)
                    count += 1
                else:
                    conn.close()
    return count


# ═══════════════════════════════════════════════════════════
# ffmpeg / 下載引擎
# ═══════════════════════════════════════════════════════════

_HAS_YTDLP = check_cmd("yt-dlp") or check_cmd("python -m yt_dlp")
_HAS_FFMPEG = check_cmd("ffmpeg")


def _get_ytdlp_cmd() -> List[str]:
    if check_cmd("yt-dlp"):
        return ["yt-dlp"]
    return ["python", "-m", "yt_dlp"]


def _new_download_temp_path(output: str) -> Path:
    """建立同目錄的唯一暫存輸出路徑，避免失敗檔案污染正式檔名。"""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{output_path.stem}.tdm-",
        suffix=output_path.suffix or ".mp4",
        dir=str(output_path.parent),
    )
    os.close(fd)
    Path(temp_path).unlink(missing_ok=True)
    return Path(temp_path)


def _remove_file(path: Path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _download_m3u8_with_fallback(
    m3u8: str,
    output: str,
    cut_start: float = None,
    cut_dur: float = None,
    progress_callback: Callable = None,
) -> bool:
    """依序嘗試 TDM CDN，成功後才將暫存檔移到正式輸出路徑。"""
    candidates = _m3u8_candidates(m3u8)
    total = len(candidates)
    for index, candidate in enumerate(candidates, 1):
        temp_output = _new_download_temp_path(output)
        try:
            if progress_callback and total > 1:
                progress_callback(
                    "TDM CDN",
                    -1,
                    f"嘗試後備來源 {index}/{total}: {candidate}",
                )

            success = False
            if _HAS_YTDLP and cut_start is None and cut_dur is None:
                yt_cmd = _get_ytdlp_cmd() + [
                    "--no-playlist", "-o", str(temp_output), candidate
                ]
                if progress_callback:
                    progress_callback("📦 yt-dlp", 5, "$ " + " ".join(yt_cmd))
                success = _run_ytdlp(yt_cmd, progress_callback)

            if not success:
                _remove_file(temp_output)
                ff_cmd = [
                    "ffmpeg", "-y",
                    "-rw_timeout", "30000000",
                    "-http_persistent", "0",
                    "-reconnect", "1",
                    "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5",
                ]
                if cut_start is not None:
                    ff_cmd += ["-ss", str(cut_start)]
                ff_cmd += ["-i", candidate]
                if cut_dur is not None:
                    ff_cmd += ["-t", str(cut_dur)]
                ff_cmd.append(str(temp_output))
                if progress_callback:
                    progress_callback("🎬 ffmpeg", 25, "$ " + " ".join(ff_cmd))
                success = _run_ffmpeg(ff_cmd, progress_callback)

            if success and temp_output.exists() and temp_output.stat().st_size > 0:
                os.replace(str(temp_output), output)
                return True
        finally:
            _remove_file(temp_output)
    return False


def _run_ffmpeg(cmd: List[str], progress_callback: Callable = None) -> bool:
    """執行 ffmpeg，每行輸出即時回調 callback(status: str, pct: int, line: str)。"""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, encoding="utf-8", errors="ignore")
        total_dur = 0
        drx = re.compile(r"Duration: (\d+):(\d+):(\d+)\.\d+")
        prx = re.compile(r"time=(\d+):(\d+):(\d+)\.\d+")
        for line in iter(proc.stdout.readline, ''):
            line = line.rstrip('\n').rstrip('\r')
            if not line:
                continue
            if not total_dur:
                m = drx.search(line)
                if m:
                    total_dur = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
            m = prx.search(line)
            if m and total_dur > 0:
                cur = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
                pct = min(99, 25 + int(cur / total_dur * 74))
                if progress_callback:
                    progress_callback("🎬 ffmpeg", pct, line)
            elif progress_callback and line:
                progress_callback("🎬 ffmpeg", -1, line)
        proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def _run_ytdlp(cmd: List[str], progress_callback: Callable = None) -> bool:
    """執行 yt-dlp，每行輸出即時回調 callback(status: str, pct: int, line: str)。"""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, encoding="utf-8", errors="ignore")
        pctx = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
        for line in iter(proc.stdout.readline, ''):
            line = line.rstrip('\n').rstrip('\r')
            if not line:
                continue
            m = pctx.search(line)
            if m:
                pct = min(95, 20 + int(float(m.group(1))) * 0.75)
                if progress_callback:
                    progress_callback("📦 yt-dlp", pct, line)
            elif progress_callback:
                progress_callback("📦 yt-dlp", -1, line)
        proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def download_video(news_id: str = None, url: str = "",
                   cut_start: float = None, cut_dur: float = None,
                   output_dir: Path = None, output: str = None,
                   overwrite: bool = False,
                   download_method: str = "",
                   push_enabled: bool = False,
                   push_targets: str = None,
                   progress_callback: Callable = None) -> dict:
    """下載影片（TDM 或任意 URL），可選裁剪、可選推送。

    download_method: 'cli' | 'web' (標記下載來源)
    push_enabled: 下載完成後是否推送
    push_targets: 推送通道（逗號分隔），預設用 PUSH_DEFAULT_TARGET
    progress_callback(status: str, pct: int, log_line: str)

    回傳:
      {ok, title, news_id, filepath, filename, size_mb, duration_sec, push_ok, push_results, error}
    """
    if not _HAS_FFMPEG and not _HAS_YTDLP:
        return {"ok": False, "error": "需要 ffmpeg 或 yt-dlp"}

    out_dir = output_dir or DOWNLOAD_DIR
    vid = news_id or extract_id(url)
    m3u8 = None
    title = "video"
    length_sec = 0.0

    # ── TDM：透過 API 取得 m3u8 ──
    if vid and ("tdm.com.mo" in url or news_id):
        info = get_video_info(vid)
        if info:
            title = info["title"]
            m3u8 = info["m3u8"]
            length_sec = float(info.get("length") or 0)
            if not m3u8:
                return {"ok": False, "error": f"此新聞不含影片: {title}"}
            if progress_callback:
                progress_callback(f"TDM 影片: {title} ({length_sec}s)", 10, "")

    safe = safe_filename(title)
    out = output or str(out_dir / f"{vid or 'video'}_{safe}.mp4")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    # 已存在檢查
    if Path(out).exists() and not overwrite:
        size_mb = Path(out).stat().st_size / (1024 * 1024)
        return {"ok": True, "title": title, "news_id": vid or "",
                "filepath": out, "filename": Path(out).name,
                "size_mb": round(size_mb, 1), "duration_sec": length_sec,
                "push_ok": False, "skipped": True}

    # ── 下載 ──
    success = False

    if m3u8:
        success = _download_m3u8_with_fallback(
            m3u8,
            out,
            cut_start=cut_start,
            cut_dur=cut_dur,
            progress_callback=progress_callback,
        )

    if not success and url and not m3u8 and _HAS_YTDLP:
        yt_cmd = _get_ytdlp_cmd() + ["--no-playlist", "-o", out, url]
        if progress_callback:
            progress_callback("📦 yt-dlp", 5, "$ " + " ".join(yt_cmd))
        success = _run_ytdlp(yt_cmd, progress_callback)

    if not success and url and not m3u8 and _HAS_FFMPEG:
        ff_cmd = ["ffmpeg", "-y", "-i", url, out]
        if progress_callback:
            progress_callback("🎬 ffmpeg", 20, "$ " + " ".join(ff_cmd))
        success = _run_ffmpeg(ff_cmd, progress_callback)

    if not (success and Path(out).exists()):
        return {"ok": False, "error": "下載失敗"}

    size_mb = Path(out).stat().st_size / (1024 * 1024)
    if progress_callback:
        progress_callback("下載完成", 100, f"{Path(out).name} ({size_mb:.1f} MB)")

    # WebDAV 推送 + DB 記錄
    webdav_ok = push_to_webdav(out, title)
    dav_url = f"{_WEBDAV_URL}/dav/{_WEBDAV_PATH.strip('/')}/{Path(out).name}" if _WEBDAV_ENABLED and webdav_ok else ""
    init_db()
    # 舊 news 表記錄（向後兼容）
    record_download(news_id=vid or "0", title=title, filepath=out,
                    push_ok=webdav_ok, push_url=dav_url,
                    duration_sec=length_sec,
                    source_url=url or f"https://www.tdm.com.mo/zh-hant/news-detail/{vid}",
                    download_method=download_method,
                    download_dir=str(Path(out).parent))
    # 新 videos 表記錄
    record_video(news_id=vid or "", title=title, filepath=out,
                 source_type="download", duration_sec=length_sec,
                 download_method=download_method)
    if webdav_ok:
        update_video_push_status(Path(out).name, True, dav_url)

    # 通用推送（Telegram 等）
    push_results = {}
    tg_ok = False
    if push_enabled and PUSH_MANAGER_AVAILABLE and PUSH_ENABLED:
        if progress_callback:
            progress_callback("📤 推送", 98, "正在推送到 Telegram...")
        push_results = push_to_channels(out, title or Path(out).stem, push_targets)
        tg_ok = any(r.get("success") for r in push_results.values())

    return {"ok": True, "title": title, "news_id": vid or "",
            "filepath": out, "filename": Path(out).name,
            "size_mb": round(size_mb, 1), "duration_sec": length_sec,
            "push_ok": webdav_ok or tg_ok,
            "push_results": push_results}


# ═══════════════════════════════════════════════════════════
# 裁剪引擎
# ═══════════════════════════════════════════════════════════

def trim_video(input_path: str, start: str,
               end: str = None, duration: str = None,
               output: str = None,
               output_dir: Path = None,
               push_enabled: bool = None,
               news_id: str = None) -> dict:
    """裁剪影片。輸出到 output_dir（預設 DOWNLOAD_DIR），自動入庫 + 推送 WebDAV。

    回傳 {ok, filepath, filename, push_ok, error}。
    """
    if not _HAS_FFMPEG:
        return {"ok": False, "error": "需要 ffmpeg"}

    inp = Path(input_path)
    if not inp.exists():
        return {"ok": False, "error": f"找不到檔案: {input_path}"}

    ss = parse_time(start)
    if end:
        dur = parse_time(end) - ss
    elif duration:
        dur = parse_time(duration)
    else:
        return {"ok": False, "error": "需要 --end 或 --duration"}

    if dur <= 0:
        return {"ok": False, "error": "持續時間必須 > 0"}

    out_dir = output_dir or DOWNLOAD_DIR
    os.makedirs(str(out_dir), exist_ok=True)

    end_sec = ss + dur
    cs = fmt_cut_time(ss)
    ce = fmt_cut_time(end_sec)
    base = re.sub(r'(_cut_.*|_trimmed)$', '', inp.stem)
    out = output or str(out_dir / f"{base}_cut_{cs}_{ce}{inp.suffix}")

    cmd = ["ffmpeg", "-y", "-ss", str(ss), "-i", str(inp),
           "-t", str(dur), "-avoid_negative_ts", "make_zero", out]
    if _run_ffmpeg(cmd):
        pass  # 成功
    else:
        # fallback: 重新編碼
        cmd2 = ["ffmpeg", "-y", "-ss", str(ss), "-i", str(inp), "-t", str(dur), out]
        if _run_ffmpeg(cmd2):
            pass
        else:
            return {"ok": False, "error": "裁剪失敗"}

    # ── 裁剪成功：入庫 + 推送 ──
    push_ok = False

    # 入庫（全新資料庫首次裁剪時也必須先建立 videos 表）
    init_db()
    record_video(
        news_id=news_id or "",
        title=Path(out).stem,
        filepath=out,
        source_type="cut",
        source_filename=inp.name,
        cut_start=ss,
        cut_end=end_sec,
        duration_sec=dur,
    )

    # WebDAV 推送（預設啟用）
    should_push = push_enabled if push_enabled is not None else _WEBDAV_ENABLED
    if should_push:
        push_ok = push_to_webdav(out, Path(out).stem)
        update_video_push_status(Path(out).name, push_ok,
                                 f"{_WEBDAV_URL}/dav/{_WEBDAV_PATH.strip('/')}/{Path(out).name}" if push_ok else "")

    return {"ok": True, "filepath": out, "filename": Path(out).name,
            "push_ok": push_ok}


# ═══════════════════════════════════════════════════════════
# WebDAV 推送
# ═══════════════════════════════════════════════════════════

def push_to_webdav(filepath: str, title: str = "") -> bool:
    """透過 WebDAV PUT 推送檔案。回傳 True/False。"""
    if not _WEBDAV_ENABLED:
        return False
    if not all([_WEBDAV_URL, _WEBDAV_USERNAME, _WEBDAV_PASSWORD]):
        return False

    fp = Path(filepath)
    if not fp.exists():
        return False

    dav_path = _WEBDAV_PATH.strip("/")
    dav_url = f"{_WEBDAV_URL}/dav/{dav_path}/{fp.name}" if dav_path else f"{_WEBDAV_URL}/dav/{fp.name}"

    try:
        # 先檢查遠端是否已存在，存在則跳過（仍視為成功）
        head_resp = _requests.head(dav_url, auth=(_WEBDAV_USERNAME, _WEBDAV_PASSWORD), timeout=15)
        if head_resp.status_code == 200:
            return True  # 遠端已存在，無需重複推送

        with open(fp, "rb") as f:
            resp = _requests.put(dav_url, auth=(_WEBDAV_USERNAME, _WEBDAV_PASSWORD),
                                data=f, timeout=300)
        return resp.status_code in (200, 201, 204)
    except Exception:
        return False


def is_webdav_configured() -> bool:
    """檢查 WebDAV 配置是否完整。"""
    return _WEBDAV_ENABLED and all([_WEBDAV_URL, _WEBDAV_USERNAME, _WEBDAV_PASSWORD])


# ═══════════════════════════════════════════════════════════
# 通用推送模組整合（Telegram / 未來可擴展）
# ═══════════════════════════════════════════════════════════

def push_to_channels(filepath: str = "", caption: str = "",
                     targets: str = None) -> Dict[str, dict]:
    """透過 PushManager 推送媒體或文字到指定通道。

    Args:
        filepath: 要推送的檔案路徑（純文字時可為空字串）
        caption: 媒體說明文字 / 或純文字內容（當 filepath 為空時）
        targets: 通道逗號分隔字串（預設用 PUSH_DEFAULT_TARGET）

    Returns:
        {channel_name: {"success": bool, "message": str, "error": str}}
    """
    if not PUSH_MANAGER_AVAILABLE:
        return {"_": {"success": False, "error": "push_manager.py 不可用"}}
    if not PUSH_ENABLED:
        return {"_": {"success": False, "error": "推送功能未啟用 (PUSH_ENABLED=false)"}}

    # 純文字推送（無檔案）
    if not filepath or not Path(filepath).exists():
        results = push_text(caption, targets) if push_text else {}
    else:
        results = push_media(filepath, caption, targets)
    return {
        name: {"success": r.success, "message": r.message, "error": r.error}
        for name, r in results.items()
    }


def is_push_available() -> bool:
    """檢查推送模組是否可用且至少有一個通道已配置。"""
    if not PUSH_MANAGER_AVAILABLE or not PUSH_ENABLED:
        return False
    try:
        mgr = PushManager()
        return mgr.available
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# 檔案列表（共用）
# ═══════════════════════════════════════════════════════════

def list_videos(limit: int = 30) -> list:
    """列出已下載的影片（從 DB + 檔案系統合併），附推送狀態與裁剪來源。"""
    # 先從 videos 表讀取
    db_videos = {}
    try:
        if DB_PATH.exists():
            conn = _db_conn()
            rows = conn.execute(
                "SELECT * FROM videos ORDER BY created_at DESC LIMIT ?",
                (limit * 2,)).fetchall()
            for r in rows:
                d = dict(r)
                db_videos[d["filename"]] = d
            conn.close()
    except Exception:
        pass

    # 從檔案系統掃描補齊（DB 不存在的舊檔案）
    result = []
    seen = set()
    for p in sorted(DOWNLOAD_DIR.glob("*.mp4"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name in seen:
            continue
        seen.add(p.name)

        db_rec = db_videos.get(p.name)
        kb = p.stat().st_size / 1024

        item = {
            "name": p.name,
            "size": f"{kb/1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB",
            "bytes": p.stat().st_size,
            "path": str(p),
            "pushed": db_rec["push_status"] == "pushed" if db_rec else False,
            "push_status": db_rec["push_status"] if db_rec else "unknown",
            "source_type": db_rec["source_type"] if db_rec else "unknown",
            "source_filename": db_rec.get("source_filename") if db_rec else None,
            "cut_start": db_rec.get("cut_start") if db_rec else None,
            "cut_end": db_rec.get("cut_end") if db_rec else None,
            "news_id": db_rec.get("news_id") if db_rec else None,
            "push_url": db_rec.get("push_url") if db_rec else None,
            "created_at": db_rec.get("created_at") if db_rec else None,
        }
        result.append(item)

    # 補上 DB 有但檔案已刪除的記錄（標記為遺失）
    for fname, db_rec in db_videos.items():
        if fname not in seen:
            item = {
                "name": fname,
                "size": "已遺失",
                "bytes": db_rec.get("file_size", 0),
                "path": db_rec.get("filepath", ""),
                "pushed": db_rec["push_status"] == "pushed",
                "push_status": db_rec["push_status"],
                "source_type": db_rec["source_type"],
                "source_filename": db_rec.get("source_filename"),
                "cut_start": db_rec.get("cut_start"),
                "cut_end": db_rec.get("cut_end"),
                "news_id": db_rec.get("news_id"),
                "push_url": db_rec.get("push_url"),
                "created_at": db_rec.get("created_at"),
                "missing": True,
            }
            result.append(item)

    return result[:limit]
