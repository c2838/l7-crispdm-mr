# 階段7結果：研究摘要、報告與本機交付

狀態：階段7的NotebookLM研究核對與本機附件整合已完成。使用者提供兩題實際回答，Agent在既有授權內修訂整合；公開repo／部署與加分驗收仍待階段8，最終對話／附件封存於繳交前更新。沒有push、雲端變更、NotebookLM外部寫入或LMS繳交。

## 研究輸入與核對

兩份使用者原始貼文逐位元保存於docs/notebooklm/received/，SHA記在review.json。REVIEWED_SUMMARIES.md包含GPU188字、學生200字（僅計中文字）的摘要、採用／未採用理由及12項具體修正。NotebookLM原文與GPT核對修訂清楚區分，不用Agent自行研究冒稱使用者實際輸出。

主要修正：學生實際為參考類別dummy編碼，五方法為SelectKBest／RFE／Forward SFS／Lasso selection／ElasticNet selection後OLS；GPU已完成固定訓練與test。A2的Sobol比例與3.4%誤差僅屬其研究設定，不能移植成本作業分數或R²上限。G1／G2是評量期；背景可用時點未全部證實，不補成期末或開學已知。

A1／B1官方字典、A2第8.3節（本機16頁PDF的12–14頁）與B2原始研究、官方方法文件已核對保留主張。B2為395筆數學資料／30背景，與本作業649筆葡萄牙語／G1G2不同；B3原2008全文未取得，不使用其內文。貼文沒有內部引用點擊對照，不能驗證NotebookLM編號的連結目標；保留原標記，正式文稿使用可獨立查閱的來源URL與章節。

## 已交付

| 產物 | 頁數 | 範圍與限制 |
|---|---:|---|
| 分析報告草稿 | 20 | 完整兩題CRISP-DM、模型／區間／診斷、研究摘要及係數CI附錄；待公開網址與repo驗收定稿 |
| A3資訊圖表 | 1 | 兩題結果、流程、功能、限制與研究協作狀態 |
| HW2本作業對話快照 | 53 | 122則實際公開訊息，至階段7開始時；內容保持，最終繳交前刷新 |

PDF在reports/output/pdf/，網站副本位於web/downloads/；可編輯來源及產生／檢查程式在reports/source/。網站新增NotebookLM Research，兩題摘要、決策及來源完整可讀，提供完整核對摘要下載。僅交付HW2對話，不恢復Lecture6；舊檔保留於本機可回復歷史。原始NotebookLM貼文、對話JSON與研究原PDF不加入公開下載區。

## 實際驗證

- 三份PDF合計74頁以Poppler重新渲染，168項PDF可讀／文字邊界／非空頁／凍結數字／連結／122則訊息完整性檢查成功。
- 新20頁報告與資訊圖表逐頁視覺檢視；研究頁16／17及資訊圖表另看完整尺寸，無裁切、重疊或缺字。53頁對話SHA未改，沿用先前相同位元內容的視覺審查，同時重跑渲染與文字檢查。
- 新報告17列原尺度係數及classical／HC3 CI與凍結JSON逐列核對，顯示精度內一致。
- 本機實際HTTP檢查9份下載，全部200且逐位元相同；已移除Lecture6連結回404，NotebookLM原始貼文不由靜態目錄提供。
- 實際瀏覽器驗證桌面摘要跳轉、兩題字數與三份PDF入口；390／320寬度無水平溢出。CSS SHA與16px body字級保留，先前各自滿版排版保持。
- 188受保護分析成果、493展示JSON、11分析／匯出程式SHA及selection-freeze均未改；未重訓或依test重選模型。

證據：artifacts/validation/notebooklm-integration.json、notebooklm-browser.json、stage7-{pdf-build,pdf-check,visual,web,web-http,appendix}.json及stage7-pdf-pages/。原生Save對話框未重測，下載內容以真實HTTP位元比對驗證；以上均為本機，不代表公開Vercel可用。

## 後續

階段8提案見STAGE8_PROPOSAL.md；尚未授權實作。先確認effective GitHub與Vercel目標、包裝與限制，再展示發布preview取得執行授權，最後以公開第三份CSV／URL操作驗收。對話／附件最終封存於後續變更結束後更新；不將本機完成當成已取得加分或已繳交。
