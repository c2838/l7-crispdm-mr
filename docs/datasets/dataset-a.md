# Dataset A：SGEMM GPU 運算時間

狀態：使用者同意「以這兩份資料為主」後，取代原成衣題目。階段1來源、品質與development EDA已完成；尚未建模。

## Business Understanding

以14個事先設定的GPU核心參數估計固定矩陣工作負載的平均執行時間，供分析哪些設定與效能有關。四次計時平均為本作業Target `runtime_mean_ms`，單位毫秒，越低越快。這是條件式效能估計，不代表找到全域最佳設定，也不保證可外推其他GPU或矩陣大小。

## Data Understanding 與來源

- Kaggle：<https://www.kaggle.com/datasets/rupals/gpu-runtime>，實際版本4。
- 原始來源：<https://archive.ics.uci.edu/dataset/440/sgemm+gpu+kernel+performance>。
- Paredes, E. & Ballester-Ripoll, R. (2017). SGEMM GPU kernel performance. DOI: 10.24432/C5MK70；原始CC BY 4.0。
- 241600筆、18欄：14個設定＋4個重複計時結果。不是18個輸入，也不是Agent自行生成的資料。
- Kaggle原檔與UCI檔案SHA-256逐位元相同；原作者Readme與metadata保存在artifacts/reference/datasets。
- 舊Readme敘述有261400／241600不一致；實際檔案、Readme的Number of Instances及UCI頁面均為241600，採實際檔案列數。

## 14個原始輸入

| 欄位 | 定義 |
|---|---|
| MWG、NWG | 兩個矩陣在workgroup層的分塊大小 |
| KWG | 分塊的內積維度 |
| MDIMC、NDIMC | 區域workgroup大小 |
| MDIMA、NDIMB | 區域記憶體形狀 |
| KWI | 迴圈展開因子 |
| VWM、VWN | 向量載入／儲存寬度 |
| STRM、STRN | 是否啟用stride存取，0／1 |
| SA、SB | 是否手動快取矩陣分塊，0／1 |

逐欄位置、範圍及角色見`artifacts/analysis/data-audit/dataset-a-schema.json`。前10欄是離散有序設定，最後4欄為二元；以數值建模的線性趨勢假設仍須診斷。

## Target與準備規則

`runtime_mean_ms = (Run1 (ms) + Run2 (ms) + Run3 (ms) + Run4 (ms)) / 4`。

保留原檔不改值；處理版`data/processed/sgemm-model-input.csv`含14輸入與1個平均Target。四個Run欄全部排除於X；平均重複量測屬明確Target定義，不是填補缺值或特徵湊數。無須GPU重跑原始實驗。

## 品質、切分與限制

- 缺值0、無限值0、重複列0、重複輸入組合0、固定欄位0；全部設定符合原作者允許值，計時全為正值。
- 固定193280筆development／48320筆final test；PCG64(0)隨機留20%，完整索引已保存。EDA相關性與分布只使用development。
- 不補值、不刪離群值、不先轉log、不擬合編碼器或模型。log分布圖僅供觀察。
- 原作者建議研究log時間；後續可於training-only比較原始Target OLS與log Target OLS，須交代反轉換及區間解讀，不用final test挑方案。
- 隨機保留評估的是同來源硬體／工作負載中的未見設定，不能宣稱跨GPU外部驗證。資料完整不保證線性模型高分或殘差假設成立。
