#!/usr/bin/env python3
"""
TDMDO 網頁端 — 澳廣視一站式新聞/影片工具。
Web 層：只做 Flask 路由 + HTML UI，核心邏輯在 tdm_core.py。
用法: python app/tdm_web.py [--port 8080] [--host 0.0.0.0]
"""

import argparse
import hashlib
import os
import re
import sqlite3
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

# ── 導入核心模組 ─────────────────────────────────────────
_CORE_PATH = Path(__file__).resolve().parent.parent / '.claude' / 'skills' / 'tdm' / 'scripts'
sys.path.insert(0, str(_CORE_PATH))
from tdm_core import (
    TDM_BASE, DOWNLOAD_DIR, DB_PATH,
    extract_id, safe_filename, parse_time, fmt_cut_time,
    api_news_list, extract_items, check_video_batch,
    query_news_list, query_search, get_video_info,
    download_video, trim_video, push_to_webdav, is_webdav_configured,
    init_db, record_download, record_video, update_video_push_status,
    get_pushed_filenames, list_videos,
    get_videos_by_news_id, get_grouped_videos, get_video_by_id,
    push_to_channels, is_push_available,
)

try:
    from flask import Flask, render_template_string, request, jsonify, send_file
except ImportError:
    print("請安裝: pip install requests flask")
    sys.exit(1)

app = Flask(__name__)
_downloads: Dict[str, dict] = {}

# ═══ 載入 .env 檔案（無相依套件）═══
_ENV_DIR = Path(__file__).resolve().parent.parent / '.claude' / 'skills' / 'tdm'
for _p in [_ENV_DIR / '.env', Path.cwd() / '.env']:
    if _p.exists():
        with open(str(_p), encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith('#') or '=' not in _line:
                    continue
                _key, _val = _line.split('=', 1)
                _key, _val = _key.strip(), _val.strip().strip('"\'')
                if _key and _val:
                    os.environ.setdefault(_key, _val)

# ═══ Web 頁面密碼保護 ═══
_AUTH_ENABLED = os.getenv("WEB_AUTH_ENABLED", "").lower() in ("1", "true", "yes")
_AUTH_PASSWORDS_RAW = os.getenv("WEB_AUTH_PASSWORDS", "")
_AUTH_TOKENS = set(
    hashlib.sha256(p.strip().encode()).hexdigest()
    for p in _AUTH_PASSWORDS_RAW.split(",")
    if p.strip()
) if _AUTH_PASSWORDS_RAW.strip() else set()

if _AUTH_ENABLED and not _AUTH_TOKENS:
    print("⚠️  WEB_AUTH_ENABLED=true 但未設定 WEB_AUTH_PASSWORDS，密碼保護不會生效")
    _AUTH_ENABLED = False


HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>TDMDO — 澳廣視新聞/影片工具</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--fg:#c9d1d9;--accent:#f0c040;--dim:#8b949e;--err:#f5a5a5;--ok:#95d5b2}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft JhengHei","PingFang TC",sans-serif;background:var(--bg);color:var(--fg);min-height:100vh}
header{background:var(--card);border-bottom:1px solid var(--border);padding:.75rem 1.5rem;display:flex;align-items:center;gap:1rem}
header h1{font-size:1.2rem;color:var(--accent)}
nav{display:flex;gap:.25rem}
nav button{padding:.5rem 1rem;background:none;border:1px solid var(--border);color:var(--fg);border-radius:6px;cursor:pointer;font-size:.85rem}
nav button.active{background:var(--accent);color:var(--bg);border-color:var(--accent);font-weight:600}
main{max-width:1280px;margin:0 auto;padding:1.5rem}
.tab{display:none}.tab.active{display:block}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1rem}
.card h2{font-size:1rem;margin-bottom:.75rem;color:var(--accent)}
.row{display:flex;gap:.5rem;margin-bottom:.75rem;align-items:center}
input,select{padding:.6rem .75rem;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--fg);font-size:.85rem;outline:none;flex:1}
input:focus,select:focus{border-color:var(--accent)}
input[type="date"]{min-width:130px;color-scheme:dark;color:#e6edf3;background:var(--bg);border:1px solid var(--border)}
input[type="date"]::-webkit-calendar-picker-indicator{cursor:pointer;filter:brightness(0) invert(1);opacity:.85}
input[type="date"]::-webkit-datetime-edit-text,
input[type="date"]::-webkit-datetime-edit-month-field,
input[type="date"]::-webkit-datetime-edit-day-field,
input[type="date"]::-webkit-datetime-edit-year-field{color:#e6edf3}
button{padding:.6rem 1rem;background:var(--accent);color:var(--bg);border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:.85rem}
button:hover{filter:brightness(1.1)}
button:disabled{background:#333;color:#666;cursor:not-allowed}
.btn-sm{padding:.35rem .65rem;font-size:.75rem}
.btn-outline{background:none;border:1px solid var(--border);color:var(--fg)}
.btn-outline:hover{background:var(--border)}
.btn-danger{border-color:#f55;color:#f55}.btn-danger:hover{background:#3d1a1a}
.badge{font-size:.7rem;padding:.15rem .4rem;border-radius:4px;white-space:nowrap;font-weight:600;display:inline-block}
.badge-vid{background:#1b4332;color:#95d5b2}.badge-txt{background:#0d419d;color:#c9d1d9}.badge-chk{background:#5c4200;color:#ffc107}.badge-cut{background:#3d2e00;color:#f0c040}
.push-tg-btn{background:#0088cc;color:#fff;border-color:#0088cc}
.push-tg-btn:hover{background:#0099dd}
#toast{position:fixed;top:1rem;right:1rem;z-index:9999;max-width:420px;padding:.75rem 1rem;border-radius:8px;font-size:.85rem;font-weight:600;display:none;box-shadow:0 4px 24px rgba(0,0,0,.5)}
#toast.ok{background:#1b4332;color:#95d5b2;display:block}
#toast.err{background:#3d1a1a;color:#f5a5a5;display:block}
#toast.info{background:#0d419d;color:#c9d1d9;display:block}
.news-item,.video-item{display:flex;align-items:center;gap:.5rem;padding:.6rem 0;border-bottom:1px solid var(--border);font-size:.85rem;flex-wrap:wrap}
.news-item .title,.video-item .vname{flex:1 1 200px;min-width:0;word-break:break-all;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.35}
.news-item .meta{color:var(--dim);font-size:.75rem;white-space:nowrap;flex-shrink:0}
.news-item .actions,.video-item .actions{display:flex;gap:.25rem;flex-shrink:0}
.bar{width:100%;height:4px;background:var(--border);border-radius:2px;margin-top:.5rem;overflow:hidden;display:none}
.fill{height:100%;background:var(--accent);border-radius:2px;width:0;transition:width .3s}
.pagination{display:flex;gap:.25rem;justify-content:center;margin-top:1rem;flex-wrap:wrap}
.pagination button{padding:.35rem .65rem;font-size:.75rem}
.loading{text-align:center;padding:1rem;color:var(--dim)}.empty{text-align:center;padding:2rem;color:var(--dim)}
video{max-width:100%;border-radius:6px;background:#000}
.player-wrap{margin:.5rem 0;background:#000;border-radius:6px;overflow:hidden}
.player-wrap video{width:100%;max-height:360px;display:block}
.info-banner{padding:.5rem .75rem;border-radius:6px;font-size:.8rem;margin-bottom:.75rem;background:var(--bg);color:var(--dim)}
label.check-label{display:flex;align-items:center;gap:.35rem;font-size:.8rem;color:var(--dim);white-space:nowrap;cursor:pointer}
label.check-label input[type=checkbox]{flex:none;width:auto}
/* 影片群組 */
.video-group{background:var(--card);border:1px solid var(--border);border-radius:10px;margin-bottom:.75rem;overflow:hidden}
.video-group-header{display:flex;align-items:center;gap:.5rem;padding:.7rem 1rem;cursor:pointer;font-size:.85rem;font-weight:600;color:var(--accent);user-select:none}
.video-group-header:hover{background:rgba(240,192,64,.05)}
.video-group-header .arrow{transition:transform .2s;font-size:.65rem;color:var(--dim)}
.video-group-body .video-item{padding:.4rem 1rem}
.video-group-body .video-item:last-child{border-bottom:none}
/* 版本列表 */
.ver-item{display:flex;align-items:center;gap:.35rem;padding:.3rem 0;font-size:.8rem;flex-wrap:wrap}
.ver-item .vt{font-size:.7rem;padding:.1rem .35rem;border-radius:3px;white-space:nowrap;font-weight:600}
.ver-item .vt.dl{background:#1b4332;color:#95d5b2}
.ver-item .vt.cut{background:#3d2e00;color:#f0c040}
.ver-item .vn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ver-item .vz{color:var(--dim);font-size:.72rem;white-space:nowrap}
#dl-cut-row{display:flex;gap:.35rem;align-items:center;flex-wrap:wrap;margin:.5rem 0}
#dl-cut-row input{flex:1;min-width:90px;font-size:.8rem;padding:.45rem .55rem}
/* 登入覆蓋層 */
#auth-overlay{position:fixed;inset:0;z-index:99999;background:var(--bg);display:flex;align-items:center;justify-content:center}
#auth-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:2.5rem;width:360px;max-width:90vw;text-align:center}
#auth-box h1{color:var(--accent);font-size:1.3rem;margin-bottom:.3rem}
#auth-box p{color:var(--dim);font-size:.85rem;margin-bottom:1.5rem}
#auth-box input{width:100%;margin-bottom:.75rem;text-align:center;font-size:1rem;padding:.75rem;letter-spacing:.15em}
#auth-box button{width:100%;padding:.75rem;font-size:.95rem}
#auth-err{color:var(--err);font-size:.8rem;margin-top:.5rem;display:none}
#auth-box .hint{color:var(--dim);font-size:.7rem;margin-top:1rem;opacity:.5}
#auth-box.loading button{opacity:.6;pointer-events:none}
@media(max-width:768px){
  main{padding:.75rem}
  header{padding:.5rem .75rem;flex-wrap:wrap}
  header h1{font-size:1rem}
  nav button{padding:.35rem .6rem;font-size:.75rem}
  .card{padding:1rem}
  .row{flex-wrap:wrap}
  .news-item .title,.video-item .vname{flex:1 1 100%;font-size:.8rem}
  .news-item .meta{font-size:.7rem}
  .news-item .actions,.video-item .actions{width:100%;justify-content:flex-end}
  .video-group-header{font-size:.8rem;padding:.5rem .75rem}
}
</style>
</head>
<body>
<!-- 登入覆蓋層 -->
<div id="auth-overlay" style="display:none">
  <div id="auth-box">
    <h1>🔐 TDMDO</h1>
    <p>請輸入密碼以繼續</p>
    <input type="password" id="auth-pwd" placeholder="輸入密碼..." autocomplete="current-password" onkeydown="if(event.key==='Enter')doAuth()" autofocus>
    <button onclick="doAuth()">解鎖</button>
    <div id="auth-err">❌ 密碼錯誤，請重試</div>
    <div class="hint"></div>
  </div>
</div>
<header>
  <h1>📡 TDMDO</h1>
  <nav>
    <button class="active" onclick="switchTab('news')">📰 新聞</button>
    <button onclick="switchTab('download')">⬇️ 下載</button>
    <button onclick="switchTab('videos')">📁 已下載</button>
  </nav>
</header>

<main>
<!-- Toast -->
<div id="toast"></div>
<!-- ═══ 新聞 ═══ -->
<div id="tab-news" class="tab active">
  <div class="card">
    <h2>搜尋新聞</h2>
    <div class="row">
      <input id="search-input" placeholder="輸入關鍵字..." onkeydown="if(event.key==='Enter')searchNews(1)" style="flex:2">
      <label class="check-label"><input type="checkbox" id="video-only" onchange="onVOSearchChange()" checked>僅影片</label>
      <select id="search-type" style="flex:1">
        <option value="search_news">全部新聞</option>
        <option value="search_program">節目</option>
      </select>
      <button onclick="searchNews(1)">搜索</button>
    </div>
    <div class="info-banner" id="search-range" style="display:none"></div>
    <div id="news-status"></div>
  </div>
  <div class="card">
    <h2>📹 影片新聞 <span style="font-weight:400;color:var(--dim);font-size:.8rem" id="news-info"></span></h2>
    <div class="row">
      <select id="news-category" onchange="loadNews(1)" style="flex:0 0 auto;min-width:100px">
        <option value="">全部分類</option>
        <option value="27">本地</option>
        <option value="41">要聞</option>
        <option value="42">體育</option>
        <option value="143">特稿</option>
      </select>
      <input id="news-date" type="date" style="flex:0 0 auto;min-width:130px" onchange="loadNews(1)" title="指定日期">
      <button class="btn-sm btn-outline" onclick="S('news-date').value='';S('news-category').value='';S('video-only').checked=true;activeVOsearch=true;loadNews(1)" title="重設">🔄 重設</button>
    </div>
    <div id="news-list"><div class="loading">載入中...</div></div>
    <div class="pagination" id="news-pager"></div>
  </div>
</div>

<!-- ═══ 下載（統一卡片）═══ -->
<div id="tab-download" class="tab">
  <div class="card">
    <h2>查詢 / 下載 / 裁剪</h2>
    <div class="row">
      <input id="dl-input" placeholder="輸入 TDM URL 或 6-7 位影片 ID..." onkeydown="if(event.key==='Enter')queryVideo()">
      <button id="dl-query-btn" onclick="queryVideo()">查詢</button>
    </div>

    <!-- 影片資訊 -->
    <div id="dl-info" style="display:none">
      <div style="display:flex;gap:1rem;align-items:flex-start;flex-wrap:wrap;margin-top:.75rem;padding:1rem;background:var(--bg);border-radius:8px;border:1px solid var(--border)">
        <img id="dl-thumb" style="width:160px;border-radius:6px;display:none" onerror="this.style.display='none'">
        <div style="flex:1;min-width:200px">
          <h3 style="margin:0 0 .5rem;color:var(--accent)" id="dl-title"></h3>
          <div style="color:var(--dim);font-size:.8rem;margin-bottom:.5rem" id="dl-meta"></div>
          <div id="dl-content" style="font-size:.8rem;color:var(--dim);margin-bottom:.5rem;line-height:1.5;white-space:pre-wrap;max-height:120px;overflow-y:auto"></div>
          <div style="font-size:.8rem;margin-bottom:.3rem">
            <span style="color:var(--dim)">m3u8: </span>
            <code id="dl-m3u8" style="font-size:.72rem;word-break:break-all;cursor:pointer;color:#58a6ff" onclick="copyText(this.textContent,'m3u8')" title="點擊複製"></code>
          </div>
          <div id="dl-already" style="font-size:.8rem;margin-bottom:.5rem"></div>
          <!-- 裁切控制 -->
          <div id="dl-cut-row">
            <input id="dl-cut-start" placeholder="裁剪開始 (HH:MM:SS)" title="開始時間">
            <button class="btn-sm btn-outline" onclick="capTime('dl','start')" title="從預覽擷取">▶</button>
            <span style="color:var(--dim);font-size:.8rem">→</span>
            <input id="dl-cut-end" placeholder="裁剪結束 (HH:MM:SS)" title="結束時間">
            <button class="btn-sm btn-outline" onclick="capTime('dl','end')" title="從預覽擷取">▶</button>
            <button id="dl-go-btn" onclick="startDownload()">⬇️ 下載/裁剪</button>
          </div>
          <div style="display:flex;gap:.5rem;flex-wrap:wrap">
            <button class="btn-sm btn-outline" id="dl-preview-btn" onclick="togglePreview()" style="display:none">▶️ 預覽</button>
            <button class="btn-sm btn-outline" onclick="window.open('https://www.tdm.com.mo/zh-hant/news-detail/'+(currentVideoInfo?.id||''))">🔗 新聞頁</button>
            <button class="btn-sm btn-outline" onclick="copyText(currentVideoInfo?.m3u8_full||'','m3u8')">📋 m3u8</button>
          </div>
          <!-- 預覽播放器 -->
          <div class="player-wrap" id="dl-preview-wrap" style="display:none"><video id="dl-preview" controls></video></div>
          <!-- 進度 -->
          <div id="dl-status" style="display:none;padding:.5rem;border-radius:6px;font-size:.8rem;margin-top:.5rem"></div>
          <div class="bar" id="dl-bar"><div class="fill" id="dl-fill"></div></div>
          <pre id="dl-log" style="display:none;margin-top:.5rem;padding:.5rem;background:#000;border-radius:6px;font-size:.7rem;color:var(--dim);max-height:160px;overflow-y:auto;white-space:pre-wrap;word-break:break-all"></pre>
        </div>
      </div>
      <!-- 已下載版本 -->
      <div id="dl-versions" style="margin-top:.75rem;display:none">
        <div style="font-size:.85rem;color:var(--accent);font-weight:600;margin-bottom:.4rem">📁 已下載版本</div>
        <div id="dl-versions-list"></div>
      </div>
    </div>
    <div id="dl-no-video" style="display:none;margin-top:1rem;padding:1rem;background:#3d1a1a;border-radius:8px;color:var(--err)"></div>
  </div>
</div>

<!-- ═══ 已下載 ═══ -->
<div id="tab-videos" class="tab">
  <div class="card">
    <h2>已下載影片 <span style="font-weight:400;color:var(--dim);font-size:.8rem" id="video-count"></span></h2>
    <div id="video-list"><div class="loading">載入中...</div></div>
  </div>
</div>
</main>

<script>
const S=id=>document.getElementById(id);
// ── 密碼認證 ──
const _AUTH_OVERLAY=S('auth-overlay'),_AUTH_ERR=S('auth-err'),_AUTH_PWD=S('auth-pwd');
let _authOk=false;
async function initAuth(){try{const r=await fetch('/api/auth-check');const d=await r.json();if(!d.enabled)return;_authOk=d.ok;if(!d.ok){_AUTH_OVERLAY.style.display='flex';setTimeout(()=>_AUTH_PWD.focus(),100)}}catch(e){}}
async function doAuth(){const pwd=_AUTH_PWD.value;if(!pwd)return;_AUTH_ERR.style.display='none';document.getElementById('auth-box').classList.add('loading');try{const r=await fetch('/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pwd})});const d=await r.json();if(d.ok){_AUTH_OVERLAY.style.display='none';_authOk=true}else{_AUTH_ERR.style.display='block';_AUTH_PWD.value='';_AUTH_PWD.focus()}}catch(e){_AUTH_ERR.textContent='❌ 網路錯誤';_AUTH_ERR.style.display='block'}document.getElementById('auth-box').classList.remove('loading')}
initAuth();
let newsPage=1,newsTotal=0,dlTimer=null,searchKW='',currentVideoInfo=null,activeVOsearch=false,_hls=null;

// ── Tab ──
function switchTab(t){
  document.querySelectorAll('.tab').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('nav button').forEach((e,i)=>{
    e.classList.toggle('active',(t==='news'&&i===0)||(t==='download'&&i===1)||(t==='videos'&&i===2));
  });
  S('tab-'+t).classList.add('active');
  if(t==='news') loadNews(1);
  else if(t==='videos') loadVideos();
}

// ── URL 參數 ──
function updateURL(params){
  const u=new URL(location);
  Object.entries(params).forEach(([k,v])=>{if(v)u.searchParams.set(k,v);else u.searchParams.delete(k)});
  history.replaceState(null,'',u);
}
function getParam(k){return new URLSearchParams(location.search).get(k)||'';}

// ── 新聞 ──
function onVOSearchChange(){activeVOsearch=S('video-only').checked;}
async function loadNews(p){
  newsPage=p;searchKW='';activeVOsearch=S('video-only').checked;
  S('search-range').style.display='none';
  const dateVal=S('news-date').value.trim(),cat=S('news-category').value,vo=activeVOsearch?'1':'0';
  let url=`/api/news?page=${p}&size=15&video_only=${vo}`;
  if(dateVal)url+=`&date=${encodeURIComponent(dateVal)}`;
  if(cat)url+=`&category=${encodeURIComponent(cat)}`;
  S('news-list').innerHTML=`<div class="loading">${vo==='1'?'[僅影片] 載入中...':'載入中...'}</div>`;
  const r=await fetch(url);const d=await r.json();
  if(d.error){S('news-list').innerHTML=`<div class="empty">${d.error}</div>`;return}
  newsTotal=d.total||0;S('news-info').textContent=`(共 ${newsTotal} 篇)`;
  renderNewsList(d.items,d.offset||0);
  renderPager(newsTotal,p,loadNews,15);
}
async function searchNews(p){
  if(!p||p===1){searchKW=S('search-input').value.trim();activeVOsearch=S('video-only').checked;if(!searchKW)return loadNews(1);}
  newsPage=p||1;
  const st=S('search-type').value,vo=activeVOsearch?'1':'0';
  const dateVal=S('news-date').value.trim(),cat=S('news-category').value;
  let url=`/api/news?search=${encodeURIComponent(searchKW)}&page=${newsPage}&size=15&stype=${st}&video_only=${vo}`;
  if(dateVal)url+=`&date=${encodeURIComponent(dateVal)}`;
  if(cat)url+=`&category=${encodeURIComponent(cat)}`;
  S('news-list').innerHTML=`<div class="loading">${vo==='1'?'[僅影片] 檢查中...':'搜索中...'}</div>`;
  const r=await fetch(url);const d=await r.json();
  if(d.error){S('news-list').innerHTML=`<div class="empty">${d.error}</div>`;S('search-range').style.display='none';S('news-pager').innerHTML='';return}
  newsTotal=d.total||0;S('news-info').textContent=`(找到 ${newsTotal} 篇)`;
  S('search-range').style.display='block';
  S('search-range').innerHTML=d.range||(vo?`僅影片模式 — 已檢查 ${d.checked||0} 條`:`全文搜尋 — ${newsTotal} 篇`);
  renderNewsList(d.items,d.offset||0);
  renderPager(newsTotal,newsPage,searchNews,15);
}
function renderNewsList(items,offset){
  let h='';
  items.forEach((it,i)=>{
    const v=it.checking?'<span class="badge badge-chk">檢查中</span>':(it.video?'<span class="badge badge-vid">影片</span>':'<span class="badge badge-txt">純文字</span>');
    h+=`<div class="news-item"><span class="title">${i+offset+1}. ${it.title}</span>
      <span class="meta">${it.date||''}</span>${v}
      <span class="actions">${it.video?`<button class="btn-sm" onclick="quickDownload('${it.id}')">下載</button>`:''}
      <button class="btn-sm btn-outline" onclick="window.open('https://www.tdm.com.mo/zh-hant/news-detail/${it.id}')">開啟</button></span></div>`;
  });
  S('news-list').innerHTML=h||'<div class="empty">無結果</div>';
}
function renderPager(total,pg,fn,ps){ps=ps||15;let h='';const tp=Math.ceil(total/ps);if(tp>1)for(let i=1;i<=Math.min(tp,50);i++)h+=`<button onclick="${fn.name}(${i})" ${i===pg?'style="background:var(--accent);color:var(--bg)"':''}>${i}</button>`;S('news-pager').innerHTML=h;}
function quickDownload(id){switchTab('download');S('dl-input').value=id;queryVideo();}

function copyText(t,label){navigator.clipboard.writeText(t).then(()=>{_flash(`✅ 已複製: ${label||''}`,'ok')});}
function _flash(msg,cls){const t=S('toast');clearTimeout(t._tid);t.textContent=msg;t.className=cls;t.style.display='block';t._tid=setTimeout(()=>{t.style.display='none'},3000);}

// ── 下載頁 ──
async function queryVideo(){
  const inp=S('dl-input').value.trim();if(!inp)return;
  S('dl-query-btn').disabled=true;S('dl-query-btn').textContent='查詢中...';
  S('dl-info').style.display='none';S('dl-no-video').style.display='none';
  S('dl-preview-wrap').style.display='none';S('dl-preview-btn').style.display='none';
  S('dl-versions').style.display='none';S('dl-bar').style.display='none';S('dl-log').style.display='none';
  try{
    const r=await fetch('/api/query-video',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:inp})});
    const d=await r.json();
    if(d.error){S('dl-no-video').style.display='block';S('dl-no-video').textContent='❌ '+d.error;return}
    S('dl-title').textContent=d.title;
    S('dl-meta').innerHTML=`<b>日期:</b> ${d.date||'?'} &nbsp;|&nbsp; <b>時長:</b> ${d.length?d.length+' 秒':'?'} &nbsp;|&nbsp; <b>ID:</b> ${d.id}`;
    S('dl-content').textContent=d.content||'';
    S('dl-m3u8').textContent=d.m3u8_full||'';
    S('dl-m3u8').title='點擊複製 m3u8 連結';
    if(d.thumbnail){S('dl-thumb').src=d.thumbnail;S('dl-thumb').style.display='block'}else S('dl-thumb').style.display='none';
    if(d.m3u8_full)S('dl-preview-btn').style.display='';
    // 已下載狀態
    const fname=(d.file_path||'').split(/[\\/]/).pop()||'';
    const webUrl=d.file_path?`${location.origin}/api/download-file/${encodeURIComponent(fname)}`:'';
    if(d.already_exists){
      S('dl-already').innerHTML=`<span style="color:var(--ok)">✅ 已下載: ${fname}</span>`;
      S('dl-go-btn').textContent='⬇️ 重新下載/裁剪';
    }else{
      S('dl-already').innerHTML='<span style="color:var(--dim)">⬇️ 尚未下載</span>';
      S('dl-go-btn').textContent='⬇️ 下載/裁剪';
    }
    currentVideoInfo=d;
    S('dl-info').style.display='block';
    updateURL({news_id:d.id, vid:getParam('vid'), cut:getParam('cut')});
    // 讀取 URL cut/filename 參數
    const cutP=getParam('cut'),fileP=getParam('file');
    if(cutP){const parts=cutP.split(',');if(parts[0])S('dl-cut-start').value=parts[0];if(parts[1])S('dl-cut-end').value=parts[1];}
    // 渲染已下載版本
    renderVersions(d.downloaded_versions||[]);
    if(fileP){
      // 自動播放指定檔案
      const u=`${location.origin}/api/download-file/${encodeURIComponent(fileP)}`;
      _showResultVideo(decodeURIComponent(fileP),u);
    }
  }catch(e){S('dl-no-video').style.display='block';S('dl-no-video').textContent='❌ '+e.message}
  finally{S('dl-query-btn').disabled=false;S('dl-query-btn').textContent='查詢'}
}

function renderVersions(vers){
  const c=S('dl-versions'),l=S('dl-versions-list');
  if(!vers||!vers.length){c.style.display='none';return}
  c.style.display='block';
  l.innerHTML=vers.map(v=>{
    const isCut=v.source_type==='cut';
    const label=isCut?`<span class="vt cut">✂️ ${fmtCut(v.cut_start,v.cut_end)}</span>`:'<span class="vt dl">📹 原片</span>';
    const sz=v.file_size?`<span class="vz">${fmtSize(v.file_size)}</span>`:'';
    const ts=v.created_at?`<span class="vz">${v.created_at.slice(0,16).replace('T',' ')}</span>`:'';
    const pushIcon=v.push_status==='pushed'?'☁️':'⬆️';
    // 需要從 DB 拿到 id (videos 表的主鍵)
    return`<div class="ver-item">${label}<span class="vn" title="${v.filename}">${v.filename}</span>${sz}${ts}
      ${v.vid?`<button class="btn-sm" onclick="versPlayV(${v.vid})" title="播放">▶</button>
      <button class="btn-sm btn-outline" onclick="versCutV(${v.vid})" title="裁剪">✂️</button>
      <button class="btn-sm push-tg-btn" onclick="versPushTg(${v.vid})" title="推送 Telegram">📤</button>
      <button class="btn-sm btn-outline" onclick="versPushV(${v.vid})" title="推送 WebDAV">${pushIcon}</button>
      <button class="btn-sm btn-danger" onclick="delVideo(${v.vid})" title="刪除">🗑</button>`:''}</div>`;
  }).join('');
}
function _showResultVideo(name,url){
  let w=S('dl-result-player');
  if(!w){
    w=document.createElement('div');w.id='dl-result-player';
    w.innerHTML=`<div class="player-wrap" style="margin-top:.5rem"><video id="dl-result-video" controls></video></div>
      <div style="display:flex;gap:.5rem;align-items:center;margin-top:.25rem;flex-wrap:wrap">
        <span id="dl-result-name" style="flex:1;font-size:.8rem;color:var(--ok)"></span>
        <a id="dl-result-dl" href="#" download><button class="btn-sm">📥</button></a>
        <button class="btn-sm btn-outline" onclick="copyText(getResultUrl(),'連結')">📋</button>
        <button class="btn-sm btn-outline" onclick="trimResult()">✂️ 裁剪此片</button>
      </div>
      <div id="dl-result-trim" style="display:none;margin-top:.4rem">
        <div style="display:flex;gap:.35rem;align-items:center;flex-wrap:wrap">
          <input id="trim-r-start" placeholder="開始 (HH:MM:SS)" style="flex:1;min-width:100px;font-size:.8rem;padding:.4rem .5rem">
          <button class="btn-sm btn-outline" onclick="capResultTime('start')" title="從播放器擷取">▶</button>
          <span style="color:var(--dim);font-size:.8rem">→</span>
          <input id="trim-r-end" placeholder="結束 (HH:MM:SS)" style="flex:1;min-width:100px;font-size:.8rem;padding:.4rem .5rem">
          <button class="btn-sm btn-outline" onclick="capResultTime('end')" title="從播放器擷取">▶</button>
          <button class="btn-sm" onclick="doTrimResult()" style="background:var(--ok);color:var(--bg)">✂️ 裁剪</button>
        </div>
      </div>`;
    S('dl-info').appendChild(w);
  }
  S('dl-result-video').src=url;S('dl-result-name').textContent=name;
  S('dl-result-dl').href=`${location.origin}/api/download-file/${encodeURIComponent(name)}?dl=1`;
  S('dl-preview-wrap').style.display='none';
  S('dl-result-trim').style.display='none'; // 切換影片時收合裁剪區
}
function getResultUrl(){return S('dl-result-dl').href;}
function trimResult(){
  const t=S('dl-result-trim');
  t.style.display=t.style.display==='none'?'block':'none';
  S('trim-r-start').value='';S('trim-r-end').value='';
}
function capResultTime(pos){
  const v=S('dl-result-video'),t=v.currentTime;
  if(isNaN(t)){alert('請先播放影片');return}
  const h=Math.floor(t/3600),m=Math.floor((t%3600)/60),s=Math.floor(t%60);
  const ts=`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  if(pos==='start')S('trim-r-start').value=ts;else S('trim-r-end').value=ts;
}
async function doTrimResult(){
  const fn=S('dl-result-name').textContent;
  const st=S('trim-r-start').value.trim(),en=S('trim-r-end').value.trim();
  if(!fn||!st){alert('請輸入開始時間');return}
  S('dl-bar').style.display='block';S('dl-fill').style.width='10%';
  _showStatus('info','✂️ 裁剪中...');
  try{
    const r=await fetch('/api/trim',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file:fn,start:st,end:en})});
    const d=await r.json();
    if(d.error){_showStatus('err','❌ '+d.error);S('dl-bar').style.display='none';return}
    if(d.ok){
      _showStatus('ok','✅ '+d.filename);S('dl-fill').style.width='100%';
      // 顯示裁剪結果
      const u=`${location.origin}/api/download-file/${encodeURIComponent(d.filename)}`;
      _showResultVideo(d.filename,u);
      S('dl-result-trim').style.display='none';
      // 刷新版本列表
      if(currentVideoInfo)queryVideo();
    }else{_showStatus('err','❌ 裁剪失敗');S('dl-bar').style.display='none';}
  }catch(e){_showStatus('err','❌ '+e.message);S('dl-bar').style.display='none';}
}

function togglePreview(){
  if(!currentVideoInfo||!currentVideoInfo.m3u8_full)return;
  const w=S('dl-preview-wrap');
  if(w.style.display!='none'){w.style.display='none';if(_hls){_hls.destroy();_hls=null;}return}
  w.style.display='block';
  const v=S('dl-preview'),m3u8=currentVideoInfo.m3u8_full;
  if(typeof Hls!=='undefined'&&Hls.isSupported()){_hls=new Hls();_hls.loadSource(m3u8);_hls.attachMedia(v)}
  else if(v.canPlayType('application/vnd.apple.mpegurl'))v.src=m3u8;
}
function capTime(section,pos){
  const v=S(section+'-preview'),t=v.currentTime;
  if(isNaN(t)){alert('請先播放影片');return}
  const h=Math.floor(t/3600),m=Math.floor((t%3600)/60),s=Math.floor(t%60);
  const ts=`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  if(section==='dl'){
    if(pos==='start')S('dl-cut-start').value=ts;else S('dl-cut-end').value=ts;
  }
}

function startDownload(){
  if(!currentVideoInfo)return;
  if(currentVideoInfo.already_exists&&!confirm('影片已存在，確定重新下載？'))return;
  const cs=S('dl-cut-start').value.trim(),ce=S('dl-cut-end').value.trim();
  S('dl-go-btn').disabled=true;S('dl-go-btn').textContent='下載中...';
  S('dl-bar').style.display='block';S('dl-fill').style.width='5%';
  _showStatus('info','⬇️ 下載中...');
  const body={url:`https://www.tdm.com.mo/zh-hant/news-detail/${currentVideoInfo.id}`,overwrite:!!currentVideoInfo.already_exists};
  if(cs)body.cut_start=cs;if(ce)body.cut_end=ce;
  fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(r=>r.json()).then(d=>{
      if(d.error){_showStatus('err','❌ '+d.error);_resetDl();return}
      _showStatus('info','⬇️ '+d.info);pollProgress(d.download_id);
      if(cs||ce)updateURL({cut:`${cs||'0'},${ce||''}`});
    }).catch(e=>{_showStatus('err','❌ '+e.message);_resetDl()});
}
function pollProgress(id){
  if(dlTimer)clearInterval(dlTimer);
  dlTimer=setInterval(async()=>{
    const r=await fetch('/api/progress/'+id);const d=await r.json();
    if(!d)return;
    const icon=d.status?.includes('yt-dlp')?'📦':d.status?.includes('ffmpeg')?'🎬':'⏳';
    S('dl-status').textContent=icon+' '+d.status;
    S('dl-fill').style.width=Math.min(95,d.pct||10)+'%';
    if(d.log){S('dl-log').style.display='block';S('dl-log').textContent=d.log.join('\n');}
    if(d.done){clearInterval(dlTimer);dlTimer=null;
      if(d.ok){
        _showStatus('ok','✅ '+d.filename);
        S('dl-fill').style.width='100%';
        _showResultVideo(d.filename,`${location.origin}/api/download-file/${encodeURIComponent(d.filename)}`);
        updateURL({file:d.filename});
        // 刷新版本列表
        queryVideo();
      }else{_showStatus('err','❌ '+(d.error||'失敗'));_resetDl();}
    }
  },1500);
}
function _resetDl(){const b=S('dl-go-btn');b.disabled=false;b.textContent=currentVideoInfo?.already_exists?'⬇️ 重新下載/裁剪':'⬇️ 下載/裁剪';}
function _showStatus(cls,msg){const s=S('dl-status');s.className=cls;s.textContent=msg;s.style.display='block';}

// ── 已下載頁 ──
async function loadVideos(){
  S('video-list').innerHTML='<div class="loading">載入中...</div>';
  const r=await fetch('/api/videos?grouped=1');const d=await r.json();
  const groups=d.groups||[];
  if(!groups.length){S('video-list').innerHTML='<div class="empty">尚未下載任何影片</div>';return}
  let totalOriginals=0, totalCuts=0;
  let h='';
  groups.forEach(g=>{
    const nid=g.news_id, title=g.title||'未歸類', isUG=!nid;
    const originals=g.videos.filter(v=>v.source_type==='download');
    const cuts=g.videos.filter(v=>v.source_type==='cut');
    if(!originals.length && !cuts.length) return;
    totalOriginals+=originals.length; totalCuts+=cuts.length;
    const gid=nid||'ungrouped';
    h+=`<div class="video-group">
      <div class="video-group-header" onclick="toggleVGroup(this,'${gid}')">
        <span class="arrow">▶</span>`;
    if(!isUG) h+=`<a href="?news_id=${nid}" style="color:var(--accent);text-decoration:none" onclick="event.stopPropagation()" title="在下載頁開啟">📰 ${nid}</a>`;
    else h+='📁';
    h+=`<span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0 .5rem">${title}</span>`;
    const cutsInfo=cuts.length?` +${cuts.length} 裁剪`:'';
    h+=`<span style="color:var(--dim);font-size:.75rem;font-weight:400">${originals.length+cuts.length} 部${cutsInfo}</span>`;
    h+=`</div><div class="video-group-body" style="display:none" id="vg-body-${gid}">`;
    originals.forEach(f=>{h+=_renderVideoItem(f);});
    cuts.forEach(f=>{h+=_renderVideoItem(f);});
    h+=`</div></div>`;
  });
  S('video-count').textContent=`(${totalOriginals} 原片${totalCuts?' +'+totalCuts+' 裁剪':''})`;
  S('video-list').innerHTML=h;
}
function toggleVGroup(el,gid){
  const body=S('vg-body-'+gid);
  if(!body) return;
  const open=body.style.display!=='none';
  body.style.display=open?'none':'block';
  el.querySelector('.arrow').textContent=open?'▶':'▼';
}
function _renderVideoItem(f){
  const isCut=f.source_type==='cut', isMissing=f.missing;
  const vid=f.id; // videos 表 ID
  const cutBadge=isCut
    ?`<span class="badge badge-cut">✂️ ${fmtCut(f.cut_start,f.cut_end)}</span>`
    :`<span class="badge badge-vid">📹 原片</span>`;
  let pushHtml='';
  if(f.push_status==='pushed') pushHtml='<span class="badge badge-vid">☁️ WD</span>';
  else if(f.push_status==='failed') pushHtml='<span class="badge badge-txt">❌ WD</span>';
  else if(!isMissing) pushHtml=`<button class="btn-sm push-btn" data-vid="${vid}" title="推送 WebDAV">☁️</button>`;
  if(!isMissing) pushHtml+=`<button class="btn-sm push-tg-btn" data-vid="${vid}" title="推送 Telegram">📤</button>`;
  const missingHtml=isMissing?'<span class="badge badge-txt">⚠️ 遺失</span>':'';
  return`<div class="video-item">${cutBadge}
    <span class="vname">${f.filename} ${missingHtml}</span>
    <span class="vsize">${f.size||''}</span>
    ${pushHtml}
    <span class="actions">
      ${isMissing?`<button class="btn-sm btn-danger" onclick="delVideo(${vid})">🗑</button>`:`
      <a href="/api/download-file/${encodeURIComponent(f.filename)}?dl=1" download><button class="btn-sm" title="下載">📥</button></a>
      <button class="btn-sm btn-outline" onclick="gotoVideo(${vid},${f.news_id||0})" title="播放">▶️</button>
      ${!isCut?`<button class="btn-sm btn-outline" onclick="cutVideo(${vid},${f.news_id||0})" title="裁剪">✂️</button>`:''}
      <button class="btn-sm btn-danger" onclick="delVideo(${vid})" title="刪除">🗑</button>`}
    </span></div>`;
}

// ── video_id 驅動操作 ──
function gotoVideo(vid,news_id){
  switchTab('download');
  updateURL({news_id:news_id,vid:String(vid)});
  return openVideo(vid,news_id);
}
function cutVideo(vid,news_id){
  switchTab('download');
  updateURL({news_id:news_id,vid:String(vid)});
  return openVideo(vid,news_id,true);
}
async function openVideo(vid,news_id,cutMode){
  const nid=String(news_id||getParam('news_id')||'');
  S('dl-input').value=nid;
  S('dl-info').style.display='block';
  if(nid&&nid!=='0'){
    try{
      const r=await fetch('/api/query-video',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:nid})});
      const d=await r.json();
      if(!d.error){
        currentVideoInfo=d;
        S('dl-title').textContent=d.title;
        S('dl-meta').innerHTML='<b>日期:</b> '+ (d.date||'?') +' &nbsp;|&nbsp; <b>時長:</b> '+(d.length?d.length+' 秒':'?')+' &nbsp;|&nbsp; <b>ID:</b> '+d.id;
        S('dl-content').textContent=d.content||'';
        S('dl-m3u8').textContent=d.m3u8_full||'';
        if(d.thumbnail){S('dl-thumb').src=d.thumbnail;S('dl-thumb').style.display='block'}else S('dl-thumb').style.display='none';
        if(d.m3u8_full)S('dl-preview-btn').style.display='';
        if(d.already_exists){S('dl-already').innerHTML='<span style="color:var(--ok)">✅ 已下載</span>';S('dl-go-btn').textContent='⬇️ 重新下載/裁剪';}
        else{S('dl-already').innerHTML='<span style="color:var(--dim)">⬇️ 尚未下載</span>';S('dl-go-btn').textContent='⬇️ 下載/裁剪';}
        renderVersions(d.downloaded_versions||[]);
      }
    }catch(e){}
  }
  // 查詢影片並播放
  if(vid){
    try{
      const r=await fetch(`/api/video-by-id/${vid}`);
      const v=await r.json();
      if(!v.error){
        const u=`${location.origin}/api/download-file/${encodeURIComponent(v.filename)}`;
        _showResultVideo(v.filename,u);
        if(cutMode){
          S('dl-cut-start').value='';S('dl-cut-end').value='';
          _flash('📋 在裁剪欄輸入時間後點「下載/裁剪」','info');
        }
      }
    }catch(e){}
  }
}
// 從下載頁版本列表操作
function versPlayV(vid){
  updateURL({vid:String(vid)});
  fetch(`/api/video-by-id/${vid}`).then(r=>r.json()).then(v=>{
    if(!v.error){
      const u=`${location.origin}/api/download-file/${encodeURIComponent(v.filename)}`;
      _showResultVideo(v.filename,u);
    }
  });
}
function versCutV(vid){
  updateURL({vid:String(vid)});
  S('dl-cut-start').value='';S('dl-cut-end').value='';
  _flash('📋 在裁剪欄輸入時間後點「下載/裁剪」','info');
}
function versPushV(vid){pushToWebdav(vid);}
function versPushTg(vid){pushToTg(vid);}
async function delVideo(vid){
  if(!confirm('確定刪除？'))return;
  await fetch(`/api/delete-video-by-id/${vid}`,{method:'DELETE'});
  if(S('tab-videos').classList.contains('active'))loadVideos();
  else if(currentVideoInfo)queryVideo();
}

// ── 推送 WebDAV ──
async function pushToWebdav(video_id,btn){
  if(btn)btn.disabled=true,btn.textContent='☁️…';
  try{
    const r=await fetch('/api/push-to-webdav',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:video_id})});
    const d=await r.json();
    if(d.ok){_flash(`✅ WebDAV: ${d.filename} (${d.size_mb} MB)`,'ok');if(btn)btn.textContent='☁️✅';}
    else {_flash('❌ WebDAV: '+(d.error||'失敗'),'err');if(btn)btn.textContent='☁️❌';}
  }catch(e){_flash('❌ '+e.message,'err');if(btn)btn.textContent='☁️❌';}
  if(btn)setTimeout(()=>{btn.disabled=false;btn.textContent='☁️'},2000);
}

// ── 推送 Telegram ──
async function pushToTg(video_id,btn){
  if(btn)btn.disabled=true,btn.textContent='📤…';
  try{
    const r=await fetch('/api/push-to-tg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:video_id})});
    const d=await r.json();
    if(d.ok){_flash(`✅ TG: ${d.filename} (${d.size_mb} MB)`,'ok');if(btn)btn.textContent='📤✅';}
    else {_flash('❌ TG: '+(d.error||'失敗'),'err');if(btn)btn.textContent='📤❌';}
  }catch(e){_flash('❌ '+e.message,'err');if(btn)btn.textContent='📤❌';}
  if(btn)setTimeout(()=>{btn.disabled=false;btn.textContent='📤'},2000);
}

// bind push buttons (video_id)
document.addEventListener('click',function(e){
  if(e.target.classList.contains('push-btn')){
    pushToWebdav(parseInt(e.target.dataset.vid),e.target);
  }
  if(e.target.classList.contains('push-tg-btn')){
    pushToTg(parseInt(e.target.dataset.vid),e.target);
  }
});

// ── 共用 ──
function fmtCut(cs,ce){
  if(cs==null&&ce==null)return'';
  const f=s=>{const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60);return`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`};
  return`${cs!=null?f(cs):'0'}-${ce!=null?f(ce):'尾'}`;
}
function fmtSize(b){if(!b||b===0)return'';const kb=b/1024;return kb>=1024?`${(kb/1024).toFixed(1)} MB`:`${kb.toFixed(0)} KB`;}
// ── 初始化 ──
(function(){
  const news_id=getParam('news_id');
  const vid=getParam('vid');
  if(news_id){
    switchTab('download');
    S('dl-input').value=news_id;
    // 查詢新聞資訊
    queryVideo();
    // 若指定了 vid，自動播放
    if(vid) setTimeout(()=>openVideo(parseInt(vid),news_id),300);
  }else{
    loadNews(1);
  }
})();
</script>
</body>
</html>"""



# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index(): return render_template_string(HTML)

# ── 新聞 API ─────────────────────────────────────────────
@app.route("/api/news")
def api_news():
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 15))
    search = request.args.get("search", "").strip()
    stype = request.args.get("stype", "search_news")
    vo = request.args.get("video_only", "0") == "1"
    date_filter = request.args.get("date", "").strip()
    category = request.args.get("category", "").strip()

    if search:
        result = query_search([search], stype, size, vo)
        if result.get("error"):
            return jsonify({"error": result["error"]})
        return jsonify({
            "items": [{"id": it["id"], "title": it.get("title",""), "date": it.get("date",""),
                       "video": it.get("video", False)} for it in result["items"]],
            "total": result["total"], "checked": result.get("checked", 0),
            "range": result.get("range", ""),
        })

    result = query_news_list(page, size, video_only=vo,
                             category=category,
                             date_filter=date_filter)
    if result.get("error"):
        return jsonify({"error": result["error"]})
    return jsonify({
        "items": [{"id": it["id"], "title": it.get("title",""), "date": it.get("date",""),
                   "video": bool(it.get("video"))} for it in result["items"]],
        "total": result["total"], "page": page, "page_size": result.get("page_size", size),
    })


# ── 影片查詢 API ─────────────────────────────────────────
@app.route("/api/query-video", methods=["POST"])
def api_query_video():
    data = request.get_json(silent=True) or {}
    inp = data.get("input", "").strip()
    if not inp:
        return jsonify({"error": "請輸入 TDM URL 或 ID"})

    nid = extract_id(inp)
    if not nid:
        return jsonify({"error": "無法解析 ID"})

    info = get_video_info(nid)
    if not info or not info.get("m3u8"):
        return jsonify({"error": f"ID {nid} 不含影片或不存在"})

    out_path = DOWNLOAD_DIR / f"{nid}_{safe_filename(info['title'])}.mp4"

    # 查詢該新聞所有已下載版本
    init_db()
    versions = get_videos_by_news_id(nid)

    return jsonify({
        "id": info["id"], "title": info["title"], "date": info.get("date",""),
        "length": info.get("length"), "content": info.get("content",""),
        "m3u8_full": info["m3u8_full"], "thumbnail": info.get("thumbnail",""),
        "already_exists": out_path.exists(),
        "file_path": str(out_path) if out_path.exists() else None,
        "downloaded_versions": [
            {"vid": v["id"], "filename": v["filename"],
             "source_type": v.get("source_type",""),
             "cut_start": v.get("cut_start"), "cut_end": v.get("cut_end"),
             "file_size": v.get("file_size"), "filepath": v.get("filepath"),
             "push_status": v.get("push_status"),
             "created_at": v.get("created_at")}
            for v in versions
        ],
    })


# ── 下載 API ─────────────────────────────────────────────
@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "請提供 URL"}), 400

    nid = extract_id(url)
    cut_start = data.get("cut_start", "").strip()
    cut_end = data.get("cut_end", "").strip()

    # 先查影片資訊
    title = "video"
    length = 0.0
    if nid:
        info = get_video_info(nid)
        if info:
            title = info["title"]
            length = float(info.get("length") or 0)
            if not info.get("m3u8"):
                return jsonify({"error": f"不含影片: {title}"}), 400

    # 解析裁剪
    cs_sec = None
    ce_sec = None
    try:
        if cut_start: cs_sec = parse_time(cut_start)
        if cut_end: ce_sec = parse_time(cut_end)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    cut_dur = (ce_sec - cs_sec) if (cs_sec is not None and ce_sec is not None) else None

    # 產出檔名
    safe = safe_filename(title)
    suffix = ""
    if cut_start or cut_end:
        s1 = fmt_cut_time(cs_sec or 0)
        s2 = fmt_cut_time(ce_sec) if cut_end else "end"
        suffix = f"_cut_{s1}_{s2}"
    out = str(DOWNLOAD_DIR / f"{nid or 'video'}_{safe}{suffix}.mp4")

    if Path(out).exists() and not data.get("overwrite"):
        size_mb = Path(out).stat().st_size / (1024 * 1024)
        return jsonify({"error": f"檔案已存在: {Path(out).name} ({size_mb:.1f} MB)"}), 409

    dl_id = str(uuid.uuid4())[:8]
    _downloads[dl_id] = {
        "status": "準備中", "pct": 10, "log": [f"標題: {title}"],
        "done": False, "ok": False, "filename": None}

    def _progress(status, pct, line):
        d = _downloads.get(dl_id)
        if d:
            if pct >= 0:
                d["status"] = status
                d["pct"] = min(95, pct)
            if line:
                d["log"].append(line)

    def _run():
        result = download_video(
            news_id=nid, url=url,
            cut_start=cs_sec, cut_dur=cut_dur,
            output=out, overwrite=data.get("overwrite", False),
            download_method="web",
            progress_callback=_progress,
        )
        d = _downloads.get(dl_id)
        if d:
            if result["ok"]:
                d["status"] = f"完成: {result['title']}"
                d["pct"] = 100; d["done"] = True; d["ok"] = True
                d["filename"] = result["filename"]
            else:
                d["status"] = "失敗"
                d["done"] = True; d["ok"] = False
                d["error"] = result.get("error", "未知")

    threading.Thread(target=_run, daemon=True).start()
    label = title
    if cut_start or cut_end:
        label += f" (裁剪 {cut_start or '0'}->{cut_end or '尾'})"
    return jsonify({"download_id": dl_id, "info": f"{label} ({length}s)"})


@app.route("/api/progress/<dl_id>")
def api_progress(dl_id):
    d = _downloads.get(dl_id)
    return jsonify(d) if d else (jsonify({"error": "找不到任務"}), 404)


# ── 裁剪 API ─────────────────────────────────────────────
@app.route("/api/trim", methods=["POST"])
def api_trim():
    data = request.get_json(silent=True) or {}
    fname = data.get("file", "").strip()
    start = data.get("start", "").strip()
    end = data.get("end", "").strip()
    if not fname or not start:
        return jsonify({"error": "請提供檔案名和開始時間"}), 400

    inp = DOWNLOAD_DIR / Path(fname).name
    if not inp.exists():
        return jsonify({"error": f"找不到: {Path(fname).name}"}), 404

    # 嘗試從檔名解析 news_id
    nid_match = re.match(r'^(\d{6,7})_', Path(fname).name)
    nid = nid_match.group(1) if nid_match else None

    result = trim_video(str(inp), start, end=end if end else None,
                        output_dir=DOWNLOAD_DIR, push_enabled=True,
                        news_id=nid)
    if result["ok"]:
        return jsonify({"ok": True, "filename": result["filename"],
                        "push_ok": result.get("push_ok", False)})
    else:
        return jsonify({"ok": False, "error": result["error"]})


# ── 影片管理 API ─────────────────────────────────────────
@app.route("/api/videos")
def api_videos():
    grouped = request.args.get("grouped") == "1"
    if grouped:
        return jsonify({"groups": get_grouped_videos()})
    return jsonify({"files": list_videos()})


@app.route("/api/videos-by-news/<news_id>")
def api_videos_by_news(news_id):
    init_db()
    versions = get_videos_by_news_id(news_id)
    return jsonify({"versions": versions})


@app.route("/api/video-by-id/<int:video_id>")
def api_video_by_id(video_id):
    init_db()
    v = get_video_by_id(video_id)
    if not v:
        return jsonify({"error": "找不到影片"}), 404
    return jsonify(v)


@app.route("/api/push-to-webdav", methods=["POST"])
def api_push_to_webdav():
    if not is_webdav_configured():
        return jsonify({"ok": False, "error": "WebDAV 未啟用或配置不完整"})

    data = request.get_json() or {}
    video_id = data.get("video_id")
    filename = data.get("filename", "")

    # 優先從 video_id 查檔案路徑
    if video_id:
        init_db()
        v = get_video_by_id(int(video_id))
        if v and v.get("filepath"):
            fp = Path(v["filepath"])
        else:
            return jsonify({"ok": False, "error": f"video_id={video_id} 找不到"})
    elif filename:
        fp = DOWNLOAD_DIR / Path(filename).name
        if not fp.exists():
            return jsonify({"ok": False, "error": f"檔案不存在: {filename}"})
    else:
        return jsonify({"ok": False, "error": "請提供 video_id 或 filename"})

    init_db()
    ok = push_to_webdav(str(fp))
    if ok:
        record_video(news_id="", title=fp.stem, filepath=str(fp),
                     source_type="download")
        update_video_push_status(fp.name, True, "")
    size_mb = fp.stat().st_size / (1024 * 1024)
    if ok:
        return jsonify({"ok": True, "filename": fp.name, "size_mb": round(size_mb, 1)})
    else:
        return jsonify({"ok": False, "error": "WebDAV 推送失敗"})


@app.route("/api/push-to-tg", methods=["POST"])
def api_push_to_tg():
    if not is_push_available():
        return jsonify({"ok": False, "error": "Telegram 推送不可用。請檢查 TG_TOKEN / TG_CHATID 配置及 python-telegram-bot 是否已安裝"})

    data = request.get_json() or {}
    video_id = data.get("video_id")
    filename = data.get("filename", "")

    if video_id:
        init_db()
        v = get_video_by_id(int(video_id))
        if v and v.get("filepath"):
            fp = Path(v["filepath"])
        else:
            return jsonify({"ok": False, "error": f"video_id={video_id} 找不到"})
    elif filename:
        fp = DOWNLOAD_DIR / Path(filename).name
        if not fp.exists():
            return jsonify({"ok": False, "error": f"檔案不存在: {filename}"})
    else:
        return jsonify({"ok": False, "error": "請提供 video_id 或 filename"})

    init_db()
    caption = fp.stem
    results = push_to_channels(str(fp), caption)

    all_ok = True
    details = []
    for ch_name, r in results.items():
        if r.get("success"):
            details.append(f"[{ch_name}] OK: {r.get('message', '')}")
        else:
            all_ok = False
            details.append(f"[{ch_name}] FAIL: {r.get('error', '')}")

    size_mb = fp.stat().st_size / (1024 * 1024)
    if all_ok:
        return jsonify({
            "ok": True, "filename": fp.name, "size_mb": round(size_mb, 1),
            "detail": "; ".join(details)
        })
    else:
        return jsonify({
            "ok": False,
            "error": "; ".join(details)
        })


@app.route("/api/download-file/<path:filename>")
def api_download_file(filename):
    fp = DOWNLOAD_DIR / Path(filename).name
    if not fp.exists():
        return jsonify({"error": "檔案不存在"}), 404
    as_attachment = request.args.get("dl") == "1"
    return send_file(str(fp), as_attachment=as_attachment)


@app.route("/api/delete-video/<path:filename>", methods=["DELETE"])
def api_delete_video(filename):
    # 支援 video_id 查詢：/api/delete-video/vid/123
    # 兼容舊 filename 路徑
    pass


@app.route("/api/delete-video-by-id/<int:video_id>", methods=["DELETE"])
def api_delete_video_by_id(video_id):
    init_db()
    v = get_video_by_id(video_id)
    if not v:
        return jsonify({"ok": False, "error": "找不到記錄"}), 404
    fp = Path(v.get("filepath", ""))
    if fp.exists():
        fp.unlink()
    # 從 videos 表移除
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return jsonify({"ok": True})


# ═══ 密碼保護路由 ═══

@app.route("/api/auth-check")
def api_auth_check():
    """檢查 Cookie 是否包含有效的認證 token。"""
    if not _AUTH_ENABLED:
        return jsonify({"ok": True, "enabled": False})
    token = request.cookies.get("tdmdo_auth", "")
    ok = token in _AUTH_TOKENS
    return jsonify({"ok": ok, "enabled": True})


@app.route("/auth", methods=["POST"])
def api_auth_login():
    """驗證密碼，設置認證 Cookie。"""
    if not _AUTH_PASSWORDS_RAW.strip():
        return jsonify({"ok": False, "error": "未設定密碼"}), 403

    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    token = hashlib.sha256(password.encode()).hexdigest()

    if token in _AUTH_TOKENS:
        resp = jsonify({"ok": True})
        resp.set_cookie(
            "tdmdo_auth", token,
            max_age=30 * 24 * 3600,   # 30 天
            httponly=True,
            samesite="Lax",
            # secure=True  # 若需 HTTPS 可取消註釋
        )
        return resp
    return jsonify({"ok": False, "error": "密碼錯誤"}), 401


@app.route("/auth/logout", methods=["POST"])
def api_auth_logout():
    """清除認證 Cookie。"""
    resp = jsonify({"ok": True})
    resp.delete_cookie("tdmdo_auth", path="/")
    return resp


# ─── main ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="TDMDO 網頁端")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    print(f"\n  TDMDO  http://{args.host}:{args.port}\n  下載目錄: {DOWNLOAD_DIR}")
    if _AUTH_ENABLED:
        print(f"  [AUTH] 密碼保護: 啟用 (密碼數: {len(_AUTH_TOKENS)})")
    else:
        print(f"  [AUTH] 密碼保護: 關閉")
    print()
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == "__main__":
    main()
