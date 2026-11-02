# 階段1資料稽核：已核准的新組合

使用者確認「ok以這兩份資料為主」。本次改選SGEMM與學生表現，不進入階段2建模或環境安裝。原成衣／lattice資料與舊稽核保留追溯，不再是正式題目。

| 項目 | A：SGEMM | B：葡萄牙語學生表現 |
|---|---:|---:|
| 筆數 | 241600 | 649 |
| 原始輸入數 | 14 | 32 |
| Target | runtime_mean_ms | G3 |
| 缺值／無限值／重複列 | 0／0／0 | 0／0／0 |
| development | 193280 | 519 |
| final test | 48320 | 130 |
| 編碼後欄數初估，不含截距 | 14 | 41 |

方法：實際Kaggle檔案與UCI原檔比對；pandas／numpy檢查schema、缺值、重複、範圍；固定隨機保留20%；只在development計算分布與相關性。原始值不改動。GPU只定義四次計時平均Target，學生處理版保留原值。

判斷：兩題均在作業14～39個原始輸入範圍。B=32為使用者明確接受的取捨，並非達到舊35～39偏好。學生編碼後41欄須與原始32分開呈現。

限制：沒有訓練模型、R²、殘差診斷或區間覆蓋率。GPU可能非線性且CSV約14.35MB，線上運算／上傳仍須階段2實測。學生題目為回顧條件估計；問卷與缺席時點不支持提前預警宣稱。無須修復缺值不代表免除Data Preparation或統計診斷。

證據：`artifacts/analysis/data-audit/summary.json`、各題schema／split／development EDA及`artifacts/validation/stage1.json`。舊快照：`artifacts/history/stage1-garment-lattice/`；舊raw與processed檔保留，正式入口以目前manifest為準。
