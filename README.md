# Lesson 7｜CRISP-DM Multiple Regression

物聯網應用與資料分析 HW2。兩個真實問題、同一套多元線性回歸流程，並提供任意CSV／公開網址的即時分析。

- **公開網站**：https://l7-crispdm-mr.vercel.app/
- **GitHub**：https://github.com/c2838/l7-crispdm-mr
- **狀態**：階段8公開功能與附件已驗收；階段9最終繳交準備中。GitHub／Vercel由使用者操作，尚未LMS提交。

## 兩個正式問題

| 問題 | 資料／輸入 | Target | 凍結代表與完整test |
|---|---|---|---|
| SGEMM GPU執行時間 | 241,600列；14個原始X、14 encoded | 四次Run平均時間，毫秒；四次Run不作X | SelectKBest 13欄後OLS；R² 0.409873，RMSE 285.227 ms |
| 學生葡萄牙語成績 | student-por 649列；32個原始X、41 encoded | G3，0～20分 | ElasticNet選G1／G2後OLS；R² 0.928986，RMSE 0.840分 |

GPU保留為原始特徵下加法式線性模型能力有限的案例；18.40%負時間預測及寬PI如實呈現。這不否定所有帶轉換／交互作用的線性模型。學生主版以已知G1／G2為前提，不能稱開學預警或因果效果。log時間與學生背景版為事先規劃的補充。

Kaggle來源：[GPU Runtime v4](https://www.kaggle.com/datasets/rupals/gpu-runtime)、[Student Alcohol Consumption v2](https://www.kaggle.com/datasets/uciml/student-alcohol-consumption)。已核對UCI原件，採CC BY 4.0歸屬與處理說明；詳見[來源與授權](docs/datasets/ATTRIBUTION.md)。原始輸入不含Target、純ID或dummy；32原始欄位與41編碼欄位分開計數。

## 操作與兩項加分

1. 頂部Dataset下拉切換GPU／Student；可探索五種選擇方法、既定k／參數、凍結模型比較、區間、診斷及單筆預測。
2. Custom Dataset Analysis可上傳CSV或載入公開HTTPS CSV，預覽後設定Target、排除X及群組，執行基準加五種選擇方法，真正重算九模型。可取消、單方法重試、查看CI／PI並下載結果JSON。

逐步示範、第三份真實資料與加分證據見[加分操作指南](docs/BONUS_DEMO.md)。兩項加分分別對應教師標示的總分1分／2分，實際評定由教師決定。

## 分析與架構

CRISP-DM六階段均在網站與報告說明。SelectKBest、RFE、Forward SFS、Lasso及ElasticNet執行選擇後重新擬合OLS；另列Mean baseline、全特徵OLS、Ridge／Lasso獨立預測模型。前處理與選擇限training fold；固定development／test，不依已揭露test重新挑模型。

原生HTML／CSS／ES modules／SVG前端，普通Python分析核心＋FastAPI薄層。Vercel以`vercel_app:app`為入口，`app.frontend`讓前端資源走CDN；每方法自足請求，不以instance記憶體冒充跨請求DB。上傳與結果只存在當次請求／瀏覽器，不自動保存到Git或NotebookLM。

限制：CSV 3.5MB、50～10,000列、來源最多100欄、原始X最多39／encoded最多64、每類別最多20類。單方法協作預算120秒；取消不保證native數值求解立即中止。係數CI、位置CI及個別PI分開標示；未修正選擇不確定性與群內相關，HC3不等同修復PI。詳見[API契約](docs/API_CONTRACT.md)、[推論格式](docs/INFERENCE_SCHEMA.md)、[部署與故障修正](docs/DEPLOYMENT.md)。

## 報告、資訊圖表與對話

網站Research & Deliverables提供三份PDF及NotebookLM核對摘要。階段9本機版為20頁報告、1頁A3圖表、108頁HW2對話；對話含36回合、204則公開訊息，截止本次階段9啟動與初始進度，後續提交紀錄不在本快照。只收錄本作業，不含Lecture6其他對話。階段9新附件發布前，公開站仍是階段8版本。

使用者實際操作NotebookLM並提供兩題回答；GPT依原文與來源核對後整合，各題摘要均超過100中文字。報告與網站明示GPT輔助與NotebookLM摘要，未將外部研究數值當成本作業成績。原始貼文／來源對話JSON僅本機保存，公開的是核對後摘要及待review的對話PDF。

## 驗證與目前公開版本

公開commit `6b7ec625d177cfa5228358d5659e4eba759f94cd`；release `ae136bfdd390000c956e9b54684727f7cf9244bc899fdc4ae6cf65616382bda6`。49項真實公開HTTP檢查涵蓋509靜態檔、第三資料上傳／URL、六請求九模型、錯誤及獨立完整test重算；另17項核對收尾四資產。瀏覽器實際操作、下載、取消重試及1280／390寬度已驗證；兩個有界並行請求均成功。

平台方案、Function記憶體與冷啟動instance身分無管理端證據，不宣稱已量測。Build機器資源不視為Function設定。完整紀錄見[階段8結果](docs/STAGE8_RESULTS.md)、[階段9檢查表](docs/STAGE9_RESULTS.md)及`artifacts/validation/stage8-public/`。功能成功不保證統計假設、外部族群效能或教師加分。

## 本機執行與重現

Python3.12，保留`requirements.txt`36個精確pin；完整開發鎖定見`requirements-dev.lock.txt`，不需要Node套件建置。已有本機環境時：

```sh
.venv/bin/python -B scripts/preview_stage6.py
```

開啟 http://127.0.0.1:8768/ ，Ctrl+C停止。頁面需HTTP載入，不能直接開index.html。新環境可用Python3.12建立獨立venv並安裝既有requirements；不提交`.venv`或任何憑證。

已執行72項單元測試及各階段獨立數值檢查；重現單元可用`.venv/bin/python -B -m unittest discover -s tests -q`。正式結果已存在，`run_stage3.py`／`run_stage4.py`不是日常網站啟動步驟；不要重建split、freeze或為追求分數覆寫test結果。網站靜態打包用`scripts/build_vercel_static.py`，產生的public與release不提交Git。

## 文件入口

- [作業需求矩陣](docs/REQUIREMENTS.md)、[完整計畫](docs/PLAN.md)、[決策紀錄](docs/DECISIONS.md)
- [資料稽核](docs/datasets/AUDIT_SUMMARY.md)、[模型結果](docs/STAGE4_RESULTS.md)、[前端結果](docs/STAGE5_RESULTS.md)
- [自訂分析](docs/STAGE6_RESULTS.md)、[NotebookLM入口](docs/notebooklm/START_HERE.md)
- [公開驗收](docs/STAGE8_RESULTS.md)、[最終繳交預覽](docs/SUBMISSION_PREVIEW.md)

`data/raw`、`data/processed`、歷史、研究原文、對話來源JSON、渲染暫存與提交壓縮包不進Function；授權與再散布範圍分開記錄。使用者上傳資料不作版本控制。
