# Vercel部署契約與操作範圍

狀態：使用者已自行建立c2838/l7-crispdm-mr及Vercel公開站，階段8功能與收尾檔案驗收通過。最新證據見STAGE8_RESULTS.md及stage8-public/final-assets.json；階段9新附件尚待使用者review／推送，LMS尚未提交。實際方案／Function記憶體／冷啟動身分未取得管理端證據。

## 架構

本機入口app.py維持掛載web/；雲端入口vercel_app.py建立同一API，並以app.frontend明確宣告web/；Vercel原生collector將其提升至CDN。pyproject.toml指定tool.vercel.entrypoint，Vercel framework=fastapi。既有requirements.txt與.python-version不變，不升級或增加分析套件。pyproject.toml的project.dependencies必須逐項等於原36個精確鎖定版本，requires-python約束3.12.x；建置會檢查兩份清單一致。

Build Command為python scripts/build_vercel_static.py，逐位元複製web/到public/，產生release.json記錄靜態與程式SHA、凍結版本及release_id。pyproject.toml的tool.vercel.fastapi.static明設cdn=true、exclude=true，由原生框架處理CDN資源與Function排除；public/是建置副本，web/的宣告是原生辨識依據。API仍是/api/health、/api/data/preview、/api/data/url及/api/analyze/{method}，單方法120秒協作預算，平台maxDuration配置300秒；不宣稱native求解能硬停。

正式分析、候選、36凍結模型及split不變。靜態493展示JSON與三份PDF走CDN；不把79MB網站資料重複帶入每個Python instance。沒有DB、付費服務、自訂網域或DNS變更。

## 本機建置

使用已鎖定環境執行：

```sh
.venv/bin/python -B scripts/build_vercel_static.py
```

public/為產生物，不加入Git。建置遇到web/的未知副檔名、隱藏檔、symlink或public/的額外殘留檔會停止，不自行遞迴刪除。release.json為版本核對用途，不顯示在產品操作流程。

## 發布邊界與前置盤點

先取得GitHub帳號、完整owner/repository，Vercel帳號與team ID、effective方案、project及region。新建名稱已確認不等於公開建立／push／部署授權；不能把尚未登入的名稱當成已確認目標。

Git來源以明確allowlist產生待發布來源包與完整SHA清單，排除本機.venv、secrets、歷史、原資料、NotebookLM原始貼文／研究PDF、對話JSON及渲染暫存。已在網站提供的HW2對話PDF會列入公開內容preview，須使用者review。Lecture6不發布。

對外操作前展示完整execution preview，包括實際目標、檔案清單／SHA、公開可見範圍、預定操作、費用、驗證與回滾。使用者再次要求執行後才能建repo／push／部署。任何目標或檔案變更須重新核對preview。

## 公開驗收與回滾

本機驗證不等於Vercel build成功。部署後確認release.json與Function實際版本、Python3.12、Fluid Compute、記憶體／冷啟動／並行、所有靜態下載、第三真實CSV／URL六請求九模型、Target切換與取消重試。訪客無登入可操作才可列加分證據。

首次發布失敗保留本機來源及錯誤證據，不改其他專案或DNS；後續更新保留上一部署與commit，可回滾既有deployment。未公開成功前不將報告補成已部署，不執行LMS繳交。

## 官方依據

- https://vercel.com/docs/frameworks/backend/fastapi （public/ CDN與resolved入口配置）
- https://vercel.com/docs/functions/runtimes/python （Python3.12、requirements、500MB與excludeFiles）
- https://vercel.com/docs/functions/limitations （Hobby300秒、2GB／1vCPU、payload4.5MB）
- https://vercel.com/docs/project-configuration/vercel-json （fluid、functions、buildCommand與region設定）

查閱日期2026-11-02；實際方案／region未經登入核對，使用placeholder狀態，不推定為已生效。


## 首次部署故障與修正

使用者已建立https://github.com/c2838/l7-crispdm-mr（main），並部署https://l7-crispdm-mr.vercel.app/。初始commit12ca7c4雖被Vercel回報Deployment completed，首頁／release.json／api/health實際均為500 FUNCTION_INVOCATION_FAILED。使用者提供runtime traceback：vercel_app.py與l7_service/api.py均已找到，但import fastapi失敗。

初始pyproject.toml僅包含tool.vercel入口、未宣告project.dependencies，與Vercel選用manifest處理依賴的機制不相容。修正為標準project表、Python3.12.x及與requirements.txt相同36個精確pin，並新增建置一致性檢查。不是變更Root Directory，也不新增套件版本。使用者推送d7ff5c4後，公開API實際200，依賴故障解除；當時靜態404另外依下段修復。

依使用者最新分工，Chrome登入、GitHub與Vercel平台操作由使用者處理；Agent負責本機修正、具體差異／步驟與唯讀公開驗證。不得自行push或重部署。

## 靜態404與資料遺失的修正（已公開驗證）

未宣告frontend時原生collector找不到前端；另.vercelignore的data/誤匹配web/data/，493個分析JSON被排除，Build只剩16檔。修正為app.frontend根路徑及CDN設定，ignore目錄全部使用根目錄錨定/data/等；建置若缺493正式JSON或候選detail則停止。使用者部署後509檔逐檔200且SHA一致；兩題、第三份CSV／URL六方法九模型及錯誤處理已實測。

最新階段8commit6b7ec62，首頁、release、API、兩份PDF均實際核對。平台可能在建置中改寫設定，但確切原因未確認：公開release只有vercel.json來源雜湊不同，其餘runtime程式與全部靜態內容一致；不假稱設定完全相同。
