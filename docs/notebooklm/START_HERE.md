# NotebookLM研究資料包：從這裡開始

狀態：使用者已提供兩題NotebookLM回答；經核對的摘要與修正見REVIEWED_SUMMARIES.md。以下保留原始操作指南；本指南與提示詞是Agent準備，並非NotebookLM原始產出。

## 你要完成的操作

1. 自行登入NotebookLM，建立「L7 GPU運算時間」與「L7 學生葡萄牙語成績」兩個筆記本，避免兩題來源混用。
2. GPU先加入A1 UCI資料頁與A2原始研究PDF／網址；學生先加入B1 UCI資料頁與B2公開全文。確認每份來源真的完成讀取。M1～M4可依需要加入，Kaggle主要作來源追蹤，不依賴它的登入頁作研究證據。
3. 將對應的A_GPU_PROMPT.txt或B_STUDENT_PROMPT.txt貼上提問。至少保留每題200～300中文字摘要、NotebookLM引用編號及原始頁碼／章節。
4. 依RETURN_TEMPLATE.md貼回兩題回答與引用。保留完整回答／匯出或畫面可供核對；不要只傳一段沒有引用的短結論。沒有成功讀到的來源要註明。
5. 我會核對引文、整理每題至少100字的研究摘要，再整合到報告與網站；你不需要叫NotebookLM重新跑程式。

不用將CSV、整份程式碼、對話紀錄或私人資料全部上傳；研究目標是同主題既有解法。CONTEXT是GPT整理的本作業設定，不能當成外部研究來源；正式資料數字來自凍結產物。

## GPU來源

- A1：[UCI原始資料與字典](https://archive.ics.uci.edu/dataset/440/sgemm+gpu+kernel+performance)。定義原始14欄與四次計時；原始資料CC BY 4.0。
- A2：Ballester-Ripoll、Paredes與Pajarola (2017)，[Sobol Tensor Trains for Global Sensitivity Analysis](https://arxiv.org/abs/1712.00233)，[PDF](https://arxiv.org/pdf/1712.00233)。優先看第8.3節，PDF第12～14頁。已取得原PDF，可使用本機research/sobol-tensor-trains-1712.00233.pdf自行匯入；只供研究，不複製到公開下載區。
- A3：[Kaggle鏡像](https://www.kaggle.com/datasets/rupals/gpu-runtime)，版本4與UCI原始值一致已於資料稽核核對。

重要差異：A2的GEMM實驗用12080個設定、各25次計時，與本作業241600列、四次Run平均不是同一實驗設定；可比較解法及限制，不能直接比較分數。

## 學生來源

- B1：[UCI原始資料與字典](https://archive.ics.uci.edu/dataset/320/student+performance)。G1／G2是前期成績、G3為期末；本作業用student-por。
- B2：Qiang、Liu與Zhang (2026)，[公開研究全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13004980/)，DOI 10.1038/s41598-026-40538-y。研究ANN／SHAP／SPPE，使用395筆數學成績與30背景特徵。研究的資料科目及資訊條件不同，不直接比較其分數；只分享原文連結，不再散布全文或圖表。
- B3（選讀，非必要）：Cortez與Silva (2008)，Using Data Mining to Predict Secondary School Student Performance。[作者PDF](https://www3.dsi.uminho.pt/pcortez/student.pdf)及[學校典藏](https://repositorium.sdum.uminho.pt/bitstream/1822/8024/1/student.pdf)。本輪只能從UCI核對書目，兩個全文入口未成功取得；不要以為已核對全文。若NotebookLM也讀不到，直接略過，使用B1與B2。
- B4：[Kaggle鏡像](https://www.kaggle.com/datasets/uciml/student-alcohol-consumption)，版本2，選student-por.csv。

## 共用方法來源

- M1：[scikit-learn Linear Models](https://scikit-learn.org/stable/modules/linear_model.html)，OLS、Ridge、Lasso、ElasticNet定義。
- M2：[Feature selection](https://scikit-learn.org/stable/modules/feature_selection.html)，固定k、RFE、SFS、L1非零選取的差別。
- M3：[Data leakage](https://scikit-learn.org/stable/common_pitfalls.html)，前處理與特徵選擇不能在test擬合。
- M4：[statsmodels prediction](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.get_prediction.html)，平均反應與觀測區間不同。

## 檔案與回傳

`A_GPU_PROMPT.txt`、`B_STUDENT_PROMPT.txt`可直接複製使用；`RETURN_TEMPLATE.md`提供回傳欄位；`sources.json`保存書目、核對狀態與限制。兩題實際回答已收到，摘要與引用核對已完成本機整合；NotebookLM內部引用點擊對照未提供，此限制另有明示。
