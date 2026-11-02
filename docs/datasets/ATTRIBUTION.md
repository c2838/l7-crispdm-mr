# 資料來源、版本與授權

正式題目依`artifacts/reference/datasets-manifest.json`，僅SGEMM與student-por；原檔雜湊、UCI原件比對、metadata與字典均已保存。

## A：SGEMM

Paredes, E. & Ballester-Ripoll, R. (2017). SGEMM GPU kernel performance [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5MK70>。

Kaggle鏡像：<https://www.kaggle.com/datasets/rupals/gpu-runtime>，版本4，頁面授權標籤Other (specified in description)。依原始UCI CC BY 4.0保留作者、來源、授權與改作說明。原始18欄不改；處理版取14個設定並新增四次計時平均Target，排除四個答案欄位於輸入。

## B：學生表現

Cortez, P. (2008). Student Performance [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5TG7T>。

Kaggle鏡像：<https://www.kaggle.com/datasets/uciml/student-alcohol-consumption>，版本2，頁面標籤CC0: Public Domain；原始UCI明示CC BY 4.0，採原始作者歸屬及CC BY 4.0，不以鏡像CC0取代原條款。只選葡萄牙語649筆，數學資料未混入。處理版不改變觀測值。

## 共通

- CC BY 4.0：<https://creativecommons.org/licenses/by/4.0/>。後續網站、報告與公開資料包均須保留上述出處及處理說明。
- 公開資料不是使用者上傳私有資料；自訂上傳內容不可自動放入Git或NotebookLM。
- 尚未推送或公開再散布。本機保存與後續公開發布須分開記錄。
- 原成衣與lattice來源／授權保留於歷史快照，不能沿用為新題目的來源。
