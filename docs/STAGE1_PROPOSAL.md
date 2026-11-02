# 階段1：資料選定與稽核（已核准並更新）

原授權為「階段1 go」；使用者另同意「ok以這兩份資料為主」，核准新組合替換。

- [x] 正式A改為SGEMM GPU運算時間，14個原始設定，Target為四次執行時間平均（ms）。
- [x] 正式B改為student-por，32個原始輸入，G3為Target；接受第二題32欄的取捨。
- [x] 保存Kaggle版本、UCI原件、字典、來源授權及SHA-256；逐值比對。
- [x] 檢查缺值、無限值、重複、固定欄位、範圍；固定development／final test，僅development EDA。
- [x] 更新資料卡、manifest、需求、Checklist、協作規則、NotebookLM準備及階段2提案。
- [x] 原成衣／lattice資料保留，舊文件／稽核另存歷史快照，不作正式入口。

執行證據：`artifacts/validation/stage1.json`。未建立新環境、訓練模型、啟動API或公開服務。下一步見`STAGE2_PROPOSAL.md`，仍待使用者確認。
