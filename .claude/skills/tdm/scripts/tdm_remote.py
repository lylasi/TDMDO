# -*- coding: utf-8 -*-
"""
TDMDO Remote Client — 遠端 CLI 客戶端。

當設定 TDM_SERVER，tdm_tool.py 會將命令轉成遠端 HTTP API 請求。
所有請求都驗證 HTTP 狀態、JSON 格式及 API error 欄位。
"""

import json
import math
import os
import sys
import time
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

try:
    import requests
except ImportError:
    print("遠端模式需要 requests 套件: pip install requests")
    sys.exit(1)


_DEFAULT_POLL_TIMEOUT = 600.0
_MAX_CONSECUTIVE_POLL_ERRORS = 3
_POLL_INTERVAL = 2.0
_AUTH_COOKIES_BY_SERVER: Dict[str, Dict[str, str]] = {}


class RemoteError(RuntimeError):
    """遠端請求或回應格式錯誤。"""


def _abort(message: str) -> None:
    print(f"遠端操作失敗: {message}", file=sys.stderr)
    raise SystemExit(1)


def _get_server() -> str:
    """取得並驗證 tdm_tool.py 已解析的 TDM_SERVER。"""
    server = os.environ.get("TDM_SERVER", "").strip().rstrip("/")
    if not server:
        _abort("未設定 TDM_SERVER；請設定環境變數或使用 --server")
    parsed = urlparse(server)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        _abort("TDM_SERVER 必須是有效的 HTTP(S) URL")
    return server


def is_remote() -> bool:
    """檢查是否啟用遠端模式。"""
    return bool(os.environ.get("TDM_SERVER", "").strip())


def _response_error(response) -> str:
    if response is None:
        return ""
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("error") or payload.get("message") or "").strip()


def _server_origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _login(server: str, password: str) -> Dict[str, str]:
    """登入啟用密碼保護的遠端伺服器，密碼只送往相同 origin。"""
    try:
        response = requests.post(
            f"{server}/auth", json={"password": password}, timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        raise RemoteError(f"遠端伺服器登入失敗: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RemoteError(str(payload.get("error") if isinstance(payload, dict) else "登入回應格式錯誤"))
    cookie_jar = getattr(response, "cookies", None)
    cookies = cookie_jar.get_dict() if hasattr(cookie_jar, "get_dict") else dict(cookie_jar or {})
    if not cookies:
        raise RemoteError("遠端伺服器登入成功但未返回認證 Cookie")
    _AUTH_COOKIES_BY_SERVER[server] = cookies
    return cookies


def _request_json(method: str, url: str, **kwargs) -> Dict:
    """發送 HTTP 請求並統一驗證狀態、認證、JSON 物件及 API error。"""
    response = None
    request_func = requests.get if method.upper() == "GET" else requests.post
    server = _server_origin(url)
    request_kwargs = dict(kwargs)
    cached_cookies = _AUTH_COOKIES_BY_SERVER.get(server)
    if cached_cookies:
        request_kwargs["cookies"] = cached_cookies
    try:
        response = request_func(url, **request_kwargs)
        if getattr(response, "status_code", None) == 401:
            password = os.environ.get("TDM_SERVER_PASSWORD", "")
            if not password:
                raise RemoteError(
                    "伺服器需要登入；請設定 TDM_SERVER_PASSWORD（HTTPS 環境建議使用）"
                )
            request_kwargs["cookies"] = _login(server, password)
            response = request_func(url, **request_kwargs)
        response.raise_for_status()
    except RemoteError:
        raise
    except requests.RequestException as exc:
        error_response = getattr(exc, "response", None)
        if error_response is None:
            error_response = response
        detail = _response_error(error_response)
        suffix = f": {detail}" if detail else ""
        raise RemoteError(f"HTTP 請求失敗 ({method.upper()} {url}): {exc}{suffix}") from exc

    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise RemoteError(f"伺服器回應不是有效 JSON ({method.upper()} {url})") from exc
    if not isinstance(payload, dict):
        raise RemoteError(f"伺服器 JSON 回應必須是物件 ({method.upper()} {url})")
    if payload.get("error"):
        raise RemoteError(str(payload["error"]))
    return payload


def _request_or_exit(method: str, url: str, **kwargs) -> Dict:
    try:
        return _request_json(method, url, **kwargs)
    except RemoteError as exc:
        _abort(str(exc))


def _poll_timeout() -> float:
    raw = os.environ.get("TDM_REMOTE_POLL_TIMEOUT", str(_DEFAULT_POLL_TIMEOUT)).strip()
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise RemoteError("TDM_REMOTE_POLL_TIMEOUT 必須是正數秒數") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise RemoteError("TDM_REMOTE_POLL_TIMEOUT 必須是有限且大於 0 的秒數")
    return timeout


def _parse_time_seconds(value: str) -> float:
    text = value.strip()
    try:
        if ":" not in text:
            seconds = float(text)
        else:
            parts = text.split(":")
            if len(parts) == 2:
                seconds = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            else:
                raise ValueError
    except (TypeError, ValueError) as exc:
        raise RemoteError(f"無法解析時間: {value}") from exc
    if not math.isfinite(seconds):
        raise RemoteError(f"時間必須是有限數值: {value}")
    return seconds


def _format_seconds(seconds: float) -> str:
    if seconds == int(seconds):
        return str(int(seconds))
    return f"{seconds:.3f}".rstrip("0").rstrip(".")


def _print_news_list(items: List[dict]) -> None:
    tdm_base = "https://www.tdm.com.mo"
    for index, item in enumerate(items, 1):
        video_label = "[影片]" if item.get("video") else "[純文字]"
        print(f"  {index:2d}. {video_label} {item.get('title', '無標題')}")
        print(
            f"      ID:{item.get('id')} | {item.get('date', '?')} | "
            f"{tdm_base}/zh-hant/news-detail/{item.get('id')}"
        )
        print()


def cmd_news(args) -> Optional[List[dict]]:
    """遠端查詢新聞列表。"""
    server = _get_server()
    params = {
        "page": args.page,
        "size": args.limit,
        "video_only": "1" if args.video_only else "0",
    }
    if getattr(args, "search", ""):
        params["search"] = args.search
    if getattr(args, "category", ""):
        params["category"] = args.category
    if getattr(args, "date", ""):
        params["date"] = args.date

    data = _request_or_exit("GET", f"{server}/api/news", params=params, timeout=30)
    items = data.get("items", [])
    if not isinstance(items, list):
        _abort("新聞回應的 items 格式錯誤")
    total = data.get("total", 0)
    print(f"\nTDM 新聞 (遠端 {server})")
    print(f"   第 {args.page} 頁，顯示 {len(items)} 篇，總庫 {total} 篇\n")
    _print_news_list(items)
    return items


def cmd_search(args) -> Optional[List[dict]]:
    """遠端關鍵字搜索。"""
    server = _get_server()
    keywords = args.keywords
    if not keywords:
        _abort("請提供關鍵字")

    query = " ".join(keywords)
    stype_label = {"search_news": "新聞", "search_short_video": "微視頻", "search_program": "節目"}
    video_label = " (僅影片)" if args.video_only else ""
    print(f"遠端搜索: '{query}' [{stype_label.get(args.stype, args.stype)}{video_label}] -> {server}")

    params = {
        "search": query,
        "size": args.limit,
        "stype": args.stype,
        "video_only": "1" if args.video_only else "0",
    }
    data = _request_or_exit("GET", f"{server}/api/news", params=params, timeout=30)
    items = data.get("items", [])
    if not isinstance(items, list):
        _abort("搜索回應的 items 格式錯誤")
    if not items:
        print(f"  未找到匹配（總庫 {data.get('total', 0)} 篇）")
        return []
    if data.get("range"):
        print(f"\n[{data['range']}]:\n")
    _print_news_list(items)
    return items


def cmd_download(args) -> None:
    """遠端下載影片（伺服器執行 ffmpeg）。"""
    server = _get_server()
    raw_url = args.url or ""
    video_id = args.id
    if not raw_url and video_id:
        raw_url = f"https://www.tdm.com.mo/zh-hant/news-detail/{video_id}"

    body = {
        "url": raw_url,
        "overwrite": bool(getattr(args, "overwrite", False)),
        "push": bool(getattr(args, "push", False)),
    }
    if getattr(args, "output", None):
        body["output"] = args.output
    if getattr(args, "push_target", None):
        body["push_target"] = args.push_target
    if getattr(args, "cut", None):
        cut_start, cut_duration = [part.strip() for part in args.cut.split(",", 1)]
        body["cut_start"] = cut_start
        body["cut_duration"] = cut_duration

    data = _request_or_exit("POST", f"{server}/api/download", json=body, timeout=30)
    download_id = data.get("download_id")
    if not download_id:
        _abort("下載回應缺少 download_id")

    print(f"\n下載中: {data.get('info', '')}")
    print(f"   檔案將儲存在遠端伺服器 ({server})")

    try:
        timeout = _poll_timeout()
    except RemoteError as exc:
        _abort(str(exc))
    started_at = time.monotonic()
    last_pct = -1
    consecutive_errors = 0

    try:
        while True:
            if time.monotonic() - started_at >= timeout:
                _abort(f"進度輪詢超時（{timeout:g} 秒）；伺服器端任務可能仍在執行")
            time.sleep(_POLL_INTERVAL)
            try:
                progress = _request_json(
                    "GET", f"{server}/api/progress/{download_id}", timeout=10
                )
            except RemoteError as exc:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_POLL_ERRORS:
                    _abort(
                        f"進度輪詢連續失敗 {consecutive_errors} 次: {exc}"
                    )
                continue

            consecutive_errors = 0
            try:
                pct = max(0, min(100, int(progress.get("pct", 0))))
            except (TypeError, ValueError):
                pct = 0
            if pct != last_pct:
                bar = "#" * (pct // 2)
                sys.stdout.write(f"\r    進度: [{pct:3d}%] {bar:<50}")
                sys.stdout.flush()
                last_pct = pct

            if progress.get("done"):
                sys.stdout.write("\r" + " " * 70 + "\r")
                sys.stdout.flush()
                if not progress.get("ok"):
                    _abort(str(progress.get("error") or "下載失敗（未知錯誤）"))
                filename = str(progress.get("filename") or "")
                if not filename:
                    _abort("下載完成回應缺少 filename")
                print(f"下載完成: {filename}")
                print(f"   下載連結: {server}/api/download-file/{quote(filename)}?dl=1")
                return
    except KeyboardInterrupt:
        _abort("已中斷輪詢（伺服器端任務仍可能在執行）")


def cmd_trim(args) -> None:
    """遠端裁剪影片（伺服器上的檔案）。"""
    server = _get_server()
    filename = args.input
    if args.duration:
        duration = args.duration
    else:
        duration_seconds = _parse_time_seconds(args.end) - _parse_time_seconds(args.start)
        if duration_seconds <= 0:
            _abort("trim --end 必須晚於 --start")
        duration = _format_seconds(duration_seconds)

    body = {"file": filename, "start": args.start, "duration": duration}
    if getattr(args, "output", None):
        body["output"] = args.output

    print(f"遠端裁剪: {filename} (從 {args.start}，持續 {duration})")
    data = _request_or_exit("POST", f"{server}/api/trim", json=body, timeout=300)
    if not data.get("ok"):
        _abort(str(data.get("error") or "裁剪失敗（未知錯誤）"))
    output_name = str(data.get("filename") or "")
    if not output_name:
        _abort("裁剪完成回應缺少 filename")
    print(f"裁剪完成: {output_name}")
    print(f"   下載連結: {server}/api/download-file/{quote(output_name)}?dl=1")


def cmd_push(args) -> None:
    """遠端推送（觸發伺服器端推送）。"""
    server = _get_server()
    target = getattr(args, "target", None)

    if args.text:
        body = {"text": args.text}
        if target:
            body["target"] = target
        data = _request_or_exit("POST", f"{server}/api/push-text", json=body, timeout=30)
        if not data.get("ok"):
            _abort(str(data.get("error") or "文字推送失敗（未知錯誤）"))
        print(f"文字已推送: {data.get('detail', '')}")
        return

    filepath = args.video or args.image or args.file
    if not filepath:
        _abort("請指定 --video / --image / --file（遠端模式下需為伺服器上的檔名）")

    filename = filepath.replace("\\", "/").split("/")[-1]
    body = {"filename": filename, "caption": getattr(args, "caption", "") or ""}
    if target:
        body["target"] = target
    data = _request_or_exit("POST", f"{server}/api/push-to-tg", json=body, timeout=60)
    if not data.get("ok"):
        _abort(str(data.get("error") or "媒體推送失敗（未知錯誤）"))
    print(f"推送成功: {data.get('detail', data.get('filename', ''))}")


def cmd_db_stats() -> None:
    """遠端查看資料庫統計。"""
    server = _get_server()
    stats = _request_or_exit("GET", f"{server}/api/db-stats", timeout=10)
    print(f"遠端資料庫統計 ({server}):")
    print(f"  總新聞數: {stats.get('total_news', '?')}")
    print(f"  含影片:   {stats.get('video_count', '?')}")
    print(f"  最新日期: {stats.get('latest_date', '?')}")
    print(f"  推送記錄: {stats.get('push_total', '?')} (已推送: {stats.get('push_ok', '?')})")
    print(f"  資料庫路徑: {stats.get('db_path', '?')}")


def cmd_db_sync(args) -> None:
    """遠端觸發資料庫同步。"""
    server = _get_server()
    body = {
        "force": bool(getattr(args, "force", False)),
        "pages": getattr(args, "pages", 3),
        "all_days": bool(getattr(args, "all_days", False)),
    }
    print(f"觸發遠端同步 ({server})...")
    data = _request_or_exit("POST", f"{server}/api/db-sync", json=body, timeout=120)
    if not data.get("ok"):
        _abort(str(data.get("error") or "同步失敗（未知錯誤）"))
    print(f"同步完成: 新增/更新 {data.get('count', 0)} 篇新聞")


def cmd_push_log(args) -> None:
    """遠端查看推送記錄。"""
    server = _get_server()
    limit = getattr(args, "limit", 10)
    data = _request_or_exit(
        "GET", f"{server}/api/push-log", params={"limit": limit}, timeout=10
    )
    rows = data.get("rows", [])
    if not isinstance(rows, list):
        _abort("推送記錄回應的 rows 格式錯誤")
    if not rows:
        print("尚無推送記錄")
        return

    print(f"\n遠端推送記錄 (最近 {len(rows)} 筆) [{server}]:\n")
    for index, row in enumerate(rows, 1):
        timestamp = row.get("push_time") or row.get("downloaded") or ""
        push_time = str(timestamp)[:19] if timestamp else "?"
        print(f"  {index:2d}. [已推送] {row.get('title', '')[:50]}")
        print(f"      時間: {push_time} | ID: {row.get('news_id', '')}")
        if row.get("push_url"):
            print(f"      推送: {str(row.get('push_url', ''))[:80]}")
