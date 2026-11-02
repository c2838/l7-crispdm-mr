# 階段8提案：整合、發布準備與公開驗收

狀態：下一階段規劃，尚未授權或開始。階段7的NotebookLM實際輸入與摘要本機整合已完成；本文件不構成公開發布授權。

## 目標與前置條件

將本機正確與公開服務可用分開驗證，完成兩題下拉及任意Dataset加分的公開證據。NotebookLM引用核對、報告／網站研究內容已有本機成果；本階段再鎖定將發布的版本。使用者已選Hobby作免費方案評估基準，未驗證實際帳號／專案設定，也未指定effective Vercel team、project或repo。

## A. 唯讀盤點與本機準備

- [ ] 核對實際Git託管目標（作業要求GitHub）、帳號／repo、Vercel帳號／team／project、方案、region、Python runtime、Fluid Compute及既有部署；不自行命名既有資源。
- [ ] 以官方當日文件及effective設定檢查限制，實際打包並量測依賴與Function大小，避免把.venv、原始資料、歷史快照、對話來源JSON及PDF渲染暫存全部包進Function。
- [ ] 確認靜態正式成果與PDF下載的發佈方式；研究論文PDF只保留原文連結，不公開再散布；對話PDF的公開範圍先讓使用者review。
- [ ] 保持既有模型與split凍結；資料／code／附件版本互相綁定，不依已知test重新選模。

規劃時已讀[Vercel Function限制](https://vercel.com/docs/functions/limitations)：Fluid Compute的Hobby列300秒上限、2GB／1vCPU、Python一般未壓縮bundle 500MB、request／response 4.5MB；是否適用仍以實際專案及部署當日核對，large-function beta不作先決條件。現有應用程式CSV 3.5MB／POST 3.57MB／JSON 3MB、單方法120秒預算只是設計，不能代替雲端實測。

[Hobby官方說明](https://vercel.com/docs/plans/hobby)為免費個人非商業用途，超過用量通常需等待恢復；不保證任意流量可一直免費。此階段不自動升Pro、不建立付費DB或購買網域。若完整需求無法落在Hobby，先提出實測瓶頸、具體替代架構／目標／費用與回滾供確認，不偷偷減少方法或取消加分。

## B. Execution preview與外部操作授權

- [ ] 列出effective帳號、repo與分支、Vercel team／project／region、將送出的實際完整檔案清單／SHA、公開下載內容及預定操作。
- [ ] 說明影響範圍、費用上限、驗證方式及回滾：保留前一部署與版本，失敗時回復或移除新部署；不觸碰無關服務／DNS。
- [ ] 展示具體preview後停止；使用者看過並再次明確要求執行，才可建repo／push／建立或變更公開部署。目標或檔案範圍改變須更新preview。

## C. 實際公開驗收與定稿

- [ ] 無本機依賴的訪客可查看兩題、方法、區間與附件；確認實際部署版本與所有連結。
- [ ] 公開HTTP／瀏覽器實際執行第三份真實CSV上傳與URL、Target／X變更、六方法、失敗、取消／重試及JSON下載；不以本機或mock通過代替。
- [ ] 量測冷啟動／暖啟動、時間／記憶體、回應大小及合理並行；確認平台限制下不會把部分完成誤稱全部成功。
- [ ] 桌面／手機／鍵盤、中文／英文圖表、下載與來源標示驗收；保留截圖、HTTP結果、版本及未驗證限制。
- [ ] 填入真正公開網址與repo，重新產生報告／資訊圖表，逐頁檢視；最後繳交前另更新對話快照。
- [ ] 提出階段9繳交清單，LMS實際提交仍另需preview與明確執行授權。
