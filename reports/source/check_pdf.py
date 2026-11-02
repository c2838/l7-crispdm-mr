from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,hashlib,re,math
from PIL import Image,ImageDraw
from pypdf import PdfReader
import pdfplumber

ROOT=Path('/Users/c2838/NCHU/115-1 中興作業/AIOT/L7_CRISPDM_MR')
PDF=ROOT/'reports/output/pdf';TMP=ROOT/'reports/tmp/pdfs';QA=ROOT/'artifacts/validation/stage7-pdf-pages'
BIN='/Users/c2838/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm'
TMP.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True)

def render(p):
    out=TMP/(p.stem+'-'+hashlib.sha256(p.read_bytes()).hexdigest()[:10]);out.mkdir(exist_ok=True)
    subprocess.run([BIN,'-r','90','-png',str(p),str(out/'page')],check=True,capture_output=True)
    images=sorted(out.glob('page-*.png'))
    sheets=[]
    for start in range(0,len(images),12):
        group=images[start:start+12];sheet=Image.new('RGB',(960,4*474),(222,230,232));draw=ImageDraw.Draw(sheet)
        for j,f in enumerate(group):
            im=Image.open(f).convert('RGB');im.thumbnail((300,440));x=(j%3)*320+(320-im.width)//2;y=(j//3)*474+24;sheet.paste(im,(x,y));draw.text(((j%3)*320+10,(j//3)*474+5),f'{p.stem} / {start+j+1}',fill=(25,50,60))
        target=QA/f'{p.stem}-contact-{start//12+1}.jpg';sheet.save(target,quality=90);sheets.append(str(target.relative_to(ROOT)))
    print(p.name,'rendered',len(images),flush=True)
    return {'pdf':str(p.relative_to(ROOT)),'rendered_pages':len(images),'contact_sheets':sheets,'png_dir':str(out.relative_to(ROOT))}

def normalize(x):return re.sub(r'\s+','',x.replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2212','-').replace('\u00a0',' '))

def main():
    pdfs=sorted(PDF.glob('*.pdf'))
    with ThreadPoolExecutor(max_workers=2) as pool:rendered=list(pool.map(render,pdfs))
    checks=[];bounds=[];pages=0
    def check(name,b,detail=None):checks.append({'name':name,'passed':bool(b),'detail':detail});assert b,name
    for p in pdfs:
        reader=PdfReader(p);check(p.name+' readable and unencrypted',len(reader.pages)>0 and not reader.is_encrypted)
        with pdfplumber.open(p) as doc:
            for i,page in enumerate(doc.pages):
                pages+=1;bad=[{'x0':x['x0'],'x1':x['x1'],'top':x['top'],'bottom':x['bottom']} for x in page.chars if x['x0']<1 or x['x1']>page.width+1 or x['top']<1 or x['bottom']>page.height-1]
                check(p.name+f' page {i+1} text within page',not bad,{'characters':len(page.chars),'overflow':len(bad)})
                check(p.name+f' page {i+1} has expected text',len(page.chars)>30)
                bounds.append({'pdf':p.name,'page':i+1,'characters':len(page.chars),'lowest_text_bottom':max(x['bottom'] for x in page.chars) if page.chars else None})
        check(p.name+' complete render',next(x['rendered_pages'] for x in rendered if x['pdf'].endswith(p.name))==len(reader.pages))
    report=PdfReader(PDF/'L7_CRISPDM_MR_report_draft.pdf');text=normalize(''.join(p.extract_text() or '' for p in report.pages))
    for value in ['0.409873','0.928986','285.227','0.840','1111.408','5.312','NotebookLM','未公開部署','193280','48320','4623','1252']:
        check('report retains '+value,normalize(value) in text)
    links=[a.get_object() for page in report.pages for a in page.get('/Annots',[])];uris=[a.get('/A',{}).get('/URI') for a in links]
    check('bibliography contains actual clickable links',len([x for x in uris if x])>=8,uris)
    for name,filename in [('hw2','HW2_conversation_snapshot.pdf')]:
        original=json.loads((ROOT/f'reports/source/transcripts/{name}.json').read_text());out=PdfReader(PDF/filename);body=[]
        for page_index,page in enumerate(out.pages):
            lines=(page.extract_text() or '').splitlines()
            expected=['L7  /  CRISP-DM  /  MULTIPLE REGRESSION','對話訊息快照 / '+original['title'],str(page_index+1)]
            assert lines[:3]==expected,(filename,page_index,'header/footer ordering changed')
            body.append('\n'.join(lines[3:]))
        extracted=normalize(''.join(body))
        missing=[]
        for t in original['turns']:
            for m in t['messages']:
                cleaned=re.sub(r'<in-app-browser-context\b[^>]*>.*?</in-app-browser-context>','',m['text'],flags=re.S)
                if cleaned!=m['text']:cleaned=re.sub(r'^\s*## My request:\s*','',cleaned)
                if normalize(cleaned) not in extracted:missing.append(m['id'])
        check(filename+' each public message retained after declared automatic-context removal',not missing,{'messages':sum(len(t['messages']) for t in original['turns']),'missing_ids':missing})
    result={'status':'automated_passed_pending_visual_review','checks':checks,'passed_checks':len(checks),'pages_rendered':pages,'renders':rendered,'page_bounds':bounds,'method':'Actual Poppler rendering of every page; pdfplumber text bounds; PDF parse; literal message text replay; report frozen value checks and clickable links. Contact sheets and selected full pages require visual review.','limitations':['Text bounds cannot detect all raster-chart clipping; visual review is separate.','Research summaries integrated; report remains draft awaiting public deployment and final submission refresh.']}
    (ROOT/'artifacts/validation/stage7-pdf-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'pages':pages,'contact_sheets':sum(len(x['contact_sheets']) for x in rendered)},ensure_ascii=False))

if __name__=='__main__':main()
