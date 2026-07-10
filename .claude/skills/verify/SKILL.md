---
name: verify
description: Runtime verification recipe for TDMDO CLI and Flask Web/API changes.
---

# TDMDO Runtime Verification

## Isolated Web server

Use process-level environment overrides so the real `.env` is not exposed or modified:

```bash
WEB_AUTH_ENABLED=true WEB_AUTH_PASSWORDS=qa-secret \
PUSH_ENABLED=false WEBDAV_ENABLED=false \
TDM_DB_PATH=<temp-db> TDM_DOWNLOAD_DIR=<temp-dir> \
python app/tdm_web.py --host 127.0.0.1 --port <port>
```

Drive the real surfaces:

1. Browser: unauthenticated `/` must show the login shell; login must reveal the main UI.
2. API: unauthenticated `/api/videos` returns 401; malformed query/body returns 400.
3. Generate a tiny local MP4 with ffmpeg, then POST `/api/trim` using `duration`; confirm the output appears in `/api/videos`.
4. Query `/api/news?video_only=1&size=1`, then POST `/api/query-video`; confirm the m3u8 URL is not duplicated/corrupted.

## Remote CLI

Run the real CLI against an isolated local HTTP mock and inspect captured requests:

```bash
python .claude/skills/tdm/scripts/tdm_tool.py news --server http://127.0.0.1:<port> --category local --limit 1
python .claude/skills/tdm/scripts/tdm_tool.py download --server http://127.0.0.1:<port> --id 1234567 --cut 20,30 --output qa.mp4 --push --push-target tg
python .claude/skills/tdm/scripts/tdm_tool.py trim --server http://127.0.0.1:<port> --input qa.mp4 --start 20 --duration 30 --output qa-cut.mp4
```

Expected payload fields are `cut_duration`, `duration`, `output`, `push`, `push_target`, and `target`.

For a password-protected real server, set `TDM_SERVER_PASSWORD` and confirm CLI login succeeds; missing or wrong passwords must exit nonzero.

## Safety

- Bind only to `127.0.0.1`.
- Set `PUSH_ENABLED=false` and `WEBDAV_ENABLED=false`.
- Do not perform large downloads or real Telegram/WebDAV sends.
- Stop local servers and delete temporary DB, media, cookie, response, and request-log files after verification.
