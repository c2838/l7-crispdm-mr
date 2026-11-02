"""Produce reviewable report, infographic and verbatim-message snapshot PDFs.
Run with bundled artifact Python, without changing the analysis environment.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,math,hashlib,re,html,shutil
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4,A3
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT=Path('/Users/c2838/NCHU/115-1 中興作業/AIOT/L7_CRISPDM_MR')
OUT=ROOT/'reports/output/pdf'
SRC=ROOT/'reports/source'
TEAL=colors.HexColor('#205D66');INK=colors.HexColor('#203B43');MUTED=colors.HexColor('#5C6F76');PALE=colors.HexColor('#EDF5F4');BLUE=colors.HexColor('#EDF1F8');GOLD=colors.HexColor('#B06B24')
NOW=datetime.now(ZoneInfo('Asia/Taipei'));DATE=NOW.strftime('%Y-%m-%d')
FONT='/Library/Fonts/Arial Unicode.ttf'
pdfmetrics.registerFont(TTFont('TC',FONT))
pdfmetrics.registerFontFamily('TC',normal='TC',bold='TC',italic='TC',boldItalic='TC')
GLYPHS=pdfmetrics.getFont('TC').face.charToGlyph
FALLBACKS={}

def safe(text):
    # Original transcript JSON is unchanged. Typography is normalized only in PDF.
    value=str(text).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2212','-').replace('\u00a0',' ')
    result=[]
    for ch in value:
        if ch in '\n\t\r' or ord(ch) in GLYPHS:result.append(ch)
        else:
            substitute='[U+%04X]'%ord(ch);FALLBACKS[ch]=substitute;result.append(substitute)
    return ''.join(result)

STYLES={
 'body':ParagraphStyle('body',fontName='TC',fontSize=11.5,leading=18.2,textColor=INK,wordWrap='CJK',spaceAfter=9,splitLongWords=True),
 'small':ParagraphStyle('small',fontName='TC',fontSize=9.4,leading=14,textColor=MUTED,wordWrap='CJK',spaceAfter=7,splitLongWords=True),
 'h1':ParagraphStyle('h1',fontName='TC',fontSize=23,leading=31,textColor=TEAL,spaceAfter=17,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='TC',fontSize=14.5,leading=22,textColor=TEAL,spaceBefore=10,spaceAfter=7,keepWithNext=True),
 'cell':ParagraphStyle('cell',fontName='TC',fontSize=9.3,leading=14,textColor=INK,wordWrap='CJK',splitLongWords=True),
 'th':ParagraphStyle('th',fontName='TC',fontSize=9.3,leading=14,textColor=colors.white,wordWrap='CJK',splitLongWords=True),
 'message':ParagraphStyle('message',fontName='TC',fontSize=10.4,leading=16,textColor=INK,wordWrap='CJK',spaceAfter=13,splitLongWords=True),
 'role':ParagraphStyle('role',fontName='TC',fontSize=10.4,leading=15,textColor=TEAL,spaceBefore=13,spaceAfter=5,keepWithNext=True),
}

def para(text,style='body',markup=False):
    s=safe(text)
    if not markup:
        s=html.escape(s).replace('\n','<br/>')
        if style!='message' and re.fullmatch(r'https?://[^\s]+',str(text)):
            s='<link href="'+html.escape(str(text),quote=True)+'" color="#205D66">'+s+'</link>'
    return Paragraph(s,STYLES[style])

def table(rows,widths,small=False):
    data=[[para(v,'th' if i==0 else 'cell') for v in row] for i,row in enumerate(rows)]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,TEAL),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#D5E1E3'))]))
    return t

def footer(title,draft=True):
    def draw(c,doc):
        w,h=A4;c.saveState();c.setFillColor(TEAL);c.rect(0,h-10,w,10,fill=1,stroke=0)
        c.setFont('TC',8.5);c.setFillColor(MUTED);c.drawString(42,h-31,'L7  /  CRISP-DM  /  MULTIPLE REGRESSION')
        c.setStrokeColor(colors.HexColor('#D9E3E5'));c.line(42,38,w-42,38)
        c.setFont('TC',8.2);c.drawString(42,25,safe(title)[:55]);c.drawRightString(w-42,25,str(doc.page))
        if draft:c.setFillColor(GOLD);c.drawRightString(w-42,h-31,'研究摘要已核對 / 公開驗收待補')
        c.restoreState()
    return draw

def read(path):return json.loads((ROOT/path).read_text())
CASES={n:read(f'web/data/{n}.json') for n in ['sgemm','sgemm_log','student','student_background']}
EVAL={n:read(f'artifacts/analysis/evaluation/{n}/evaluation.json') for n in CASES}
REP={n:next(c for c in d['candidates'] if c['id']==d['representative_id']) for n,d in CASES.items()}
NAMES={'dummy':'Mean baseline','ols':'All-feature OLS','kbest':'SelectKBest -> OLS','rfe':'RFE -> OLS','sfs':'Forward SFS -> OLS','lasso_select':'Lasso selection -> OLS','elasticnet_select':'ElasticNet selection -> OLS','ridge':'Ridge prediction','lasso_reg':'Lasso prediction'}
ORDER=list(NAMES)
TRACE=[]
TEXT=[]

def fmt(x,d=3):return '-' if x is None else f'{x:,.{d}f}'
def percent(x):return f'{x*100:.2f}%'
def pvalue(x):return '< floating-point resolution' if x==0 else f'{x:.4g}'

def display_message(text):
    cleaned=re.sub(r'<in-app-browser-context\b[^>]*>.*?</in-app-browser-context>','',text,flags=re.S)
    if cleaned!=text:cleaned=re.sub(r'^\s*## My request:\s*','',cleaned)
    return cleaned

def figure(path,width=511,maxheight=340):
    image=Image(str(ROOT/path));ratio=min(width/image.imageWidth,maxheight/image.imageHeight);image.drawWidth=image.imageWidth*ratio;image.drawHeight=image.imageHeight*ratio;image.hAlign='LEFT';return image

def report():
    story=[]
    def p(text,style='body'):story.append(para(text,style));TEXT.append(text)
    def h(text):p(text,'h2')
    def page(num,title):
        if story:story.append(PageBreak())
        p(f'{num:02d}  /  ANALYSIS REPORT','small');p(title,'h1');TEXT.extend(['','## '+title])
    def tab(rows,widths):story.append(table(rows,widths));TEXT.extend([' | '.join(map(str,r)) for r in rows]);story.append(Spacer(1,11))
    def pic(path,caption,maxheight=340):story.append(figure(path,maxheight=maxheight));p(caption,'small');TEXT.append('Figure: '+path)
    def metrics(n):
        c=REP[n];m=c['test'];i=EVAL[n]['representative']['interval_summary']
        TRACE.append({'scenario':n,'candidate':c['id'],'test_metrics':m,'interval_summary':i,'source':f'artifacts/analysis/evaluation/{n}/evaluation.json'})
        return c,m,i
    def comparison(n):
        d=CASES[n];rows=[['Method','Fields','CV RMSE','Test RMSE','Test R²']]
        for method in ORDER:
            c=next(c for c in d['candidates'] if c['id']==d['winner_ids'][method]);rows.append([NAMES[method],str(c['selected_count']),fmt(c['cv']['rmse']),fmt(c['test']['rmse']),fmt(c['test']['r2'],4)])
        tab(rows,[192,47,90,90,92])
    page(1,'兩份資料，一套可重現的分析流程')
    p('物聯網應用與資料分析 HW2\nLesson 7 | CRISP-DM | Multiple Regression','h2')
    p('本報告以SGEMM GPU時間與葡萄牙語學生成績為兩個正式問題，完成特徵選擇、多元線性回歸、固定測試集評估、區間及診斷，並以真實第三資料驗證自訂CSV分析。')
    tab([['正式問題','原始輸入 / 資料量','凍結代表的test結果'],['GPU運算時間','14 / 241,600列',f"R² {REP['sgemm']['test']['r2']:.4f}\nRMSE {REP['sgemm']['test']['rmse']:.3f} ms"],['學生葡萄牙語G3','32 / 649列',f"R² {REP['student']['test']['r2']:.4f}\nRMSE {REP['student']['test']['rmse']:.3f} 分"]],[133,165,213])
    h('本次分析的判斷')
    p('GPU保留為目前原始特徵加法式線性模型能力有限的案例；學生主模型以G1與G2保留較多預測資訊，但只支持回顧條件估計。兩題都以正確方法、評估隔離及忠實揭露限制為完成標準，不以提高R²重選test。')
    h('文件版本與未完成範圍')
    p(f'本機附件草稿，整理日期 {DATE}（Asia/Taipei）。分析數字取自既有凍結JSON，未重新調模。使用者已提供兩題NotebookLM回答，摘要經來源核對修訂後整合；公開網站、原始碼repo及雲端驗收在階段8完成後定稿。此PDF尚非最終繳交版。')
    p('GPT協作：需求整理、分析程式、網站、驗證、文稿與版面由Agent協助。使用者決定資料、案例定位與階段範圍，並負責NotebookLM實際研究。','small')

    page(2,'需求對照與實驗設計')
    tab([['作業要求','本專案對應','目前狀態'],['Kaggle / 14-39原始輸入','GPU 14；student-por 32','完成'],['線性回歸 / 特徵選擇 / 評估','OLS、五種選擇、baseline與正則化比較','完成'],['預測圖含CI或PI','係數CI、平均反應CI與個別觀測PI分開','本機完成'],['CRISP-DM六階段','兩題均記錄；Deployment含實際自訂API','公開驗收待階段8'],['兩題下拉 / 任意Dataset加分','靜態正式成果 + 新CSV真正運算','本機完成；公開待驗收'],['NotebookLM / AI標示','兩題資料包及GPT協作說明','兩題回答已收到、摘要已核對'],['報告 / 資訊圖表 / 對話PDF','optional依使用者要求均製作','本機草稿；最終待更新']],[145,252,114])
    p('老師主文要求線性回歸與特徵選擇；九模型比較及共同OLS重擬合是本專案的實驗設計，不能把所有補充方法寫成教師強制要求。')
    h('Frozen的定義')
    p('先以development CV選各方法候選與主代表，保存selection-freeze.json，再進行final test評估。表格列各方法預先選定的勝出模型；上方其他k／參數屬development探索，不用已揭露test重新挑選。')

    page(3,'資料理解、來源與輸入口徑')
    tab([['項目','GPU','學生葡萄牙語'],['Kaggle版本','rupals/gpu-runtime，v4','uciml/student-alcohol-consumption，v2'],['原始來源','UCI SGEMM，DOI C5MK70','UCI Student Performance，DOI C5TG7T'],['樣本與缺值','241600列；無缺值','649列；無缺值'],['Target','四次Run平均毫秒','G3，0-20分'],['有效原始X','14個GPU設定；Run全部排除','30背景欄位 + G1 / G2'],['編碼後X','14','41（主版本）；不含截距'],['來源核對','與UCI原檔逐位元相同','與UCI解析值一致，CSV格式不同']],[106,202,203])
    p('正式資料原值不修改。Kaggle鏡像的授權標籤與UCI原始CC BY 4.0分開記錄，保留原作者及來源。Target、ID及編碼展開不能拿來湊14-39個原始特徵。來源與SHA見datasets-manifest.json。[A1/A3/B1/B4]')
    h('可用資訊與用途')
    p('GPU的四個Run是Target來源，若放進X會直接洩漏答案。學生G1／G2是前兩期成績，可用於已知前期評量後的條件估計；問卷與absences時點未完全確認，因此即使移除G1／G2，也不直接宣稱開學預警。')

    page(4,'資料準備與模型選擇流程')
    tab([['步驟','實際處理'],['保留final test','GPU 193280 / 48320；學生519 / 130；固定索引，不為分數重切'],['Development CV','外層五折；SFS內部三折；群組或重複X依規則隔離'],['每fold前處理','只用當次training資料學習填補、類別編碼、標準化；validation / test僅轉換'],['調參與選擇','CV驗證預測誤差合併計算RMSE；同分優先較少平均特徵數，再固定ID'],['最終模型','用完整development重作選取／擬合，凍結後僅評固定test'],['結果保存','36正式模型、四情境488候選、來源與程式SHA；不以test反向挑模型']],[123,388])
    p('CV是調參／選模型的依據，本身帶有選擇樂觀性，不能冒充外部驗證。測試集評估與development內模型診斷分開標示。[M3]')
    h('評估指標')
    p('MAE表示平均絕對誤差，MSE對大誤差較敏感，RMSE保留Target單位，R²以測試集變異為比較基準。不同題目的RMSE單位不同，不直接跨題排名。Adjusted R²標明development OLS與自由度；不把它當另一個test R²。')

    page(5,'五種選擇方法與OLS的角色')
    tab([['方法','候選控制','最後預測模型'],['SelectKBest','單變量F評分，k逐一比較','選取欄位後OLS'],['RFE','標準化OLS權重，遞迴移除，k逐一比較','選取欄位後OLS'],['Forward SFS','內部CV逐步加入，k逐一比較','選取欄位後OLS'],['Lasso selection','α網格，保留非零係數','選取欄位後OLS'],['ElasticNet selection','α與L1 ratio網格，保留非零係數','選取欄位後OLS']],[144,236,131])
    p('OLS是普通最小平方法，也是sklearn LinearRegression使用的線性回歸估計方式。統一最終OLS有助比較不同選擇策略；另列Ridge／Lasso直接預測，以比較正則化係數的作用。[M1/M2]')
    h('與DIC2的差異')
    p('DIC2也有調α，但以係數排序後強制取前k個，可能納入零係數尾端。本次只保留實際非零係數（數值容差1e-10），k是結果，故不保證每個整數都出現。不是刪掉已跑完但分數不好的k。')
    p('Mean baseline不使用X，一律預測training的Target平均值；All-feature OLS使用全部X。前者檢查是否優於猜平均，後者檢查選特徵是否改善表現或節省欄位。兩者不是特徵選擇演算法。')

    page(6,'GPU：CRISP-DM與凍結方法比較')
    c,m,i=metrics('sgemm')
    p('Business：用GPU設定估計矩陣乘法執行時間；錯估可能導致錯誤的配置或資源規劃。成功標準是可重現流程與可信評估，不宣稱能取代硬體量測。')
    p('Understanding / Preparation：241600設定、14X、四次Run平均Target；固定development / test，所有轉換與選擇限training。Modeling：主代表為SelectKBest k=13再OLS，選擇依據為CV。')
    comparison('sgemm')
    p(f"Evaluation：主代表test MAE={m['mae']:.3f} ms、MSE={m['mse']:.3f} ms²、RMSE={m['rmse']:.3f} ms、R²={m['r2']:.6f}。同子集合的不同流程可能得到相同test，但fold選取不同使CV略有差異。",'small')
    p('Deployment：網站呈現公式、區間、診斷及用途限制；只能作同資料分布的探索，未經跨硬體驗證不能外推其他GPU。')

    page(7,'GPU：區間與負時間的意義')
    pic('artifacts/analysis/evaluation/sgemm/intervals.png','Figure A1. Frozen GPU representative. Sorted held-out predictions with conditional 95% intervals; full-test metrics are computed on all 48,320 rows.',315)
    p(f"95%個別觀測PI描述性覆蓋 {percent(i['observation_pi_coverage'])}；平均寬度 {i['observation_pi_mean_width']:.3f} ms。平均反應CI平均寬度 {i['location_ci_mean_width']:.3f} ms，兩者不能混稱。")
    p(f"負點預測 {i['negative_prediction_count']:,}/{i['rows']:,}（{i['negative_prediction_count']/i['rows']*100:.2f}%），PI下界負值 {i['negative_pi_lower_count']:,}筆。執行時間不能為負，顯示目前加法線性形式與不受界限的誤差模型有實用限制；保留原值，不裁成零美化結果。")
    p('寬PI可能提高覆蓋，但不代表模型具有高解析度或未來一定覆蓋95%。本案例支持「目前形式能力有限」，不支持「任何多元線性回歸都不可能有效」。')

    page(8,'GPU：假設診斷與用途限制')
    pic('artifacts/analysis/evaluation/sgemm/diagnostics.png','Figure A2. Development residuals, normal Q-Q and influence diagnostics. These observations diagnose the frozen model; they do not retune final test.',320)
    d=read(EVAL['sgemm']['representative']['diagnostics_path']);v=max(x['vif'] for x in d['vif'])
    p(f"殘差skew={d['normality']['skewness']:.3f}、excess kurtosis={d['normality']['excess_kurtosis']:.3f}，Q-Q偏離及BP檢定揭示誤差形狀／等變異限制。p值低於浮點解析度時不寫成精確機率零。最大VIF={v:.3f}，condition number={d['condition_number_standardized_design']:.3f}，不能把低VIF解讀為模型形式已正確。")
    p('Cook與leverage只作影響診斷；敏感度分析限development，不因test分數較差刪資料。參數配置資料也不等於隨機獨立的未來硬體實驗；沒有任意套用列序自相關檢定。')
    p('HC3可以補充係數／位置的不確定性，但不會自動修正傳統觀測PI、非線性、群內相關或選擇後推論。')

    page(9,'學生：CRISP-DM與凍結方法比較')
    c,m,i=metrics('student')
    p('Business：估計已知前期評量與背景條件下的G3，作模型比較及教學分析；不據此決定個別學生處置，也不宣稱因果或開學預警。')
    p('Understanding / Preparation：只用649筆student-por，不混入另一科的重複學生；主版32原始X／41編碼欄位。Modeling：ElasticNet非零選取後OLS為主代表，最終只保留G1與G2。')
    comparison('student')
    p(f"Evaluation：主代表test MAE={m['mae']:.3f}分、MSE={m['mse']:.3f}分²、RMSE={m['rmse']:.3f}分、R²={m['r2']:.6f}。Lasso prediction的test可較好，但不因此事後替換原先CV凍結的主代表。",'small')
    p('Deployment：網站提供G1／G2條件試算、CI／PI及背景版本；可計算不等於可用於教育干預或跨校預測。')

    page(10,'學生：預測區間與成績資訊')
    pic('artifacts/analysis/evaluation/student/intervals.png','Figure B1. Frozen student representative. Test observations sorted by prediction; 95% mean-response CI and observation PI have different targets.',315)
    p(f"PI覆蓋 {percent(i['observation_pi_coverage'])}，僅130筆test；平均寬度 {i['observation_pi_mean_width']:.3f}分。平均反應CI平均寬度 {i['location_ci_mean_width']:.3f}分。100%描述性覆蓋不等於未來100%正確，亦不證明全部假設成立。")
    p('G1／G2與G3高度相關，有助於已取得前期成績後估計期末表現；這個資訊條件需要在介面及報告中說清楚。係數是模型條件關聯，不能解讀成提高某次成績必然造成G3增加。')
    p('分數定義為0-20，OLS／PI不受此界限限制；超界輸出依原值呈現並提示，不在沒有評估的情況下裁切。')

    page(11,'學生：診斷與移除前期成績的補充')
    pic('artifacts/analysis/evaluation/student/diagnostics.png','Figure B2. Development diagnostics of the two-predictor OLS. High held-out R² does not imply normality, equal variance or causal validity.',295)
    d=read(EVAL['student']['representative']['diagnostics_path'])
    p(f"BP p={pvalue(d['heteroskedasticity']['p_value'])}，殘差skew={d['normality']['skewness']:.3f}、excess kurtosis={d['normality']['excess_kurtosis']:.3f}；G1／G2的VIF約{d['vif'][0]['vif']:.3f}。兩所學校、樣本量與觀察性資料限制代表性；高R²不抵銷這些限制。")
    bg=REP['student_background'];p(f"背景版本移除G1／G2，30原始／39編碼X，CV選k=7；test R²={bg['test']['r2']:.4f}、RMSE={bg['test']['rmse']:.3f}分。與主版的落差顯示前期成績資訊的重要性，不能用來證明單一背景欄位的因果效果。")
    p('背景版本也可能含學期內才完整可知的缺席等資訊；未確認時間點前仍不稱開學預測。影響點不直接刪除；其development敏感度只作限制說明。')

    page(12,'補充情境與區間的三種意義')
    tab([['預先規劃的情境','CV主代表 / 選取數','Test RMSE','Test R²'],*[[n,NAMES[REP[n]['method']]+' / '+str(REP[n]['selected_count']),fmt(REP[n]['test']['rmse']),fmt(REP[n]['test']['r2'],4)] for n in CASES]],[141,190,90,90])
    p('GPU log版本是先預測log時間再exp回轉換，沒有smearing校正，表示幾何位置，不是原尺度算術平均。本次其MAE較小、RMSE與R²並未全面優於原版；不挑單一指標宣稱全面改善。')
    tab([['區間','回答的問題','本作業界線'],['係數95% CI','所選設計下的回歸係數不確定性','classical與HC3分開；選擇後條件推論'],['平均反應95% CI','這組X的條件平均反應在哪裡','不能用個別y的命中率驗證真實平均'],['個別觀測95% PI','一筆新觀測可能落在哪裡','含殘差變異；通常更寬；依賴誤差模型']],[120,192,199])
    p('區間依相同最終OLS與前處理計算，獨立核對係數、covariance、Student-t與PI覆蓋。rank、自由度或變異不足時明示不可推論；正則化／Dummy不硬套OLS CI。名目95%不是預測正確率。[M4]')

    page(13,'新CSV的真實分析與網站操作')
    pic('artifacts/validation/screenshots/stage6/final-six-methods.jpg','Figure C1. Actual local browser: third public dataset, six successful method requests and nine computed models. Scores are shown faithfully, including negative held-out R².',300)
    p('CSV上傳或公開HTTPS URL -> 預覽 -> 選Target／排除X／指定group -> 執行基準與五方法 -> 查看CV、完整test、公式、區間、診斷 -> 單筆預測及下載。換設定隔離舊結果；取消保留完成模型並可逐方法重試。')
    p('以UCI Parkinsons Telemonitoring真實5875列、16X及42名受試者驗證兩條路徑；群組隔離後4623 development／1252 test，九模型均真正重算。這是功能驗證，不是第三正式題或醫療可用性證明。')
    p('50_Startups另驗證50列、State類別、換Target及排除欄位，不能拿舊題預設JSON冒充第三資料分析。')

    page(14,'部署架構、資源界線與隱私')
    tab([['層次','本機落地'],['Frontend','原生HTML / CSS / ES modules / SVG，沿用DIC2版型；正式結果按需載入'],['Analysis','一般Python核心，共用於CLI、正式資料與自訂資料'],['HTTP','FastAPI薄層；每方法自足請求，無跨instance歷史DB'],['URL取得','僅公開HTTPS 443；逐跳檢查DNS／固定公開IP／原host TLS與SNI'],['取消／並行','instance互斥鎖由真正運算結束釋放；協作取消不保證立即停止求解'],['資料保留','當次請求與頁面記憶體；表單系統暫存關閉清理；可下載結果']],[120,391])
    p('CSV最多3,500,000 bytes，50-10000列，來源最多100欄、原始X最多39、encoded最多64、每類別最多20類。JSON單回應最多3,000,000 bytes；圖有界顯示，指標／覆蓋使用全test。每方法協作預算120秒；URL整體15秒。')
    p('部署目標為Vercel Hobby，但尚未公開部署。build大小、套件、實際runtime／冷啟動、並行總額、費用與公開新資料操作留待階段8驗證；不把本機速度當雲端保證。沒有Git push、雲端狀態變更或LMS繳交。')

    page(15,'驗證證據與可重現性')
    tab([['驗證','方法與判斷依據','實際結果'],['正式模型／區間','獨立NumPy / sklearn / Student-t核對，全test與凍結SHA','279項；33原單元'],['正式前端推論','Python對網站共用模組，含原尺度方程','3590數值；1891資料／公式核對'],['階段6單元','原33 + 39服務測試；傳輸失敗／deadline為受控測試','72成功'],['真實HTTP／資料','外部UCI HTTPS + localhost + CLI + 獨立重算','48成功；類別資料另14'],['新模型前端數值','18模型21案例；容差1e-7絕對 + 1e-8相對','129核對；最大誤差8.73e-11'],['瀏覽器與下載','真實上傳／URL／取消重試／390與320寬度；實際下載對HTTP','31瀏覽器；2894數值差異0']],[110,280,121])
    p('驗證成功只表示軟體與計算符合所檢查契約，不證明統計假設成立、教育／醫療可用或公開服務已驗收。真實外部資料取得、localhost服務、受控失敗及未部署範圍分開保存。')
    p('selection-freeze SHA-256：\n3a4fec9047f6e08b4eace272bd2f43d7fb4be1fb8356525549340561f15425f3','small')
    p('主要證據：artifacts/validation/stage4.json、stage5-data.json、stage5-prediction.json、stage6-{unit,http,teaching,prediction,browser,downloads,completion}.json。188受保護分析成果、493展示JSON及原始／處理資料保持原SHA。','small')

    research=read('docs/notebooklm/review.json')
    page(16,'NotebookLM研究：GPU執行時間')
    p('來源：使用者提供NotebookLM實際回答；以下經GPT核對、修訂整合，不是逐字原始輸出。原文與SHA保存在本機docs/notebooklm/received/與review.json。','small')
    h('研究摘要（超過100中文字）')
    p(research['summaries']['gpu']['summary'])
    h('本作業採用／未採用')
    p(research['summaries']['gpu']['adopted'])
    p(research['summaries']['gpu']['not_adopted'])
    h('研究結果與本次實驗的邊界')
    p('A2第8.3節位於本機16頁arXiv版本的PDF第12–14頁。其對數TT模型的Sobol比例不是本作業raw-time OLS的R²上限；保留相關機制提示，不用來定量證明本作業損失了75%變異。選特徵不新增交互作用項，但仍可能改變泛化表現。')
    p('本作業已完成193280／48320固定切分與訓練；原文「尚未訓練」已更正。GPU傳統95% PI實測覆蓋97.32%、平均寬1111.408 ms，需連同假設限制閱讀，不能說完全沒有區間資訊，也不保證未來有效。')
    p('[A1] UCI Dataset Information / Additional Variable Information；[A2] §8.3、Tables6–9，PDF pp12–14。完整URL見引用頁。','small')

    page(17,'NotebookLM研究：學生葡萄牙語成績')
    h('研究摘要（超過100中文字）')
    p(research['summaries']['student']['summary'])
    h('本作業採用／未採用')
    p(research['summaries']['student']['adopted'])
    p(research['summaries']['student']['not_adopted'])
    h('核對修正與協作範圍')
    p('已修正原文的Label Encoding及五方法誤列。G1／G2是第一、第二評量期，不寫成兩個學期；背景欄位的收集時點沒有全部證實，不能自行補成期末已知。B2之編碼敏感度與分數只屬其數學資料實驗。')
    p('GPT協助需求、程式、分析、驗證、研究核對與排版；使用者決定範圍、保留GPU案例並實際操作NotebookLM。貼文未附內部引用點擊對照，因此只聲明已獨立核對保留主張，不冒稱已驗證其NotebookLM介面。')
    p('[B1] UCI Dataset Information / Additional Variable Information；[B2] DOI10.1038/s41598-026-40538-y，Abstract / Methodology / encoding sensitivity / Discussion。B3全文未取得，不使用內文。','small')
    p('尚待階段8：repo、公開部署與加分操作實證；最終繳交前更新對話／附件並逐頁檢查。研究摘要本機整合完成，不代表已公開或已繳交。','small')

    page(18,'引用與資料來源')
    p('以下為可追溯的外部來源；頁碼／章節及取得限制另見docs/notebooklm/sources.json。研究主張與本作業計算分開。','small')
    sources=read('docs/notebooklm/sources.json')['sources']
    for s in sources:
        if s['id'] in ['A3','B4']:continue
        p(f"[{s['id']}] {s['author']}\n{s['title']}",'small')
        p(s['url'],'small')
        if s['id']=='B3':p('僅核對UCI書目；原作者／典藏全文未取得，不依此宣稱已核對全文方法。','small')
    p('Kaggle來源：rupals/gpu-runtime（v4）、uciml/student-alcohol-consumption（v2）；原始字典與授權依UCI。[A3/B4]','small')
    p('作業正文：https://lms2020.nchu.edu.tw/course/homework/74761；本機唯讀快照artifacts/reference/lms-assignment.txt。第三驗證資料：Tsanas與Little，UCI Parkinsons Telemonitoring，DOI 10.24432/C5ZS3N，CC BY 4.0。','small')

    for number,n,title in [(19,'sgemm','附錄A：GPU原尺度公式與係數'),(20,'student','附錄B：學生原尺度公式與係數')]:
        page(number,title)
        detail=read('web/'+REP[n]['detail'])
        rows=[x for x in detail['coefficient_intervals'] if x['basis']=='unscaled_encoded' and x['covariance']=='classical']
        robust={x['column']:x for x in detail['coefficient_intervals'] if x['basis']=='unscaled_encoded' and x['covariance']=='HC3'}
        p('下表為完整development擬合的原尺度encoded OLS係數；非標準化係數。顯示值四捨五入，網站推論與JSON使用完整精度；所選設計與選擇後推論的條件限制仍成立。')
        equation=CASES[n]['target']+' = '+fmt(rows[0]['coefficient'],5)
        for row in rows[1:]:equation+=(' + ' if row['coefficient']>=0 else ' - ')+fmt(abs(row['coefficient']),5)+' x '+row['column']
        p(equation,'small')
        tab([['Predictor','Coefficient','95% classical CI','95% HC3 CI'],*[[x['column'],fmt(x['coefficient'],5),'['+fmt(x['ci_lower'],5)+', '+fmt(x['ci_upper'],5)+']','['+fmt(robust[x['column']]['ci_lower'],5)+', '+fmt(robust[x['column']]['ci_upper'],5)+']'] for x in rows]],[88,100,161,162])
        p('係數描述在其他所選變數固定時的條件線性關係，不是因果效果。HC3調整係數／位置的標準誤，不能解讀為已修正個別觀測PI、群內相關或模型選擇不確定性。')
        if n=='student':p('學生主代表的最終輸入只有G1與G2。這個方程以已知前期成績為前提，不代表僅靠開學背景可達到相同表現。')
        p('數值來源：web/'+REP[n]['detail']+'；係數與區間已於階段4／5獨立核對。','small')

    doc=SimpleDocTemplate(str(OUT/'L7_CRISPDM_MR_report_draft.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=49,bottomMargin=49,title='L7 CRISP-DM Multiple Regression - Analysis Draft',author='AIoT coursework - GPT-assisted; user reviewed scope',pageCompression=1)
    doc.build(story,onFirstPage=footer('分析報告草稿 / 研究已核對；公開驗收待完成'),onLaterPages=footer('分析報告草稿 / 研究已核對；公開驗收待完成'))
    (SRC/'report-draft.md').write_text('# L7 CRISP-DM Multiple Regression\n\n'+'\n\n'.join(TEXT)+'\n')
    (SRC/'report-data.json').write_text(json.dumps({'created_at':NOW.isoformat(),'status':'research_integrated_pending_public_deployment','scenario_values':TRACE,'freeze_sha256':hashlib.sha256((ROOT/'artifacts/analysis/models/selection-freeze.json').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')

def infographic():
    dest=OUT/'L7_CRISPDM_MR_infographic.pdf';w,h=A3;c=canvas.Canvas(str(dest),pagesize=A3,pageCompression=1);c.setTitle('L7 CRISP-DM Multiple Regression - Infographic')
    c.setFillColor(colors.HexColor('#F6F9FA'));c.rect(0,0,w,h,fill=1,stroke=0)
    def block(x,y,bw,bh,title,body,bg=colors.white):
        c.setFillColor(bg);c.setStrokeColor(colors.HexColor('#D3E0E3'));c.roundRect(x,y,bw,bh,12,fill=1,stroke=1)
        titleP=Paragraph(html.escape(safe(title)),ParagraphStyle('it',fontName='TC',fontSize=17,leading=24,textColor=TEAL,wordWrap='CJK'))
        bodyP=Paragraph(html.escape(safe(body)).replace('\n','<br/>'),ParagraphStyle('ib',fontName='TC',fontSize=13.3,leading=20,textColor=INK,wordWrap='CJK',splitLongWords=True))
        _,th=titleP.wrap(bw-30,bh);_,bhh=bodyP.wrap(bw-30,bh)
        assert th+bhh+39<bh,(title,th,bhh,bh)
        titleP.drawOn(c,x+15,y+bh-15-th);bodyP.drawOn(c,x+15,y+bh-24-th-bhh)
    c.setFillColor(TEAL);c.rect(0,h-118,w,118,fill=1,stroke=0)
    c.setFillColor(colors.white);c.setFont('TC',28);c.drawString(36,h-45,'CRISP-DM × Multiple Regression')
    c.setFont('TC',15);c.drawString(36,h-75,'兩題正式分析 + 真實新CSV分析 | L7 / HW2')
    c.setFont('TC',11.5);c.drawString(36,h-98,'同一分析核心、先CV後test、如實呈現能力與限制')
    margin=36;gap=18;cw=(w-2*margin-gap)/2;top=h-138
    a=REP['sgemm'];b=REP['student']
    block(margin,top-223,cw,223,'A / GPU Kernel Runtime',f"14個原始輸入 | 241,600列\nTarget：四次Run平均時間\nSelectKBest 13欄 -> OLS\nTest R² = {a['test']['r2']:.4f}\nRMSE = {a['test']['rmse']:.3f} ms\n定位：目前原始特徵加法模型能力有限",PALE)
    block(margin+cw+gap,top-223,cw,223,'B / Student Portuguese Grade',f"32個原始輸入 | 649列\nTarget：G3（0-20分）\nElasticNet選G1/G2 -> OLS\nTest R² = {b['test']['r2']:.4f}\nRMSE = {b['test']['rmse']:.3f} 分\n定位：已知前期成績的回顧條件估計",BLUE)
    y=top-245;c.setFillColor(TEAL);c.setFont('TC',18);c.drawString(margin,y,'CRISP-DM / 六階段都有證據')
    smallw=(w-2*margin-2*gap)/3;bh=112;ytop=y-18
    steps=[('01 Business','定義Target、用途與錯誤影響\n不把高分等同高R²'),('02 Understanding','來源、字典、缺值與分布\n原始X與encoded欄位分開'),('03 Preparation','固定development / test\n前處理只fit training fold'),('04 Modeling','五方法選取 -> OLS\n另列mean、全X與正則化'),('05 Evaluation','固定test、CI / PI與診斷\n不看test重新選勝出者'),('06 Deployment','兩題下拉 + CSV / URL實算\n本機完成，公開驗收待8')]
    for i,(title,body) in enumerate(steps):block(margin+(i%3)*(smallw+gap),ytop-(i//3+1)*(bh+gap),smallw,bh,title,body)
    ybase=ytop-2*(bh+gap)-132
    block(margin,ybase,w-2*margin,112,'Feature Selection / 選擇策略有不同控制方式','SelectKBest、RFE、SFS：比較k；Lasso、ElasticNet：比較α等參數，保留非零係數。\nFrozen表格列各方法CV勝出者；其他候選只作development探索，不用test反向挑模型。')
    y2=ybase-176
    block(margin,y2,cw,158,'CI / PI / 限制要一起讀','係數CI、平均反應CI、個別PI不同。\nGPU有18.40%負時間預測；PI寬。\n學生PI覆蓋100%，但test只有130筆。\n高覆蓋不保證未來有效，HC3不修復PI。')
    block(margin+cw+gap,y2,cw,158,'Bring Your Own Data / 真正重算','CSV / 公開HTTPS -> 預覽與設定\n六請求、九模型、取消重試及下載\nUCI第三資料：5875列 / 16X / 42群組\n上傳與URL均完成本機實際分析。')
    foot=y2-80
    p=Paragraph('資料：UCI SGEMM / Student Performance（CC BY 4.0）；Kaggle鏡像。數字取自凍結正式JSON。<br/>原作者：Paredes、Ballester-Ripoll；Cortez。DOI：10.24432/C5MK70、10.24432/C5TG7T。<br/>GPT協助程式、分析、驗證與排版；使用者確認範圍及案例定位。NotebookLM兩題回答已由使用者提供；摘要經來源核對整合。<br/>本機分析成果；尚未公開部署、取得加分最終證據或繳交。'+DATE,ParagraphStyle('if',fontName='TC',fontSize=10.5,leading=16,textColor=MUTED,wordWrap='CJK'))
    _,ph=p.wrap(w-2*margin,75);assert foot-ph>17;p.drawOn(c,margin,foot-ph)
    c.showPage();c.save()

def transcripts():
    manifest=[]
    for name,title,outname in [('hw2','物聯網作業 2 - CRISP-DM & 多元線性回歸','HW2_conversation_snapshot.pdf')]:
        data=read(f'reports/source/transcripts/{name}.json');story=[para('AI協作對話紀錄','h1'),para(title,'h2'),para('實際使用者與助手公開訊息快照；不是GPT重寫的對話摘要。工具呼叫／輸出、內部推理及自動附加的瀏覽器情境（非使用者輸入）不納入閱讀版。來源為read_thread全部分頁，無截斷旗標；保存原始JSON供核對。'),para(f'匯出整理：{DATE}（Asia/Taipei）。本作業仍在進行，HW2含階段7開始時的訊息快照；最終繳交前必須重新匯出。', 'small'),para('版面將Markdown符號保留為文字、長行折行；連續空白作排版調整，破折號統一為ASCII，字型未涵蓋字元以[U+代碼]呈現。原JSON完整保留原字元與訊息內容。','small'),PageBreak()]
        count=0
        for turn in data['turns']:
            stamp=datetime.fromtimestamp(turn['startedAt'],ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M')
            for message in turn['messages']:
                count+=1;role='使用者' if message['role']=='user' else '助手 / '+('最終回覆' if message.get('phase')=='final_answer' else '公開進度')
                story.append(para(f'{count:03d}  |  {role}  |  {stamp}','role'));story.append(para(display_message(message['text']),'message'))
        doc=SimpleDocTemplate(str(OUT/outname),pagesize=A4,rightMargin=43,leftMargin=43,topMargin=49,bottomMargin=49,title=title+' - Message Snapshot',author='User and GPT assistant; verbatim message source',pageCompression=1)
        doc.build(story,onFirstPage=footer('對話訊息快照 / '+title,False),onLaterPages=footer('對話訊息快照 / '+title,False))
        manifest.append({'title':title,'thread_id':data['thread_id'],'messages':count,'automatic_browser_context_blocks_omitted':sum('<in-app-browser-context' in m['text'] for t in data['turns'] for m in t['messages']),'path':'reports/output/pdf/'+outname,'source_json':f'reports/source/transcripts/{name}.json','source_sha256':hashlib.sha256((ROOT/f'reports/source/transcripts/{name}.json').read_bytes()).hexdigest()})
    return manifest

def main():
    OUT.mkdir(parents=True,exist_ok=True);SRC.mkdir(parents=True,exist_ok=True)
    for group in ['protected_sha256','export_sha256','source_sha256']:
        for path,sha in read('artifacts/analysis/website/export-manifest.json')[group].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    report();infographic();ts=read('artifacts/validation/stage7-pdf-build.json')['transcripts'] if '--research-only' in __import__('sys').argv else transcripts()
    artifacts=[]
    for p in sorted(OUT.glob('*.pdf')):
        reader=PdfReader(p);artifacts.append({'path':str(p.relative_to(ROOT)),'pages':len(reader.pages),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text_characters':sum(len(page.extract_text() or '') for page in reader.pages)})
    manifest={'status':'authored_pending_render_review','created_at':NOW.isoformat(),'notebooklm_status':'user_outputs_received_summaries_reviewed','public_deployment':'not_done','artifacts':artifacts,'transcripts':ts,'font':'Arial Unicode embedded; unsupported characters visibly annotated','glyph_substitutions':{f'U+{ord(k):04X}':v for k,v in FALLBACKS.items()},'source_script':'reports/source/build_deliverables.py'}
    (ROOT/'artifacts/validation/stage7-pdf-build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'artifacts':artifacts,'glyph_substitution_types':len(FALLBACKS)},ensure_ascii=False))

if __name__=='__main__':main()
