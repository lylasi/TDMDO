---
name: vision
description: Vision — 開發者識圖工具。當你貼圖片、截圖、設計稿、錯誤訊息、架構圖時觸發。自動辨識圖片類型並提取對寫程式最有用的結構化資訊（程式碼轉錄、UI 規格、錯誤分析、架構還原）。特別適合搭配非 vision 模型使用。
argument-hint: "[image_path_or_url] [--mode auto|code|ui|error|diagram]"
---

# 👁️ Vision — 開發者識圖工具

**核心用途**：當你用的模型不支援視覺（如 deepseek-v4-pro），這個 skill 作為橋樑——把圖片發給專用視圖模型（grok-4.20-fast），提取所有對寫程式有用的資訊後回傳。

## 何時觸發

- **程式碼截圖**：用戶貼 IDE/編輯器截圖問「這段程式碼有什麼問題」「幫我改」「這個怎麼寫」
- **UI 設計稿**：用戶貼 Figma/設計稿截圖問「幫我實現這個頁面」「照這個做一個組件」
- **錯誤訊息**：用戶貼報錯截圖問「這個錯誤怎麼修」「為什麼會報錯」
- **架構圖/流程圖**：用戶貼圖表問「這個架構怎麼實現」「解釋這個流程」
- **終端輸出**：用戶貼命令列截圖
- **任何圖片**：用戶說「看這張圖」「分析這個」「這是什麼」

## 快速開始

```bash
# 自動模式（預設）— 自動判斷圖片類型，開發者視角詳盡提取
python .claude/skills/vision/scripts/vision_client.py screenshot.png

# 指定模式 — 針對性提取
python .claude/skills/vision/scripts/vision_client.py -m code main.py.png
python .claude/skills/vision/scripts/vision_client.py -m ui design.png
python .claude/skills/vision/scripts/vision_client.py -m error crash.png
python .claude/skills/vision/scripts/vision_client.py -m diagram arch.png

# 自訂問題 — 前面會自動加上開發者系統指示
python .claude/skills/vision/scripts/vision_client.py code.png -p "這段程式碼的 race condition 在哪？"

# 高解析度 — 截圖小字必用（code/ui/error 模式已預設 high）
python .claude/skills/vision/scripts/vision_client.py -d high screenshot.png
```

## 分析模式詳解

| 模式 | 參數 | 提取內容 |
|------|------|----------|
| 🔍 自動 | `--mode auto`（預設） | 自動辨識圖片類型，套用最佳策略 |
| 💻 程式碼 | `--mode code` | 逐行轉錄程式碼（保持縮排）、檔名/路徑、行號、IDE 上下文（Git 分支、頁籤、lint 標記、終端）、函數簽名 |
| 🎨 UI 設計 | `--mode ui` | 佈局結構、所有組件清單（類型/位置/狀態）、顏色表（hex）、字型表、間距、互動行為、響應式差異 |
| 🐛 錯誤 | `--mode error` | 錯誤類型與訊息、完整堆疊（每行檔案/行號/方法）、HTTP 上下文、環境資訊、根因與修復建議 |
| 📐 架構圖 | `--mode diagram` | 圖表類型、所有實體/節點、關係/連線、資料流、技術棧、實現指引（模組/目錄/API 建議） |
| 🔄 對比 | 多圖自動觸發 | 逐一分析後差異比較 |
| 📝 OCR | `--ocr` | 純文字提取，保持排版 |

## Claude 工作流程（必讀）

當用戶貼入圖片時，嚴格按以下步驟執行：

### Step 1：確定圖片路徑

**⚠️ 核心事實：Claude Code 貼上圖片時，圖片以 base64 嵌入 API 請求，不落盤。非視覺模型（如 deepseek-v4-pro）看不到圖片內容，需要 vision_client.py 從系統剪貼簿讀取圖片後發給視圖模型。**

**策略優先級：剪貼簿 → 目錄掃描 → 手動指定路徑/URL**

**1a. 剪貼簿模式（預設，推薦 — 處理 Claude Code 貼圖）**
```bash
# 無參數直接執行 → 自動從系統剪貼簿讀取圖片
python .claude/skills/vision/scripts/vision_client.py -m auto --raw

# 明確指定剪貼簿
python .claude/skills/vision/scripts/vision_client.py -c -m auto --raw
```
> Windows: 用 PowerShell `[System.Windows.Forms.Clipboard]::GetImage()` 讀取
> macOS: 用 `osascript` 讀取 `the clipboard as «class PNGf»`

**1b. 目錄掃描模式（備案 — 圖片已落盤時）**
```bash
# 掃描預設目錄（目前目錄 + $TEMP + .playwright-mcp/ + downloads/）
python .claude/skills/vision/scripts/vision_client.py -s --scan-age 10 -m auto --raw

# 指定掃描目錄
python .claude/skills/vision/scripts/vision_client.py -s --scan-dir downloads .playwright-mcp -m auto --raw
```

**1c. 手動指定路徑/URL**
```bash
python .claude/skills/vision/scripts/vision_client.py path/to/img.png -m auto --raw
python .claude/skills/vision/scripts/vision_client.py https://example.com/img.png -m auto --raw
```

**1d. 多張圖片** → 自動切換為 compare 模式

### Step 2：選擇模式
- 用戶未指定 → **永遠用 `--mode auto`**（預設），讓視圖模型自己判斷
- 用戶明確問程式碼 → `-m code`
- 用戶明確問 UI/設計 → `-m ui`
- 用戶明確問報錯 → `-m error`
- 用戶明確問架構/流程 → `-m diagram`
- 用戶問「圖片裡寫什麼字」→ `--ocr`
- 多張圖片 → 自動切 `compare` 模式

### Step 3：執行命令

**⚠️ 無法提供圖片路徑時，直接用無參數模式（自動從剪貼簿讀取）。**

```bash
# 🔥 最常用：用戶貼圖但未給路徑 → 自動從剪貼簿讀取
python .claude/skills/vision/scripts/vision_client.py -m auto --raw

# 用戶給檔案路徑或 URL
python .claude/skills/vision/scripts/vision_client.py <圖片路徑> -m auto --raw

# 用戶有具體問題，用 -p 傳入
python .claude/skills/vision/scripts/vision_client.py -m auto -p "用戶的具體問題" --raw

# 明確讀取剪貼簿
python .claude/skills/vision/scripts/vision_client.py -c -m auto --raw

# 一律加 --raw 避免 Windows 終端 emoji 編碼問題
```

### Step 4：處理結果
- **直接展示視圖模型回傳的完整分析結果給用戶**（不要摘要，不要截斷）
- 如果結果包含程式碼，用戶可以直接複製使用
- 如果結果包含 UI 規格，直接基於規格寫程式碼
- 如果結果包含錯誤分析，直接給修復方案
- **重要**：結果本身就是「餵給非 vision 模型的完整上下文」，不要再次摘要

## 完整參數說明

| 參數 | 說明 |
|------|------|
| `image` | 圖片來源：本地路徑、HTTP(S) URL、data URL。支援多個。**留空時自動從剪貼簿讀取** |
| `--mode, -m` | `auto`\|`code`\|`ui`\|`error`\|`diagram`\|`compare`\|`ocr`（預設 auto） |
| `--prompt, -p` | 自訂問題（自動加上開發者系統指示） |
| `--detail, -d` | `auto`\|`low`\|`high`。code/ui/error 模式預設 high |
| `--ocr, -o` | 純文字提取（等同 `--mode ocr`） |
| `--output, -f` | 寫入檔案 |
| `--raw, -r` | 純文字輸出，不加格式框（Windows 建議常用） |
| `--clipboard, -c` | 強制從系統剪貼簿讀取圖片（無參數時預設自動嘗試） |
| `--scan, -s` | 自動掃描目錄找最近圖片（備用方案） |
| `--scan-dir` | 指定掃描目錄（預設：目前目錄 + $TEMP + .playwright-mcp/ + downloads/） |
| `--scan-age` | 掃描時間範圍（分鐘，預設 10） |
| `--max-tokens` | 覆蓋 config.json 的 max_tokens |
| `--list-modes` | 列出所有模式 |

## 支援圖片格式

PNG, JPEG, JPG, GIF, WebP, BMP, SVG

## 設定

`config.json` 和 `.env` 已設定好，無需改動。如要更換 API 端點或模型，編輯 `config.json` 的 `model` 欄位。

## 最佳實踐

1. **截圖要完整**：擷取整個視窗/頁面，不要只截一部分，讓視圖模型有足夠上下文
2. **錯誤截圖要包含堆疊**：不要只截錯誤訊息那行
3. **程式碼截圖要包含頁籤**：這樣模型可以看到檔案名
4. **多張圖同時傳**：系統會自動切到 compare 模式做對比分析
