# 兩項加分操作與真實證據

公開網站：https://l7-crispdm-mr.vercel.app/
原始碼：https://github.com/c2838/l7-crispdm-mr

## 加總分1分：兩題下拉

1. 首頁右上Dataset選擇「01 · GPU Runtime」，確認14個原始輸入，R² 0.4099、RMSE 285.23 ms。
2. 改選「02 · Student Performance」，確認32個原始輸入、41 encoded，R² 0.9290、RMSE 0.84分。
3. 可切換五種特徵選擇方法與既定候選，查看凍結比較表、CI／PI、診斷及單筆試算。探索不重新用test選勝出者。

已在公開瀏覽器實際切換並核對；不是只提供兩份截圖。

## 加總分2分：任意Dataset真正重算

第三份資料為UCI Parkinsons Telemonitoring，與兩份正式預設不同；5875列、22來源欄、42名受試者。

1. 點「Custom Dataset · 自訂分析」。Public HTTPS CSV URL貼上：

https://archive.ics.uci.edu/ml/machine-learning-databases/parkinsons/telemonitoring/parkinsons_updrs.data

2. 點「Load public CSV · 取得資料」，預覽應顯示5875列、22欄、0缺值、0完全重複列。也可下載同一公開檔案後，透過Upload CSV及Preview file上傳。
3. Numeric Target選`total_UPDRS`；Group identifier選`subject#`，同一受試者不可跨訓練／測試，group不作X。
4. Exclude勾選`age`、`sex`、`test_time`、`motor_UPDRS`；其餘保留，應有16個原始輸入。Target transformation保留Original scale。
5. 點Run Analysis；等待實際回應，完成時顯示「6/6 個方法請求成功，取得9個模型」。六請求為baseline、SelectKBest、RFE、Forward SFS、Lasso selection、ElasticNet selection；baseline一次包含mean、全特徵OLS、Ridge及Lasso prediction。
6. 查看比較表、群組隔離4623 development／1252 test、公式及適用區間；可切換模型、單筆預測，再點Download results JSON。此資料的負R²忠實保留，不當成醫療可用模型。
7. 若點Cancel，尚未送出的工作會停止；已送出的數值運算可能仍協作收尾。可逐方法Retry，忙碌時稍候重試，不能把部分完成稱全部成功。

不需登入、不依賴歷史DB，也沒有拿預設JSON冒充上傳分析。這份第三資料只作功能驗證，不當第三個正式問題。

## 證據與適用範圍

- `artifacts/validation/stage8-public/summary.json`：49項真實公開HTTP檢查、九模型完整test指標獨立重算。
- `browser.json`：公開瀏覽器6/6、九模型、下載、取消／重試、CSV／URL與排版。
- `concurrency.json`：兩個有界並行請求實際200，不是壓力測試。
- `final-assets.json`：階段8收尾新版文字／PDF與API17項核對。

第三資料原件指紋SHA-256：`f2c7d5025dec4e92e7feae367a5f7ccf58789a10ac6b54bdf15976c599f9dd39`。來源與歸屬：Tsanas, A. & Little, M. (2009). Parkinsons Telemonitoring. UCI. https://doi.org/10.24432/C5ZS3N ，CC BY 4.0，https://creativecommons.org/licenses/by/4.0/ 。驗證CSV原值未變，Target／X／group選擇如上。

兩項為作業標示的學期總分加分入口；最終分數及是否累加依教師評定。平台內部記憶體、冷啟動及實際方案尚未取得管理端證據。
