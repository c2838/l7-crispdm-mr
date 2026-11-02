from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,re,hashlib,subprocess,importlib.util
from pypdf import PdfReader
from PIL import Image,ImageDraw
import pdfplumber

R=Path('/Users/c2838/NCHU/115-1 中興作業/AIOT/L7_CRISPDM_MR')
V=R/'artifacts/validation';PAGES=V/'stage9-pdf-pages';PAGES.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('authoring',R/'reports/source/build_deliverables.py');author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    assert ok,name
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(text):return re.sub(r'\s+','',text)
pdfs=sorted((R/'reports/output/pdf').glob('*.pdf'))
def render(p):
    out=PAGES/p.stem;out.mkdir(exist_ok=True)
    binary='/Users/c2838/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm'
    subprocess.run([binary,'-r','75','-png',str(p),str(out/'page')],check=True,capture_output=True)
    images=sorted(out.glob('page-*.png'));sheets=[]
    for start in range(0,len(images),12):
        sheet=Image.new('RGB',(960,1896),(225,233,235));draw=ImageDraw.Draw(sheet)
        for j,image in enumerate(images[start:start+12]):
            im=Image.open(image).convert('RGB');im.thumbnail((300,440));x=(j%3)*320+(320-im.width)//2;y=(j//3)*474+24;sheet.paste(im,(x,y));draw.text(((j%3)*320+8,(j//3)*474+6),f'{p.stem} p{start+j+1}',fill=(20,45,50))
        target=PAGES/f'{p.stem}-contact-{start//12+1}.jpg';sheet.save(target,quality=90);sheets.append(str(target.relative_to(R)))
    print(json.dumps({'rendered':p.name,'pages':len(images)}),flush=True)
    return {'pdf':str(p.relative_to(R)),'pages':len(images),'png_dir':str(out.relative_to(R)),'contact_sheets':sheets}
try:
    with ThreadPoolExecutor(max_workers=2) as pool:rendered=list(pool.map(render,pdfs))
    total=0
    expected={'HW2_conversation_snapshot.pdf':108,'L7_CRISPDM_MR_report_draft.pdf':20,'L7_CRISPDM_MR_infographic.pdf':1}
    for p in pdfs:
        reader=PdfReader(p);check(p.name+' pages/unencrypted',len(reader.pages)==expected[p.name] and not reader.is_encrypted)
        check(p.name+' complete rendering',next(x['pages'] for x in rendered if x['pdf'].endswith(p.name))==len(reader.pages))
        check(p.name+' website copy byte-identical',sha(p)==sha(R/'web/downloads'/p.name))
        with pdfplumber.open(p) as doc:
            for i,page in enumerate(doc.pages):
                total+=1
                bad=[c for c in page.chars if c['x0']<1 or c['x1']>page.width+1 or c['top']<1 or c['bottom']>page.height-1]
                check(p.name+f' page{i+1} text within bounds',not bad,{'characters':len(page.chars),'overflow':len(bad)})
                check(p.name+f' page{i+1} nonempty',len(page.chars)>30)
    source=json.loads((R/'reports/source/transcripts/hw2.json').read_text());messages=[m for t in source['turns'] for m in t['messages']]
    check('204 distinct actual public messages',len(messages)==204 and len({m['id'] for m in messages})==204)
    check('all4 source pages and no truncation',len(source['pages'])==4 and not source['pages'][-1]['hasMore'] and not source['truncated_items'])
    pdf=PdfReader(R/'reports/output/pdf/HW2_conversation_snapshot.pdf');body=[]
    for n,page in enumerate(pdf.pages):
        lines=(page.extract_text() or '').splitlines()
        expected_header=['L7  /  CRISP-DM  /  MULTIPLE REGRESSION','對話訊息快照 / '+source['title'],str(n+1)]
        check(f'transcript page{n+1} header/footer consistent',lines[:3]==expected_header)
        body.append('\n'.join(lines[3:]))
    replay=norm(''.join(body));missing=[]
    for m in messages:
        value=norm(author.safe(author.display_message(m['text'])))
        if value not in replay:missing.append(m['id'])
    check('204/204 message text retained after declared presentation normalization',not missing,{'missing_ids':missing})
    check('no raw tool/automatic citation markup in reading PDF','<oai-mem-citation>' not in replay and '<send_user_message_question_reply>' not in replay)
    for name,pattern in {'OpenAI literal key':r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}','GitHub literal credential':r'\bgh[pousr]_[A-Za-z0-9]{30,}','private key block':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'}.items():
        check('no credential pattern '+name,not any(re.search(pattern,m['text']) for m in messages))
    report=norm(''.join(p.extract_text() or '' for p in PdfReader(R/'reports/output/pdf/L7_CRISPDM_MR_report_draft.pdf').pages))
    for value in ['0.409873','0.928986','285.227','0.840','1111.408','5.312','NotebookLM','204','對話截止點','l7-crispdm-mr.vercel.app','github.com/c2838/l7-crispdm-mr']:
        check('report retains '+value,norm(value) in report)
    review=json.loads((R/'docs/notebooklm/review.json').read_text())
    for name in ['gpu','student']:
        chinese=len(re.findall(r'[\u4e00-\u9fff]',review['summaries'][name]['summary']));check(name+' NotebookLM summary >100 Chinese characters',chinese>100,chinese)
    for group in ['protected_sha256','export_sha256','source_sha256']:
        entries=json.loads((R/'artifacts/analysis/website/export-manifest.json').read_text())[group];check(group+' unchanged',all(sha(R/p)==h for p,h in entries.items()),len(entries))
    check('Lecture6 PDF absent from public downloads',not any('lecture6' in p.name.lower() for p in (R/'web/downloads').rglob('*')))
    result={'status':'automated_passed_pending_visual_review','checks':checks,'passed_checks':len(checks),'pages_rendered':total,'renders':rendered,'message_count':len(messages),'limits':['PDF bounds and text replay do not replace visual inspection.','LMS authentication/submission not performed.','This snapshot deliberately ends at stage9 kickoff; later messages are outside its declared cutoff.']}
    (V/'stage9-pdf.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'pages':total,'messages':len(messages),'sheets':sum(len(x['contact_sheets']) for x in rendered)}),flush=True)
except Exception as exc:
    (V/'stage9-pdf.json').write_text(json.dumps({'status':'failed','checks':checks,'error':str(exc)},ensure_ascii=False,indent=2)+'\n')
    raise
