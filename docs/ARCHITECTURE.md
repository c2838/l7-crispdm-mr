# 階段2架構決策

決策狀態：本機證據支持的實作基準；公開服務驗證在階段8。使用者已同意以Hobby免費方案評估，尚未查實際帳號設定與剩餘額度。

## 結構與框架

1. 核心：一般Python模組，資料、前處理、特徵選擇、OLS、評估／區間與結果schema分開，可由CLI及HTTP共用。
2. HTTP：FastAPI薄層，處理CSV multipart、參數型態、錯誤與下載。原生handler的raw CSV可用，但相同上傳／驗證需要手動補齊；本機11項真實HTTP檢查支持採FastAPI。原型位於scripts/probe_http_stage2.py，不能作正式API直接發布。
3. 前端：延續DIC2版型，採HTML／CSS／JavaScript及所需圖表，這階段不引入Node框架或改動Volta。
4. 部署目標：單一Vercel專案，後續app.py匯出FastAPI app；public/靜態頁面、圖表資料及公開附件由CDN提供。API負責自訂運算與必要預測。不需要將整份GPU CSV從瀏覽器重新上傳。

官方支援FastAPI入口與public/ CDN：[FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)。本階段未建立app.py、vercel.json或雲端專案，候選設定僅保存於artifacts/feasibility/vercel-candidate.json。

## 分析與狀態

- 正式兩題：本機完整分析後保存版本化結果、來源SHA與模型資訊，老師開站即可看兩題；完整預測表及附件可由靜態檔提供，API圖表回應只含必要點位。
- 自訂CSV：資料預覽後，由瀏覽器依序送出基準及五方法的有界分析請求，攜帶相同CSV／Target／seed／設定及來源hash。每個請求自行計算並回傳該方法結果；後續請求不依賴上一個instance的記憶體或暫存檔。
- 本機正式批次與每個HTTP方法請求使用同一引擎及相同fold／前處理規則。前端依CV結果比較；final test只用於最終評估，不用於選方法、k或參數。
- queued／running／succeeded／failed／cancelled為瀏覽器中各方法的真實請求狀態；只有收到成功回應才算完成。重新整理會失去這次暫存結果，提供下載並明示，無跨裝置恢復承諾。
- 取消：停止後續方法並中止等待中的請求。已在雲端進行的數值求解不保證立即停止，須由deadline與候選／fold間的協作檢查結束；不能把前端Abort當作雲端程序已被殺掉。
- 單一瀏覽器一次只送一個方法；單一instance對CPU分析採互斥／忙碌回應，這不代表平台全域只有一個instance。部署前驗證記憶體與實際並行行為。

## 暫定運算預算

以下是由階段2代表性測量設定的工程預算，尚未在正式API與Vercel執行；階段3完整CV與階段6上線路徑實測後可再調整，不能默默截斷資料或縮減承諾的方法。

| 項目 | 初始規則 |
|---|---|
| 自訂檔案／URL內容 | 最多3500000 bytes，HTTP multipart另留空間；超限明確拒絕 |
| 筆數 | 50～10000；不足或超限明確提示，不抽樣冒充全量 |
| 原始輸入 | 最多39；14以下可作教學示範，標示不符正式題目最低特徵數 |
| 編碼後輸入 | 最多64，不含截距；類別展開超限要求使用者調整欄位 |
| 類別數 | 個別原始類別欄最多20類，同時受總編碼64限制；ID／高基數欄不得自動湊數 |
| 每方法分析 | 120秒協作deadline；Vercel候選maxDuration=240秒，給載入、URL、冷啟動及回傳留空間 |
| 公開URL | HTTPS、15秒有界下載、內容大小上限同上；階段6需實作private IP／redirect重驗等URL驗證，不能發布任意內網讀取端點 |
| API結果 | 每次JSON上限3000000 bytes；圖表最多2000顯示點，指標與覆蓋率仍計算完整保留集 |
| 方法與進度 | 五方法都保留；回傳實際已完成項目及未完成原因，逾時不宣稱完整比較成功 |

資源測試樣本恰好10000列、39原始／64編碼欄位，測過OLS及五方法；它只測資源路徑，並未驗證所有資料型態、共線性或正式完整網格。

## 特徵與統計口徑

- 五種選擇方法以編碼後模型欄位為單位，保留其原始欄位映射；同一類別的dummy可能部分選取。網站並列原始欄位數、編碼後欄位數與選取模型欄位數，不能混算。
- 學生32原始→目前development drop-first為41；各fold的實際轉換只從training學習，未知類別明示處理，選擇結果依名稱映射。
- GPU原始Target OLS為基準，log Target作training-only補充比較，反轉換點估計、平均CI／PI需正確解讀。學生含G1/G2主分析＋不含的30背景欄位敏感度分析，皆限回顧條件估計。
- Lasso／ElasticNet既作選特徵後重擬合OLS，也另有正則化預測比較；兩者分開命名。rank不足或自由度不夠不硬算推論。

## 資料保存、成本與回滾

不建立使用者結果資料庫、登入或持久工作排程。CSV與自訂結果只在當次瀏覽器／請求記憶體；必要的上傳暫存檔於請求內關閉，不靠shutdown hook保證長期清理。重新整理恢復若日後成為需求，才另提持久狀態方案。

Hobby官方目前為300秒、2GB／1vCPU與4.5MB請求／回應限制；本案採更小的工程預算。[Function限制](https://vercel.com/docs/functions/limitations)。標準Python bundle為500MB，本輪Linux wheels約369.8MB，應用與實際build額外尺寸仍待確認。[Python runtime](https://vercel.com/docs/functions/runtimes/python)。

費用目標為Hobby額度內USD0；不購買Pro、Blob或資料庫。Hobby有月度使用額度，尚未核對此帳號剩餘額度，因此不保證所有流量永久免費。[Hobby方案](https://vercel.com/docs/plans/hobby)。

回滾：本階段只新增本機環境、原型、鎖檔與文件；未有雲端變更。文件舊版保存stage2-before快照，原始資料與固定切分不改。部署階段另先確認實際目標、公開內容、排除項目、版本及回退方式後才發布。

若實際Hobby build、冷啟動或完整分析無法在預算內完成，先調整分方法的粒度與打包；若仍不行，再提Vercel前端＋常駐Python服務的具體平台與費用，獲確認後執行，不減少自訂分析或五方法。


## 階段6本機落地（最新）

app.py與l7_service已實作FastAPI薄層；scripts/preview_stage6.py在127.0.0.1:8768提供前後端。CSV／URL、分方法自足請求、共用引擎、真實狀態／取消／重試及來源綁定均有本機證據。資料／HTTP契約見API_CONTRACT.md，結果見STAGE6_RESULTS.md。

每instance互斥鎖由真正數值thread結束才釋放；不冒稱平台全域排程。group與相同X聯集形成不可拆組；URL用已核對IP＋原host TLS／SNI，總deadline可關閉socket。CSV上限3.5MB、POST 3.57MB、JSON 3MB分開處理；不使用跨請求結果DB。multipart短暫系統檔在表單關閉清理，沒有應用程式持久上傳儲存。新增來源最多100欄及有效類別字串最多256字元的資源護欄。

真實UCI 5,875列／16X／42group資料六請求本機約0.2～12.7秒，最大回應516,044 bytes；不代表Hobby冷啟動／平台並行與成本已通過。原正式資料／引擎及凍結結果不變，公開build／runtime／限制與替代方案留待階段8。
