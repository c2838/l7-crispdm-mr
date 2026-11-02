# NotebookLM研究摘要與核對紀錄

收到並核對日期：2026-11-02（Asia/Taipei）。使用者提供NotebookLM兩題實際回答；以下為Agent核對、修訂後的整合摘要，並非逐字原始輸出。原始兩份貼文在docs/notebooklm/received/本機保存，不放公開下載區。

User supplied two pasted answers as NotebookLM output. No notebook session access, citation-click export, or source-ID table supplied. Original text and citation labels preserved; named source claims independently checked where retained. Numeric citation IDs are not invented or remapped.

## GPU執行時間

SGEMM資料以14個GPU設定描述矩陣乘法效能，四次Run為毫秒計時結果，本作業以其平均作Target並排除於輸入。[A1] Ballester-Ripoll等人的相關研究使用對數時間、Tensor Train代理模型與Sobol敏感度分析；其模型的一階效應合計不到四分之一，提示交互作用值得考慮。[A2 §8.3] 但該研究的12080個設定與25次計時不同於本作業241600列、四次Run，不能把其變異比例或誤差當作本作業結果。據此，本作業保留原始特徵加法OLS作能力有限的案例，並忠實呈現已凍結的評分、負時間及區間限制；此定位不否定加入轉換或交互作用項的其他線性模型。

採用：採14個設定與四次Run平均Target；以原始特徵OLS呈現限制，保留已完成的log補充分析。正式split為development 193280／test 48320，test R² 0.409873、RMSE 285.227 ms。

未採用：未實作Tensor Train／Sobol分析，也不依已揭露test新增高階調模；未採外部12080設定、25次計時或70/15/15切分，未把其3.4%相對誤差當成本作業分數。

## 學生葡萄牙語成績

UCI學生資料包含數學與葡萄牙語兩科；G1、G2為第一、第二評量期成績，G3為最後評量期的年度成績，前期成績與G3有強相關。[B1] Qiang等人的研究以395筆數學資料及30個背景特徵建立ANN，結合SHAP解釋與SPPE領域知識約束，提供預測能力與解釋性並重的既有解法。[B2 摘要／方法] 本作業採649筆葡萄牙語資料，主版本含G1／G2，另以背景版比較資訊差異；兩者不能直接移植該文的準確率或RMSE。本作業採參考類別dummy編碼與五種特徵選擇後OLS，不採ANN／SHAP／SPPE。由於背景欄位的可用時點未全部證實，結果僅作條件關聯分析，不宣稱開學預警或教育干預的因果效果。

採用：採student-por 649列、G3 Target；主版本32原始X→41 encoded，背景版30→39。每個training fold內學習類別、dummy編碼與標準化；主代表選G1／G2後OLS，test R² 0.928986。

未採用：未採B2的Label Encoding、ANN、SHAP或SPPE；本作業五方法為SelectKBest、RFE、Forward SFS、Lasso與ElasticNet selection，皆接OLS。未讀取B3全文，不補寫其方法；不移植外部分數或宣稱因果效果。

## 重要修正

- G1：更正為已完成固定80/20、development CV及final test；數字只取凍結產物。（依據：web/data/sgemm.json; artifacts/analysis/evaluation/sgemm/evaluation.json）
- G2：本機16頁arXiv版本第8.3節為PDF第12–14頁；不同版本頁碼不混用。（依據：A2 §8.3 PDF pp12–14, Tables6–9）
- G3：比例只屬A2的對數時間TT代理模型及其分析分布，不是本作業raw-time R²上限或已量測的Sobol比例。只作相關機制提示。（依據：A2 §8.3 PDF pp12–14; distinct sample/timing/split）
- G4：選取欄位不新增交互作用表達，但仍可能改變泛化表現；不能斷言所有子集完全無改善。（依據：M2; frozen method comparisons）
- G5：揭露傳統PI假設不滿足與條件限制，同時報告實測覆蓋97.32%及平均寬1111.408 ms；不以高覆蓋保證未來，也不以HC3宣稱修復觀測PI。（依據：artifacts/analysis/evaluation/sgemm/evaluation.json; M4）
- G6：不將秩表示或可表示交互作用寫成擬合保證；刪除不必要的rank定值與精準保證，僅保留論文實際方法。3.4%不是MAPE或本作業RMSE。（依據：A2 §4, §8.3）
- S1：實作FrameEncoder為參考類別dummy（one-hot drop-reference），非任意多類整數排序；主版本41、背景39，不含截距。（依據：l7_analysis/preprocessing.py FrameEncoder.fit; model preprocessor specs）
- S2：這是混合分類與工具，並非本作業五方法；改列SelectKBest、RFE、Forward SFS、Lasso selection、ElasticNet selection。RFE遞迴刪除，SFS逐步加入，不都等同單次排名top-k。（依據：l7_analysis/config.py; selection.py; M2）
- S3：改為同一學年的第一、第二評量期（period），G3為第三期發出的年度最終成績。（依據：B1 Dataset Information / Additional Variable Information）
- S4：B1僅確定學校報告與問卷，未確定所有背景欄位測量於期末；刪除期末已證實的說法，保留可用時點未核實與不得宣稱開學預警。（依據：B1 Dataset Information）
- S5：常態與同變異是傳統有限樣本推論／PI的條件，非計算OLS的必要條件；原始加法設計未含交互作用，不等於所有線性參數模型不能用非線性基底。（依據：M1/M4; existing inference contract）
- S6：SPPE是該文領域知識約束，不等同本作業L1/L2懲罰。選擇後CI/p值保留未校正條件限制，不籠統寫成任何情況皆失效。（依據：B2 Methodology; M1; l7_analysis/inference.py selection_conditioning）

## 可追溯來源

- [A1](https://archive.ics.uci.edu/dataset/440/sgemm+gpu+kernel+performance)：UCI Dataset Information / Additional Variable Information
- [A2](https://arxiv.org/pdf/1712.00233)：arXiv 1712.00233 local16-page PDF §8.3, pp12–14; Tables6–9
- [B1](https://archive.ics.uci.edu/dataset/320/student+performance)：UCI Dataset Information / Additional Variable Information
- [B2](https://www.nature.com/articles/s41598-026-40538-y)：DOI10.1038/s41598-026-40538-y Abstract / Methodology / Data understanding and pre-processing / Sensitivity analysis of feature encoding schemes / Discussion
- [M2](https://scikit-learn.org/stable/modules/feature_selection.html)：scikit-learn feature_selection: univariate/RFE/SFS/L1

引用限制：只有貼上文字，沒有NotebookLM引用點擊匯出或來源編號對照表；保留原編號，不假造其對應。正式文稿改用可獨立查閱的來源名稱、URL及章節。來源主張已核對與NotebookLM操作介面已驗證是不同範圍。
