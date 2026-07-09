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
"""

import argparse
import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# ── Windows 終端 UTF-8 ───────────────────────────────────
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# ── 導入核心模組 ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
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

def main():
    p = argparse.ArgumentParser(description="TDMDO — 澳廣視新聞/影片工具")
    sp = p.add_subparsers(dest="cmd")

    pn = sp.add_parser("news", help="查詢新聞列表")
    pn.add_argument("--limit", type=int, default=20)
    pn.add_argument("--page", type=int, default=1)
    pn.add_argument("--search", help="過濾關鍵字")
    pn.add_argument("--date", help="指定日期 YYYY-MM-DD（如 2026-07-09）")
    pn.add_argument("--category", choices=["27", "41", "42", "143"],
                    help="分類 ID（27=本地 41=要聞 42=體育 143=特稿，不指定=全部）")
    pn.add_argument("--video-only", action="store_true", help="僅顯示有影片的新聞")

    ps = sp.add_parser("search", help="關鍵字搜索新聞")
    ps.add_argument("keywords", nargs="+", help="關鍵字")
    ps.add_argument("--limit", type=int, default=20, help="顯示篇數")
    ps.add_argument("--type", dest="stype", default="search_news",
                    choices=["search_news", "search_short_video", "search_program"],
                    help="類型")
    ps.add_argument("--video-only", action="store_true", help="僅含影片的新聞")

    pd = sp.add_parser("download", help="下載影片")
    g = pd.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="新聞/影片 ID")
    g.add_argument("--url", help="TDM 頁面 URL")
    pd.add_argument("--output", help="輸出檔案路徑")
    pd.add_argument("--cut", help="裁剪參數，格式 START,DURATION (HH:MM:SS)")
    pd.add_argument("--overwrite", action="store_true", help="強制覆蓋已存在的檔案")
    pd.add_argument("--push", action="store_true", help="下載完成後推送到 Telegram")
    pd.add_argument("--push-target", default=None, help="推送目標通道，逗號分隔 (預設: tg)")

    pt = sp.add_parser("trim", help="裁剪影片")
    pt.add_argument("--input", required=True)
    pt.add_argument("--start", required=True, help="開始時間 HH:MM:SS")
    pt.add_argument("--end", help="結束時間 HH:MM:SS")
    pt.add_argument("--duration", help="持續時間 HH:MM:SS")
    pt.add_argument("--output", help="輸出檔案路徑")

    pdb = sp.add_parser("db", help="資料庫管理")
    pdb.add_argument("action", choices=["init", "stats", "sync"], help="init|stats|sync")
    pdb.add_argument("--force", action="store_true", help="sync 時強制更新既有新聞的 detail 資料")
    pdb.add_argument("--pages", type=int, default=3, help="sync 時同步頁數（每頁 40 篇）")
    pdb.add_argument("--all-days", action="store_true", help="sync 時不限 7 天")

    pp = sp.add_parser("push", help="推送媒體到 Telegram / 其他通道")
    g2 = pp.add_mutually_exclusive_group(required=True)
    g2.add_argument("--text", help="發送純文字")
    g2.add_argument("--video", help="發送影片檔案路徑")
    g2.add_argument("--image", help="發送圖片檔案路徑")
    g2.add_argument("--file", help="發送文件檔案路徑")
    pp.add_argument("--caption", default="", help="媒體說明文字（1024 字元內）")
    pp.add_argument("--target", default=None, help="推送目標通道，逗號分隔 (預設: tg)")

    ph = sp.add_parser("push-log", help="查看 WebDAV 推送記錄")
    ph.add_argument("--limit", type=int, default=20, help="顯示筆數")

    args = p.parse_args()

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
