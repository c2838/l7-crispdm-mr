# 結果與模型格式 v1.0

機器可讀JSON Schema：RESULT_SCHEMA.json；核心格式實際驗證入口scripts/verify_contract_stage3.py。模型維度、跨欄位關係及選擇凍結由verify_stage3.py另驗證。

## 分析入口

`run_analysis(frame, AnalysisConfig(target=..., methods=...), progress=callback, cancel=callable)`接收已界定的開發資料。正式題目由load_development驗證來源hash並跳過final-test列；未來API亦使用相同引擎，資料上限與HTTP錯誤包裝在對應服務層實作。

狀態為completed／partial_timeout／cancelled；每個cv_results候選另有completed／incomplete_or_failed。只有全部五折完成者具有cv指標及代表模型資格。輸入錯誤拋出InputError，由CLI／API轉為可讀錯誤，不捏造空白成功結果。

## 主要欄位

- config、frame_values_sha256、source、execution：設定、來源、固定開發列、套件與程式SHA；scope明示development tuning。
- raw_input_fields、input_fields、encoded_fold_counts、encoded_full_development_fields：原始與各fold／全development的編碼後維度。
- folds與cv-fold-assignments.csv：training／validation列數、位置SHA、訓練折前處理SHA與完整開發列對應。不保存final test預測。
- cv_results：method、parameters、每折selected_keys／實際選取數、指標、警告／失敗；聚合MSE按驗證列數加權，RMSE為其平方根，R²以整份開發y的SST計算。常數Target的R²為null，負R²保留。
- method_winner_ids、representative_candidate_id：每法在已探索網格的最佳設定；主代表限OLS家族，以CV RMSE、平均選取欄位數、穩定ID排序。數值幾乎相等不代表顯著差異。
- models是記憶體版本的JSON模型；CLI將其另存為model_files路徑映射。representative_model_available與completed_methods只在實際有匯出成果時成立。
- events.jsonl記錄實際開始／完成的fold、方法與refit；它是本機計算事件，不是已實作的公開網站進度服務。

## 係數與預測口徑

每個模型保存preprocessor的原始欄位類型、訓練fill值、類別與reference、active encoded keys及center／scale。所有補值與尺度只從該模型training資料學習。

`model.coefficients`與`model.intercept`作用在標準化後的selected_keys；Target已還原至原本回歸反應尺度。identity為原Target單位，log為自然對數Target單位。不得將標準化係數直接稱為「原始欄位增加1單位」的效果。

coefficients.csv另提供unscaled_encoded_coefficient：係數除以對應scale，截距減去所有raw係數乘center；此時連續欄位以原單位、dummy以0／1解讀，仍非因果效果。log模型預測最後取exp，不含smearing，也不等於原尺度算術平均反應。

類別輸入未見於training時使用全零dummy block，等同訓練reference，並回報unknown_categories。參考類別及常數移除均在spec中；不同fold可能有不同dummy數，結果以語意key映射，不按欄位位置硬套。

JSON模型只存轉換、係數與metadata，不含來源資料列或可執行pickle。predict_artifact可重播單筆／多筆；statsmodels區間與最終測試在階段4另接相同設計矩陣，不在此重選模型。

## 部分結果與限制

deadline在候選／fold邊界協作檢查，取消不是即時殺掉底層線性求解。未完成的CV候選沒有完整cv欄；已完成模型與原因可保留。正式API的回應大小、網路中止與所有狀態仍需階段6驗證。

selection-stability.csv是選定參數下五個訓練折的實際選取頻率，不是選中特徵的真實機率或95%信賴度。
