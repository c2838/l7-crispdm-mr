# Dataset B：學生表現（葡萄牙語課程）

狀態：使用者同意新組合，接受32個原始輸入，取代原先35～39個偏好與lattice題目。階段1完成；尚未建模。

## Business Understanding

使用學生背景、學習情況與前兩期成績，回顧分析／條件估計期末成績`G3`，單位為分、文件定義0～20。實際葡萄牙語資料G3為0～19，不能將零分自動當缺值刪除。目標是預測誤差、可解釋性與限制的完整展示，不做因果推論或個別學生介入建議。

G1與G2是前兩期已取得的成績；本題不能宣稱開學時預測。缺席次數及問卷欄位的量測時點未證明早於期末，因此主題明確採回顧條件估計；即使補做排除G1/G2版本，也不能自動稱為提前預警。

## Data Understanding 與來源

- Kaggle：<https://www.kaggle.com/datasets/uciml/student-alcohol-consumption>，版本2。雖頁面名稱為飲酒，底層為UCI Student Performance；本作業Target選G3，並非飲酒分類。
- 原始來源：<https://archive.ics.uci.edu/dataset/320/student+performance>。
- Cortez, P. (2008). Student Performance. DOI: 10.24432/C5TG7T；原始CC BY 4.0。
- 兩所葡萄牙學校的學校紀錄與問卷。只使用student-por.csv的649筆，不混入數學課程；原作者說明跨課程有重複學生，避免混合切分洩漏。
- 33欄＝30個背景欄位＋G1＋G2＋G3；本題X為32、y為G3。UCI頁面30 features是背景欄位口徑，不可與本題計數混淆。
- Kaggle與UCI原檔位元不同（CSV分隔／引號格式不同），但解析後的欄名、列序、數值與類別完全一致。

## 32個輸入欄位

| 欄位 | 定義 |
|---|---|
| school | 學校 |
| sex | 性別 |
| age | 年齡 |
| address | 居住地類型 |
| famsize | 家庭人數類型 |
| Pstatus | 父母同住狀態 |
| Medu | 母親教育程度 |
| Fedu | 父親教育程度 |
| Mjob | 母親職業 |
| Fjob | 父親職業 |
| reason | 選校原因 |
| guardian | 監護人 |
| traveltime | 通學時間等級 |
| studytime | 每週讀書時間等級 |
| failures | 過去不及格紀錄 |
| schoolsup | 學校額外學習支援 |
| famsup | 家庭學習支援 |
| paid | 額外付費課程 |
| activities | 課外活動 |
| nursery | 是否就讀幼兒園 |
| higher | 是否希望升學 |
| internet | 家中網路 |
| romantic | 戀愛關係 |
| famrel | 家庭關係等級 |
| freetime | 空閒時間等級 |
| goout | 外出社交等級 |
| Dalc | 平日飲酒等級 |
| Walc | 週末飲酒等級 |
| health | 健康自評等級 |
| absences | 缺席次數 |
| G1 | 第一期成績 |
| G2 | 第二期成績 |

完整原作者字典：`artifacts/reference/datasets/student-dictionary.txt`；實際型態、類別與範圍：`artifacts/analysis/data-audit/dataset-b-schema.json`。

## 品質、切分與後續準備

- 缺值0、無限值0、完整重複列0、重複32欄輸入0、固定欄位0；無須補值或修正文字。
- 固定519筆development／130筆final test；PCG64(0)隨機留20%，完整索引已保存。
- 17個文字類別欄位仍須編碼。依development現有類別推估，drop-first編碼後為41欄，不含截距；這是模型設計矩陣維度，原始輸入仍32，不用dummy欄位湊作業特徵數。
- 尚未擬合編碼器；類別表、縮放及選特徵均限相應training fold。實際編碼後維度可隨fold／選定欄位改變。
- 學校與社會背景有來源偏差；無個人ID不能證明所有獨立性假設。隨機保留不代表跨學校或跨年度外部驗證。
- 後續規劃含32輸入主分析與排除G1/G2的30背景欄位敏感度比較；仍用開發資料選模型，不據test改方案。
- OLS可能輸出0～20以外預測，後續如實呈現與診斷，不先裁切以改善分數。序位欄位視為數值的線性假設亦須說明。
