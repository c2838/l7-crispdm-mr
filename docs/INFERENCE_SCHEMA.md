# 區間、診斷與網站資料契約

本文件補充[RESULT_SCHEMA.md](RESULT_SCHEMA.md)，適用階段4實際產出；API與前端仍待各自階段。正式模型JSON保持原有格式與SHA，區間另存，不覆寫模型。

## 計算契約

對已凍結模型，以保存的training前處理轉換development資料，僅取`selected_keys`，在首欄加截距組成D；y依模型的identity／log轉換。statsmodels OLS係數須與已凍結方程在1e-7容差一致。rank不足、殘差自由度不足、數值上零殘差變異或非有限HC3時，回傳明確不可用狀態，不製造區間。

完整rank時，beta=(D'D)^(-1)D'y，s²=RSS/(n-rank)。classical covariance=s²(D'D)^(-1)；HC3使用殘差除以(1-h)後的sandwich covariance。取t=t_(1-alpha/2, df_resid)，alpha預設0.05。

給定含截距的一列x，位置m=x'beta，classical位置CI為m±t√(x'Cov_classical x)，觀測PI為m±t√(x'Cov_classical x+s²)。HC3位置CI將Cov改為Cov_hc3；沒有輸出聲稱穩健的HC3觀測PI。log模型在log尺度完成上述計算，再逐端點取exp，標成幾何位置CI／觀測PI，不稱算術平均CI。

數值／類別填補、類別reference、drop-first、標準化及選欄完全沿用凍結preprocessor。未知類別映射至reference向量並回報；網站需明示此情況。新資料不重fit前處理。`model_equation_sha256`綁定前處理、選欄、點係數、截距、Target與轉換，拒絕套到不同方程。

## interval-spec JSON

| 欄位 | 內容與用途 |
|---|---|
| schema_version、status | 1.0；已在條件OLS假設下計算，不代表假設通過 |
| model_equation_sha256 | 所對應的凍結模型方程指紋 |
| alpha | 預設0.05；網站預設95% |
| coefficients_with_intercept | 第一項為截距，後續順序與selected_keys相同 |
| covariance_classical、covariance_hc3 | 方形矩陣；包含截距與交叉covariance，不只保留對角線 |
| mse_resid、df_resid | training殘差變異、自由度 |
| training_rows、design_columns_including_intercept、design_rank | 資料來源與設計維度 |
| target_transform、location_kind | identity為條件算術平均；log回轉換為幾何位置 |
| observation_kind | 新row的Target；GPU為四次Run平均 |
| HC3_scope、selection_conditioning | 係數／位置CI範圍與未修正的選擇不確定性 |

`fit_inference`在程式內的`status='available'`代表規格可以計算；持久JSON的`status='computed_under_conditional_OLS_assumptions'`明示其條件。這兩種狀態不可改寫成假設檢定全部通過。

## 預測與係數輸出

`prediction`、`location_ci_lower/upper`、`observation_pi_lower/upper`、`location_ci_hc3_lower/upper`皆為原Target單位；另保留`regression_*`對應欄位供log尺度核對。`interval_summary`報告全體test PI覆蓋筆數、比例、平均寬度及負值；平均CI對個別y的覆蓋刻意為null並附原因。

`coefficient-intervals.csv`的basis分為`standardized_encoded`與`unscaled_encoded`，covariance分為classical／HC3。unscaled包含類別dummy，並非重新定義類別為連續原始變數。若z=(x-center)/scale，係數／截距一併經線性矩陣T變換，covariance也轉成T Cov T'；不能只把標準誤除以scale而漏掉截距的交叉covariance。log係數仍是log反應單位。

係數表的p值與CI皆條件於已選模型；不作因果陳述，不把選擇後p值稱為經多重選擇校正的證據。

## 診斷及顯示

`*-diagnostics.json`以development為來源，保存normality、heteroskedasticity、functional_form、VIF、standardized condition number、independence、influence與sensitivity。p值數值下溢為0時，顯示「小於浮點解析度」，不可解讀為機率恰好0。Cook與leverage門檻是診斷提示，不是自動刪點規則。

`plot-data/*.json`最多2,000筆顯示點，採預測排序的分散位置並保留最大誤差點；附`total_test_rows`與`display_rows`。所有測試指標、覆蓋及寬度從完整CSV算出；不可用稀疏顯示點重新估算或聲稱畫面代表資料密度。Q-Q樣點取自全體殘差分位數；其他殘差散點為有界顯示樣本。

`site-summary.json`提供4情境×9模型的CV、test、代表標誌、選欄數與結果路徑。路徑是本機成果引用，階段5仍須製作適合瀏覽器的公開資料包，排除不必要的大型完整預測。不能將本機路徑直接當作已可下載的網址。完整CSV、報告與NotebookLM等下載僅在實際成果存在時啟用。

## 參考與實際版本

- 本機實際使用statsmodels 0.14.6，版本鎖定於requirements；點／區間已由實際執行及numpy公式核對。
- [statsmodels OLSResults.get_prediction](https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.OLSResults.get_prediction.html)：平均反應與新觀測預測的參考介面。
- [statsmodels HC3](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.HC3_se.html)：HC3係數標準誤的定義；不提供異質變異穩健個別觀測PI保證。
- [Breusch-Pagan診斷](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_breuschpagan.html)：本案採預設studentized／Koenker版本。

方法文件支持定義；本案適用性與限制以實際診斷及STAGE4_RESULTS.md為準。
