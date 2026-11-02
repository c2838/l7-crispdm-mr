# 自訂Dataset API契約

狀態：階段6本機實作並驗證；入口app.py，服務模組l7_service，靜態檔僅掛載web/。既有l7_analysis作共用分析核心，未改正式凍結成果。完整驗證見STAGE6_RESULTS.md。

## 路徑與輸入

| 路徑 | 請求 | 成功回應 |
|---|---|---|
| GET /api/health | 無 | status、pipeline、方法及大小限制 |
| POST /api/data/preview | multipart/form-data，唯一file | source SHA／bytes／rows、欄位型態／缺值／唯一值、前五列及提示 |
| POST /api/data/url | application/json，僅`{"url":"https://…/file.csv"}` | 經CSV驗證的原始text/csv；X-Dataset-SHA256、X-Source-Host、X-Redirect-Count |
| POST /api/analyze/{method} | multipart唯一file、options JSON字串、sha256 | 來源設定綁定、切分、CV候選、真正模型、完整test指標、適用推論與診斷 |

method只接受baseline、kbest、rfe、sfs、lasso_select、elasticnet_select。baseline回四模型，其餘各回一個選擇後OLS。無持久job ID或查詢歷史端點；每次請求帶完整CSV與設定，跨instance不依賴共享記憶體。

options：target（必要字串）、exclude（預設空陣列）、categorical（預設空陣列，指定數值欄視為類別）、group（字串或null）、target_transform（identity或log）、seed（固定0）。未知欄位及型態不符明確拒絕；sha256若提供必須與實際bytes一致。UI每次分析均傳來源SHA。

analysis_id以原始資料SHA、完整options及pipeline／CV版本產生；清單順序不同可能產生不同ID，屬保守隔離，不表示數值一定不同。瀏覽器固定排序並核對每回應的data SHA／options／analysis_id，設定改變即隔離舊結果。

## 內容、資源與切分

CSV ≤3,500,000 bytes、整份POST ≤3,570,000 bytes、單JSON回應 ≤3,000,000 bytes；CSV URL成功回應為raw CSV，因此不受JSON上限誤限為3MB。URL請求body最多4,096 bytes，URL最多2,048字元。50～10,000列、2～100來源欄、1～39原始X、≤64編碼欄、每類別≤20類、有效類別字串≤256字元。相同／空／保留欄名、不等列寬、非UTF-8等明確拒絕，不截斷資料後假稱完成。

Target須非缺值、有限、非定值數字；log須全部大於0。X不可含無限值，全常數設計拒絕。X缺值與編碼限training fold；不以test擬合前處理。指定group與完全相同X以聯集形成不可拆組；group不作X。保留約20%群組／資料作test，development五折，SFS內部三折。每方法共用固定split，test不參與選擇。

120秒協作分析預算；前端等待上限240秒。thread內數值運算遇到deadline／取消檢查點才結束，不保證任何原生求解能立即中止。每instance一把互斥鎖，真正運算結束才釋放；忙碌409不代表平台全域限一工作。

## 回應與失敗語意

HTTP 200分析可為completed或已明示的partial狀態，需看status與模型數，不以200直接當九模型全成功。前端六個請求狀態另有queued、running、succeeded、failed、cancelled等；只有預期模型與completed回應才標該方法成功。取消或局部失敗保留此前已成功模型，可逐方法重試；設定改變則清除。

錯誤格式為`{"status":"failed","error":{"code":"…","message":"…"}}`。主要狀態包含400格式錯誤、403不同origin、409忙碌、413內容／回應超限、415格式不支援、422資料或設定不適用；未知路徑／方法亦明確失敗。URL傳輸失敗依錯誤契約回報，不把HTML登入頁當CSV成功。

JSON非有限統計數值轉null並附不可用原因，不轉成0。rank／自由度／零殘差變異使推論不可用時，點預測仍與適用範圍分開呈現。正則化／Dummy不回OLS CI。傳統PI是有條件誤差模型推論；HC3只用係數／位置CI，不修正群組PI或選擇不確定性。log exp為幾何位置。

test圖最多1,000點，回應需縮小時可250點；metrics及PI coverage用全test。CV候選完整保留；回應仍超限則明確拒絕，不默默改訓練樣本或評分資料。

## 網址取得與隱私

只接受公開HTTPS 443，拒絕URL登入資訊、fragment、控制字元、私有／loopback／link-local／混合內網DNS。每次redirect重新檢查，最多三跳，固定連線到已驗證公開IP並核對實際peer；TLS依原host憑證及SNI驗證。無proxy／使用者cookie／token轉送。總15秒deadline可中斷socket；有Content-Length與串流大小限制；壓縮、HTML／PDF等不接受。

無歷史DB、無應用程式持久上傳儲存、無資料列log；multipart可能短暫使用系統暫存檔，請求表單關閉後清理。瀏覽器只保留當頁記憶體，可下載JSON但不寫localStorage。啟動腳本停用access log。正式資料JSON與公開驗證fixture有獨立來源，不混入使用者上傳。

公開部署的防濫用、平台日誌、並行總額、套件大小、冷啟動、request/runtime限制及帳號effective設定留待階段8實測。此契約不宣稱Vercel已上線。
