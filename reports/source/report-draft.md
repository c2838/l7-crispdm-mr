# L7 CRISP-DM Multiple Regression

01  /  ANALYSIS REPORT

兩份資料，一套可重現的分析流程



## 兩份資料，一套可重現的分析流程

物聯網應用與資料分析 HW2
Lesson 7 | CRISP-DM | Multiple Regression

本報告以SGEMM GPU時間與葡萄牙語學生成績為兩個正式問題，完成特徵選擇、多元線性回歸、固定測試集評估、區間及診斷，並以真實第三資料驗證自訂CSV分析。

正式問題 | 原始輸入 / 資料量 | 凍結代表的test結果

GPU運算時間 | 14 / 241,600列 | R² 0.4099
RMSE 285.227 ms

學生葡萄牙語G3 | 32 / 649列 | R² 0.9290
RMSE 0.840 分

本次分析的判斷

GPU保留為目前原始特徵加法式線性模型能力有限的案例；學生主模型以G1與G2保留較多預測資訊，但只支持回顧條件估計。兩題都以正確方法、評估隔離及忠實揭露限制為完成標準，不以提高R²重選test。

文件版本與未完成範圍

本機附件草稿，整理日期 2026-11-02（Asia/Taipei）。分析數字取自既有凍結JSON，未重新調模。使用者已提供兩題NotebookLM回答，摘要經來源核對修訂後整合；公開網站、原始碼repo及雲端驗收在階段8完成後定稿。此PDF尚非最終繳交版。

GPT協作：需求整理、分析程式、網站、驗證、文稿與版面由Agent協助。使用者決定資料、案例定位與階段範圍，並負責NotebookLM實際研究。

02  /  ANALYSIS REPORT

需求對照與實驗設計



## 需求對照與實驗設計

作業要求 | 本專案對應 | 目前狀態

Kaggle / 14-39原始輸入 | GPU 14；student-por 32 | 完成

線性回歸 / 特徵選擇 / 評估 | OLS、五種選擇、baseline與正則化比較 | 完成

預測圖含CI或PI | 係數CI、平均反應CI與個別觀測PI分開 | 本機完成

CRISP-DM六階段 | 兩題均記錄；Deployment含實際自訂API | 公開驗收待階段8

兩題下拉 / 任意Dataset加分 | 靜態正式成果 + 新CSV真正運算 | 本機完成；公開待驗收

NotebookLM / AI標示 | 兩題資料包及GPT協作說明 | 兩題回答已收到、摘要已核對

報告 / 資訊圖表 / 對話PDF | optional依使用者要求均製作 | 本機草稿；最終待更新

老師主文要求線性回歸與特徵選擇；九模型比較及共同OLS重擬合是本專案的實驗設計，不能把所有補充方法寫成教師強制要求。

Frozen的定義

先以development CV選各方法候選與主代表，保存selection-freeze.json，再進行final test評估。表格列各方法預先選定的勝出模型；上方其他k／參數屬development探索，不用已揭露test重新挑選。

03  /  ANALYSIS REPORT

資料理解、來源與輸入口徑



## 資料理解、來源與輸入口徑

項目 | GPU | 學生葡萄牙語

Kaggle版本 | rupals/gpu-runtime，v4 | uciml/student-alcohol-consumption，v2

原始來源 | UCI SGEMM，DOI C5MK70 | UCI Student Performance，DOI C5TG7T

樣本與缺值 | 241600列；無缺值 | 649列；無缺值

Target | 四次Run平均毫秒 | G3，0-20分

有效原始X | 14個GPU設定；Run全部排除 | 30背景欄位 + G1 / G2

編碼後X | 14 | 41（主版本）；不含截距

來源核對 | 與UCI原檔逐位元相同 | 與UCI解析值一致，CSV格式不同

正式資料原值不修改。Kaggle鏡像的授權標籤與UCI原始CC BY 4.0分開記錄，保留原作者及來源。Target、ID及編碼展開不能拿來湊14-39個原始特徵。來源與SHA見datasets-manifest.json。[A1/A3/B1/B4]

可用資訊與用途

GPU的四個Run是Target來源，若放進X會直接洩漏答案。學生G1／G2是前兩期成績，可用於已知前期評量後的條件估計；問卷與absences時點未完全確認，因此即使移除G1／G2，也不直接宣稱開學預警。

04  /  ANALYSIS REPORT

資料準備與模型選擇流程



## 資料準備與模型選擇流程

步驟 | 實際處理

保留final test | GPU 193280 / 48320；學生519 / 130；固定索引，不為分數重切

Development CV | 外層五折；SFS內部三折；群組或重複X依規則隔離

每fold前處理 | 只用當次training資料學習填補、類別編碼、標準化；validation / test僅轉換

調參與選擇 | CV驗證預測誤差合併計算RMSE；同分優先較少平均特徵數，再固定ID

最終模型 | 用完整development重作選取／擬合，凍結後僅評固定test

結果保存 | 36正式模型、四情境488候選、來源與程式SHA；不以test反向挑模型

CV是調參／選模型的依據，本身帶有選擇樂觀性，不能冒充外部驗證。測試集評估與development內模型診斷分開標示。[M3]

評估指標

MAE表示平均絕對誤差，MSE對大誤差較敏感，RMSE保留Target單位，R²以測試集變異為比較基準。不同題目的RMSE單位不同，不直接跨題排名。Adjusted R²標明development OLS與自由度；不把它當另一個test R²。

05  /  ANALYSIS REPORT

五種選擇方法與OLS的角色



## 五種選擇方法與OLS的角色

方法 | 候選控制 | 最後預測模型

SelectKBest | 單變量F評分，k逐一比較 | 選取欄位後OLS

RFE | 標準化OLS權重，遞迴移除，k逐一比較 | 選取欄位後OLS

Forward SFS | 內部CV逐步加入，k逐一比較 | 選取欄位後OLS

Lasso selection | α網格，保留非零係數 | 選取欄位後OLS

ElasticNet selection | α與L1 ratio網格，保留非零係數 | 選取欄位後OLS

OLS是普通最小平方法，也是sklearn LinearRegression使用的線性回歸估計方式。統一最終OLS有助比較不同選擇策略；另列Ridge／Lasso直接預測，以比較正則化係數的作用。[M1/M2]

與DIC2的差異

DIC2也有調α，但以係數排序後強制取前k個，可能納入零係數尾端。本次只保留實際非零係數（數值容差1e-10），k是結果，故不保證每個整數都出現。不是刪掉已跑完但分數不好的k。

Mean baseline不使用X，一律預測training的Target平均值；All-feature OLS使用全部X。前者檢查是否優於猜平均，後者檢查選特徵是否改善表現或節省欄位。兩者不是特徵選擇演算法。

06  /  ANALYSIS REPORT

GPU：CRISP-DM與凍結方法比較



## GPU：CRISP-DM與凍結方法比較

Business：用GPU設定估計矩陣乘法執行時間；錯估可能導致錯誤的配置或資源規劃。成功標準是可重現流程與可信評估，不宣稱能取代硬體量測。

Understanding / Preparation：241600設定、14X、四次Run平均Target；固定development / test，所有轉換與選擇限training。Modeling：主代表為SelectKBest k=13再OLS，選擇依據為CV。

Method | Fields | CV RMSE | Test RMSE | Test R²

Mean baseline | 0 | 368.113 | 371.298 | -0.0000

All-feature OLS | 14 | 283.541 | 285.227 | 0.4099

SelectKBest -> OLS | 13 | 283.539 | 285.227 | 0.4099

RFE -> OLS | 13 | 283.539 | 285.227 | 0.4099

Forward SFS -> OLS | 13 | 283.539 | 285.227 | 0.4099

Lasso selection -> OLS | 13 | 283.540 | 285.227 | 0.4099

ElasticNet selection -> OLS | 13 | 283.540 | 285.227 | 0.4099

Ridge prediction | 14 | 283.541 | 285.227 | 0.4099

Lasso prediction | 14 | 283.540 | 285.229 | 0.4099

Evaluation：主代表test MAE=176.374 ms、MSE=81354.533 ms²、RMSE=285.227 ms、R²=0.409873。同子集合的不同流程可能得到相同test，但fold選取不同使CV略有差異。

Deployment：網站呈現公式、區間、診斷及用途限制；只能作同資料分布的探索，未經跨硬體驗證不能外推其他GPU。

07  /  ANALYSIS REPORT

GPU：區間與負時間的意義



## GPU：區間與負時間的意義

Figure A1. Frozen GPU representative. Sorted held-out predictions with conditional 95% intervals; full-test metrics are computed on all 48,320 rows.

Figure: artifacts/analysis/evaluation/sgemm/intervals.png

95%個別觀測PI描述性覆蓋 97.32%；平均寬度 1111.408 ms。平均反應CI平均寬度 9.379 ms，兩者不能混稱。

負點預測 8,892/48,320（18.40%），PI下界負值 44,349筆。執行時間不能為負，顯示目前加法線性形式與不受界限的誤差模型有實用限制；保留原值，不裁成零美化結果。

寬PI可能提高覆蓋，但不代表模型具有高解析度或未來一定覆蓋95%。本案例支持「目前形式能力有限」，不支持「任何多元線性回歸都不可能有效」。

08  /  ANALYSIS REPORT

GPU：假設診斷與用途限制



## GPU：假設診斷與用途限制

Figure A2. Development residuals, normal Q-Q and influence diagnostics. These observations diagnose the frozen model; they do not retune final test.

Figure: artifacts/analysis/evaluation/sgemm/diagnostics.png

殘差skew=3.530、excess kurtosis=19.242，Q-Q偏離及BP檢定揭示誤差形狀／等變異限制。p值低於浮點解析度時不寫成精確機率零。最大VIF=1.266，condition number=1.697，不能把低VIF解讀為模型形式已正確。

Cook與leverage只作影響診斷；敏感度分析限development，不因test分數較差刪資料。參數配置資料也不等於隨機獨立的未來硬體實驗；沒有任意套用列序自相關檢定。

HC3可以補充係數／位置的不確定性，但不會自動修正傳統觀測PI、非線性、群內相關或選擇後推論。

09  /  ANALYSIS REPORT

學生：CRISP-DM與凍結方法比較



## 學生：CRISP-DM與凍結方法比較

Business：估計已知前期評量與背景條件下的G3，作模型比較及教學分析；不據此決定個別學生處置，也不宣稱因果或開學預警。

Understanding / Preparation：只用649筆student-por，不混入另一科的重複學生；主版32原始X／41編碼欄位。Modeling：ElasticNet非零選取後OLS為主代表，最終只保留G1與G2。

Method | Fields | CV RMSE | Test RMSE | Test R²

Mean baseline | 0 | 3.262 | 3.153 | -0.0001

All-feature OLS | 41 | 1.441 | 0.844 | 0.9284

SelectKBest -> OLS | 2 | 1.354 | 0.840 | 0.9290

RFE -> OLS | 2 | 1.354 | 0.840 | 0.9290

Forward SFS -> OLS | 1 | 1.367 | 0.849 | 0.9275

Lasso selection -> OLS | 2 | 1.354 | 0.840 | 0.9290

ElasticNet selection -> OLS | 2 | 1.354 | 0.840 | 0.9290

Ridge prediction | 41 | 1.441 | 0.845 | 0.9282

Lasso prediction | 41 | 1.398 | 0.829 | 0.9308

Evaluation：主代表test MAE=0.675分、MSE=0.706分²、RMSE=0.840分、R²=0.928986。Lasso prediction的test可較好，但不因此事後替換原先CV凍結的主代表。

Deployment：網站提供G1／G2條件試算、CI／PI及背景版本；可計算不等於可用於教育干預或跨校預測。

10  /  ANALYSIS REPORT

學生：預測區間與成績資訊



## 學生：預測區間與成績資訊

Figure B1. Frozen student representative. Test observations sorted by prediction; 95% mean-response CI and observation PI have different targets.

Figure: artifacts/analysis/evaluation/student/intervals.png

PI覆蓋 100.00%，僅130筆test；平均寬度 5.312分。平均反應CI平均寬度 0.361分。100%描述性覆蓋不等於未來100%正確，亦不證明全部假設成立。

G1／G2與G3高度相關，有助於已取得前期成績後估計期末表現；這個資訊條件需要在介面及報告中說清楚。係數是模型條件關聯，不能解讀成提高某次成績必然造成G3增加。

分數定義為0-20，OLS／PI不受此界限限制；超界輸出依原值呈現並提示，不在沒有評估的情況下裁切。

11  /  ANALYSIS REPORT

學生：診斷與移除前期成績的補充



## 學生：診斷與移除前期成績的補充

Figure B2. Development diagnostics of the two-predictor OLS. High held-out R² does not imply normality, equal variance or causal validity.

Figure: artifacts/analysis/evaluation/student/diagnostics.png

BP p=0.0002153，殘差skew=-3.100、excess kurtosis=18.627；G1／G2的VIF約3.867。兩所學校、樣本量與觀察性資料限制代表性；高R²不抵銷這些限制。

背景版本移除G1／G2，30原始／39編碼X，CV選k=7；test R²=0.3654、RMSE=2.511分。與主版的落差顯示前期成績資訊的重要性，不能用來證明單一背景欄位的因果效果。

背景版本也可能含學期內才完整可知的缺席等資訊；未確認時間點前仍不稱開學預測。影響點不直接刪除；其development敏感度只作限制說明。

12  /  ANALYSIS REPORT

補充情境與區間的三種意義



## 補充情境與區間的三種意義

預先規劃的情境 | CV主代表 / 選取數 | Test RMSE | Test R²

sgemm | SelectKBest -> OLS / 13 | 285.227 | 0.4099

sgemm_log | Forward SFS -> OLS / 10 | 287.779 | 0.3993

student | ElasticNet selection -> OLS / 2 | 0.840 | 0.9290

student_background | SelectKBest -> OLS / 7 | 2.511 | 0.3654

GPU log版本是先預測log時間再exp回轉換，沒有smearing校正，表示幾何位置，不是原尺度算術平均。本次其MAE較小、RMSE與R²並未全面優於原版；不挑單一指標宣稱全面改善。

區間 | 回答的問題 | 本作業界線

係數95% CI | 所選設計下的回歸係數不確定性 | classical與HC3分開；選擇後條件推論

平均反應95% CI | 這組X的條件平均反應在哪裡 | 不能用個別y的命中率驗證真實平均

個別觀測95% PI | 一筆新觀測可能落在哪裡 | 含殘差變異；通常更寬；依賴誤差模型

區間依相同最終OLS與前處理計算，獨立核對係數、covariance、Student-t與PI覆蓋。rank、自由度或變異不足時明示不可推論；正則化／Dummy不硬套OLS CI。名目95%不是預測正確率。[M4]

13  /  ANALYSIS REPORT

新CSV的真實分析與網站操作



## 新CSV的真實分析與網站操作

Figure C1. Actual local browser: third public dataset, six successful method requests and nine computed models. Scores are shown faithfully, including negative held-out R².

Figure: artifacts/validation/screenshots/stage6/final-six-methods.jpg

CSV上傳或公開HTTPS URL -> 預覽 -> 選Target／排除X／指定group -> 執行基準與五方法 -> 查看CV、完整test、公式、區間、診斷 -> 單筆預測及下載。換設定隔離舊結果；取消保留完成模型並可逐方法重試。

以UCI Parkinsons Telemonitoring真實5875列、16X及42名受試者驗證兩條路徑；群組隔離後4623 development／1252 test，九模型均真正重算。這是功能驗證，不是第三正式題或醫療可用性證明。

50_Startups另驗證50列、State類別、換Target及排除欄位，不能拿舊題預設JSON冒充第三資料分析。

14  /  ANALYSIS REPORT

部署架構、資源界線與隱私



## 部署架構、資源界線與隱私

層次 | 本機落地

Frontend | 原生HTML / CSS / ES modules / SVG，沿用DIC2版型；正式結果按需載入

Analysis | 一般Python核心，共用於CLI、正式資料與自訂資料

HTTP | FastAPI薄層；每方法自足請求，無跨instance歷史DB

URL取得 | 僅公開HTTPS 443；逐跳檢查DNS／固定公開IP／原host TLS與SNI

取消／並行 | instance互斥鎖由真正運算結束釋放；協作取消不保證立即停止求解

資料保留 | 當次請求與頁面記憶體；表單系統暫存關閉清理；可下載結果

CSV最多3,500,000 bytes，50-10000列，來源最多100欄、原始X最多39、encoded最多64、每類別最多20類。JSON單回應最多3,000,000 bytes；圖有界顯示，指標／覆蓋使用全test。每方法協作預算120秒；URL整體15秒。

部署目標為Vercel Hobby，但尚未公開部署。build大小、套件、實際runtime／冷啟動、並行總額、費用與公開新資料操作留待階段8驗證；不把本機速度當雲端保證。沒有Git push、雲端狀態變更或LMS繳交。

15  /  ANALYSIS REPORT

驗證證據與可重現性



## 驗證證據與可重現性

驗證 | 方法與判斷依據 | 實際結果

正式模型／區間 | 獨立NumPy / sklearn / Student-t核對，全test與凍結SHA | 279項；33原單元

正式前端推論 | Python對網站共用模組，含原尺度方程 | 3590數值；1891資料／公式核對

階段6單元 | 原33 + 39服務測試；傳輸失敗／deadline為受控測試 | 72成功

真實HTTP／資料 | 外部UCI HTTPS + localhost + CLI + 獨立重算 | 48成功；類別資料另14

新模型前端數值 | 18模型21案例；容差1e-7絕對 + 1e-8相對 | 129核對；最大誤差8.73e-11

瀏覽器與下載 | 真實上傳／URL／取消重試／390與320寬度；實際下載對HTTP | 31瀏覽器；2894數值差異0

驗證成功只表示軟體與計算符合所檢查契約，不證明統計假設成立、教育／醫療可用或公開服務已驗收。真實外部資料取得、localhost服務、受控失敗及未部署範圍分開保存。

selection-freeze SHA-256：
3a4fec9047f6e08b4eace272bd2f43d7fb4be1fb8356525549340561f15425f3

主要證據：artifacts/validation/stage4.json、stage5-data.json、stage5-prediction.json、stage6-{unit,http,teaching,prediction,browser,downloads,completion}.json。188受保護分析成果、493展示JSON及原始／處理資料保持原SHA。

16  /  ANALYSIS REPORT

NotebookLM研究：GPU執行時間



## NotebookLM研究：GPU執行時間

來源：使用者提供NotebookLM實際回答；以下經GPT核對、修訂整合，不是逐字原始輸出。原文與SHA保存在本機docs/notebooklm/received/與review.json。

研究摘要（超過100中文字）

SGEMM資料以14個GPU設定描述矩陣乘法效能，四次Run為毫秒計時結果，本作業以其平均作Target並排除於輸入。[A1] Ballester-Ripoll等人的相關研究使用對數時間、Tensor Train代理模型與Sobol敏感度分析；其模型的一階效應合計不到四分之一，提示交互作用值得考慮。[A2 §8.3] 但該研究的12080個設定與25次計時不同於本作業241600列、四次Run，不能把其變異比例或誤差當作本作業結果。據此，本作業保留原始特徵加法OLS作能力有限的案例，並忠實呈現已凍結的評分、負時間及區間限制；此定位不否定加入轉換或交互作用項的其他線性模型。

本作業採用／未採用

採14個設定與四次Run平均Target；以原始特徵OLS呈現限制，保留已完成的log補充分析。正式split為development 193280／test 48320，test R² 0.409873、RMSE 285.227 ms。

未實作Tensor Train／Sobol分析，也不依已揭露test新增高階調模；未採外部12080設定、25次計時或70/15/15切分，未把其3.4%相對誤差當成本作業分數。

研究結果與本次實驗的邊界

A2第8.3節位於本機16頁arXiv版本的PDF第12–14頁。其對數TT模型的Sobol比例不是本作業raw-time OLS的R²上限；保留相關機制提示，不用來定量證明本作業損失了75%變異。選特徵不新增交互作用項，但仍可能改變泛化表現。

本作業已完成193280／48320固定切分與訓練；原文「尚未訓練」已更正。GPU傳統95% PI實測覆蓋97.32%、平均寬1111.408 ms，需連同假設限制閱讀，不能說完全沒有區間資訊，也不保證未來有效。

[A1] UCI Dataset Information / Additional Variable Information；[A2] §8.3、Tables6–9，PDF pp12–14。完整URL見引用頁。

17  /  ANALYSIS REPORT

NotebookLM研究：學生葡萄牙語成績



## NotebookLM研究：學生葡萄牙語成績

研究摘要（超過100中文字）

UCI學生資料包含數學與葡萄牙語兩科；G1、G2為第一、第二評量期成績，G3為最後評量期的年度成績，前期成績與G3有強相關。[B1] Qiang等人的研究以395筆數學資料及30個背景特徵建立ANN，結合SHAP解釋與SPPE領域知識約束，提供預測能力與解釋性並重的既有解法。[B2 摘要／方法] 本作業採649筆葡萄牙語資料，主版本含G1／G2，另以背景版比較資訊差異；兩者不能直接移植該文的準確率或RMSE。本作業採參考類別dummy編碼與五種特徵選擇後OLS，不採ANN／SHAP／SPPE。由於背景欄位的可用時點未全部證實，結果僅作條件關聯分析，不宣稱開學預警或教育干預的因果效果。

本作業採用／未採用

採student-por 649列、G3 Target；主版本32原始X→41 encoded，背景版30→39。每個training fold內學習類別、dummy編碼與標準化；主代表選G1／G2後OLS，test R² 0.928986。

未採B2的Label Encoding、ANN、SHAP或SPPE；本作業五方法為SelectKBest、RFE、Forward SFS、Lasso與ElasticNet selection，皆接OLS。未讀取B3全文，不補寫其方法；不移植外部分數或宣稱因果效果。

核對修正與協作範圍

已修正原文的Label Encoding及五方法誤列。G1／G2是第一、第二評量期，不寫成兩個學期；背景欄位的收集時點沒有全部證實，不能自行補成期末已知。B2之編碼敏感度與分數只屬其數學資料實驗。

GPT協助需求、程式、分析、驗證、研究核對與排版；使用者決定範圍、保留GPU案例並實際操作NotebookLM。貼文未附內部引用點擊對照，因此只聲明已獨立核對保留主張，不冒稱已驗證其NotebookLM介面。

[B1] UCI Dataset Information / Additional Variable Information；[B2] DOI10.1038/s41598-026-40538-y，Abstract / Methodology / encoding sensitivity / Discussion。B3全文未取得，不使用內文。

尚待階段8：repo、公開部署與加分操作實證；最終繳交前更新對話／附件並逐頁檢查。研究摘要本機整合完成，不代表已公開或已繳交。

18  /  ANALYSIS REPORT

引用與資料來源



## 引用與資料來源

以下為可追溯的外部來源；頁碼／章節及取得限制另見docs/notebooklm/sources.json。研究主張與本作業計算分開。

[A1] Enrique Paredes; Rafael Ballester-Ripoll
SGEMM GPU kernel performance

https://archive.ics.uci.edu/dataset/440/sgemm+gpu+kernel+performance

[A2] Rafael Ballester-Ripoll; Enrique G. Paredes; Renato Pajarola (2017)
Sobol Tensor Trains for Global Sensitivity Analysis

https://arxiv.org/abs/1712.00233

[B1] Paulo Cortez (2008)
Student Performance

https://archive.ics.uci.edu/dataset/320/student+performance

[B2] Ming Qiang; Ziyang Liu; Ru Zhang (2026)
Explainable AI in education: integrating educational domain knowledge into the deep learning model for improved student performance prediction

https://pmc.ncbi.nlm.nih.gov/articles/PMC13004980/

[B3] Paulo Cortez; Alice Maria Goncalves Silva (2008)
Using Data Mining to Predict Secondary School Student Performance

https://www3.dsi.uminho.pt/pcortez/student.pdf

僅核對UCI書目；原作者／典藏全文未取得，不依此宣稱已核對全文方法。

[M1] scikit-learn developers
Linear Models

https://scikit-learn.org/stable/modules/linear_model.html

[M2] scikit-learn developers
Feature selection

https://scikit-learn.org/stable/modules/feature_selection.html

[M3] scikit-learn developers
Common pitfalls and recommended practices

https://scikit-learn.org/stable/common_pitfalls.html

[M4] statsmodels developers
OLSResults.get_prediction

https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.get_prediction.html

Kaggle來源：rupals/gpu-runtime（v4）、uciml/student-alcohol-consumption（v2）；原始字典與授權依UCI。[A3/B4]

作業正文：https://lms2020.nchu.edu.tw/course/homework/74761；本機唯讀快照artifacts/reference/lms-assignment.txt。第三驗證資料：Tsanas與Little，UCI Parkinsons Telemonitoring，DOI 10.24432/C5ZS3N，CC BY 4.0。

19  /  ANALYSIS REPORT

附錄A：GPU原尺度公式與係數



## 附錄A：GPU原尺度公式與係數

下表為完整development擬合的原尺度encoded OLS係數；非標準化係數。顯示值四捨五入，網站推論與JSON使用完整精度；所選設計與選擇後推論的條件限制仍成立。

runtime_mean_ms = -51.10389 + 3.31970 x MWG + 3.05277 x NWG + 5.19218 x KWG - 16.70985 x MDIMC - 16.33293 x NDIMC + 1.04918 x MDIMA + 1.06800 x NDIMB + 3.87688 x KWI - 1.42585 x VWM - 2.64559 x VWN - 9.43742 x STRM + 38.40582 x SA + 47.15202 x SB

Predictor | Coefficient | 95% classical CI | 95% HC3 CI

Intercept | -51.10389 | [-58.49019, -43.71758] | [-58.22147, -43.98630]

MWG | 3.31970 | [3.28656, 3.35284] | [3.28182, 3.35757]

NWG | 3.05277 | [3.01962, 3.08592] | [3.01471, 3.09083]

KWG | 5.19218 | [5.02520, 5.35915] | [5.01068, 5.37367]

MDIMC | -16.70985 | [-16.88502, -16.53468] | [-16.92002, -16.49968]

NDIMC | -16.33293 | [-16.50809, -16.15777] | [-16.54347, -16.12239]

MDIMA | 1.04918 | [0.90381, 1.19455] | [0.89735, 1.20102]

NDIMB | 1.06800 | [0.92264, 1.21336] | [0.91570, 1.22030]

KWI | 3.87688 | [3.45556, 4.29821] | [3.45555, 4.29822]

VWM | -1.42585 | [-2.15342, -0.69829] | [-2.32301, -0.52869]

VWN | -2.64559 | [-3.37301, -1.91818] | [-3.53033, -1.76086]

STRM | -9.43742 | [-11.96535, -6.90949] | [-11.96548, -6.90936]

SA | 38.40582 | [35.87787, 40.93377] | [35.88288, 40.92877]

SB | 47.15202 | [44.62408, 49.67996] | [44.62246, 49.68159]

係數描述在其他所選變數固定時的條件線性關係，不是因果效果。HC3調整係數／位置的標準誤，不能解讀為已修正個別觀測PI、群內相關或模型選擇不確定性。

數值來源：web/data/sgemm/e8bdf42a699b8cc8.json；係數與區間已於階段4／5獨立核對。

20  /  ANALYSIS REPORT

附錄B：學生原尺度公式與係數



## 附錄B：學生原尺度公式與係數

下表為完整development擬合的原尺度encoded OLS係數；非標準化係數。顯示值四捨五入，網站推論與JSON使用完整精度；所選設計與選擇後推論的條件限制仍成立。

G3 = -0.20432 + 0.15608 x G1 + 0.89167 x G2

Predictor | Coefficient | 95% classical CI | 95% HC3 CI

Intercept | -0.20432 | [-0.70790, 0.29926] | [-0.89123, 0.48259]

G1 | 0.15608 | [0.07382, 0.23834] | [0.06454, 0.24762]

G2 | 0.89167 | [0.81245, 0.97089] | [0.80117, 0.98217]

係數描述在其他所選變數固定時的條件線性關係，不是因果效果。HC3調整係數／位置的標準誤，不能解讀為已修正個別觀測PI、群內相關或模型選擇不確定性。

學生主代表的最終輸入只有G1與G2。這個方程以已知前期成績為前提，不代表僅靠開學背景可達到相同表現。

數值來源：web/data/student/4e91b01431a71eed.json；係數與區間已於階段4／5獨立核對。
