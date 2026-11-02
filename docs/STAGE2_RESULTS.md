# 階段2實測與判斷

狀態：使用者回覆「階段 2 go」，已完成獨立環境、本機效能、HTTP路徑及部署可行性評估。另確認先以Hobby免費方案評估；未登入查實際帳號／專案設定，未公開部署。階段3未核准。

## 已執行與證據

- 新建本專案.venv，Python 3.12.14，不複製L5V2環境。runtime鎖定36個直接／間接依賴，開發工具另存requirements-dev.lock.txt；pip check無依賴衝突。
- 真實development資料18個案例：兩份各測載入、前處理、OLS、SelectKBest、RFE、Forward SFS、Lasso、ElasticNet，另GPU log Target與學生移除G1/G2各一例。
- 6個邊界資源案例：10000列、39個原始輸入、64個編碼欄位，使用固定seed產生的測試樣本。它不是正式第三份資料，也不能充當加分證據。
- 11項真實localhost HTTP檢查：原生raw CSV、FastAPI multipart、遺漏／不存在Target、參數邊界、3500001 bytes超限與下載標頭。兩個臨時伺服器已結束；不是公開API驗證。
- 真實HTTPS CSV來源測試：UCI student data.csv HTTP200，可讀649列33欄。僅連線／解析可行性，不拿這個全檔訓練或評分。
- 新.venv的matplotlib實際產圖，圖檔另行視覺核對。沒有正式模型匯出或final test分數。

## 代表性效能

| 測量資料 | OLS＋區間操作秒數 | Forward SFS操作秒數 | 該資料所有案例最高RSS MiB |
|---|---:|---:|---:|
| GPU：193280開發列 | 0.119 | 1.250 | 443.6 |
| 學生：519開發列 | 0.015 | 0.814 | 190.0 |
| 產生的資源測試樣本：10000列 | 0.057 | 6.546 | 243.8 |

量測在本機macOS ARM64，以每個案例獨立程序、BLAS及運算各單執行緒執行。操作秒數不含套件載入／CSV讀取／前處理；RSS含整個程序。每例完整wall、CPU、載入、前處理、warning及threadpool紀錄在artifacts/feasibility/benchmarks或stress。

第一個程序初次載入套件約26.34秒，之後案例多約1～1.5秒載入。這是本機觀察，不能作為Vercel冷啟動數字。方法表也不是完整五折外層CV、所有k、alpha／l1_ratio網格的總時間，階段3完成引擎後須重測完整流程。

SFS真實GPU案例k=7、3-fold、231次回歸；學生k=20、3-fold、1890次回歸。前處理按各CV training fold獨立擬合並快取，同fold候選共用其轉換，不讀validation值擬合。kbest／RFE以約半數編碼欄位測一次；Lasso／ElasticNet只測固定alpha=.001，不是調參結論。所有已測案例無ConvergenceWarning。

OLS與sklearn預測最大差異：GPU約7.41e-11、學生約3.20e-14；兩題設計矩陣含截距rank分別15／15、42／42。區間只核對可計算、有限值與PI寬度不小於平均CI；不代表殘差假設、名目覆蓋率或選擇後推論已驗證。

## 套件與平台

Linux x86_64、CPython3.12已鎖定的36個wheel均可下載，展開內容共369832759 bytes（約352.7 MiB）。48條Linux必要依賴metadata條件均滿足。這不是Linux程式執行測試或完整Vercel build；未包含應用、資料、生成bytecode與建置額外內容。

官方標準Python bundle上限500 MB，故目前有打包空間，但仍須排除.venv、歷史稽核、測試、原始資料與不必要附件，實際build尺寸才是最終驗收。來源見platform-reference.json與ARCHITECTURE.md。

## 判斷與未完成界線

採一般Python分析模組＋FastAPI薄HTTP層，先以Vercel Hobby為部署目標，採有界且無伺服器工作狀態的請求，不建使用者歷史資料庫。自訂分析先採分方法請求，由瀏覽器依實際完成結果追蹤進度；具體預算及取消語意見ARCHITECTURE.md。

正式資料的完整比較在本機預先產生，網站可直接展示；新CSV與公開URL仍須真的跑相同引擎，不以兩題快取結果冒充。部署前必須過實際Linux/Vercel build、公開HTTP、冷啟動、完整分析與上傳／URL測試；若不符合預算，改以Python常駐服務承接分析，保留兩項加分功能。
