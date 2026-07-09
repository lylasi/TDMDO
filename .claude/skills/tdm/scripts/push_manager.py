# -*- coding: utf-8 -*-
"""
Push Manager — 通用推送模組（CLI & API 雙用）

支援通道:
  - Telegram (sendVideo / sendPhoto / sendDocument / sendMessage)
  未來可擴展: 微信、釘釘、Discord、Slack...

支援內容類型:
  - 純文字 (text)
  - 影片 (video)          — .mp4 / .mkv / .webm
  - 影片+文字 (video_caption) — 影片附 caption
  - 圖片 (image)          — .jpg / .png / .gif / .webp
  - 圖片+文字 (image_caption) — 圖片附 caption
  - 文件 (document)       — 任意檔案

環境變數（在 .env 中配置）:
  TG_TOKEN            — Telegram Bot Token
  TG_CHATID           — Telegram 聊天/群組/頻道 ID
  PUSH_ENABLED        — 是否啟用推送 (true/false，預設 true)
  PUSH_DEFAULT_TARGET — 預設推送目標 (tg / tg,wx)，預設 tg

用法:
  # 模組導入
  from push_manager import PushManager, push_text, push_video, push_image

  # CLI
  python push_manager.py --text "Hello"
  python push_manager.py --video video.mp4 --caption "新聞影片"
  python push_manager.py --image photo.jpg --caption "截圖"
"""

import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, List, Union
from dataclasses import dataclass

# ── .env 載入（相容 CLI & 模組導入）──
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    with open(_ENV_FILE, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHATID = os.getenv("TG_CHATID", "")
PUSH_ENABLED = os.getenv("PUSH_ENABLED", "true").lower() in ("true", "1", "yes")
PUSH_DEFAULT_TARGET = os.getenv("PUSH_DEFAULT_TARGET", "tg")

# 檔案大小限制 (Telegram Bot API)
TG_VIDEO_MAX_MB = 50       # sendVideo
TG_DOCUMENT_MAX_MB = 50    # sendDocument (Bot API)
TG_PHOTO_MAX_MB = 10       # sendPhoto

# 支援的媒體副檔名
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


# ═══════════════════════════════════════════════════════════
# 結果資料類
# ═══════════════════════════════════════════════════════════

@dataclass
class PushResult:
    """單通道推送結果。"""
    channel: str
    success: bool
    message: str = ""
    error: str = ""


# ═══════════════════════════════════════════════════════════
# 抽象通道
# ═══════════════════════════════════════════════════════════

class BaseChannel(ABC):
    """推送通道抽象基底類別。"""
    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        """檢查此通道是否已正確配置。"""
        ...

    @abstractmethod
    def send_text(self, text: str) -> PushResult:
        """發送純文字訊息。"""
        ...

    @abstractmethod
    def send_video(self, filepath: str, caption: str = "",
                   supports_streaming: bool = True) -> PushResult:
        """發送影片。"""
        ...

    @abstractmethod
    def send_image(self, filepath: str, caption: str = "") -> PushResult:
        """發送圖片。"""
        ...

    @abstractmethod
    def send_document(self, filepath: str, caption: str = "") -> PushResult:
        """發送文件（任意格式）。"""
        ...

    def _check_file(self, filepath: str) -> Optional[str]:
        """檢查檔案是否存在，回傳錯誤訊息或 None。"""
        if not filepath:
            return "未提供檔案路徑"
        if not Path(filepath).exists():
            return f"檔案不存在: {filepath}"
        return None

    def _check_size(self, filepath: str, max_mb: int) -> Optional[str]:
        """檢查檔案大小是否超限，回傳錯誤訊息或 None。"""
        size_mb = Path(filepath).stat().st_size / (1024 * 1024)
        if size_mb > max_mb:
            return f"檔案過大: {size_mb:.1f} MB (上限 {max_mb} MB)"
        return None


# ═══════════════════════════════════════════════════════════
# Telegram 通道
# ═══════════════════════════════════════════════════════════

class TelegramChannel(BaseChannel):
    """Telegram Bot API 推送通道。"""

    name = "telegram"

    def __init__(self, token: str = "", chat_id: str = ""):
        self._token = token or TG_TOKEN
        self._chat_id = chat_id or TG_CHATID
        self._bot = None
        self._available = False
        self._init_check()

    def _init_check(self):
        try:
            import telegram
            from telegram import Bot
            from telegram.request import HTTPXRequest
            from telegram.error import TelegramError
            self._telegram = telegram
            self._Bot = Bot
            self._HTTPXRequest = HTTPXRequest
            self._TelegramError = TelegramError
            self._available = True
        except ImportError:
            self._available = False

    def is_configured(self) -> bool:
        return self._available and bool(self._token) and bool(self._chat_id)

    def _get_bot(self):
        if self._bot is None and self._available:
            # v22.x 的 timeout 統一透過 HTTPXRequest 設定
            # media_write_timeout: 檔案上傳階段的寫入超時（50MB / 1MBps ≈ 50s，設 300s 留餘量）
            # read_timeout:        等 Telegram 回應的超時（大檔伺服器端處理可能較慢）
            # connect_timeout:     TCP 連線超時
            request = self._HTTPXRequest(
                media_write_timeout=300,
                read_timeout=180,
                connect_timeout=10,
            )
            self._bot = self._Bot(token=self._token, request=request)
        return self._bot

    def _config_error(self) -> PushResult:
        if not self._available:
            return PushResult("telegram", False, error="python-telegram-bot 未安裝，請執行: pip install python-telegram-bot")
        if not self._token or not self._chat_id:
            return PushResult("telegram", False, error="TG_TOKEN 或 TG_CHATID 未配置（請在 .env 中設定）")
        return PushResult("telegram", False, error="未知配置錯誤")

    # ── 文字 ──

    def send_text(self, text: str) -> PushResult:
        if not self.is_configured():
            return self._config_error()
        if not text:
            return PushResult("telegram", False, error="文字內容為空")
        try:
            bot = self._get_bot()
            import asyncio
            async def _send():
                await bot.send_message(chat_id=self._chat_id, text=text)
            asyncio.run(_send())
            return PushResult("telegram", True, message="文字已發送")
        except Exception as e:
            return PushResult("telegram", False, error=str(e))

    # ── 影片 ──

    def send_video(self, filepath: str, caption: str = "",
                   supports_streaming: bool = True) -> PushResult:
        if not self.is_configured():
            return self._config_error()

        err = self._check_file(filepath) or self._check_size(filepath, TG_VIDEO_MAX_MB)
        if err:
            # 超過 50MB → 自動降級為 send_document
            if "過大" in err:
                print(f"[Telegram] [!] {err}，自動改用 send_document 發送")
                return self.send_document(filepath, caption)
            return PushResult("telegram", False, error=err)

        try:
            bot = self._get_bot()
            import asyncio
            async def _send():
                with open(filepath, "rb") as f:
                    await bot.send_video(
                        chat_id=self._chat_id,
                        video=f,
                        caption=caption[:1024] if caption else "",
                        supports_streaming=supports_streaming,
                    )
            asyncio.run(_send())
            size_mb = Path(filepath).stat().st_size / (1024 * 1024)
            return PushResult("telegram", True, message=f"影片已發送 ({size_mb:.1f} MB)")
        except Exception as e:
            return PushResult("telegram", False, error=str(e))

    # ── 圖片 ──

    def send_image(self, filepath: str, caption: str = "") -> PushResult:
        if not self.is_configured():
            return self._config_error()

        err = self._check_file(filepath) or self._check_size(filepath, TG_PHOTO_MAX_MB)
        if err:
            # 超過 10MB → 自動降級為 send_document
            if "過大" in err:
                print(f"[Telegram] [!] {err}，自動改用 send_document 發送")
                return self.send_document(filepath, caption)
            return PushResult("telegram", False, error=err)

        try:
            bot = self._get_bot()
            import asyncio
            async def _send():
                with open(filepath, "rb") as f:
                    await bot.send_photo(
                        chat_id=self._chat_id,
                        photo=f,
                        caption=caption[:1024] if caption else "",
                    )
            asyncio.run(_send())
            return PushResult("telegram", True, message="圖片已發送")
        except Exception as e:
            return PushResult("telegram", False, error=str(e))

    # ── 文件 ──

    def send_document(self, filepath: str, caption: str = "") -> PushResult:
        if not self.is_configured():
            return self._config_error()

        err = self._check_file(filepath) or self._check_size(filepath, TG_DOCUMENT_MAX_MB)
        if err:
            return PushResult("telegram", False, error=err)

        try:
            bot = self._get_bot()
            import asyncio
            async def _send():
                with open(filepath, "rb") as f:
                    await bot.send_document(
                        chat_id=self._chat_id,
                        document=f,
                        caption=caption[:1024] if caption else "",
                    )
            asyncio.run(_send())
            size_mb = Path(filepath).stat().st_size / (1024 * 1024)
            return PushResult("telegram", True, message=f"文件已發送 ({size_mb:.1f} MB)")
        except Exception as e:
            return PushResult("telegram", False, error=str(e))


# ═══════════════════════════════════════════════════════════
# 通道登錄表（新增通道只需加一行）
# ═══════════════════════════════════════════════════════════

CHANNEL_REGISTRY: Dict[str, type] = {
    "tg": TelegramChannel,
    "telegram": TelegramChannel,
    # 未來擴展:
    # "wx": WeChatChannel,
    # "dd": DingTalkChannel,
    # "discord": DiscordChannel,
}


def _resolve_channels(targets: Union[str, List[str], None] = None) -> List[BaseChannel]:
    """解析目標通道字串 → 通道實例列表。"""
    if targets is None:
        targets = PUSH_DEFAULT_TARGET
    if isinstance(targets, str):
        targets = [t.strip() for t in targets.split(",") if t.strip()]

    channels = []
    for t in targets:
        cls = CHANNEL_REGISTRY.get(t.lower())
        if cls:
            channels.append(cls())
        else:
            print(f"[PushManager] ⚠️ 未知通道: '{t}'，已跳過（可用: {list(CHANNEL_REGISTRY.keys())}）")
    return channels


# ═══════════════════════════════════════════════════════════
# PushManager — 統一入口
# ═══════════════════════════════════════════════════════════

class PushManager:
    """通用推送管理器。"""

    def __init__(self, targets: Union[str, List[str], None] = None):
        self._channels = _resolve_channels(targets)

    @property
    def channels(self) -> List[BaseChannel]:
        return self._channels

    @property
    def available(self) -> bool:
        """是否至少有一個通道可用。"""
        return any(c.is_configured() for c in self._channels)

    def _push(self, method: str, *args, **kwargs) -> Dict[str, PushResult]:
        """通用推送方法，對所有可用通道執行指定操作。"""
        results = {}
        for ch in self._channels:
            if not ch.is_configured():
                results[ch.name] = PushResult(ch.name, False, error="通道未配置")
                continue
            func = getattr(ch, method)
            results[ch.name] = func(*args, **kwargs)
        return results

    def push_text(self, text: str) -> Dict[str, PushResult]:
        """推送純文字。"""
        return self._push("send_text", text)

    def push_video(self, filepath: str, caption: str = "") -> Dict[str, PushResult]:
        """推送影片，可選 caption。"""
        return self._push("send_video", filepath, caption)

    def push_image(self, filepath: str, caption: str = "") -> Dict[str, PushResult]:
        """推送圖片，可選 caption。"""
        return self._push("send_image", filepath, caption)

    def push_document(self, filepath: str, caption: str = "") -> Dict[str, PushResult]:
        """推送文件。"""
        return self._push("send_document", filepath, caption)

    def push_media(self, filepath: str, caption: str = "") -> Dict[str, PushResult]:
        """智能推送：根據副檔名自動選擇影片/圖片/文件。"""
        ext = Path(filepath).suffix.lower()
        if ext in VIDEO_EXTS:
            return self.push_video(filepath, caption)
        elif ext in IMAGE_EXTS:
            return self.push_image(filepath, caption)
        else:
            return self.push_document(filepath, caption)


# ═══════════════════════════════════════════════════════════
# 便捷函數（模組級別，直接導入使用）
# ═══════════════════════════════════════════════════════════

def push_text(text: str, targets: Union[str, List[str], None] = None) -> Dict[str, PushResult]:
    """便捷函數：推送純文字。"""
    return PushManager(targets).push_text(text)


def push_video(filepath: str, caption: str = "",
               targets: Union[str, List[str], None] = None) -> Dict[str, PushResult]:
    """便捷函數：推送影片。"""
    return PushManager(targets).push_video(filepath, caption)


def push_image(filepath: str, caption: str = "",
               targets: Union[str, List[str], None] = None) -> Dict[str, PushResult]:
    """便捷函數：推送圖片。"""
    return PushManager(targets).push_image(filepath, caption)


def push_media(filepath: str, caption: str = "",
               targets: Union[str, List[str], None] = None) -> Dict[str, PushResult]:
    """便捷函數：智能推送（自動判斷媒體類型）。"""
    return PushManager(targets).push_media(filepath, caption)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def _print_results(results: Dict[str, PushResult]):
    """格式化輸出推送結果。"""
    print()
    for name, r in results.items():
        icon = "[OK]" if r.success else "[FAIL]"
        detail = r.message if r.success else r.error
        print(f"  {icon} [{name}] {detail}")
    print()


def main():
    import argparse

    p = argparse.ArgumentParser(
        description="Push Manager — 通用推送工具（Telegram / 未來可擴展）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python push_manager.py --text "下載完成：世界盃16強.mp4"
  python push_manager.py --video video.mp4 --caption "新聞影片"
  python push_manager.py --image photo.jpg
  python push_manager.py --file report.pdf --caption "今日報表"
  python push_manager.py --video video.mp4 --target "tg"
        """,
    )
    p.add_argument("--target", default=PUSH_DEFAULT_TARGET,
                   help=f"推送目標通道，逗號分隔 (預設: {PUSH_DEFAULT_TARGET})")

    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="發送純文字")
    g.add_argument("--video", help="發送影片")
    g.add_argument("--image", help="發送圖片")
    g.add_argument("--file", help="發送文件（任意格式）")

    p.add_argument("--caption", default="", help="媒體說明文字（1024 字元內）")

    args = p.parse_args()

    if not PUSH_ENABLED:
        print("推送功能未啟用 (PUSH_ENABLED=false)")
        sys.exit(0)

    mgr = PushManager(args.target)

    if not mgr.available:
        print("❌ 無可用推送通道。請檢查:")
        print("   1. pip install python-telegram-bot")
        print("   2. .env 中設定 TG_TOKEN 和 TG_CHATID")
        sys.exit(1)

    if args.text:
        results = mgr.push_text(args.text)
    elif args.video:
        results = mgr.push_video(args.video, args.caption)
    elif args.image:
        results = mgr.push_image(args.image, args.caption)
    elif args.file:
        results = mgr.push_document(args.file, args.caption)

    _print_results(results)

    # 任一失敗則 exit 1
    if any(not r.success for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
