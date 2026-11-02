# Lesson 7｜CRISP-DM Multiple Regression

物聯網應用與資料分析 HW2。專案名稱代表 Lesson 7、CRISP-DM 與 Multiple Regression。

## 目前狀態

階段0與階段1資料稽核已完成；使用者確認改採SGEMM GPU時間（14輸入）與學生葡萄牙語成績（32輸入）。舊成衣／lattice題目已取代並保留歷史。階段2已完成獨立環境、本機效能與HTTP原型；採一般Python分析核心＋FastAPI薄層，以Vercel Hobby為部署目標，不建使用者結果資料庫。階段3已完成共用引擎、正式開發CV及凍結模型；階段4已完成36模型固定test評分、24個OLS區間、診斷與13張圖。階段5已完成本機互動網站與驗證；階段6已完成FastAPI本機服務、自訂CSV上傳／公開URL、六請求九模型與瀏覽器驗證。階段7已授權：NotebookLM資料包與附件草稿／對話快照已完成，使用者兩題回答已收到、核對摘要已整合；階段8～9待各階段確認，公開服務尚未部署。

## 目標

- 兩份Kaggle資料：SGEMM 14個有效原始輸入、student-por 32個有效原始輸入；使用者接受第二題32欄以優先提高完整性。
- 多元線性回歸、特徵選擇、完整CRISP-DM、模型評估、信賴與預測區間。
- 沿用DIC2排版，提供兩題切換、單筆預測、新CSV上傳／公開網址分析。
- GitHub與公開網站，以及完整報告、資訊圖表、對話PDF、NotebookLM研究摘要。

## 文件入口

- [需求對照表](docs/REQUIREMENTS.md)
- [完整規劃與Checklist](docs/PLAN.md)
- [決策與授權紀錄](docs/DECISIONS.md)
- [階段0環境唯讀基線](docs/environment-baseline.json)
- [階段0驗證](artifacts/validation/stage0.json)
- [階段1資料稽核摘要](docs/datasets/AUDIT_SUMMARY.md)
- [Dataset A：14個特徵](docs/datasets/dataset-a.md)
- [Dataset B：32個原始特徵](docs/datasets/dataset-b.md)
- [資料來源與授權](docs/datasets/ATTRIBUTION.md)
- [NotebookLM來源與提示詞](docs/NOTEBOOKLM_RESEARCH.md)
- [階段1驗證](artifacts/validation/stage1.json)
- [階段2實測結果](docs/STAGE2_RESULTS.md)
- [架構決策與運算預算](docs/ARCHITECTURE.md)
- [階段2驗證](artifacts/validation/stage2.json)
- [階段3正式開發結果](docs/STAGE3_RESULTS.md)
- [結果與模型格式](docs/RESULT_SCHEMA.md)
- [階段3驗證](artifacts/validation/stage3.json)
- [階段4正式測試與診斷結果](docs/STAGE4_RESULTS.md)
- [區間與診斷資料契約](docs/INFERENCE_SCHEMA.md)
- [階段4獨立驗證](artifacts/validation/stage4.json)
- [階段4圖表檢視](artifacts/validation/stage4-visual.json)
- [階段5網站與驗證結果](docs/STAGE5_RESULTS.md)
- [網站入口](web/index.html)（需透過本機HTTP預覽）
- [階段5數值核對](artifacts/validation/stage5-prediction.json)
- [階段5資料核對](artifacts/validation/stage5-data.json)
- [階段5瀏覽器驗證](artifacts/validation/stage5-browser.json)
- [階段6實作與驗證](docs/STAGE6_RESULTS.md)
- [自訂資料API契約](docs/API_CONTRACT.md)
- [階段6瀏覽器驗證](artifacts/validation/stage6-browser.json)
- [階段7資料包與附件進度](docs/STAGE7_RESULTS.md)
- [NotebookLM從這裡開始](docs/notebooklm/START_HERE.md)
- [階段8提案（尚未開始）](docs/STAGE8_PROPOSAL.md)
- [LMS正文快照](artifacts/reference/lms-assignment.txt)
- [專案協作規則](AGENTS.md)

## 目錄用途

- `docs/`：需求、規劃、決策與階段提案；目前不是GitHub Pages發布目錄，發布結構在後續決定。
- `data/raw/`、`data/processed/`：原始及處理版公開資料，預設不加入Git；授權與處理說明見docs/datasets/ATTRIBUTION.md。
- `artifacts/reference/`：作業來源證據。
- `artifacts/validation/`：實際驗證紀錄。
- `artifacts/analysis/`：目前兩題的data-audit資料品質與development EDA；models/已包含四個正式開發情境、CV比較與JSON模型；evaluation/包含固定test評分、完整預測、CI／PI與診斷。
- `artifacts/history/stage1-garment-lattice/`：已取代題目的文件與稽核快照；舊資料保留但不供正式分析使用，正式入口以目前manifest為準。

## 來源與部署狀態

- [作業說明](https://lms2020.nchu.edu.tw/course/homework/74761)：個人作業，占10%，頁面期限2026-11-04，允許遲交但未列扣分規則。
- [DIC2參考成果](https://c2838.github.io/L5V2/)只作版型與既有方法參考。
- 本專案GitHub儲存庫：尚未建立／設定。
- 本專案成果網址：尚未部署。

## 尚未執行

已建立.venv、鎖定套件並執行階段2效能／HTTP原型；階段3正式開發模型已訓練並凍結，階段4已完成固定final test、區間及診斷；本機網站已完成；已完成本機產品API／自訂Dataset分析；尚未初始化Git、推送、部署或繳交。後續只在對應階段獲確認後進行；不預設建立使用者歷史資料庫。


## 本機可重現性

Python版本見.python-version；部署runtime精確版本見requirements.txt；含本機HTTP／測量工具的完整環境見requirements-dev.lock.txt。目前.venv已實際建立並通過pip check。

效能原型：`.venv/bin/python -B scripts/benchmark_stage2.py --root . --output artifacts/feasibility/benchmarks`。HTTP原型：`.venv/bin/python -B scripts/probe_http_stage2.py --root .`。它們只供階段2驗證，未匯出正式模型、未評final test、未提供公開API。


## 正式分析入口

`.venv/bin/python -B scripts/run_stage3.py --scenario sgemm`（其他情境sgemm_log、student、student_background）。已存在result.json時會拒絕覆寫，需先明確保留舊結果；不改原始資料或固定切分。

單元驗證：`.venv/bin/python -B -m unittest discover -s tests -v`。目前整合核對：`.venv/bin/python -B scripts/verify_stage4.py --root .`。33項單元與279項獨立檢查已有實際成功證據，指令供重現，不需使用者再跑才算完成。

正式評估入口：`.venv/bin/python -B scripts/run_stage4.py --root .`，目前結果已存在，程式會拒絕覆寫。test已揭露，請保留本次正式成績；階段3舊驗證器會重建凍結紀錄，不應在此階段重新執行。圖表入口為scripts/render_stage4.py，13張已實際產出並檢視。


## 目前主要結果與限制

GPU原始時間代表test R²=0.409873、RMSE=285.227 ms；學生含前期成績代表R²=0.928986、RMSE=0.840分。95%個別PI的描述性覆蓋為97.32%及100%（學生僅130筆且平均PI寬5.31分），不等於未來覆蓋保證。GPU18.40%負點預測及異質變異／殘差形狀限制如實保留；log時間與背景資料版本為預先規劃的補充。詳細結果、CI語意及統計限制見階段4報告。


## GPU案例的呈現定位

使用者確認保留GPU作為原始特徵下加法式多元線性回歸能力有限的案例；重點為方法應用、實作、正確評估與忠實呈現，不以提高R²為目標擴充模型或更換資料。這不等於否定所有轉換或交互作用形式的線性模型。學生題與GPU題分別呈現各自結果與限制；學生高R²也不代表假設全部成立。網站已依此定位實作；正式報告與公開服務仍待後續階段。


## 本機網站預覽與驗證

在本專案執行`.venv/bin/python -B scripts/preview_stage6.py`，再開啟`http://127.0.0.1:8768/`；此為包含API的完整網站，Ctrl+C可停止。舊preview_stage5.py的8767僅靜態展示，不能執行自訂分析。工具只監聽本機並停用開發快取。網站使用ES modules及JSON，請透過HTTP而非直接開啟檔案。已實際執行預覽與驗收，這些指令供重現，無需使用者補跑才算完成。

前端數值核對：`node scripts/verify_stage5.mjs`（Volta Node，無需安裝npm套件）；候選資料獨立核對：`.venv/bin/python -B scripts/verify_stage5_data.py`。

網站採原生HTML／CSS／JavaScript與SVG，不依賴外部圖表CDN。488候選按需載入；CV探索與凍結test分區，避免用另一個k的公式假互動。輸入溢位曾被原生number欄位清成缺值，已改保留輸入字串並明確驗證；靜態快取以資產版本及預覽no-store解決。學生learning curve的小樣本rank限制也有明示。詳見階段5結果。

`web/data/`是正式公開資料衍生的展示成果，不包含使用者上傳資料；大型完整test CSV不隨首頁載入。GitHub／Vercel發布仍待preview與授權，不能把本機切換成功當作已取得加分。


## 自訂分析與階段6驗證

CSV上傳或公開HTTPS CSV → 預覽 → Target／X／群組設定 → Run Analysis → 九模型、CV、完整test、適用區間／診斷、單筆預測與JSON下載。新資料使用共用引擎實算，不依賴使用者歷史資料庫。設定變更清除舊結果；取消保留已完成模型，instance忙碌可稍後逐方法重試。

限制：CSV 3.5MB、50～10,000列、來源最多100欄、原始X最多39／encoded最多64、每類別最多20類；少於14個原始X明標教學資料。模型區間與群組資料限制、完整API／隱私見API_CONTRACT.md。

已執行的可重現驗證：`.venv/bin/python -B -m unittest discover -s tests -q`（72項）、啟動8768後執行`.venv/bin/python -B scripts/verify_stage6_http.py`（48項）、`scripts/verify_stage6_teaching.py`（14項），以及`node scripts/verify_stage6_prediction.mjs`（129數值）。HTTP／teaching腳本會重新運算並更新其驗證輸出，需先保存舊證據；它們不是使用者尚待執行的工作。實際瀏覽器另完成31項操作與真實下載的2,894個數值核對，全部詳見STAGE6_RESULTS.md。

本輪解決的架構問題：完全重複X與指定group需聯集隔離，避免只防一種洩漏；網址需固定已驗證IP、保留原host憑證並有整體socket deadline，避免DNS落差與慢速回應；取消後互斥鎖須由真正運算結束釋放，避免重疊分析；raw CSV大小與JSON回應上限分開，避免3～3.5MB合法CSV被誤擋；小係數用科學記號，避免顯示四捨五入誤導。

UCI第三份資料的上傳／URL已實測六方法九模型；50_Startups另驗證類別、50列下限及換Target／X。所有結論是本機實測，Vercel build、冷啟動與公開操作仍待階段8。PDF附件已在階段7製作草稿，NotebookLM實際回答與經核對摘要已整合。


## 階段7附件與NotebookLM

研究入口見docs/notebooklm/START_HERE.md，兩題提示詞與回傳模板已準備。使用者已完成研究並提供兩題回答，真實回答已收到，摘要經GPT核對修訂整合；原始貼文與修訂版分別保存。

reports/output/pdf/已有20頁報告草稿、1頁A3資訊圖表、53頁本作業HW2對話快照；可編輯來源與產生／檢查程式在reports/source/。三份共74頁已實際渲染，168項重新執行的自動核對與逐頁版面檢視見stage7-pdf-check.json及stage7-visual.json。本機網站Research & Deliverables可下載；研究已整合，報告尚待公開驗收，對話須在最後繳交前更新。

產生附件使用Codex獨立文件runtime與已存在的中文字型，沒有將reportlab／Poppler加進分析requirements或改動.venv。渲染暫存與研究原PDF不應包進Function；實際發布檔案清單在階段8preview再核對。


使用者追加桌面排版：正式模型的Coefficients & Conditional Inference與Single-sample Predictor已改為上下各自滿版，GPU／學生及手機3項實際瀏覽器檢查通過，見predictor-layout.json；其餘模型／資料／字級未改。係數附錄另有17項PDF顯示值對凍結JSON核對，差異在顯示精度內為0。
