# 階段6結果：自訂Dataset實際分析

狀態：依使用者「階段 6 go」授權，已完成本機API、網站整合與實際驗證。公開平台與加分的公開操作驗收仍在階段8；未部署、未push、未操作NotebookLM或LMS。

## 已完成的使用流程

網站的Custom Dataset區塊支援原生檔案上傳與公開HTTPS CSV網址。讀取後顯示前五列、筆數、欄位型態、缺值、重複與來源SHA；可選數值Target、排除欄位、指定群組、將數值欄視為類別，或選擇正值Target的log補充。設定變更會清除舊結果，避免將不同X／y的模型混用。

基準請求實算Dummy、全特徵OLS、Ridge及Lasso預測；接著依序實算SelectKBest、RFE、Forward SFS、Lasso與ElasticNet選擇後的OLS，共六請求、九模型。使用既有l7_analysis，非預製JSON、非新資料換標題。各方法按development CV選定模型後評固定test；跨方法代表也只用CV，不依test挑選。

結果包含完整test MAE／MSE／RMSE／R²、CV比較、選定欄位、原尺度encoded公式、標準化／未標準化係數、適用OLS的classical／HC3係數CI、平均反應CI與觀測PI、覆蓋率與寬度、殘差／Q-Q／VIF／Cook等診斷，以及本次模型的單筆預測。Dummy／正則化模型不冒用OLS區間；rank、自由度或殘差變異不足時明確不可推論。log回轉換是幾何位置，不稱原尺度算術平均；很小的非零係數改用科學記號，避免公式顯示成零。

支援實際狀態、取消與單方法重試。取消保留已完成結果並停止後續請求；伺服器的在途數值求解只在協作檢查點結束。忙碌回應409會提示重試，不把部分完成稱為全部完成。下載JSON含來源、設定、各請求狀態及真正模型。正式兩題維持獨立展示，自訂資料失敗不影響原結果。全站先前放大2px的字級保留。

## 資料、資源與區間界線

- UTF-8（可含BOM）的逗號、分號或tab分隔CSV；50～10,000列、來源2～100欄、1～39個原始X、編碼後最多64欄（不含截距）、每類別最多20類、有效類別文字最多256字元。1～13個X明標教學用途，不冒充正式題目14～39特徵要求。
- CSV內容最多3,500,000 bytes；含表單的API請求最多3,570,000 bytes；單次JSON回應最多3,000,000 bytes。整份瀏覽器下載可彙整六次回應，故不受單次JSON上限限制。本次實際下載4,147,362 bytes。
- 每方法協作分析預算120秒，前端請求等待上限240秒；URL整體取得預算15秒、最多三次redirect。這些是應用程式預算，不是Vercel已驗證的保證。
- 約20%保留為test。指定群組與完全相同X列以聯集形成不可拆群組，避免split及CV跨組；按群組比例切分時列數不必恰為20%。群組不足時拒絕，不退回洩漏的隨機切分。
- development五折、SFS內部三折；編碼、填補、標準化、選擇、調參都在相應training fold。Target不填補、不靜默刪列；X缺值依training規則處理並明示。
- 圖最多顯示1,000個test點，必要時縮減為250點以滿足回應預算；評分與覆蓋使用全量test。CV圖查看候選不宣稱已重新擬合該候選的test模型。
- 群組隔離不等於誤差已獨立，傳統OLS區間未修正群內相關與選擇不確定性；HC3不是cluster-robust觀測PI。超出訓練範圍、未知類別與填補均提示，不靜默裁切預測。

## 真實新資料驗證

採用未預設的[UCI Parkinsons Telemonitoring](https://archive.ics.uci.edu/dataset/189/parkinsons+telemonitoring)，作者Tsanas與Little，DOI 10.24432/C5ZS3N；頁面列CC BY 4.0，公開驗證檔保留作者／來源與授權。這是功能驗證資料，不是第三個正式題目或使用者上傳歷史。

實際HTTPS取得911,261 bytes、5,875列、22欄、42名受試者；SHA-256為`f2c7d5025dec4e92e7feae367a5f7ccf58789a10ac6b54bdf15976c599f9dd39`。Target為total_UPDRS，以subject#分組，排除age、sex、test_time及另一輸出motor_UPDRS，使用16個聲音特徵。固定4,623 development／1,252 test，受試者不跨組。來源、公開測試檔見artifacts/validation/fixtures/stage6/。

瀏覽器原生上傳與公開URL兩條路徑均實際完成六請求／九模型，代表RFE預設輸入點預測同為28.0593。獨立HTTP實測六請求約0.2～12.7秒，最大單次回應516,044 bytes；僅代表此電腦此次實測。病人分組test的RFE R²約−0.2572、OLS約−0.4209；如實保留，不能解讀為醫療可用性證明。

另用作業提供的50_Startups真實公開CSV驗證50列下限、4個原始／5個編碼輸入及State類別；實際完成六請求九模型，換Target為Administration或排除Marketing Spend均重新計算且來源設定綁定改變。它曾出現在舊作業中，因此不拿它取代獨立第三份資料證明；不保存或再散布其raw CSV。

## 驗證方法、結果與證據

| 方法／實際範圍 | 預期與判斷基準 | 實際結果 | 證據 |
|---|---|---|---|
| Python單元測試；原33項加39項服務測試 | CSV／型態／群組／選擇隔離／錯誤狀態符合契約 | 72項成功；遠端失敗與deadline使用受控測試 | stage6-unit.json |
| 真實localhost HTTP＋真實UCI HTTPS＋獨立sklearn／NumPy／Student-t | 同來源、切分、全test指標、係數／covariance／PI、CLI及API一致 | 48項成功、9模型 | stage6-http.json、stage6-http/*.json |
| 真實50_Startups HTTPS＋HTTP／換設定 | 類別編碼、下限、Target／X變更真正生效 | 14項成功 | stage6-teaching.json、stage6-teaching/*.json |
| 網站共用JavaScript推論模組對Python與原尺度公式 | 點預測／CI／PI／未知類別／缺值在1e-7絕對＋1e-8相對容差內 | 18模型、21案例、129核對；最大絕對誤差8.73e-11 | stage6-prediction.json |
| 真實瀏覽器操作與390／320寬度 | 上傳／URL完整流程、九模型、取消／409／重試完成、換設定、log、鍵盤、無頁面橫溢 | 31項成功，2次測試斷言誤判已釐清，無未解失敗；最終分頁無console error | stage6-browser.json、screenshots/stage6/ |
| 實際瀏覽器下載檔獨立解析對HTTP結果 | 六成功／九模型、來源／X／y／切分與數值一致 | 10項成功、2,894數值、差異0 | stage6-downloads.json |

上述證據皆在artifacts/validation/。兩次瀏覽器斷言誤判分別是預期模型數寫錯，以及原生select需Enter才提交；保留失敗與修正紀錄，不刪除歷史。最終下載以實際瀏覽器儲存檔核對，非另行重建JSON；options排除欄位順序會影響保守fingerprint，因此CLI與UI的dataset_id不直接當等價判準，實際資料／設定欄位／切分及模型數值均另核對。

網址安全邊界的私有／混合DNS、redirect、連線固定IP／原host憑證、超限／壓縮／逾時等由受控測試驗證；真實瀏覽器另確認私有URL拒絕。失敗注入不冒充遠端成功。正式分析188個受保護成果、493個展示JSON與凍結SHA保持不變，最終完整性見stage6-completion.json。

## 隱私、啟動與未完成項目

未建結果資料庫，不記錄資料列、完整敏感URL或cookie/token。上傳解析器可能使用短暫系統暫存檔，表單關閉即清理，不承諾資料從未接觸暫存磁碟；沒有應用程式持久上傳儲存。瀏覽器結果限目前頁面記憶體，重新整理會清除，需自行下載。公開平台的log、保留及費用須階段8另核對。

本機啟動：在專案目錄執行`.venv/bin/python -B scripts/preview_stage6.py`，開啟`http://127.0.0.1:8768/`，Ctrl+C停止。8767舊靜態預覽不含API；請用8768驗證自訂分析。本輪已實際啟動、測試並於驗收後停止自己建立的8768服務；既有8767服務不受影響。指令供重現，不表示尚待使用者補跑。

階段7的NotebookLM實際研究、報告／資訊圖表／對話PDF待確認；階段8的Vercel實際build、套件大小、冷啟動、公開HTTPS與新資料操作均未驗證；尚未取得公開加分證據。下一階段見STAGE7_PROPOSAL.md。
