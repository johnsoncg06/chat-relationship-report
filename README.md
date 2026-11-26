# 聊天關係報告（桌面 App）

把 LINE `.txt` / Instagram `.json` 聊天記錄拖進來，**在你自己的電腦上**算出親密度、浪漫訊號、關係區間、五維度、10+ 張圖表，以及未來 8 週的關係落點（相對可能性）與目前建議。資料不會上傳到任何地方。

## 安裝

到 [Releases](../../releases) 下載：

| 系統 | 檔案 | 說明 |
|---|---|---|
| Windows | `ChatRelationshipReport-Windows-Setup.exe` | 安裝程式，可選桌面捷徑 |
| macOS（Apple Silicon，M1 以後） | `ChatRelationshipReport-macOS-arm64.dmg` | 開啟後把 App 拖進「Applications」 |
| macOS（Intel） | `ChatRelationshipReport-macOS-intel.dmg` | 同上 |

**第一次開啟的安全提示**：安裝檔沒有付費簽章，所以系統會警告。
- Windows：SmartScreen 出現時，點「其他資訊」→「仍要執行」。
- macOS：在 App 上按右鍵 →「打開」；若仍被擋，終端機執行 `xattr -cr /Applications/ChatRelationshipReport.app`。

App 會開成獨立視窗（用系統上的 Edge 或 Chrome；找不到就用預設瀏覽器），畫面只有本機能連。關掉視窗約 2 分鐘後會自動結束，也可按側邊欄的「結束程式」。

**還沒有 Release？** 到 Actions → `build-installers` → Run workflow，完成後在 Artifacts 下載。要正式發佈：`git tag v0.1.0 && git push --tags`。

**從原始碼跑**（Python 3.10+）：

```bash
# 不需要安裝任何套件（只用標準函式庫）
python app.py        # macOS 也可雙擊 run.command，Windows 雙擊 run.bat
```

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
- 目前只用合成資料測試過；真實匯出檔的格式差異（語系、舊版 LINE 格式）可能需要調整解析。

## 專案結構
- `app.py`：本機伺服器與視窗啟動；`web/index.html`：介面（深色、側邊欄分頁）
- `installer.iss`：Windows 安裝程式（Inno Setup）；macOS 的 .dmg 由 workflow 用 hdiutil 產生
- `scripts/`：chat_stats / score_intimacy / chat_charts / forecast / chat_dashboard（分析核心），anonymize / coding_stats（給 LLM 解讀用的輔助工具，App 內未使用）
- `.github/workflows/build.yml`：PyInstaller 打包，產出 Windows 安裝檔與 macOS .dmg

## 隱私
`.gitignore` 已排除 `*.txt` 與分析輸出。**請勿把聊天記錄提交到 GitHub。**

## 發布流程（給維護者）

- 推到 `main`（改到程式、介面、腳本、圖示或 workflow）就會自動編譯 Windows、macOS arm64、macOS Intel。
- 每個平台都會做「自我檢查」：開啟 App、上傳一份合成聊天、跑完整流程；Windows 另外做 Defender 掃描。
- Windows 與 Apple 晶片版全部通過才發布新版本（版本號 v0.1.N 自動遞增，附 `SHA256SUMS.txt`）；Intel 版失敗不擋發布，但該版本會缺 `.dmg`。
- 只改 README 不會觸發編譯。要強制重編，到 Actions → build-installers → Run workflow。
- 自我檢查只證明「打得開、元件齊全」，取代不了實機測試。
