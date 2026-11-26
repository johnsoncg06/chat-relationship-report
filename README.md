# 暈船小狗偵測器（桌面 App，原名「聊天關係報告」）

把 LINE `.txt` / Instagram `.json` 聊天記錄拖進來，**在你自己的電腦上**算出親密度、浪漫訊號、關係區間、五維度、10+ 張圖表，以及未來 8 週的關係落點（相對可能性）與目前建議。資料不會上傳到任何地方。

## 下載最新版

[![最新版本](https://img.shields.io/github/v/release/johnsoncg06/chat-relationship-report?label=%E6%9C%80%E6%96%B0%E7%89%88%E6%9C%AC)](../../releases/latest)　[![建置狀態](https://github.com/johnsoncg06/chat-relationship-report/actions/workflows/build.yml/badge.svg)](../../actions/workflows/build.yml)

下面的連結永遠指向**最新版**，不用自己找版本號：

| 系統 | 下載 | 大小 |
|---|---|---|
| Windows 10 / 11 | [ChatRelationshipReport-Windows-Setup.exe](https://github.com/johnsoncg06/chat-relationship-report/releases/latest/download/ChatRelationshipReport-Windows-Setup.exe) | 約 8 MB |
| macOS（Apple 晶片，M1 以後） | [ChatRelationshipReport-macOS-arm64.dmg](https://github.com/johnsoncg06/chat-relationship-report/releases/latest/download/ChatRelationshipReport-macOS-arm64.dmg) | 約 9 MB |
| macOS（Intel） | [ChatRelationshipReport-macOS-intel.dmg](https://github.com/johnsoncg06/chat-relationship-report/releases/latest/download/ChatRelationshipReport-macOS-intel.dmg) | 約 10 MB |

所有版本與更新紀錄在 [Releases](../../releases)。檔案的 SHA256 在每個版本的 `SHA256SUMS.txt`，可用來確認下載沒被改過。

**第一次開啟的安全提示**：安裝檔沒有付費簽章，系統會警告，這是預期的。
- Windows：SmartScreen 出現時，點「其他資訊」→「仍要執行」。
- macOS：在 App 上按右鍵 →「打開」；若仍被擋，終端機執行 `xattr -cr /Applications/ChatRelationshipReport.app`。

> Windows 版目前只在 CI 的虛擬機測過「能開、能跑完整流程」，還沒有在實體電腦上驗證安裝畫面。遇到問題請到 [Issues](../../issues) 回報（不要附聊天內容）。

**從原始碼跑**（Python 3.10+，不需要安裝任何套件）：

```bash
python app.py        # macOS 也可雙擊 run.command，Windows 雙擊 run.bat
```

## 說明文件

| 文件 | 內容 |
|---|---|
| [使用說明書](docs/MANUAL.md) | 安裝、匯出聊天記錄、操作步驟、怎麼看結果、常見問題 |
| [算法說明](docs/ALGORITHM.md) | 每個分數怎麼算、權重與門檻、預測方法、統計檢定、已知限制 |

App 會開成獨立視窗（用系統上的 Edge 或 Chrome；找不到就用預設瀏覽器），畫面只有本機能連。關掉視窗約 2 分鐘後會自動結束，也可按側邊欄的「結束程式」。

**歷史紀錄**：可指定一個資料夾存放每次的分析結果（不存聊天原文），之後做前後比對，並用過去的預測檢驗準不準。用法見[使用說明書](docs/MANUAL.md#5-歷史紀錄儲存前後比對回測)。

## 計算概要

一句話：把雙方的互動拆成可計數的指標（回覆速度、訊息量、話語長度、晚安、情感詞、沉默等），各自映射到 0–100 後加權，得到**親密度**與**浪漫訊號**，再依門檻落到關係區間。未來 8 週用趨勢模擬加上手設權重的 softmax 得到「相對可能性」。完整公式見[算法說明](docs/ALGORITHM.md)。

**請記住**：權重與門檻是經驗設定、沒有用大量真實資料校準；未來落點是啟發式分數，**不是機率**。

> **關於權重與證據等級**：每個指標都標有證據等級（台灣驗證／東亞參考／西方參考／未驗證），目前沒有任何指標經台灣聊天紀錄驗證。預設的 `tw` 權重依台灣貼圖與已讀習慣微調，詳見 [算法說明](docs/ALGORITHM.md#證據等級與台灣習慣微調)。

## 匯出聊天記錄
- **LINE**：聊天室右上角 ≡ → 設定 → 傳送聊天記錄 → .txt（建議用電腦版匯出）。
- **Instagram**：帳號中心 → 你的資訊和權限 → 匯出你的資訊 → 訊息 → 格式選 **JSON**，把 `message_*.json` 一起選取。
- 同一個人在 LINE 與 IG 都聊過：兩種檔一起選，並在「合併名字」填 `IG名=LINE名`。

## 分析前請先看「健檢警告」
機器人／系統帳號、資料不到 14 天、單日爆量、回覆速度不可用，都會在警告區顯示，信心會自動降為「低」。排錯人時用「排除機器人」欄位手動指定。

## 誠實的限制
- 只看文字；電話與見面看不到，分數是**下限估計**。
- 門檻是經驗設定，沒有用大樣本校準，不要說「超過 X% 的人」。
- 「未來落點」百分比是手設權重的**啟發式分數，不是真實機率**，沒有用真實關係結果驗證；請只看排名與區間寬度。
- 文字看不出性別與血緣：兄弟／姊妹／閨蜜統稱「摯友」，家人關係需本人確認。
- 不做臨床診斷或依附型態標籤；這是自我觀察與娛樂，不是心理或醫療建議。
- 已用一份真實的 LINE 匯出驗證解析，但其他語系、Android 版與舊版格式可能仍需調整。

## 專案結構
- `app.py`：本機伺服器與視窗啟動；`store.py`：歷史紀錄（儲存、比對、回測）；`web/index.html`：介面（深色、側邊欄分頁）
- `installer.iss`：Windows 安裝程式（Inno Setup）；macOS 的 .dmg 由 workflow 用 hdiutil 產生
- `scripts/`：chat_stats / score_intimacy / chat_charts / forecast / chat_dashboard（分析核心），`_lite.py`（統計函式）、`_svg.py`（繪圖）；anonymize / coding_stats 是給 LLM 解讀用的輔助工具，App 內未使用
- `docs/`：使用說明書與算法說明
- `.github/workflows/build.yml`：PyInstaller 打包，產出 Windows 安裝檔與 macOS .dmg

## 隱私
`.gitignore` 已排除 `*.txt` 與分析輸出。**請勿把聊天記錄提交到 GitHub。**

## 發布流程（給維護者）

- 推到 `main`（改到程式、介面、腳本、圖示或 workflow）就會自動編譯 Windows、macOS arm64、macOS Intel。
- 每個平台都會做「自我檢查」：開啟 App、上傳一份合成聊天、跑完整流程；Windows 另外做 Defender 掃描。
- Windows 與 Apple 晶片版全部通過才發布新版本（版本號 v0.1.N 自動遞增，附 `SHA256SUMS.txt`）；Intel 版失敗不擋發布，但該版本會缺 `.dmg`。
- 只改 README 或 `docs/` 不會觸發編譯。要強制重編，到 Actions → build-installers → Run workflow。
- 自我檢查只證明「打得開、元件齊全」，取代不了實機測試。
