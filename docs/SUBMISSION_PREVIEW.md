# HW2最終繳交預覽

**狀態：本機準備包已核對；階段9新版尚未push／部署，LMS尚未提交。**

## 目標與主要網址

- 作業：https://lms2020.nchu.edu.tw/course/homework/74761
- GitHub：https://github.com/c2838/l7-crispdm-mr （main）
- 網站：https://l7-crispdm-mr.vercel.app/

先確認下面內容與三份PDF，再由使用者推送階段9新版。Agent會核對公開新版附件，之後使用者在已登入LMS提交。本文件不是提交成功證據。

## 建議提交內容

1. 在LMS文字欄貼上同目錄SUBMISSION_TEXT.txt的完整文字；包含兩個主要網址、兩題14／32原始輸入、兩項加分操作與GPT／NotebookLM說明。
2. 附上三份PDF：L7_CRISPDM_MR_report.pdf（20頁）、L7_CRISPDM_MR_infographic.pdf（1頁A3）、HW2_conversation_snapshot.pdf（108頁／204則）。完整準備包位於artifacts/submission/L7_CRISPDM_MR_HW2/。
3. ZIP含上述檔案、操作指南、來源／授權、公開測試資料及證據；供整包下載與備份，僅在LMS允許時另附。不假定檔案數量／大小限制。

網站既有report_draft.pdf下載網址保留相容性，本包report.pdf內容相同。對話截止階段9啟動及初始進度，完整部署日誌保留；其後的提交回執另存，不編造未來訊息。

## 操作、驗證與回滾

使用者commit／push本機明確清單，會更新GitHub文件並由既有整合觸發Vercel。對訪客可見的變更僅index.html與三份PDF；API、模型、493正式JSON與split不變。完整檔案及SHA清單見artifacts/validation/stage9-publication-preview.json。

部署後核對新頁面108頁／204則標示、三份PDF的公開SHA與API健康200。若失敗，可revert這次階段9 commit並重新部署既有已驗證6b7ec62；不改DNS、DB或其他專案。

LMS正式提交後，應核對已繳交狀態／時間、兩個網址及三份附件是否正確。LMS目前在本瀏覽器沒有登入後提交畫面；須由使用者登入操作。期限快照2026-11-04但未列時刻，請依登入畫面確認。
