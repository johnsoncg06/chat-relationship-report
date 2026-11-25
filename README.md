# 聊天關係報告（桌面 App）

把 LINE `.txt` / Instagram `.json` 聊天記錄拖進來，**在你自己的電腦上**算出親密度、浪漫訊號、關係區間、五維度、10+ 張圖表，以及未來 8 週的關係落點（相對可能性）與目前建議。資料不會上傳到任何地方。

## 使用

**直接下載（建議）**：到 Releases 或 Actions → 最新一次 build → 下載對應系統的執行檔，雙擊開啟。會自動打開瀏覽器介面（只有本機能連）。關掉黑色視窗即結束。

**從原始碼跑**（Python 3.10+）：

```bash
pip install -r requirements.txt
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
- `app.py`：本機網頁介面（標準函式庫 http.server）
- `scripts/`：chat_stats / score_intimacy / chat_charts / forecast / chat_dashboard（分析核心），anonymize / coding_stats（給 LLM 解讀用的輔助工具，App 內未使用）
- `.github/workflows/build.yml`：用 PyInstaller 打包 Windows / macOS / Linux 執行檔

## 隱私
`.gitignore` 已排除 `*.txt` 與分析輸出。**請勿把聊天記錄提交到 GitHub。**
