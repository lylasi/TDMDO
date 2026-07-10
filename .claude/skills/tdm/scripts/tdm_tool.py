# -*- coding: utf-8 -*-
"""
TDMDO CLI — 澳廣視一站式新聞查詢、關鍵字搜索、影片下載、裁剪。
CLI 層：只做 argparse + 格式化輸出，核心邏輯在 tdm_core.py。

用法:
  tdm_tool.py news    [--limit 10] [--page 1] [--video-only] [--search KEYWORD]
  tdm_tool.py search  KEYWORDS...
  tdm_tool.py download  --id ID | --url URL  [--output PATH] [--cut START,END] [--push]
  tdm_tool.py trim    --input PATH --start HH:MM:SS (--end HH:MM:SS | --duration HH:MM:SS)
  tdm_tool.py push    --text TEXT | --video PATH | --image PATH | --file PATH  [--caption C]
  tdm_tool.py db      init | stats | sync
  tdm_tool.py push-log [--limit N]

遠端模式:
  set TDM_SERVER=http://192.168.1.100:8080
  tdm_tool.py --server http://192.168.1.100:8080 news --limit 10
"""

import argparse
import io
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

# ── Windows 終端 UTF-8 ───────────────────────────────────
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# ── CLI 前置驗證／環境載入 ───────────────────────────────
_SKILL_DIR = Path(__file__).resolve().parent.parent
_ID_PATTERN = re.compile(r"^\d{6,7}$")
_URL_ID_PATTERN = re.compile(r"(?<!\d)\d{6,7}(?!\d)")
_CATEGORY_MAP = {
    "all": "", "local": "27", "world": "41", "sport": "42", "feature": "143",
    "27": "27", "41": "41", "42": "42", "143": "143",
}


def _load_skill_env() -> None:
    """載入 skill/.env，保留系統環境變數的較高優先權。"""
    env_file = _SKILL_DIR / ".env"
    if not env_file.exists():
        return
    try:
        with env_file.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except OSError as exc:
        print(f"警告: 無法讀取 {env_file}: {exc}", file=sys.stderr)


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必須是正整數") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("必須是正整數")
    return number


def _date_value(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必須為有效的 YYYY-MM-DD") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise argparse.ArgumentTypeError("日期格式必須為有效的 YYYY-MM-DD")
    return value


def _time_seconds(value: str) -> float:
    text = value.strip()
    try:
        if ":" not in text:
            seconds = float(text)
        else:
            parts = text.split(":")
            if len(parts) not in (2, 3) or any(not part for part in parts):
                raise ValueError
            if len(parts) == 2:
                hours = 0
                minutes, seconds = int(parts[0]), float(parts[1])
            else:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
            if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
                raise ValueError
            seconds = hours * 3600 + minutes * 60 + seconds
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("時間格式必須為 HH:MM:SS、MM:SS 或秒數")
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("時間必須是有限且非負的數值")
    return seconds


def _time_value(value: str) -> str:
    _time_seconds(value)
    return value.strip()


def _cut_value(value: str) -> str:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError("--cut 格式必須為 START,DURATION")
    _time_seconds(parts[0])
    if _time_seconds(parts[1]) <= 0:
        raise argparse.ArgumentTypeError("--cut 的 DURATION 必須大於 0")
    return ",".join(parts)


def _news_id(value: str) -> str:
    text = value.strip()
    if not _ID_PATTERN.fullmatch(text):
        raise argparse.ArgumentTypeError("ID 必須為 6 至 7 位數字")
    return text


def _tdm_url(value: str) -> str:
    text = value.strip()
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in ("tdm.com.mo", "www.tdm.com.mo"):
        raise argparse.ArgumentTypeError("URL 必須是有效的 tdm.com.mo HTTP(S) 網址")
    if not _URL_ID_PATTERN.search(parsed.path + "?" + parsed.query):
        raise argparse.ArgumentTypeError("TDM URL 中找不到 6 至 7 位 ID")
    return text


def _server_url(value: str) -> str:
    text = value.strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise argparse.ArgumentTypeError("--server 必須是有效的 HTTP(S) URL")
    return text


def _category_value(value: str) -> str:
    key = value.strip().lower()
    if key not in _CATEGORY_MAP:
        choices = ", ".join(_CATEGORY_MAP)
        raise argparse.ArgumentTypeError(f"分類必須是以下之一: {choices}")
    return _CATEGORY_MAP[key]


def _caption_value(value: str) -> str:
    if len(value) > 1024:
        raise argparse.ArgumentTypeError("caption 不可超過 1024 字元")
    return value


# ── 導入核心模組（遠端模式時延遲導入，避免無意義的依賴檢查）──
_LOCAL_IMPORTS_DONE = False


def _local_imports():
    global _LOCAL_IMPORTS_DONE
    if _LOCAL_IMPORTS_DONE:
        return
    _LOCAL_IMPORTS_DONE = True

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    global TDM_BASE, DOWNLOAD_DIR, DB_PATH
    global extract_id, safe_filename, strip_html, parse_time, fmt_time, fmt_cut_time
    global api_news_list, api_news_detail, extract_items, check_video_batch
    global query_news_list, query_search, get_video_info
    global download_video, trim_video, push_to_webdav
    global init_db, record_download, get_push_log, get_db_stats, get_pushed_filenames
    global upsert_news, sync_latest_news, list_videos
    global push_to_channels, is_push_available

    from tdm_core import (
        TDM_BASE, DOWNLOAD_DIR, DB_PATH,
        extract_id, safe_filename, strip_html, parse_time, fmt_time, fmt_cut_time,
        api_news_list, api_news_detail, extract_items, check_video_batch,
        query_news_list, query_search, get_video_info,
        download_video, trim_video, push_to_webdav,
        init_db, record_download, get_push_log, get_db_stats, get_pushed_filenames,
        upsert_news, sync_latest_news, list_videos,
        push_to_channels, is_push_available,
    )


# ═══════════════════════════════════════════════════════════
# 命令: news
# ═══════════════════════════════════════════════════════════

def cmd_news(args):
    result = query_news_list(
        args.page, args.limit,
        search=args.search or "",
        video_only=args.video_only,
        category=args.category or "",
        date_filter=args.date or "",
    )
    if result.get("error"):
        print(f"API 錯誤: {result['error']}")
        return

    items = result["items"]
    total = result["total"]
    print(f"\nTDM 新聞 (第{args.page}頁，顯示 {len(items)} 篇，總庫 {total} 篇):\n")
    _print_news_list(items)
    return items


# ═══════════════════════════════════════════════════════════
# 命令: search
# ═══════════════════════════════════════════════════════════

def cmd_search(args):
    keywords = args.keywords
    if not keywords:
        print("請提供關鍵字")
        return
    query = " ".join(keywords)
    stype_label = {"search_news": "新聞", "search_short_video": "微視頻", "search_program": "節目"}
    vlabel = " (僅影片)" if args.video_only else ""
    print(f"搜索: '{query}' [{stype_label.get(args.stype, args.stype)}{vlabel}]")

    result = query_search(keywords, args.stype, args.limit, args.video_only)
    if result.get("error"):
        print(result["error"])
        return
    if not result["items"]:
        print(f"  未找到匹配（總庫 {result['total']} 篇）")
        return

    if result.get("range"):
        print(f"\n[{result['range']}]:\n")
    _print_news_list(result["items"])

    init_db()
    for it in result["items"][:10]:
        upsert_news(it)
    return result["items"]


def _print_news_list(items: List[dict]):
    for i, it in enumerate(items, 1):
        vid = "[VIDEO]" if it.get("video") else "[TEXT]"
        print(f"  {i:2d}. {vid} {it.get('title', '無標題')}")
        print(f"      ID:{it.get('id')} | {it.get('date', '?')} | {TDM_BASE}/zh-hant/news-detail/{it.get('id')}")
        print()


# ═══════════════════════════════════════════════════════════
# 命令: download
# ═══════════════════════════════════════════════════════════

def _dl_progress(status: str, pct: int, line: str):
    """下載進度回調（CLI 版：顯示進度條）。"""
    if pct < 0:
        return
    if pct >= 100:
        return
    bar = "#" * (pct // 2)
    sys.stdout.write(f"\r    進度: [{pct:3d}%] {bar:<50}")
    sys.stdout.flush()


def cmd_download(args):
    raw_url = args.url or ""
    vid = args.id or extract_id(raw_url)

    # 解析裁剪
    cut_start = None
    cut_dur = None
    if args.cut:
        parts = [p.strip() for p in args.cut.split(",")]
        cut_start = parse_time(parts[0])
        cut_dur = parse_time(parts[1]) if len(parts) > 1 else None

    # 先取得影片資訊（顯示標題）
    if vid:
        info = get_video_info(vid)
        if info:
            print(f"TDM 影片 ID: {vid}")
            print(f"  標題: {info['title']}")
            print(f"  日期: {info.get('date', '?')}")
            print(f"  時長: {info.get('length', '?')} 秒")
            if not info["m3u8"]:
                print(f"此新聞不含影片: {info['title']}")
                sys.exit(1)

    # 輸出路徑
    output = args.output
    if not output and vid:
        safe = safe_filename(info["title"] if info else "video")
        output = str(DOWNLOAD_DIR / f"{vid}_{safe}.mp4")

    # 已存在檢查
    if output and Path(output).exists() and not args.overwrite:
        size_mb = Path(output).stat().st_size / (1024 * 1024)
        print(f"影片已存在，跳過下載: {output} ({size_mb:.1f} MB)")
        print("使用 --overwrite 強制重新下載")
        return

    # 呼叫核心下載
    result = download_video(
        news_id=vid, url=raw_url or (f"https://www.tdm.com.mo/zh-hant/news-detail/{vid}" if vid else ""),
        cut_start=cut_start, cut_dur=cut_dur,
        output=output, overwrite=args.overwrite,
        download_method="cli",
        push_enabled=args.push,
        push_targets=args.push_target,
        progress_callback=_dl_progress,
    )

    if result.get("skipped"):
        size_mb = Path(output).stat().st_size / (1024 * 1024)
        print(f"影片已存在: {output} ({size_mb:.1f} MB)")
        return

    if not result["ok"]:
        print(f"下載失敗: {result.get('error', '未知')}")
        sys.exit(1)

    print(f"\n下載完成: {result['filepath']} ({result['size_mb']} MB)")
    if result["push_ok"]:
        print("[WebDAV] [OK] 已自動推送")
    # 顯示通用推送結果
    push_results = result.get("push_results", {})
    if push_results:
        for ch_name, pr in push_results.items():
            icon = "[OK]" if pr.get("success") else "[FAIL]"
            detail = pr.get("message") if pr.get("success") else pr.get("error", "")
            print(f"[Push/{ch_name}] {icon} {detail}")
    sys.stdout.write("\r    進度: [100%] " + "#" * 50 + "\n")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════
# 命令: trim
# ═══════════════════════════════════════════════════════════

def cmd_trim(args):
    result = trim_video(args.input, args.start, args.end, args.duration, args.output)
    if result["ok"]:
        print(f"完成: {result['filepath']}")
    else:
        print(f"失敗: {result['error']}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════
# 命令: push-log
# ═══════════════════════════════════════════════════════════

def cmd_push_log(args):
    init_db()
    rows = get_push_log(args.limit)
    if not rows:
        print("尚無推送記錄")
        return
    print(f"\nWebDAV 推送記錄 (最近 {len(rows)} 筆):\n")
    for i, r in enumerate(rows, 1):
        push_time = str(r.get("downloaded", ""))[:19] if r.get("downloaded") else "?"
        push_url = str(r.get("push_url", ""))[:80]
        print(f"  {i:2d}. [已推送] {r['title'][:50]}")
        print(f"      時間: {push_time} | ID: {r['news_id']}")
        if push_url:
            print(f"      推送: {push_url}")


# ═══════════════════════════════════════════════════════════
# 命令: push
# ═══════════════════════════════════════════════════════════

def cmd_push(args):
    """獨立推送命令：推送文字/影片/圖片/文件到 Telegram 等通道。"""
    if not is_push_available():
        print("❌ 推送功能不可用。請檢查:")
        print("   1. pip install python-telegram-bot")
        print("   2. .env 中設定 TG_TOKEN 和 TG_CHATID")
        sys.exit(1)

    if args.text:
        results = push_to_channels("", args.text, args.target)
    elif args.video:
        results = push_to_channels(args.video, args.caption, args.target)
    elif args.image:
        results = push_to_channels(args.image, args.caption, args.target)
    elif args.file:
        results = push_to_channels(args.file, args.caption, args.target)
    else:
        print("請指定 --text / --video / --image / --file")
        sys.exit(1)

    print()
    all_ok = True
    for ch_name, r in results.items():
        icon = "[OK]" if r.get("success") else "[FAIL]"
        detail = r.get("message") if r.get("success") else r.get("error", "")
        print(f"  {icon} [{ch_name}] {detail}")
        if not r.get("success"):
            all_ok = False
    print()

    if not all_ok:
        sys.exit(1)


# ═══════════════════════════════════════════════════════════
# 命令: db
# ═══════════════════════════════════════════════════════════

def cmd_db_stats():
    s = get_db_stats()
    print(f"資料庫統計:")
    print(f"  總新聞數: {s['total_news']}")
    print(f"  含影片:   {s['video_count']}")
    print(f"  最新日期: {s['latest_date']}")
    print(f"  推送記錄: {s['push_total']} (已推送: {s['push_ok']})")
    print(f"  資料庫路徑: {DB_PATH}")


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════

def _resolve_remote(args) -> bool:
    """解析遠端模式：--server > 系統 TDM_SERVER > skill/.env。"""
    server = getattr(args, "server", None)
    if server:
        os.environ["TDM_SERVER"] = server
        return True
    return bool(os.environ.get("TDM_SERVER", "").strip())


def _add_server_argument(parser, *, subcommand: bool = False) -> None:
    kwargs = {
        "type": _server_url,
        "help": "遠端伺服器 URL（可置於子命令前或後；亦可使用 TDM_SERVER）",
    }
    if subcommand:
        kwargs["default"] = argparse.SUPPRESS
    else:
        kwargs["default"] = None
    parser.add_argument("--server", **kwargs)


def _validate_args(parser, args) -> None:
    if args.cmd != "trim":
        return
    start = _time_seconds(args.start)
    if args.duration is not None and _time_seconds(args.duration) <= 0:
        parser.error("trim --duration 必須大於 0")
    if args.end is not None and _time_seconds(args.end) <= start:
        parser.error("trim --end 必須晚於 --start")


def main():
    _load_skill_env()
    p = argparse.ArgumentParser(description="TDMDO — 澳廣視新聞/影片工具")
    _add_server_argument(p)
    sp = p.add_subparsers(dest="cmd")

    pn = sp.add_parser("news", help="查詢新聞列表")
    _add_server_argument(pn, subcommand=True)
    pn.add_argument("--limit", type=_positive_int, default=10)
    pn.add_argument("--page", type=_positive_int, default=1)
    pn.add_argument("--search", help="過濾關鍵字")
    pn.add_argument("--date", type=_date_value, help="指定日期 YYYY-MM-DD（如 2026-07-09）")
    pn.add_argument("--category", type=_category_value, default=None,
                    metavar="{all,local,world,sport,feature,27,41,42,143}",
                    help="分類名稱或 ID（all=全部 local=本地 world=要聞 sport=體育 feature=特稿）")
    pn.add_argument("--video-only", action="store_true", help="僅顯示有影片的新聞")

    ps = sp.add_parser("search", help="關鍵字搜索新聞")
    _add_server_argument(ps, subcommand=True)
    ps.add_argument("keywords", nargs="+", help="關鍵字")
    ps.add_argument("--limit", type=_positive_int, default=10, help="顯示篇數（預設: 10）")
    ps.add_argument("--type", dest="stype", default="search_news",
                    choices=["search_news", "search_short_video", "search_program"],
                    help="類型")
    ps.add_argument("--video-only", action="store_true", help="僅含影片的新聞")

    pd = sp.add_parser("download", help="下載影片")
    _add_server_argument(pd, subcommand=True)
    g = pd.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", type=_news_id, help="6 至 7 位新聞/影片 ID")
    g.add_argument("--url", type=_tdm_url, help="含 6 至 7 位 ID 的 TDM 頁面 URL")
    pd.add_argument("--output", help="輸出檔案路徑")
    pd.add_argument("--cut", type=_cut_value,
                    help="裁剪參數，格式 START,DURATION；第二值固定為持續時間")
    pd.add_argument("--overwrite", action="store_true", help="強制覆蓋已存在的檔案")
    pd.add_argument("--push", action="store_true", help="下載完成後推送到 Telegram")
    pd.add_argument("--push-target", default=None, help="推送目標通道，逗號分隔 (預設: tg)")

    pt = sp.add_parser("trim", help="裁剪影片")
    _add_server_argument(pt, subcommand=True)
    pt.add_argument("--input", required=True)
    pt.add_argument("--start", required=True, type=_time_value, help="開始時間 HH:MM:SS")
    trim_range = pt.add_mutually_exclusive_group(required=True)
    trim_range.add_argument("--end", type=_time_value, help="結束時間 HH:MM:SS")
    trim_range.add_argument("--duration", type=_time_value, help="持續時間 HH:MM:SS")
    pt.add_argument("--output", help="輸出檔案路徑")

    pdb = sp.add_parser("db", help="資料庫管理")
    _add_server_argument(pdb, subcommand=True)
    pdb.add_argument("action", choices=["init", "stats", "sync"], help="init|stats|sync")
    pdb.add_argument("--force", action="store_true", help="sync 時強制更新既有新聞的 detail 資料")
    pdb.add_argument("--pages", type=_positive_int, default=3, help="sync 時同步頁數（每頁 40 篇）")
    pdb.add_argument("--all-days", action="store_true", help="sync 時不限 7 天")

    pp = sp.add_parser("push", help="推送媒體到 Telegram / 其他通道")
    _add_server_argument(pp, subcommand=True)
    g2 = pp.add_mutually_exclusive_group(required=True)
    g2.add_argument("--text", help="發送純文字")
    g2.add_argument("--video", help="發送影片檔案路徑")
    g2.add_argument("--image", help="發送圖片檔案路徑")
    g2.add_argument("--file", help="發送文件檔案路徑")
    pp.add_argument("--caption", type=_caption_value, default="", help="媒體說明文字（1024 字元內）")
    pp.add_argument("--target", default=None, help="推送目標通道，逗號分隔 (預設: tg)")

    ph = sp.add_parser("push-log", help="查看 WebDAV 推送記錄")
    _add_server_argument(ph, subcommand=True)
    ph.add_argument("--limit", type=_positive_int, default=10, help="顯示筆數（預設: 10）")

    args = p.parse_args()
    _validate_args(p, args)

    # ── 遠端模式檢查 ──────────────────────────────────────
    if _resolve_remote(args):
        from tdm_remote import (
            cmd_news as _r_news,
            cmd_search as _r_search,
            cmd_download as _r_download,
            cmd_trim as _r_trim,
            cmd_push as _r_push,
            cmd_db_stats as _r_db_stats,
            cmd_db_sync as _r_db_sync,
            cmd_push_log as _r_push_log,
        )
        print(f"🌐 遠端模式: {os.environ['TDM_SERVER']}\n")

        if args.cmd == "news":
            _r_news(args)
        elif args.cmd == "search":
            _r_search(args)
        elif args.cmd == "download":
            _r_download(args)
        elif args.cmd == "trim":
            _r_trim(args)
        elif args.cmd == "push":
            _r_push(args)
        elif args.cmd == "push-log":
            _r_push_log(args)
        elif args.cmd == "db":
            if args.action == "init":
                print("⚠️ 遠端模式下 'db init' 由伺服器端管理，無需手動執行")
            elif args.action == "stats":
                _r_db_stats()
            elif args.action == "sync":
                _r_db_sync(args)
        else:
            p.print_help()
        return

    # ── 本地模式 ──────────────────────────────────────────
    _local_imports()

    if args.cmd == "news":
        cmd_news(args)
    elif args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "download":
        cmd_download(args)
    elif args.cmd == "trim":
        cmd_trim(args)
    elif args.cmd == "push-log":
        cmd_push_log(args)
    elif args.cmd == "push":
        cmd_push(args)
    elif args.cmd == "db":
        if args.action == "init":
            init_db()
            print(f"資料庫初始化完成: {DB_PATH}")
        elif args.action == "stats":
            cmd_db_stats()
        elif args.action == "sync":
            init_db()
            n = sync_latest_news(force_update=args.force,
                                 pages=args.pages, all_days=args.all_days)
            print(f"  同步完成: 新增/更新 {n} 篇新聞")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
