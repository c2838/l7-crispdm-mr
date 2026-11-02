# 階段8公開功能驗收與收尾

2026-11-03（Asia/Taipei）。使用者已自行部署；Agent僅執行公開功能測試與本機收尾，不push或操作Vercel。

## 公開功能驗收

- [x] 公開站 https://l7-crispdm-mr.vercel.app/ 首頁HTML200、API健康200。
- [x] 509靜態檔逐檔HTTP200，內容SHA符合部署release；包括493正式展示JSON與所有PDF／研究附件。
- [x] GPU／Student下拉實際切換，R²分別0.4099／0.9290。
- [x] 第三份真實UCI Parkinsons Telemonitoring，5875列；CSV上傳與公開HTTPS網址均可預覽。
- [x] Target=total_UPDRS，group=subject#，排除age、sex、test_time、motor_UPDRS，16個X；4623 development／1252 test，受試者隔離。
- [x] 公開六請求全部成功，共九模型；九模型全test指標由本機sklearn獨立重算一致。49項HTTP檢查通過。
- [x] 瀏覽器實際完成6/6與九模型，下載JSON含六份結果／九模型；取消與baseline單方法重試符合畫面狀態。
- [x] 私有網址、跨來源、指紋錯誤與不合法資料有明確錯誤；合法重試成功。
- [x] 1280／390寬度無整頁水平溢位；表格內部可捲動。
- [x] 兩個同時kbest請求均200且analysis_id一致；這僅是有界並行驗證，不是壓力測試。
- [x] 正式188受保護分析成果、493展示JSON及11個分析／匯出source指紋不變。

驗收部署release：9d3fd76d99ed3c9c1428f59f448b7d9a619a13f0ef0c0f108c93e2115338e841
本機Git HEAD：1234731f98644bf5722af175ddcf592dcddca287。
證據：artifacts/validation/stage8-public/{summary,browser,concurrency,static-http}.json。

## 本機收尾

- [x] 網站改列實際公開網址與GitHub，移除未建立／Local preview舊文字。
- [x] 報告20頁、A3資訊圖表1頁更新公開功能驗收；21頁全部渲染，文字邊界與視覺檢查通過。
- [x] 網站下載區同步兩份PDF，實際本機HTTP內容與檔案一致。
- [ ] 使用者commit／push收尾版本，Vercel部署後確認新文字及兩份PDF的SHA。
- [ ] 階段9待使用者核准；更新HW2對話快照、最終附件封存與繳交內容預覽。尚未LMS提交。

## 限制與未驗證範圍

無管理端資料，未證實實際帳號方案、Function記憶體、instance身分與冷啟動；Build機器2cores／8GB不當成Function設定。三次health與每方法時間只屬實際觀測，不標成冷啟動。公開release的vercel.json單一來源雜湊與本機不同，原因未確認；其餘runtime來源及所有靜態檔均一致，不宣稱設定檔完全一致。通過功能驗證不保證統計假設、醫療／教育可用性或教師加分。

收尾只更新文字、附件及驗收紀錄；不重新訓練、不修改test或既定代表。
