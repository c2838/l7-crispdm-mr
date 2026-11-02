"""Prepare a local, reviewable HW2 submission package. Never publishes or submits."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,shutil,zipfile

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    target=ROOT/'artifacts/submission/L7_CRISPDM_MR_HW2';target.mkdir(parents=True,exist_ok=True)
    def copy(source,dest):
        p=target/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,p)
    for source,dest in [
        ('reports/output/pdf/L7_CRISPDM_MR_report_draft.pdf','L7_CRISPDM_MR_report.pdf'),
        ('reports/output/pdf/L7_CRISPDM_MR_infographic.pdf','L7_CRISPDM_MR_infographic.pdf'),
        ('reports/output/pdf/HW2_conversation_snapshot.pdf','HW2_conversation_snapshot.pdf'),
        ('docs/SUBMISSION_TEXT.txt','SUBMISSION_TEXT.txt'),
        ('docs/BONUS_DEMO.md','BONUS_DEMO.md'),
        ('docs/REQUIREMENTS.md','REQUIREMENTS.md'),
        ('docs/datasets/ATTRIBUTION.md','DATA_ATTRIBUTION.md'),
        ('artifacts/validation/fixtures/stage6/parkinsons-updrs.csv','demo/parkinsons-updrs.csv'),
        ('artifacts/validation/fixtures/stage6/source.json','demo/SOURCE_AND_LICENSE.json'),
        ('artifacts/validation/stage8-public/summary.json','evidence/public-http.json'),
        ('artifacts/validation/stage8-public/browser.json','evidence/public-browser.json'),
        ('artifacts/validation/stage8-public/final-assets.json','evidence/stage8-final-assets.json'),
        ('artifacts/validation/stage9-pdf.json','evidence/pdf-validation.json'),
        ('artifacts/validation/stage9-browser-evidence.json','evidence/bonus-recheck.json'),
    ]:copy(source,dest)
    for name in ['public-gpu.png','public-student.png','public-custom-nine-models.png']:
        copy('artifacts/validation/stage9-evidence/'+name,'evidence/'+name)
    public=json.loads((ROOT/'artifacts/validation/stage8-public/final-assets.json').read_text())
    publication=json.loads((ROOT/'web/release.json').read_text())
    expected_public={f['path']:f['sha256'] for f in publication['static_files']}
    version={'created_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),'github':'https://github.com/c2838/l7-crispdm-mr','website':'https://l7-crispdm-mr.vercel.app/','last_verified_public_commit':public['verified_git_commit'],'last_verified_public_release':public['release_id'],'stage9_local_release':publication['release_id'],'stage9_public_assets_expected_sha256':{p:expected_public[p] for p in ['index.html','downloads/L7_CRISPDM_MR_report_draft.pdf','downloads/L7_CRISPDM_MR_infographic.pdf','downloads/HW2_conversation_snapshot.pdf']},'status':'prepared_pending_user_review_stage9_publication_and_lms','transcript':{'turns':36,'messages':204,'pages':108,'cutoff':'stage9 authorization and initial public commentary'},'frozen_selection_sha256':'3a4fec9047f6e08b4eace272bd2f43d7fb4be1fb8356525549340561f15425f3','lms_submitted':False}
    (target/'VERSIONS.json').write_text(json.dumps(version,ensure_ascii=False,indent=2)+'\n')
    (target/'README_FIRST.md').write_text('''# HW2 繳交準備包

主要成果：GitHub https://github.com/c2838/l7-crispdm-mr ；公開網站 https://l7-crispdm-mr.vercel.app/ 。

1. 先review三份PDF及SUBMISSION_TEXT.txt。分析報告20頁、資訊圖表1頁A3、HW2對話108頁／204則。對話截止階段9啟動，不含後續整理或LMS回執；沒有加入Lecture6其他對話。
2. 階段9新版附件／README需由使用者推送部署，Agent公開核對後再提交。VERSIONS.json保留上次已驗證的公開版本及本次預期資產SHA，不能把準備包誤稱已發布／已繳交。
3. 在已登入的LMS作業74761貼上SUBMISSION_TEXT.txt，附上三份PDF，確認後提交。若LMS允許可另附整包ZIP；本包不假定附件數量／大小上限。
4. 提交後保存LMS已繳交狀態、時間、連結與附件清單，供最後核對。尚未取得平台回執即未完成提交。

BONUS_DEMO.md提供兩項加分操作。demo/是第三份公開UCI功能測試資料，非正式預設、非使用者私有上傳；歸屬與CC BY 4.0見SOURCE_AND_LICENSE.json。evidence/含真實公開操作證據、PDF檢查與截圖。程式碼以GitHub為主，不重複打包虛擬環境、歷史、憑證、NotebookLM原文或對話來源JSON。

報告在網站維持原report_draft.pdf網址以避免舊連結失效，本包改用report.pdf正式檔名；內容SHA相同。MANIFEST.json逐檔核對完整性，其自身不納入遞迴雜湊。
''')
    files=[]
    for p in sorted(target.rglob('*')):
        if p.is_file() and p.name!='MANIFEST.json':files.append({'path':p.relative_to(target).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    allowed={f['path'] for f in files}|{'MANIFEST.json'}
    assert all(p.relative_to(target).as_posix() in allowed for p in target.rglob('*') if p.is_file())
    manifest={'schema':'hw2-submission-v1','status':'local_prepared_not_submitted','files':files,'total_file_bytes':sum(f['bytes'] for f in files)}
    (target/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=target.parent/'L7_CRISPDM_MR_HW2_submission.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file():z.write(p,arcname=target.name+'/'+p.relative_to(target).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for f in files:assert hashlib.sha256(z.read(target.name+'/'+f['path'])).hexdigest()==f['sha256'],f['path']
    result={'status':'prepared_and_integrity_checked_not_published_or_submitted','directory':str(target),'archive':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':sha(archive),'files_including_manifest':len(files)+1,'all_zip_entries_match_manifest':True}
    (ROOT/'artifacts/validation/stage9-package.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
