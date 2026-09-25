from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_LINE_SPACING
from pathlib import Path
import re
import math
import hashlib
from PIL import Image, ImageDraw, ImageFont

OUT = Path(r'C:\Users\Administrator\Documents\Codex\2026-09-24\referenced-chatgpt-conversation-this-is-an-3\outputs')
OUT.mkdir(parents=True, exist_ok=True)
DIAG_DIR = OUT.parent / 'work' / 'diagrams'
DIAG_DIR.mkdir(parents=True, exist_ok=True)

def _diagram_font(size=22):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simsun.ttc', r'C:\Windows\Fonts\Deng.ttf']:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def make_diagram(spec, key):
    """Create a clean, labeled coordinate diagram for a geometry condition."""
    path = DIAG_DIR / (re.sub(r'[^0-9A-Za-z_-]+', '_', key) + '.png')
    if path.exists(): return path
    W,H=720,500
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    kind=spec.get('kind','circle_generic')
    pts=[]
    if 'center' in spec: pts.append(spec['center'])
    if 'point' in spec: pts.append(spec['point'])
    pts += spec.get('points',[])
    if 'radius' in spec and 'center' in spec:
        cx,cy=spec['center']; r=spec['radius']; pts += [(cx-r,cy-r),(cx+r,cy+r)]
    if 'tangent_y' in spec: pts += [(0,spec['tangent_y'])]
    if 'line_y' in spec: pts += [(0,spec['line_y'])]
    # Include the drawn circle's full extent when the radius is inferred.
    if 'center' in spec:
        cc=spec['center']; rr=spec.get('radius')
        if rr is None and 'point' in spec: rr=math.dist(cc,spec['point'])*1.18
        if rr is not None: pts += [(cc[0]-rr,cc[1]-rr),(cc[0]+rr,cc[1]+rr)]
    if spec.get('points'):
        cc=(sum(p[0] for p in spec['points'])/len(spec['points']),sum(p[1] for p in spec['points'])/len(spec['points']))
        rr=max(3.2,max(math.dist(cc,p) for p in spec['points'])*1.2)
        pts += [(cc[0]-rr,cc[1]-rr),(cc[0]+rr,cc[1]+rr)]
    if not pts: pts=[(-4,-4),(4,4)]
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    xmin,xmax=min(xs)-2,max(xs)+2; ymin,ymax=min(ys)-2,max(ys)+2
    if 'center' in spec and 'radius' not in spec: xmin=min(xmin,spec['center'][0]-5); xmax=max(xmax,spec['center'][0]+5); ymin=min(ymin,spec['center'][1]-5); ymax=max(ymax,spec['center'][1]+5)
    scale=min((W-130)/(xmax-xmin),(H-100)/(ymax-ymin))
    def xy(x,y): return (int(70+(x-xmin)*scale), int(H-55-(y-ymin)*scale))
    # grid
    for xi in range(math.floor(xmin), math.ceil(xmax)+1):
        x0,y0=xy(xi,ymin); x1,y1=xy(xi,ymax); d.line((x0,y0,x1,y1),fill='#eeeeee',width=1)
    for yi in range(math.floor(ymin), math.ceil(ymax)+1):
        x0,y0=xy(xmin,yi); x1,y1=xy(xmax,yi); d.line((x0,y0,x1,y1),fill='#eeeeee',width=1)
    # axes
    if ymin<=0<=ymax:
        x0,y0=xy(xmin,0); x1,y1=xy(xmax,0); d.line((x0,y0,x1,y1),fill='#555555',width=2); d.polygon([(x1,y1),(x1-12,y1-6),(x1-12,y1+6)],fill='#555555')
    if xmin<=0<=xmax:
        x0,y0=xy(0,ymin); x1,y1=xy(0,ymax); d.line((x0,y0,x1,y1),fill='#555555',width=2); d.polygon([(x1,y1),(x1-6,y1+12),(x1+6,y1+12)],fill='#555555')
    font=_diagram_font(22); small=_diagram_font(18)
    if 'center' in spec and 'radius' in spec:
        cx,cy=spec['center']; r=spec['radius']; a=xy(cx-r,cy+r); b=xy(cx+r,cy-r); d.ellipse((a[0],a[1],b[0],b[1]),outline='#2468a2',width=4)
    elif kind in ('circle_generic','circle_point','circle_point_tangent','circle_point_line','three_points'):
        c=spec.get('center',(0,0)); r=spec.get('radius',4)
        if 'point' in spec: r=max(r,math.dist(c,spec['point'])*1.18)
        if 'points' in spec:
            # circumcircle-like visual framing for three-point tasks
            c=(sum(p[0] for p in spec['points'])/len(spec['points']),sum(p[1] for p in spec['points'])/len(spec['points'])); r=max(3.2,max(math.dist(c,p) for p in spec['points'])*1.2)
        a=xy(c[0]-r,c[1]+r); b=xy(c[0]+r,c[1]-r); d.ellipse((a[0],a[1],b[0],b[1]),outline='#2468a2',width=4)
    if 'center' in spec:
        p=xy(*spec['center']); d.ellipse((p[0]-7,p[1]-7,p[0]+7,p[1]+7),fill='#d33'); d.text((p[0]+10,p[1]-28),'C',font=font,fill='#222')
    if 'point' in spec:
        p=xy(*spec['point']); d.ellipse((p[0]-7,p[1]-7,p[0]+7,p[1]+7),fill='#1677c8'); d.text((p[0]+10,p[1]-28),'P',font=font,fill='#222')
    for i,pt in enumerate(spec.get('points',[])):
        p=xy(*pt); d.ellipse((p[0]-7,p[1]-7,p[0]+7,p[1]+7),fill='#1677c8'); d.text((p[0]+9,p[1]-27),chr(65+i),font=font,fill='#222')
    for field,color,label in [('tangent_y','#d55','切线'),('line_y','#e58a1a','直线')]:
        if field in spec:
            yy=spec[field]; x0,y0=xy(xmin,yy); x1,y1=xy(xmax,yy); d.line((x0,y0,x1,y1),fill=color,width=4); d.text((x1-70,y1-28),label,font=small,fill=color)
    if 'line' in spec:
        A,B,C=spec['line']; crossings=[]
        if abs(B)>1e-9:
            for xx in (xmin,xmax): crossings.append((xx,(-A*xx-C)/B))
        if abs(A)>1e-9:
            for yy in (ymin,ymax): crossings.append(((-B*yy-C)/A,yy))
        crossings=[p0 for p0 in crossings if xmin-1e-6<=p0[0]<=xmax+1e-6 and ymin-1e-6<=p0[1]<=ymax+1e-6]
        if len(crossings)>=2:
            p0,p1=crossings[0],crossings[1]; q0=xy(*p0); q1=xy(*p1); d.line((q0[0],q0[1],q1[0],q1[1]),fill='#e58a1a',width=4); d.text((q1[0]-55,q1[1]-28),'直线',font=small,fill='#e58a1a')
    d.text((W-55,H-55),'x',font=small,fill='#555'); d.text((78,15),'y',font=small,fill='#555')
    im.save(path,dpi=(150,150)); return path

def add_diagram(doc, spec, key, width=Inches(3.85)):
    p=doc.add_paragraph(); set_para(p, before=2, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    sig=hashlib.md5(repr(spec).encode('utf-8')).hexdigest()[:8]
    p.add_run().add_picture(str(make_diagram(spec,key+'_'+sig)), width=width)
    cap=doc.add_paragraph(); set_para(cap,after=4,align=WD_ALIGN_PARAGRAPH.CENTER); add_text(cap,'示意图（用于条件翻译与模型建立）',size=8.5,color='666666')

# ---------- OOXML helpers ----------
def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd'); tcPr.append(shd)
    shd.set(qn('w:fill'), fill)

def set_cell_borders(cell, color='D9D9D9', sz='6'):
    tc = cell._tc; tcPr = tc.get_or_add_tcPr()
    borders = tcPr.first_child_found_in('w:tcBorders')
    if borders is None:
        borders = OxmlElement('w:tcBorders'); tcPr.append(borders)
    for edge in ('top','left','bottom','right','insideH','insideV'):
        tag = 'w:'+edge
        el = borders.find(qn(tag))
        if el is None:
            el = OxmlElement(tag); borders.append(el)
        el.set(qn('w:val'),'single'); el.set(qn('w:sz'),sz); el.set(qn('w:space'),'0'); el.set(qn('w:color'),color)

def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc; tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None:
        tcMar = OxmlElement('w:tcMar'); tcPr.append(tcMar)
    for m,v in [('top',top),('start',start),('bottom',bottom),('end',end)]:
        node=tcMar.find(qn('w:'+m))
        if node is None:
            node=OxmlElement('w:'+m); tcMar.append(node)
        node.set(qn('w:w'),str(v)); node.set(qn('w:type'),'dxa')

def set_repeat_table_header(row):
    trPr = row._tr.get_or_add_trPr(); tblHeader = OxmlElement('w:tblHeader'); tblHeader.set(qn('w:val'),'true'); trPr.append(tblHeader)

def set_keep_with_next(paragraph):
    pPr = paragraph._p.get_or_add_pPr(); keep = OxmlElement('w:keepNext'); pPr.append(keep)

def set_run_font(run, name='Microsoft YaHei', size=10.5, bold=False, color='000000', italic=False):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:ascii'), name)
    run._element.get_or_add_rPr().rFonts.set(qn('w:hAnsi'), name)
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), name)
    run.font.size = Pt(size); run.font.bold = bold; run.font.italic = italic; run.font.color.rgb = RGBColor.from_string(color)

def set_para(paragraph, before=0, after=6, line=1.15, align=None):
    fmt=paragraph.paragraph_format; fmt.space_before=Pt(before); fmt.space_after=Pt(after); fmt.line_spacing=line
    if align is not None: paragraph.alignment=align

def add_text(paragraph, text, **kw):
    r=paragraph.add_run(text); set_run_font(r, **kw); return r

def add_label_para(doc, label, text, after=6):
    p=doc.add_paragraph(); set_para(p, after=after)
    add_text(p, label, bold=True, size=10.5)
    add_text(p, text, size=10.5)
    return p

def add_math_para(doc, text, after=6, center=False):
    p=doc.add_paragraph(); set_para(p, after=after, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER if center else None)
    add_text(p, text, name='Cambria Math', size=11.5)
    return p

def add_bullet(doc, text, level=0, after=2):
    p=doc.add_paragraph(style='List Bullet'); p.paragraph_format.left_indent=Inches(0.25*level); set_para(p, after=after, line=1.05); add_text(p,text,size=10.5); return p

def add_numbered(doc, text, num):
    p=doc.add_paragraph(); set_para(p, after=2, line=1.05); add_text(p, f'{num} ', bold=True, size=10.5); add_text(p, text, size=10.5); return p

def add_answer_area(doc, lines=5):
    p=doc.add_paragraph(); set_para(p, before=3, after=2); add_text(p, '学生作答区（写出关键步骤）', bold=True, size=10.5)
    tbl=doc.add_table(rows=lines, cols=1); tbl.alignment=WD_TABLE_ALIGNMENT.CENTER; tbl.autofit=True
    for row in tbl.rows:
        cell=row.cells[0]; cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; set_cell_borders(cell, color='BFBFBF', sz='6'); set_cell_margins(cell, top=70, bottom=70)
        cell.paragraphs[0].paragraph_format.space_after=Pt(0); cell.paragraphs[0].paragraph_format.line_spacing=1.0
        add_text(cell.paragraphs[0], ' ', size=10)
    doc.add_paragraph().paragraph_format.space_after=Pt(2)

def add_node_common(doc, node, mode='student', idx=None):
    # Heading 4 = node
    h=doc.add_heading(node['title'], level=4); set_keep_with_next(h)
    add_label_para(doc, '进化过程：', node['evolution'])
    add_label_para(doc, '一句话最优解法：', node['optimal'])
    p=doc.add_paragraph(); set_para(p, after=3); add_text(p,'解题步骤：',bold=True,size=10.5)
    for i,step in enumerate(node['steps'],1): add_numbered(doc, step, i)
    add_label_para(doc, '例题：', node['example'], after=4)
    if mode=='teacher':
        add_label_para(doc, '教学提示：', node.get('teaching','先让学生说出条件翻译，再落笔写方程。'), after=4)
    add_answer_area(doc,5)
    add_label_para(doc, '参考答案：', node['answer'], after=4)
    if mode=='teacher':
        add_label_para(doc, '分步解析：', node.get('analysis','① 识别题目条件；② 转化为圆心、半径或待定系数关系；③ 写出并核验方程。'), after=4)
        p=doc.add_paragraph(); set_para(p, after=2); add_text(p,'类似题（课堂变式）：',bold=True,size=10.5)
        for q in node.get('similar',[]): add_bullet(doc,q,after=2)
    if mode=='homework':
        # homework has no in-class prompts; answer key collected at end
        pass

def add_problem_intro(doc, problem):
    h=doc.add_heading(problem['title'], level=2); set_keep_with_next(h)
    add_label_para(doc,'问题本质：',problem['essence'])
    add_label_para(doc,'最优解法一句话：',problem['optimal'])
    target=problem['title'].split('：',1)[-1]
    add_label_para(doc,'链统一原则：',f'本问题下每条进化链都围绕“{target}”展开；可以改变已知条件、方程形式或问法，但核心研究对象保持一致。')

def add_chain(doc, chain, mode='student'):
    h=doc.add_heading(chain['title'], level=3); set_keep_with_next(h)
    add_label_para(doc,'链条说明：',chain['intro'])
    for node in chain['nodes']:
        add_node_common(doc,node,mode=mode)

def set_styles(doc):
    styles=doc.styles
    normal=styles['Normal']; normal.font.name='Microsoft YaHei'; normal._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); normal.font.size=Pt(10.5); normal.font.color.rgb=RGBColor(0,0,0)
    for name,size,bold in [('Title',20,True),('Heading 1',16,True),('Heading 2',14,True),('Heading 3',12.5,True),('Heading 4',11.5,True)]:
        st=styles[name]; st.font.name='Microsoft YaHei'; st._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); st.font.size=Pt(size); st.font.bold=bold; st.font.color.rgb=RGBColor(0,0,0)
        st.paragraph_format.space_before=Pt(10 if name!='Title' else 0); st.paragraph_format.space_after=Pt(5); st.paragraph_format.keep_with_next=True
    if 'List Bullet' in styles:
        styles['List Bullet'].font.name='Microsoft YaHei'; styles['List Bullet']._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); styles['List Bullet'].font.size=Pt(10.5)

def setup_doc(title, subtitle):
    doc=Document(); set_styles(doc)
    sec=doc.sections[0]; sec.top_margin=Inches(0.65); sec.bottom_margin=Inches(0.65); sec.left_margin=Inches(0.75); sec.right_margin=Inches(0.75)
    # header/footer
    header=sec.header.paragraphs[0]; header.alignment=WD_ALIGN_PARAGRAPH.RIGHT; set_para(header, after=0); add_text(header,'2.4 圆的方程 · 新课 Skill V2',size=8.5,color='666666')
    footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER; set_para(footer,after=0); add_text(footer,'知识点 → 问题 → 进化链 → 节点',size=8.5,color='666666')
    p=doc.add_paragraph(style='Title'); set_para(p,after=3); add_text(p,title,size=20,bold=True)
    p=doc.add_paragraph(); set_para(p,after=10); add_text(p,subtitle,size=11,color='555555')
    return doc

def add_knowledge(doc, teacher=False):
    h=doc.add_heading('知识点：圆的方程', level=1); set_keep_with_next(h)
    add_label_para(doc,'知识来源：','在平面直角坐标系中，圆是到定点距离等于定长的点的集合。把“定点、定长、距离”翻译成坐标语言，就能用方程表示圆。')
    add_label_para(doc,'知识形成：','设圆心为 C(a，b)，圆上任意一点为 P(x，y)，半径为 r。由两点距离公式 CP=r，平方后得到标准方程；展开并配方可在标准式与一般式之间互化。')
    add_math_para(doc,'CP = √[(x − a)² + (y − b)²] = r',center=True)
    add_math_para(doc,'标准式：(x − a)² + (y − b)² = r²（r > 0）',center=True)
    add_math_para(doc,'一般式：x² + y² + Dx + Ey + F = 0',center=True)
    add_label_para(doc,'核心公式：','标准式中圆心为 (a，b)，半径为 r；一般式中圆心为 (−D/2，−E/2)，半径为 1/2√(D² + E² − 4F)。实圆条件：D² + E² − 4F > 0。')
    add_diagram(doc, {'kind':'circle_generic','center':(1,1),'point':(4,3),'radius':3}, 'knowledge_circle')
    if teacher: add_label_para(doc,'教学总提示：','始终追问“题目给了什么几何条件？它对应圆心和半径的哪条关系？”')

def make_data():
    # Base classroom data
    return {
      'p1':{
        'title':'问题1：求圆的方程',
        'essence':'圆的方程本质是确定圆心 (a，b) 和半径 r。',
        'optimal':'把题目中的几何条件翻译成圆心、半径或待定系数关系，再代入合适的方程形式。',
        'chains':[
          {'title':'进化链1：由圆心和半径建立圆方程','intro':'从直接给出圆心、半径出发，逐步升级为用过点或相切条件补出半径。','nodes':[
            {'title':'节点1：已知圆心和半径','evolution':'条件直接给出圆心和半径，可以一步写出标准方程。','optimal':'识别圆心和半径，直接代入 (x−a)²+(y−b)²=r²。','steps':['读出圆心 C(a，b) 与半径 r。','把 a、b、r 代入标准式。','展开或保留标准式，并检查半径为正。'],'example':'求圆心 C(2，−1)、半径为 3 的圆的方程。','answer':'(x−2)²+(y+1)²=9','analysis':'① 读出 a=2，b=−1，r=3；② 代入标准式；③ 得 (x−2)²+(y+1)²=9。','similar':['圆心 C(−1，4)，半径 2。','圆心 C(3，0)，半径 5。','圆心 C(0，−2)，半径 √7。','圆心 C(−4，−1)，半径 6。']},
            {'title':'节点2：已知圆心和过圆上一点','evolution':'在节点1基础上，不再直接给半径，而是用圆上点到圆心的距离求出半径。','optimal':'过点意味着该点到圆心的距离就是半径，先求 r² 再代入标准式。','steps':['写出圆心 C(a，b) 和圆上点 P(x₀，y₀)。','用 r²=(x₀−a)²+(y₀−b)² 求半径平方。','代入标准式并核对点满足方程。'],'example':'已知圆心 C(2，−1)，且经过点 P(5，3)，求圆的方程。','answer':'(x−2)²+(y+1)²=25','analysis':'① r²=(5−2)²+[3−(−1)]²=25；② 代入标准式；③ 得 (x−2)²+(y+1)²=25。','similar':['C(1，2) 过 P(4，6)。','C(−2，1) 过 P(1，5)。','C(0，−3) 过 P(4，0)。','C(3，−2) 过 P(−1，1)。']},
            {'title':'节点3：已知圆心、过点和相切直线','evolution':'保留节点2的“过点求半径”，再增加相切条件；后一题的解法包含前一题，并用切线条件核验半径。','optimal':'先用过点条件求 r²，再用圆心到切线距离核验，最后写标准式。','steps':['用圆上点求 r²=(x₀−a)²+(y₀−b)²。','用点到直线距离核验该距离是否等于 r。','把 r² 代入标准式并写出圆的方程。'],'example':'已知圆心 C(2，−1)，经过点 P(5，3)，且与直线 y=4 相切，求圆的方程。','answer':'(x−2)²+(y+1)²=25','analysis':'① r²=(5−2)²+(3+1)²=25；② 圆心到 y=4 的距离为 5，与 r 一致；③ 方程为 (x−2)²+(y+1)²=25。','similar':['C(1，0) 经过 P(4，4)，且与 y=5 相切。','C(−2，1) 经过 P(2，4)，且与 y=6 相切。','C(0，−2) 经过 P(3，2)，且与 y=3 相切。','C(3，2) 经过 P(7，5)，且与 y=7 相切。']}
          ]},
          {'title':'进化链2：由一般式或三点条件求圆方程','intro':'三个节点都以“写出圆的方程”为任务：先由一般式配方，再由三个点设一般式，最后综合建立并核验方程。','nodes':[
            {'title':'节点1：由一般式配方求圆方程','evolution':'在同一“求圆方程”问题中，已知形式从标准式条件换为一般式，需要通过配方写出等价的标准方程。','optimal':'分别对 x、y 配方，常数移项后写出圆的标准方程。','steps':['按 x、y 分组并移项。','分别配成完全平方。','写出标准方程，并读取圆心和半径。'],'example':'已知圆的一般式 x²+y²−6x+4y−3=0，写出圆的标准方程，并求圆心和半径。','answer':'(x−3)²+(y+2)²=16；圆心 (3，−2)，半径 4。','analysis':'① (x²−6x+9)+(y²+4y+4)=16；② 写出标准方程；③ 读出 C(3，−2)，r=4。','similar':['x²+y²+4x−2y−4=0。','x²+y²−8x−10y+25=0。','x²+y²+2x+6y−6=0。','x²+y²−2x+8y+1=0。']},
            {'title':'节点2：三点确定圆方程','evolution':'保留节点1的“写出方程并配方”方法，把已知条件升级为三个点；先设一般式求系数，再继续配方。','optimal':'设一般式、代入三点、解系数、配方，得到圆的方程。','steps':['设 x²+y²+Dx+Ey+F=0。','把三个点分别代入得到三元一次方程组。','解出 D、E、F，继续配方写出标准方程。'],'example':'求经过 A(1，0)，B(0，1)，C(2，1) 三点的圆的方程，并写出标准式。','answer':'x²+y²−2x−2y+1=0，即 (x−1)²+(y−1)²=1。','analysis':'① 代入三点得 D+F=−1，E+F=−1，2D+E+F=−5；② 解得 D=−2，E=−2，F=1；③ 配方得 (x−1)²+(y−1)²=1。','similar':['过 (0，0)、(2，0)、(0，2)。','过 (1，1)、(3，1)、(1，4)。','过 (−1，0)、(0，2)、(2，0)。','过 (2，−1)、(4，1)、(0，1)。']},
            {'title':'节点3：综合建立并核验圆方程','evolution':'保留节点2的“设一般式—代入三点—配方”方法，再增加完整核验要求；会做本题即可完成节点2。','optimal':'先求一般式，再配方写标准式，最后把三个点全部代回核验。','steps':['设一般式并代入已知条件求 D、E、F。','配方得到标准式，读出圆心和半径。','把三个点全部代回，核验一般式和标准式。'],'example':'求经过 A(−1，2)，B(3，2)，C(1，5) 三点的圆的方程，写出标准式并核验三个点。','answer':'x²+y²−2x−4y−4=0，即 (x−1)²+(y−2)²=9；三个点代回均成立。','analysis':'① 代入三点解得 D=−2，E=−4，F=−4；② 配方得 (x−1)²+(y−2)²=9；③ 三点分别代回均成立。','similar':['过 (0，0)、(4，0)、(2，4)，并写标准式、核验三点。','过 (−2，1)、(2，1)、(0，5)，并写标准式、核验三点。','过 (1，−1)、(5，−1)、(3，3)，并写标准式、核验三点。','过 (−3，0)、(1，0)、(−1，4)，并写标准式、核验三点。']}
          ]}
        ]},
      'p2':{
        'title':'问题2：求圆的几何信息',
        'essence':'把方程识别为标准式或一般式，读取圆心、半径，并进一步判断点和直线与圆的位置关系。',
        'optimal':'先化到标准式，再用“圆心 + 半径”解释点线关系。',
        'chains':[
          {'title':'进化链1：从标准式读取圆心和半径','intro':'从直接读参量开始，逐步升级为用距离比较判断点的位置和直线的位置关系。','nodes':[
            {'title':'节点1：标准式直接读取圆心和半径','evolution':'由求方程转向读方程：标准式中参数位置已经明确。','optimal':'括号内符号取反读圆心，右侧开平方读半径。','steps':['把方程与 (x−a)²+(y−b)²=r² 对照。','读取圆心 C(a，b)。','读取半径 r=√(右侧常数)。'],'example':'由 (x−3)²+(y+2)²=16 读出圆心和半径。','answer':'圆心 C(3，−2)，半径 r=4。','analysis':'① x−3 对应 a=3；② y+2=y−(−2)，故 b=−2；③ r=√16=4。','similar':['(x+1)²+(y−4)²=9。','(x−5)²+y²=25。','x²+(y+3)²=2。','(x+2)²+(y+1)²=12。']},
            {'title':'节点2：用距离判断点的位置','evolution':'在读出圆心半径后，增加一个点，用点到圆心的距离与 r 比较判断点在圆内、圆上或圆外。','optimal':'比较 CP² 与 r²：等于、 小于、 大于分别对应圆上、圆内、圆外。','steps':['读出圆心 C 和半径 r。','计算待判定点 P 到 C 的距离平方 CP²。','比较 CP² 与 r² 并下结论。'],'example':'圆 (x−1)²+(y+2)²=25，判断点 P(4，2) 的位置。','answer':'CP²=(4−1)²+(2+2)²=25=r²，故 P 在圆上。','analysis':'① C(1，−2)，r²=25；② CP²=3²+4²=25；③ CP²=r²，所以点在圆上。','similar':['判断 P(1，0) 的位置。','判断 P(7，−2) 的位置。','判断 P(2，−5) 的位置。','判断 P(−3，−2) 的位置。']},
            {'title':'节点3：同时判断点和直线的位置','evolution':'保留节点2的“点到圆心距离比较”方法，再增加直线条件；后一题同时完成点距和线距判断。','optimal':'先比较点到圆心距离，再比较圆心到直线距离，分别写出位置结论。','steps':['读出圆心 C 和半径 r。','计算点到圆心的距离并判断点在圆内、圆上或圆外。','计算圆心到直线距离并判断相交、相切或相离。'],'example':'圆 (x−2)²+(y+1)²=16，判断点 A(6，−1) 与直线 y=5 的位置。','answer':'CA=4=r，故 A 在圆上；圆心到 y=5 的距离为 6>4，故直线与圆相离。','analysis':'① C(2，−1)，r=4；② CA=4=r，点在圆上；③ d=6>4，直线与圆相离。','similar':['判断点 P(2，3) 与直线 y=3 的位置。','判断点 P(−2，−1) 与直线 x=−2 的位置。','判断点 P(2，−5) 与直线 3x+4y−10=0 的位置。','判断点 P(6，−1) 与直线 x−y+1=0 的位置。']}
          ]},
          {'title':'进化链2：由一般式读取几何信息','intro':'三个节点都以“从方程读取并判断几何信息”为任务：先配方读参量，再判断图形类型，最后综合判断点线位置。','nodes':[
            {'title':'节点1：由一般式配方读取几何信息','evolution':'在同一“读取几何信息”问题中，方程形式从标准式升级为一般式，需要先配方再读取。','optimal':'配方、移项、读参量三步完成一般式到标准式的转换。','steps':['对 x、y 的一次项分别配方。','把常数整理到等式右侧。','读取圆心、半径并写出标准式。'],'example':'由 x²+y²−4x+6y−3=0 读取圆心和半径。','answer':'(x−2)²+(y+3)²=16；圆心 C(2，−3)，半径 4。','analysis':'① (x−2)²+(y+3)²=16；② 读出 C(2，−3)；③ r=4。','similar':['x²+y²+2x−8y+1=0。','x²+y²−10x+2y+10=0。','x²+y²+6x+4y−12=0。','x²+y²−2x−2y−8=0。']},
            {'title':'节点2：配方后判断图形类型','evolution':'保留节点1的“配方读取”方法，再增加右侧常数的符号判断，区分实圆、点圆和无实点。','optimal':'先配方写成标准形式，再根据半径平方的符号判断图形类型。','steps':['对 x、y 配方，写出左侧平方和。','整理右侧常数并判断其符号。','根据 r²>0、r²=0 或 r²<0 写出图形类型。'],'example':'判断 x²+y²−6x+4y+13=0 表示什么图形。','answer':'配方得 (x−3)²+(y+2)²=0，表示一个点 (3，−2)，不是实圆。','analysis':'① 配方得 (x−3)²+(y+2)²=0；② 右侧为 0；③ 图形为一个点。','similar':['x²+y²+2x−4y+5=0。','x²+y²−8x+6y+25=0。','x²+y²+4x+2y+10=0。','x²+y²−2x−2y−3=0。']},
            {'title':'节点3：综合读取并判断点线位置','evolution':'保留节点2的“配方并判断图形类型”方法，再增加给定点和直线，把读取、分类和距离比较连成闭环。','optimal':'先配方确认实圆并读出 C、r，再分别比较点距和线距。','steps':['把一般式化为标准式，确认 r²>0 并读取 C、r。','对给定点计算距离并写出点的位置。','对给定直线计算距离并写出相交、相切或相离。'],'example':'圆 x²+y²−2x−4y−4=0，判断点 A(4，2) 与直线 y=5 的位置。','answer':'标准式为 (x−1)²+(y−2)²=9。A 到圆心距离为 3，故 A 在圆上；圆心到 y=5 距离为 3，故直线与圆相切。','analysis':'① 配方读出 C(1，2)，r=3 且为实圆；② CA²=3²，点在圆上；③ d=|2−5|=3=r，直线相切。','similar':['判断点 (1，5) 与直线 y=−2。','判断点 (−2，2) 与直线 x=5。','判断点 (1，−1) 与直线 3x+4y−5=0。','判断点 (4，−1) 与直线 x+y−1=0。']}
          ]}
        ]}
    }

# Atomic problem split for the circle lesson.  Each problem below has one
# mathematical target; its chains may vary the representation or question form
# while keeping that target unchanged.
def _atomic_node(title,evolution,optimal,steps,example,answer,analysis,similar,diagram=None):
    n={'title':title,'evolution':evolution,'optimal':optimal,'steps':steps,
       'example':example,'answer':answer,'analysis':analysis,'similar':similar}
    if diagram is not None: n['diagram']=diagram
    return n

def _atomic_problem(title, essence, optimal, chains):
    return {'title':title,'essence':essence,'optimal':optimal,'chains':chains}

def split_atomic_circle_problems(base):
    import copy
    p1=copy.deepcopy(base['p1'])
    p2=_atomic_problem('问题2：求圆心','从圆的方程中确定圆心坐标 C(a，b)。','先把方程整理到能直接读取或配方的形式，再只读取圆心坐标。',[
      {'title':'进化链1：由标准式求圆心','intro':'从标准式直接读取圆心，逐步升级到含参数和需要整理的形式；三节点都只求圆心。','nodes':[
        _atomic_node('节点1：标准式直接求圆心','标准式已经给出圆心参数，可以直接读取。','括号内符号取反，直接读出圆心。',['对照 (x−a)²+(y−b)²=r²。','分别读取 a、b。','写出圆心 C(a，b)。'],'由 (x−3)²+(y+2)²=16 求圆心。','圆心 C(3，−2)。','① x−3 对应 a=3。② y+2=y−(−2)，故 b=−2。③ 圆心为 C(3，−2)。',['由 (x+1)²+(y−4)²=9 求圆心。','由 (x−5)²+y²=25 求圆心。','由 x²+(y+3)²=4 求圆心。','由 (x+2)²+(y+1)²=12 求圆心。'],{'kind':'circle_only','center':(3,-2),'radius':4}),
        _atomic_node('节点2：含参数的标准式求圆心','保留直接读取方法，只把圆心横坐标换成参数。','把参数看作圆心坐标，仍按括号符号直接读取。',['与标准式对照。','读取含参数的横、纵坐标。','写出含参数的圆心。'],'由 (x−a)²+(y−2)²=9 求圆心。','圆心 C(a，2)。','① x−a 对应圆心横坐标 a。② y−2 对应纵坐标 2。③ 圆心为 C(a，2)。',['由 (x−m)²+(y+1)²=16 求圆心。','由 (x+2)²+(y−n)²=25 求圆心。','由 (x−t)²+y²=4 求圆心。','由 x²+(y−k)²=9 求圆心。'],{'kind':'circle_only','center':(1,2),'radius':3}),
        _atomic_node('节点3：整理后求圆心','保留读取圆心的方法，增加移项和配方，把展开形式整理成标准式。','先配方整理，再只读取圆心坐标。',['按 x、y 分组并移项。','分别配成完全平方。','从标准式读取圆心。'],'由 x²+y²−6x+4y+1=0 求圆心。','配方得 (x−3)²+(y+2)²=12，圆心 C(3，−2)。','① 移项并配方：(x−3)²+(y+2)²=12。② 与标准式比较。③ 圆心为 C(3，−2)。',['由 x²+y²+4x−2y−3=0 求圆心。','由 x²+y²−8x−10y+25=0 求圆心。','由 x²+y²+2x+6y−6=0 求圆心。','由 x²+y²−2x+8y+1=0 求圆心。'],{'kind':'circle_only','center':(3,-2),'radius':math.sqrt(12)})
      ]},
      {'title':'进化链2：由一般式求圆心','intro':'从一般式配方读取圆心，再加入参数和附加条件；三节点始终只研究圆心。','nodes':[
        _atomic_node('节点1：一般式配方求圆心','方程由标准式换为一般式，需要配方后读取圆心。','配方、整理、读取圆心三步完成。',['对 x、y 的一次项分别配方。','把常数整理到右侧。','读取圆心坐标。'],'由 x²+y²−4x+6y−3=0 求圆心。','配方得 (x−2)²+(y+3)²=16，圆心 C(2，−3)。','① (x−2)²+(y+3)²=16。② 对照标准式。③ 圆心为 C(2，−3)。',['由 x²+y²+2x−8y+1=0 求圆心。','由 x²+y²−10x+2y+10=0 求圆心。','由 x²+y²+6x+4y−12=0 求圆心。','由 x²+y²−2x−2y−8=0 求圆心。'],{'kind':'circle_only','center':(2,-3),'radius':4}),
        _atomic_node('节点2：含参数的一般式求圆心','保留配方读取方法，只把一次项系数换成参数。','一般式中圆心横坐标是 −D/2，纵坐标是 −E/2。',['识别 D、E。','用 −D/2、−E/2 读取圆心。','写出含参数的圆心。'],'由 x²+y²−2ax+4y−5=0 求圆心。','圆心 C(a，−2)。','① D=−2a，故 −D/2=a。② E=4，故 −E/2=−2。③ 圆心为 C(a，−2)。',['由 x²+y²+4mx−6y+1=0 求圆心。','由 x²+y²−8x+2ny−3=0 求圆心。','由 x²+y²+2tx+4y+5=0 求圆心。','由 x²+y²−6x+2ky−1=0 求圆心。']),
        _atomic_node('节点3：根据圆心条件求参数','保留一般式读取圆心方法，再增加圆心附加条件并反求参数。','先用系数写出圆心，再把圆心代入附加条件求参数。',['由一般式写出圆心。','把圆心坐标代入给定直线或坐标条件。','解出参数并回代核验。'],'已知 x²+y²−2ax+4y+a−5=0 的圆心在直线 x−y=4 上，求 a。','圆心 C(a，−2)，代入 a−(−2)=4，得 a=2。','① 圆心为 C(a，−2)。② 代入 x−y=4：a+2=4。③ 解得 a=2。',['已知 x²+y²−2ax+4y+a−5=0 的圆心在 y=−2 上，求 a。','已知 x²+y²+4mx−6y+1=0 的圆心在 x=2 上，求 m。','已知 x²+y²−8x+2ny−3=0 的圆心在 y=−1 上，求 n。','已知 x²+y²+2tx+4y+5=0 的圆心在 x+y=1 上，求 t。'])
      ]}
    ])
    p3=_atomic_problem('问题3：求半径','从圆的方程中确定半径 r 或半径平方 r²。','先整理方程得到 r²，再利用 r>0 开平方求半径。',[
      {'title':'进化链1：由标准式求半径','intro':'从标准式直接读取半径，逐步加入半径平方和参数；三节点都只求半径。','nodes':[
        _atomic_node('节点1：标准式直接求半径','标准式右侧已经给出半径平方。','右侧常数开平方，取正值。',['对照标准式。','读取 r²。','取 r=√r²。'],'由 (x−3)²+(y+2)²=16 求半径。','半径 r=4。','① r²=16。② r=√16。③ 因 r>0，得 r=4。',['由 (x+1)²+(y−4)²=9 求半径。','由 (x−5)²+y²=25 求半径。','由 x²+(y+3)²=4 求半径。','由 (x+2)²+(y+1)²=12 求半径。'],{'kind':'circle_only','center':(3,-2),'radius':4}),
        _atomic_node('节点2：由半径平方求半径','保留开平方方法，把半径信息直接写成 r² 的形式。','先确认 r²，再取正平方根得到 r。',['读出 r²=25。','计算 √25。','说明半径取正值。'],'已知圆的标准式为 (x−a)²+(y−1)²=r²，且 r²=25，求 r。','r=5。','① 已知 r²=25。② r=√25=5。③ 半径取正值，故 r=5。',['已知 r²=36，求 r。','已知 r²=49，求 r。','已知 r²=2，求 r。','已知 r²=12，求 r。']),
        _atomic_node('节点3：含参数时求半径','保留标准式读取方法，再把半径平方写成参数表达式。','先读出 r² 的参数表达式，再按 r>0 开平方。',['从标准式读出 r²。','根据参数条件判断 r²>0。','写出 r=√r²。'],'由 (x−2)²+(y+1)²=a−1（a>1）求半径。','半径 r=√(a−1)。','① r²=a−1。② a>1 保证 r²>0。③ r=√(a−1)。',['由 (x+1)²+(y−3)²=2m（m>0）求半径。','由 (x−4)²+y²=t+5（t>−5）求半径。','由 x²+(y+2)²=n²（n>0）求半径。','由 (x+2)²+(y−1)²=3k−2（k>2/3）求半径。'])
      ]},
      {'title':'进化链2：由一般式求半径','intro':'从一般式配方或使用一般式公式求半径，再升级为半径条件下的参数范围。','nodes':[
        _atomic_node('节点1：一般式配方求半径','一般式不能直接读半径，需要先配方。','配方得到标准式，再开平方读取半径。',['分别配方。','整理右侧常数得到 r²。','开平方求 r。'],'由 x²+y²−6x+4y−3=0 求半径。','配方得 (x−3)²+(y+2)²=16，半径 r=4。','① 配方得 (x−3)²+(y+2)²=16。② r²=16。③ r=4。',['由 x²+y²+4x−2y−4=0 求半径。','由 x²+y²−8x−10y+25=0 求半径。','由 x²+y²+2x+6y−6=0 求半径。','由 x²+y²−2x+8y+1=0 求半径。'],{'kind':'circle_only','center':(3,-2),'radius':4}),
        _atomic_node('节点2：利用一般式公式求半径','保留由一般式确定半径的方法，改用 D、E、F 公式直接计算。','代入 r=1/2√(D²+E²−4F)，最后取正值。',['读出 D、E、F。','代入一般式半径公式。','化简并写出半径。'],'由 x²+y²−8x+6y−11=0 求半径。','r=6。','① D=−8，E=6，F=−11。② r=1/2√(64+36+44)。③ r=1/2√144=6。',['由 x²+y²+4x−2y−4=0 求半径。','由 x²+y²−10x+2y+10=0 求半径。','由 x²+y²+6x+4y−12=0 求半径。','由 x²+y²−2x+8y+1=0 求半径。']),
        _atomic_node('节点3：根据半径条件求参数范围','保留一般式求半径方法，再增加半径不等式并反求参数范围。','先把半径平方表示成参数，再把半径条件化为不等式。',['配方或使用公式写出 r²。','根据 r>3 写出 r²>9。','解出参数范围并检查实圆条件。'],'已知 x²+y²−4x+6y+m=0，求使半径大于 3 的 m 的范围。','r²=13−m，13−m>9，故 m<4。','① 配方得 (x−2)²+(y+3)²=13−m。② r²=13−m。③ r>3 等价于 13−m>9，得 m<4。',['已知 x²+y²−4x+6y+m=0，求使半径大于 2 的 m 范围。','已知 x²+y²+2x−8y+n=0，求使半径不小于 4 的 n 范围。','已知 x²+y²−6x+4y+t=0，求使半径小于 5 的 t 范围。','已知 x²+y²+4x−2y+k=0，求使半径等于 3 的 k。'])
      ]}
    ])
    p4=_atomic_problem('问题4：判断点与圆的位置关系','比较点到圆心的距离与半径，判断点在圆内、圆上或圆外。','先得到圆心和半径，再比较 CP² 与 r²。',[
      {'title':'进化链1：由标准式判断点的位置','intro':'从标准式直接比较点距与半径，逐步升级为多结论和参数问法；三节点都判断点与圆的位置。','nodes':[
        _atomic_node('节点1：直接判断点的位置','标准式和点的坐标均已给出，可以直接计算点距。','比较 CP² 与 r²：等于圆上，小于圆内，大于圆外。',['读出圆心和 r²。','计算 CP²。','比较并写出位置结论。'],'圆 (x−1)²+(y+2)²=25，判断点 P(4，2) 的位置。','CP²=25=r²，P 在圆上。','① C(1，−2)，r²=25。② CP²=3²+4²=25。③ CP²=r²，所以 P 在圆上。',['圆 (x−1)²+(y+2)²=25，判断 P(1，0)。','圆 (x−1)²+(y+2)²=25，判断 P(7，−2)。','圆 (x−1)²+(y+2)²=25，判断 P(2，−5)。','圆 (x−1)²+(y+2)²=25，判断 P(−3，−2)。'],{'kind':'circle_point','center':(1,-2),'point':(4,2)}),
        _atomic_node('节点2：按距离比较判断点的位置','保留点距比较方法，改变点的位置并要求明确写出三类判断依据。','只比较平方即可，避免开平方。',['写出 C 和 r²。','计算给定点的 CP²。','按 CP² 与 r² 的大小规律分类。'],'圆 (x−1)²+(y+2)²=25，判断点 P(1，0) 的位置。','CP²=4<25，P 在圆内。','① C(1，−2)，r²=25。② CP²=0²+2²=4。③ 4<25，所以 P 在圆内。',['圆 (x−1)²+(y+2)²=25，判断 P(7，−2)。','圆 (x−1)²+(y+2)²=25，判断 P(2，−5)。','圆 (x−1)²+(y+2)²=25，判断 P(−3，−2)。','圆 (x−1)²+(y+2)²=25，判断 P(4，2)。'],{'kind':'circle_point','center':(1,-2),'point':(1,0)}),
        _atomic_node('节点3：由点在圆上反求参数','保留点距比较方法，把“判断位置”升级为由位置条件求参数。','把“点在圆上”翻译为 CP²=r²，再解参数。',['写出参数圆心和半径。','利用 CP²=r² 建立方程。','解参数并回代核验。'],'圆 (x−a)²+(y+2)²=25 经过点 P(4，2)，求 a。','(4−a)²+16=25，解得 a=1 或 7。','① 代入点得 (4−a)²+16=25。② (4−a)²=9。③ a=1 或 7。',['圆 (x−a)²+(y−1)²=16 经过 P(5，5)，求 a。','圆 (x−2)²+(y−b)²=25 经过 P(5，6)，求 b。','圆 (x−t)²+y²=9 经过 P(1，2)，求 t。','圆 (x+1)²+(y−k)²=25 经过 P(3，6)，求 k。'])
      ]},
      {'title':'进化链2：由一般式判断点的位置','intro':'从一般式配方后判断点的位置，再升级为多个点和参数范围；核心仍是点距与半径比较。','nodes':[
        _atomic_node('节点1：一般式化标准式后判断点','先把一般式配方，再沿用点距比较方法。','配方读出 C、r，再比较 CP² 与 r²。',['配方得到标准式。','读出圆心和半径平方。','计算点距并判断位置。'],'圆 x²+y²−2x+4y−20=0，判断点 P(4，2) 的位置。','标准式为 (x−1)²+(y+2)²=25，CP²=25，P 在圆上。','① 配方得 (x−1)²+(y+2)²=25。② C(1，−2)，r²=25。③ CP²=25，故 P 在圆上。',['圆 x²+y²+2x−8y−4=0，判断 P(4，6)。','圆 x²+y²−6x+2y−7=0，判断 P(3，1)。','圆 x²+y²+4x+2y−4=0，判断 P(0，0)。','圆 x²+y²−2x−2y−3=0，判断 P(2，2)。'],{'kind':'circle_point','center':(1,-2),'point':(4,2)}),
        _atomic_node('节点2：同时判断多个点的位置','保留配方和点距比较，增加多个点并要求分别给出结论。','对每个点分别计算 CP²，再逐一比较同一个 r²。',['化为标准式并读出 C、r²。','分别计算各点的 CP²。','按比较结果逐点写结论。'],'圆 x²+y²−2x+4y−20=0，判断 A(1，−2)、B(1，1) 的位置。','A 在圆内，B 在圆内。','① 标准式为 (x−1)²+(y+2)²=25。② CA²=0<25，A 在圆内。③ CB²=3²<25，B 在圆内。',['圆 x²+y²−2x+4y−20=0，判断 A(6，−2)、B(1，3)。','圆 x²+y²−2x+4y−20=0，判断 A(4，2)、B(1，−7)。','圆 x²+y²−2x+4y−20=0，判断 A(1，−2)、B(5，2)。','圆 x²+y²−2x+4y−20=0，判断 A(−2，−2)、B(1，−6)。']),
        _atomic_node('节点3：求使点在圆外的参数范围','保留一般式配方和点距比较，再把位置结论改为参数范围。','把“点在圆外”翻译为 CP²>r²，并同时检查实圆条件。',['配方写出 r²。','计算定点到圆心的距离平方。','解 CP²>r²，并保留实圆条件。'],'在实圆条件下，求使点 P(2，1) 在圆 x²+y²−2x+4y+m=0 外的 m 范围。','标准式为 (x−1)²+(y+2)²=5−m；CP²=10。点在圆外需 10>5−m，且 m<5，故 −5<m<5。','① 配方得 (x−1)²+(y+2)²=5−m。② CP²=1²+3²=10。③ 10>5−m 且 m<5，得 −5<m<5。',['在实圆条件下，求使 P(3，0) 在圆 x²+y²−2x+4y+m=0 外的 m 范围。','在实圆条件下，求使 P(0，1) 在圆 x²+y²+4x−2y+n=0 外的 n 范围。','在实圆条件下，求使 P(2，−1) 在圆 x²+y²−6x+2y+t=0 外的 t 范围。','在实圆条件下，求使 P(−1，2) 在圆 x²+y²+2x−8y+k=0 外的 k 范围。'])
      ]}
    ])
    p5=_atomic_problem('问题5：判断直线与圆的位置关系','比较圆心到直线的距离 d 与半径 r，判断直线与圆相交、相切或相离。','先求圆心到直线的距离，再比较 d 与 r。',[
      {'title':'进化链1：由标准式判断直线位置','intro':'从水平直线的距离比较开始，升级到一般直线和参数直线；三节点都判断直线与圆的位置关系。','nodes':[
        _atomic_node('节点1：判断水平直线与圆的位置','水平直线的距离可直接由纵坐标差得到。','比较圆心到直线的距离 d 与 r。',['读出圆心和半径。','计算 |y_C−c|。','比较 d 与 r 并下结论。'],'圆 (x−2)²+(y−1)²=9，判断直线 y=5 与圆的位置关系。','d=4>3，直线与圆相离。','① C(2，1)，r=3。② d=|1−5|=4。③ d>r，直线与圆相离。',['圆 (x−2)²+(y−1)²=9，判断 y=4。','圆 (x−2)²+(y−1)²=9，判断 y=1。','圆 (x−2)²+(y−1)²=9，判断 y=−1。','圆 (x−2)²+(y−1)²=9，判断 y=3。'],{'kind':'circle_point_line','center':(2,1),'line_y':5}),
        _atomic_node('节点2：判断一般直线与圆的位置','保留距离比较方法，把直线升级为 Ax+By+C=0。','使用点到直线距离公式计算 d，再和 r 比较。',['整理直线为 Ax+By+C=0。','计算 d=|Ax_C+By_C+C|/√(A²+B²)。','比较 d 与 r。'],'圆 (x−2)²+(y−1)²=9，判断直线 3x+4y−10=0 与圆的位置关系。','d=0<3，直线与圆相交。','① C(2，1)，r=3。② d=|6+4−10|/5=0。③ d<r，直线与圆相交。',['圆 (x−2)²+(y−1)²=9，判断 3x+4y−25=0。','圆 (x−2)²+(y−1)²=9，判断 x−y+1=0。','圆 (x−2)²+(y−1)²=9，判断 4x−3y+2=0。','圆 (x−2)²+(y−1)²=9，判断 5x+12y−60=0。'],{'kind':'circle_point_line','center':(2,1),'line':(3,4,-10)}),
        _atomic_node('节点3：由相切条件反求直线参数','保留圆心距比较方法，把“判断位置”升级为相切条件下求参数。','把相切翻译为 d=r，再解参数。',['写出圆心和半径。','建立 d=r 的方程。','解参数并核验相切。'],'圆 (x−2)²+(y−1)²=25 与直线 y=a 相切，求 a。','|a−1|=5，故 a=6 或 −4。','① C(2，1)，r=5。② 相切时 |a−1|=5。③ 解得 a=6 或 a=−4。',['圆 (x−1)²+(y+2)²=16 与 y=a 相切，求 a。','圆 (x−2)²+y²=9 与 y=a 相切，求 a。','圆 (x+1)²+(y−3)²=25 与 y=a 相切，求 a。','圆 x²+(y−1)²=4 与 y=a 相切，求 a。'],{'kind':'circle_point_line','center':(2,1),'line_y':6})
      ]},
      {'title':'进化链2：由一般式判断直线位置','intro':'从一般式配方后判断直线位置，再加入参数和参数范围；核心仍是比较 d 与 r。','nodes':[
        _atomic_node('节点1：一般式化标准式后判断直线','先配方读出圆心半径，再使用点到直线距离公式。','配方、读参量、比较 d 与 r。',['把一般式配成标准式。','读出 C、r。','计算圆心到直线距离并判断。'],'圆 x²+y²−4x−2y−4=0，判断直线 y=4 与圆的位置关系。','标准式为 (x−2)²+(y−1)²=9，d=3=r，直线与圆相切。','① 配方得 (x−2)²+(y−1)²=9。② C(2，1)，r=3。③ d=|1−4|=3=r，直线相切。',['圆 x²+y²−4x−2y−4=0，判断 y=1。','圆 x²+y²−4x−2y−4=0，判断 y=5。','圆 x²+y²−4x−2y−4=0，判断 x=5。','圆 x²+y²−4x−2y−4=0，判断 x−y+1=0。'],{'kind':'circle_point_line','center':(2,1),'line_y':4}),
        _atomic_node('节点2：含参数的一般式判断直线位置','保留一般式配方和距离比较，增加方程参数并分类讨论。','把 d 与 r 的三种关系翻译成参数不等式。',['配方写出 r²。','计算圆心到直线的固定距离。','比较 d² 与 r²，分类讨论参数。'],'圆 x²+y²−4x−2y+m=0，判断直线 y=4 与圆的位置关系。','r²=5−m，且 d=3：m<−4 相交，m=−4 相切，−4<m<5 相离，m≥5 无实圆。','① 配方得 (x−2)²+(y−1)²=5−m。② d=3，比较 d²=9 与 r²=5−m。③ 得 m<−4 相交，m=−4 相切，−4<m<5 相离；m≥5 无实圆。',['圆 x²+y²−4x−2y+n=0，判断 y=3。','圆 x²+y²+2x−6y+t=0，判断 y=0。','圆 x²+y²−6x+4y+k=0，判断 x=1。','圆 x²+y²+4x+2y+s=0，判断 x=0。'],{'kind':'circle_point_line','center':(2,1),'line_y':4}),
        _atomic_node('节点3：求直线相离的参数范围','保留一般式转标准式和距离比较方法，把位置结论改为求直线参数范围。','把相离翻译为 d>r，平方后解直线参数范围。',['读出圆心和半径。','写出 |a−y_C|>r。','解出 a 的范围并核验。'],'圆 x²+y²−4x−2y−5=0，求直线 y=a 与圆相离时 a 的范围。','标准式为 (x−2)²+(y−1)²=10；相离需 |a−1|>√10，故 a<1−√10 或 a>1+√10。','① 配方得 (x−2)²+(y−1)²=10。② d=|a−1|，r=√10。③ d>r，故 a<1−√10 或 a>1+√10。',['圆 x²+y²−4x−2y−8=0，求 y=a 与圆相离的 a 范围。','圆 x²+y²+2x−6y−6=0，求 y=a 与圆相离的 a 范围。','圆 x²+y²−6x+4y−3=0，求 y=a 与圆相离的 a 范围。','圆 x²+y²+4x+2y−4=0，求 y=a 与圆相离的 a 范围。'])
      ]}
    ])
    return {'p1':p1,'p2':p2,'p3':p3,'p4':p4,'p5':p5}

# Diagram mapping for the retained original problem and atomic problems.
def attach_base_diagrams(data):
    p1_specs=[
      {'kind':'circle_only','center':(2,-1),'radius':3},
      {'kind':'circle_point','center':(2,-1),'point':(5,3)},
      {'kind':'circle_point_tangent','center':(2,-1),'point':(5,3),'tangent_y':4},
      {'kind':'circle_only','center':(3,-2),'radius':4},
      {'kind':'three_points','points':[(1,0),(0,1),(2,1)]},
      {'kind':'three_points','points':[(-1,2),(3,2),(1,5)]}]
    i=0
    for chain in data['p1']['chains']:
      for node in chain['nodes']:
        node['diagram']=p1_specs[i]; i+=1
    # Atomic problem nodes already carry exact geometry diagrams.  Leave them intact.
    return data

# Homework changed data (same structure, different examples/answers)
def make_homework(data):
    import copy
    d=copy.deepcopy(data)
    # Replace data for every node in order.  The problem and chain targets stay
    # fixed; coordinates, coefficients, parameters, and line positions change.
    replacements=[
      ('求圆心 C(−3，2)、半径为 5 的圆的方程。','(x+3)²+(y−2)²=25'),
      ('已知圆心 C(−1，2)，且经过点 P(3，6)，求圆的方程。','(x+1)²+(y−2)²=32'),
      ('已知圆心 C(−2，3)，经过点 P(2，7)，且与直线 y=8 相切，求圆的方程。','(x+2)²+(y−3)²=32'),
      ('将 x²+y²+8x−6y−11=0 化为标准式，并写出圆心和半径。','(x+4)²+(y−3)²=36；圆心 (−4，3)，半径 6。'),
      ('求经过 A(−1，0)，B(0，−1)，C(1，2) 三点的圆的方程，并写出标准式。','x²+y²−x−y−2=0；标准式为 (x−1/2)²+(y−1/2)²=5/2。'),
      ('求经过 A(0，0)，B(4，0)，C(2，4) 三点的圆的方程，并写出标准式。','x²+y²−4x−2y=0，即 (x−2)²+(y−1)²=5。'),
      ('由 (x+4)²+(y−3)²=36 读出圆心和半径。','圆心 C(−4，3)，半径 r=6。'),
      ('圆 (x+2)²+(y−1)²=25，判断点 P(1，5) 的位置。','CP²=3²+4²=25=r²，故 P 在圆上。'),
      ('圆 (x+2)²+(y−1)²=25，判断点 P(1，5) 与直线 y=−5 的位置。','CP²=3²+4²=25=r²，点在圆上；d=4<5，直线与圆相交。'),
      ('由 x²+y²+8x−6y−11=0 读取圆心和半径。','(x+4)²+(y−3)²=36；圆心 C(−4，3)，半径 6。'),
      ('判断 x²+y²+4x−2y+5=0 表示什么图形。','配方得 (x+2)²+(y−1)²=0，表示点 (−2，1)。'),
      ('圆 x²+y²−4x−2y=0，判断点 B(4，0) 与直线 y=3 的位置。','标准式 (x−2)²+(y−1)²=5；B 在圆上，圆心到 y=3 的距离为 2<√5，直线相交。')]
    diagram_specs=[
      {'kind':'circle_only','center':(-3,2),'radius':5},
      {'kind':'circle_point','center':(-1,2),'point':(3,6)},
      {'kind':'circle_point_tangent','center':(-2,3),'point':(2,7),'tangent_y':8},
      {'kind':'circle_only','center':(-4,3),'radius':6},
      {'kind':'three_points','points':[(-1,0),(0,-1),(1,2)]},
      {'kind':'three_points','points':[(0,0),(4,0),(2,4)]},
      {'kind':'circle_only','center':(-4,3),'radius':6},
      {'kind':'circle_point','center':(-2,1),'point':(1,5)},
      {'kind':'circle_point_line','center':(-2,1),'point':(1,5),'line_y':-5},
      {'kind':'circle_only','center':(-4,3),'radius':6},
      None,
      {'kind':'circle_point_line','center':(2,1),'point':(4,0),'line_y':3}]
    # Atomic split adds 18 nodes after the original six; use new data for all
    # of them as well.
    replacements += [
      ('由 (x+4)²+(y−3)²=25 求圆心。','圆心 C(−4，3)。'),
      ('由 (x−b)²+(y+1)²=16 求圆心。','圆心 C(b，−1)。'),
      ('由 x²+y²+8x−6y−11=0 求圆心。','配方得 (x+4)²+(y−3)²=36，圆心 C(−4，3)。'),
      ('由 x²+y²+6x−4y−12=0 求圆心。','圆心 C(−3，2)。'),
      ('由 x²+y²+4ax+2y−7=0 求圆心。','圆心 C(−2a，−1)。'),
      ('已知 x²+y²−4ax+2y+a−3=0 的圆心在直线 x+y=3 上，求 a。','圆心 C(2a，−1)，代入得 2a−1=3，故 a=2。'),
      ('由 (x+4)²+(y−3)²=36 求半径。','半径 r=6。'),
      ('已知标准式 (x−a)²+(y−1)²=r²，且 r²=36，求 r。','r=6。'),
      ('由 (x+3)²+(y−2)²=2m+1（m>−1/2）求半径。','半径 r=√(2m+1)。'),
      ('由 x²+y²+8x−6y−11=0 求半径。','配方得 (x+4)²+(y−3)²=36，半径 r=6。'),
      ('由 x²+y²−10x+2y−11=0 用一般式公式求半径。','r=√37。'),
      ('已知 x²+y²−6x+4y+n=0，求使半径大于 2 的 n 的范围。','r²=13−n，13−n>4，故 n<9。'),
      ('圆 (x+2)²+(y−1)²=25，判断点 P(1，5) 的位置。','CP²=25=r²，P 在圆上。'),
      ('圆 (x+2)²+(y−1)²=25，判断点 P(−2，1) 的位置。','CP²=0<25，P 在圆内。'),
      ('圆 (x−a)²+(y−1)²=16 经过点 P(5，5)，求 a。','(5−a)²=0，故 a=5。'),
      ('圆 x²+y²+4x−2y−20=0，判断点 P(1，5) 的位置。','标准式为 (x+2)²+(y−1)²=25，CP²=25，P 在圆上。'),
      ('圆 x²+y²+4x−2y−20=0，判断 A(−2，1)、B(3，5) 的位置。','A 在圆内，B 在圆上。'),
      ('在实圆条件下，求使点 P(0，4) 在圆 x²+y²+4x−2y+n=0 外的 n 范围。','标准式为 (x+2)²+(y−1)²=5−n；13>5−n 且 n<5，故 −8<n<5。'),
      ('圆 (x+1)²+(y−2)²=16，判断直线 y=7 与圆的位置关系。','d=5>4，直线与圆相离。'),
      ('圆 (x+1)²+(y−2)²=16，判断直线 3x+4y−5=0 与圆的位置关系。','d=0<4，直线与圆相交。'),
      ('圆 (x+1)²+(y−2)²=16 与直线 y=a 相切，求 a。','|a−2|=4，故 a=6 或 −2。'),
      ('圆 x²+y²+2x−4y−4=0，判断直线 y=5 与圆的位置关系。','标准式为 (x+1)²+(y−2)²=9，d=3=r，直线相切。'),
      ('圆 x²+y²+2x−4y+m=0，判断直线 y=5 与圆的位置关系。','m<−4 相交，m=−4 相切，−4<m<5 相离，m≥5 无实圆。'),
      ('圆 x²+y²+2x−4y−8=0，求直线 y=a 与圆相离时 a 的范围。','标准式为 (x+1)²+(y−2)²=13，故 a<2−√13 或 a>2+√13。')]
    diagram_specs += [
      {'kind':'circle_only','center':(-4,3),'radius':5}, {'kind':'circle_only','center':(1,-1),'radius':4}, {'kind':'circle_only','center':(-4,3),'radius':6},
      {'kind':'circle_only','center':(-3,2),'radius':5}, {'kind':'circle_only','center':(-2,-1),'radius':4}, {'kind':'circle_only','center':(4,-1),'radius':5},
      {'kind':'circle_only','center':(-4,3),'radius':6}, {'kind':'circle_only','center':(0,1),'radius':6}, {'kind':'circle_only','center':(-3,2),'radius':4},
      {'kind':'circle_only','center':(-4,3),'radius':6}, {'kind':'circle_only','center':(5,-1),'radius':math.sqrt(37)}, {'kind':'circle_only','center':(3,-2),'radius':3},
      {'kind':'circle_point','center':(-2,1),'point':(1,5)}, {'kind':'circle_point','center':(-2,1),'point':(-2,1)}, {'kind':'circle_point','center':(5,1),'point':(5,5)},
      {'kind':'circle_point','center':(-2,1),'point':(1,5)}, {'kind':'circle_point','center':(-2,1),'point':(3,5)}, {'kind':'circle_point','center':(-2,1),'point':(0,4)},
      {'kind':'circle_point_line','center':(-1,2),'line_y':7}, {'kind':'circle_point_line','center':(-1,2),'line':(3,4,-5)}, {'kind':'circle_point_line','center':(-1,2),'line_y':6},
      {'kind':'circle_point_line','center':(-1,2),'line_y':5}, {'kind':'circle_point_line','center':(-1,2),'line_y':5}, {'kind':'circle_point_line','center':(-1,2),'line_y':7}]
    if len(replacements)!=len(diagram_specs):
        raise ValueError(f'homework replacement/diagram count mismatch: {len(replacements)} vs {len(diagram_specs)}')
    it=iter(replacements); dit=iter(diagram_specs)
    for prob in d.values():
      for chain in prob['chains']:
        for node in chain['nodes']:
          ex,ans=next(it); node['example']=ex; node['answer']=ans; node['diagram']=next(dit)
          node['analysis']=f'① {node["steps"][0]}；② {node["steps"][1]}；③ {ans}'
    return d

# ---------- builders ----------
def build_student_class(data):
    doc=setup_doc('2.4 圆的方程 学生上课版本','课堂学习资料 · 按问题解决能力组织')
    p=doc.add_paragraph(); set_para(p,after=8); add_text(p,'学习路线：',bold=True); add_text(p,'先掌握知识点，再分别训练“求圆的方程、求圆心、求半径、判断点与圆的位置关系、判断直线与圆的位置关系”。',size=10.5)
    add_knowledge(doc)
    for prob in data.values():
        add_problem_intro(doc,prob)
        for chain in prob['chains']: add_chain(doc,chain,'student')
    h=doc.add_heading('一页回顾', level=1); set_keep_with_next(h)
    add_label_para(doc,'看到求圆心：','先整理成标准式，再读取圆心。')
    add_label_para(doc,'看到求半径：','先得到 r²，再取正平方根。')
    add_label_para(doc,'看到过点：','用点到圆心距离求 r。')
    add_label_para(doc,'看到相切：','用圆心到直线距离求 r。')
    add_label_para(doc,'看到一般式：','先配方；看到三个点：设一般式并代点。')
    return doc

def build_teacher(data):
    doc=setup_doc('2.4 圆的方程 教师上课版本','课堂备课与即时训练 · 含教学提示、类似题和分步解析')
    p=doc.add_paragraph(); set_para(p,after=8); add_text(p,'使用说明：',bold=True); add_text(p,'先让学生说出问题与进化链，再讲节点中的最优解法；类似题用于当堂检测。',size=10.5)
    add_knowledge(doc,teacher=True)
    for prob in data.values():
        add_problem_intro(doc,prob)
        for chain in prob['chains']: add_chain(doc,chain,'teacher')
    h=doc.add_heading('课堂收束', level=1); set_keep_with_next(h)
    add_label_para(doc,'核心追问：','题目给出的每个条件，最后都要落到圆心、半径、待定系数或距离比较上。')
    add_label_para(doc,'板书建议：','标准式负责“读参数”；一般式负责“列方程”；距离公式负责“把几何条件变成代数条件”。')
    return doc

def build_homework(data):
    doc=setup_doc('2.4 圆的方程 学生作业版本','课后巩固 · 题目数据已更换')
    p=doc.add_paragraph(); set_para(p,after=8); add_text(p,'作业要求：',bold=True); add_text(p,'每题写出关键步骤，保持“问题 → 进化链 → 节点”的顺序完成；答案集中在文末用于自检。',size=10.5)
    add_knowledge(doc)
    for prob in data.values():
        add_problem_intro(doc,prob)
        for chain in prob['chains']:
            # compact chain note, no classroom prompts
            add_chain(doc,chain,'homework')
    h=doc.add_heading('作业自检答案', level=1); set_keep_with_next(h)
    n=1
    for prob in data.values():
      for chain in prob['chains']:
        for node in chain['nodes']:
          add_label_para(doc,f'{n}. {node["title"]}：',node['answer'],after=3); n+=1
    return doc

def build_review(data):
    doc=setup_doc('2.4 圆的方程 学生复习版本','考前回顾 · 保留每条进化链的最终模型')
    p=doc.add_paragraph(); set_para(p,after=8); add_text(p,'复习方法：',bold=True); add_text(p,'先遮住答案，依据问题本质说出模型，再写出最终节点的方程或判定方法。',size=10.5)
    add_knowledge(doc)
    # keep hierarchy but only final node of each chain
    for prob in data.values():
        add_problem_intro(doc,prob)
        for chain in prob['chains']:
            final={'title':'最终节点：'+chain['nodes'][-1]['title'].split('：',1)[-1],
                   'evolution':'把本条进化链前面的能力合并为一个可迁移模型。',
                   'optimal':chain['nodes'][-1]['optimal'],
                   'steps':chain['nodes'][-1]['steps'],
                   'example':chain['nodes'][-1]['example'],
                   'answer':chain['nodes'][-1]['answer']}
            add_chain(doc,{'title':chain['title'],'intro':'复习只保留本链最终模型，回忆前面节点如何逐步升级。','nodes':[final]},'student')
    h=doc.add_heading('一页速记', level=1); set_keep_with_next(h)
    # table for scanability
    tbl=doc.add_table(rows=1, cols=3); tbl.alignment=WD_TABLE_ALIGNMENT.CENTER
    hdr=tbl.rows[0].cells; set_repeat_table_header(tbl.rows[0])
    for i,t in enumerate(['看到的条件','翻译成的关系','优先使用的模型']):
        set_cell_shading(hdr[i],'404040'); set_cell_borders(hdr[i]); set_cell_margins(hdr[i]); hdr[i].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; p=hdr[i].paragraphs[0]; set_para(p,after=0,align=WD_ALIGN_PARAGRAPH.CENTER); add_text(p,t,bold=True,color='FFFFFF',size=10)
    rows=[('求圆的方程','确定圆心和半径','标准式或一般式'),('求圆心','整理后读取 a、b','标准式或配方'),('求半径','先求 r² 再开平方','标准式或一般式公式'),('判断点与圆的位置关系','比较 CP² 与 r²','点距比较'),('判断直线与圆的位置关系','比较 d 与 r','点到直线距离')]
    for a,b,c in rows:
        cells=tbl.add_row().cells
        for cell,text in zip(cells,[a,b,c]):
            set_cell_borders(cell); set_cell_margins(cell); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; p=cell.paragraphs[0]; set_para(p,after=0); add_text(p,text,size=10)
    return doc

def save(doc,name):
    path=OUT/name; doc.save(path); return path

# ---------- revised two-paper layout ----------
def add_page_break(doc):
    p=doc.add_paragraph(); p.add_run().add_break(WD_BREAK.PAGE)

def add_question_node(doc, node, include_evolution=True):
    h=doc.add_heading(node['title'], level=4); set_keep_with_next(h)
    if include_evolution:
        add_label_para(doc,'进化过程：',node['evolution'])
    add_label_para(doc,'一句话最优解法：',node['optimal'])
    p=doc.add_paragraph(); set_para(p,after=3); add_text(p,'解题步骤：',bold=True,size=10.5)
    for i,step in enumerate(node['steps'],1): add_numbered(doc,step,i)
    add_label_para(doc,'例题：',node['example'],after=4)
    if node.get('diagram'):
        add_diagram(doc,node['diagram'],'node_'+node['title'])
    add_answer_area(doc,5)

def split_analysis(text):
    if not text: return []
    parts=[]
    for chunk in re.split(r'[；。]', text):
        chunk=chunk.strip()
        if chunk: parts.append(chunk)
    return parts

def similar_steps(question, node):
    q=question.strip()
    title=node.get('title','')
    if '求圆心' in title:
        return ['把方程整理为标准式，或识别一般式的一次项系数。','读取圆心横、纵坐标。','写出圆心并回代检查。']
    if '求半径' in title:
        return ['把方程整理为标准式，或代入一般式半径公式。','得到半径平方 r²。','取正平方根写出半径。']
    if '判断点' in title:
        return ['读出圆心和半径平方。','计算点到圆心的距离平方。','比较 CP² 与 r² 并写出位置。']
    if '判断直线' in title or '直线位置' in title:
        return ['读出圆心和半径。','计算圆心到直线的距离。','比较 d 与 r 并写出相交、相切或相离。']
    if '相切' in title or '相切' in q:
        return ['把切线整理为 Ax+By+C=0。','用点到直线距离公式计算圆心到切线的距离 r。','将 r² 代入标准式，并检查相切条件。']
    if '过圆上一点' in title or '过点' in q or '三个点' in title or '三点' in q:
        if '三个点' in title or '三点' in q:
            return ['设圆的一般式 x²+y²+Dx+Ey+F=0。','把三个已知点逐一代入，列出三元一次方程组。','解出 D、E、F，写出一般式并配方核验。']
        return ['写出圆心和圆上点的坐标。','用 r²=(x₀−a)²+(y₀−b)² 求半径平方。','代入标准式并把已知点代回检查。']
    if '配方' in title or '一般式' in q:
        return ['按 x、y 分组并分别配方。','把常数项移到右侧，整理成标准式。','读取圆心和半径，并检查右侧常数符号。']
    if '位置' in title or '位置关系' in q:
        return ['先读出圆心和半径。','计算点到圆心的距离平方，或计算圆心到直线的距离。','将距离与半径比较并写出位置结论。']
    return ['识别题目给出的圆心、半径或几何条件。','把条件代入对应公式，逐步算出未知量。','写出结果并回代核验。']

def _fmt_num(v):
    try:
        if abs(v-round(v)) < 1e-8: return str(int(round(v)))
    except Exception: pass
    return str(round(v,3))

def _coord(v):
    return f'{v}' if v < 0 else f'{v}'

def _std_eq(h,k,r2):
    sx=f'(x−{h})' if h>=0 else f'(x+{abs(h)})'
    sy=f'(y−{k})' if k>=0 else f'(y+{abs(k)})'
    return f'{sx}²+{sy}²={_fmt_num(r2)}'

def _circle_from_points(points):
    import numpy as np
    A=[]; b=[]
    for x,y in points:
        A.append([x,y,1]); b.append(-(x*x+y*y))
    D,E,F=np.linalg.solve(np.array(A,dtype=float),np.array(b,dtype=float))
    def term(v,var):
        if abs(v)<1e-8: return ''
        sign='+' if v>0 else '−'; mag=_fmt_num(abs(v))
        return f'{sign}{mag}{var}'
    eq=f'x²+y²{term(D,"x")}{term(E,"y")}{term(F,"")} = 0'.replace(' =','=').replace('−1','−1')
    return eq

def similar_variants(node):
    """Return four same-form questions with exactly two changed data points."""
    t=node.get('title','')
    out=[]
    # Atomic problems use their own same-form question list.  Keep the
    # analysis answer concise here; the detailed one-step method is added by
    # add_analysis_node.
    if any(k in t for k in ('求圆心','求半径','判断点','判断直线','直线位置')):
        generic = '按本节点模型完成计算，并写出对应结论。'
        return [{'question':q,'answer':generic} for q in node.get('similar',[])]
    if t.startswith('节点1：已知圆心和半径'):
        for h,k,r in [(5,-1,4),(2,3,5),(-3,-1,6),(2,4,2)]:
            out.append({'question':f'求圆心 C({h}，{k})、半径为 {r} 的圆的方程。','answer':_std_eq(h,k,r*r)})
    elif t.startswith('节点2：已知圆心和过圆上一点'):
        for (h,k),(x0,y0) in [((4,-1),(5,6)),((2,2),(7,3)),((-1,-1),(3,2)),((2,4),(-2,3))]:
            r2=(x0-h)**2+(y0-k)**2
            out.append({'question':f'已知圆心 C({h}，{k})，且经过点 P({x0}，{y0})，求圆的方程。','answer':_std_eq(h,k,r2)})
    elif '相切直线' in t or '过点和相切' in t:
        if '过点和相切' in t:
            vals=[((1,0),(4,4),'y=5'),((-2,1),(2,4),'y=6'),((0,-2),(3,2),'y=3'),((3,2),(7,5),'y=7')]
            for (h,k),(x0,y0),line in vals:
                r2=(x0-h)**2+(y0-k)**2
                out.append({'question':f'已知圆心 C({h}，{k})，经过点 P({x0}，{y0})，且与直线 {line} 相切，求圆的方程。','answer':_std_eq(h,k,r2)})
        else:
            vals=[((2,1),'y=−2',9),((-1,-1),'x=3',16),((0,0),'3x+4y−10=0',4),((-2,1),'x=4',36)]
            for (h,k),line,r2 in vals:
                out.append({'question':f'已知圆心 C({h}，{k})，且与直线 {line} 相切，求圆的方程。','answer':_std_eq(h,k,r2)})
    elif '一般式配方' in t or '配方后读取' in t:
        if '配方后读取' in t or '读取几何信息' in t:
            vals=[('x²+y²+2x−8y−3=0','(x+1)²+(y−4)²=20；圆心 (−1，4)，半径 2√5。'),('x²+y²−10x+6y+5=0','(x−5)²+(y+3)²=29；圆心 (5，−3)，半径 √29。'),('x²+y²−4x+2y+7=0','(x−2)²+(y+1)²=−2；无实圆。'),('x²+y²−2x+6y−3=0','(x−1)²+(y+3)²=13；圆心 (1，−3)，半径 √13。')]
        else:
            vals=[('x²+y²+4x−2y−3=0','(x+2)²+(y−1)²=8；圆心 (−2，1)，半径 2√2。'),('x²+y²−8x+4y−11=0','(x−4)²+(y+2)²=31；圆心 (4，−2)，半径 √31。'),('x²+y²−6x−2y−3=0','(x−3)²+(y−1)²=13；圆心 (3，1)，半径 √13。'),('x²+y²−2x+4y+1=0','(x−1)²+(y+2)²=4；圆心 (1，−2)，半径 2。')]
        for eq,ans in vals: out.append({'question':f'将方程 {eq} 化为标准式，并写出圆心和半径。','answer':ans})
    elif '三点确定圆' in t or '综合条件建立方程' in t or '综合建立' in t:
        if '三点确定圆' in t:
            pts_list=[[(2,0),(0,1),(2,3)],[(1,2),(0,1),(3,1)],[(-1,0),(0,1),(2,4)],[(1,0),(2,2),(2,1)]]
        else:
            pts_list=[[(-1,3),(4,2),(1,5)],[(-1,2),(4,2),(1,4)],[(-2,2),(3,2),(0,5)],[(-2,2),(3,3),(1,5)]]
        for pts in pts_list:
            labels='，'.join([f'{chr(65+i)}({x}，{y})' for i,(x,y) in enumerate(pts)])
            out.append({'question':f'求经过 {labels} 三点的圆的方程。','answer':_circle_from_points(pts)+'。'})
    elif t.startswith('节点1：标准式直接'):
        vals=[('(x+1)²+(y−4)²=9','圆心 C(−1，4)，半径 r=3。'),('(x−5)²+y²=25','圆心 C(5，0)，半径 r=5。'),('x²+(y+3)²=4','圆心 C(0，−3)，半径 r=2。'),('(x+2)²+(y−1)²=16','圆心 C(−2，1)，半径 r=4。')]
        for eq,ans in vals: out.append({'question':f'由 {eq} 读出圆心和半径。','answer':ans})
    elif t.startswith('节点2：用距离判断点'):
        vals=[('(x−1)²+(y+2)²=25','P(1，0) 在圆内。'),('(x−1)²+(y+2)²=25','P(7，−2) 在圆外。'),('(x−1)²+(y+2)²=25','P(2，−5) 在圆上。'),('(x−1)²+(y+2)²=25','P(−3，−2) 在圆上。')]
        for eq,ans in vals: out.append({'question':f'圆 {eq}，判断点的位置。','answer':ans})
    elif t.startswith('节点3：用距离判断直线') or '同时判断点和直线' in t:
        if '同时判断点和直线' in t:
            vals=[('P(2，3)','y=3','点在圆内，直线相切。'),('P(−2，−1)','x=−2','点在圆上，直线相交。'),('P(2，−5)','3x+4y−10=0','点在圆上，直线相离。'),('P(6，−1)','x−y+1=0','点在圆上，直线相交。')]
            for pt,line,ans in vals: out.append({'question':f'圆 (x−2)²+(y+1)²=16，判断点 {pt} 与直线 {line} 的位置。','answer':ans})
        else:
            vals=[('y=3','直线与圆相交。'),('x=−2','直线与圆相切。'),('3x+4y−10=0','先求圆心到直线距离，再与半径比较。'),('x−y+1=0','先求圆心到直线距离，再与半径比较。')]
            for line,ans in vals: out.append({'question':f'圆 (x−2)²+(y+1)²=16 与直线 {line} 的位置关系。','answer':ans})
    elif '判别条件' in t or '图形类型' in t:
        vals=[('x²+y²+2x−4y+5=0','表示一个点 (−1，2)。'),('x²+y²−8x+6y+25=0','表示一个点 (4，−3)。'),('x²+y²+4x+2y+10=0','无实点。'),('x²+y²−2x−2y−3=0','表示实圆。')]
        for eq,ans in vals: out.append({'question':f'判断 {eq} 表示什么图形。','answer':ans})
    elif '综合读取' in t:
        vals=[('x²+y²−4x−2y=0','标准式为 (x−2)²+(y−1)²=5；再分别比较点距和线距。'),('x²+y²+2x−6y−6=0','标准式为 (x+1)²+(y−3)²=16；再分别比较点距和线距。'),('x²+y²−6x+4y−3=0','标准式为 (x−3)²+(y+2)²=16；再分别比较点距和线距。'),('x²+y²+4x+2y−4=0','标准式为 (x+2)²+(y+1)²=9；再分别比较点距和线距。')]
        for eq,ans in vals: out.append({'question':f'圆 {eq}，判断指定点和直线的位置关系。','answer':ans})
    else:
        for q in node.get('similar',[]): out.append({'question':q,'answer':'按对应节点模型计算并核验。'})
    return out

def add_analysis_node(doc, node, teacher=False, include_evolution=True):
    h=doc.add_heading(node['title'], level=4); set_keep_with_next(h)
    if include_evolution:
        add_label_para(doc,'进化过程：',node['evolution'])
    add_label_para(doc,'一句话最优解法：',node['optimal'])
    add_label_para(doc,'例题：',node['example'],after=3)
    if node.get('diagram'):
        add_diagram(doc,node['diagram'],'node_'+node['title'])
    p=doc.add_paragraph(); set_para(p,after=2); add_text(p,'详细解析（一步一行）：',bold=True,size=10.5)
    detailed=split_analysis(node.get('analysis',''))
    if not detailed:
        detailed=node.get('steps',[])
    for i,step in enumerate(detailed,1): add_numbered(doc,step,i)
    add_label_para(doc,'参考答案：',node['answer'],after=4)
    if teacher:
        add_label_para(doc,'教学提示：',node.get('teaching','先让学生说出条件翻译，再落笔写方程。'),after=3)
        p=doc.add_paragraph(); set_para(p,after=2); add_text(p,'类似题（同节点格式）：',bold=True,size=10.5)
        for i,item in enumerate(similar_variants(node),1):
            h=doc.add_heading(f'类似题{i}', level=4); set_keep_with_next(h)
            add_label_para(doc,'题目：',item['question'],after=2)
            add_answer_area(doc,5)
            add_label_para(doc,'参考答案：',item['answer'],after=3)

def add_similar_question_blocks(doc, node):
    """Teacher question paper: similar questions use node layout without evolution prose."""
    for i,item in enumerate(similar_variants(node),1):
        h=doc.add_heading(f'类似题{i}', level=4); set_keep_with_next(h)
        add_label_para(doc,'题目：',item['question'],after=2)
        add_answer_area(doc,5)

def add_problem_and_chain_headings(doc, prob, chain):
    add_problem_intro(doc,prob)
    h=doc.add_heading(chain['title'], level=3); set_keep_with_next(h)
    add_label_para(doc,'链条说明：',chain['intro'])

def build_two_paper_doc(title, subtitle, data, mode='student', review=False):
    doc=setup_doc(title,subtitle)
    # Question paper
    h=doc.add_heading('第一部分 题目卷', level=1); set_keep_with_next(h)
    if mode=='teacher':
        add_label_para(doc,'使用说明：','题目卷用于课堂呈现和练习，解析卷用于教师讲解；类似题只在解析卷展开。')
    elif mode=='homework':
        add_label_para(doc,'作业要求：','每题写出关键步骤，先独立完成题目卷，再对照解析卷自检。')
    elif mode=='review':
        add_label_para(doc,'复习方法：','先遮住解析卷，依据问题本质写出最终模型。')
    else:
        add_label_para(doc,'学习路线：','先看问题本质，再沿原子问题的进化链完成节点练习。')
    add_knowledge(doc,teacher=(mode=='teacher'))
    for prob in data.values():
        add_problem_intro(doc,prob)
        for chain in prob['chains']:
            h=doc.add_heading(chain['title'], level=3); set_keep_with_next(h)
            add_label_para(doc,'链条说明：',chain['intro'])
            add_label_para(doc,'前后题关系：','后一道题保留前一道题的核心步骤，只增加一个条件；会做后一道题，就能还原并完成前一道题。')
            for node in chain['nodes']:
                add_question_node(doc,node,include_evolution=True)
                if mode=='teacher': add_similar_question_blocks(doc,node)
    # Analysis paper
    add_page_break(doc)
    h=doc.add_heading('第二部分 解析卷', level=1); set_keep_with_next(h)
    add_label_para(doc,'解析要求：','每一步单独成行，先写条件翻译，再写计算或方程，最后回代核验。')
    # Repeat the knowledge-point diagram so the analysis paper is independently usable.
    add_knowledge(doc,teacher=(mode=='teacher'))
    for prob in data.values():
        add_problem_intro(doc,prob)
        for chain in prob['chains']:
            h=doc.add_heading(chain['title'], level=3); set_keep_with_next(h)
            add_label_para(doc,'链条说明：',chain['intro'])
            add_label_para(doc,'前后题关系：','解析按“前一道题的步骤 + 新增条件”展开；后一节点的解法包含前一节点的解法。')
            for node in chain['nodes']:
                add_analysis_node(doc,node,teacher=(mode=='teacher'),include_evolution=True)
    if mode=='review':
        h=doc.add_heading('一页速记', level=1); set_keep_with_next(h)
        rows=[('求圆的方程','确定圆心和半径','标准式或一般式'),('求圆心','整理后读取 a、b','标准式或配方'),('求半径','先求 r² 再开平方','标准式或一般式公式'),('判断点与圆的位置关系','比较 CP² 与 r²','点距比较'),('判断直线与圆的位置关系','比较 d 与 r','点到直线距离')]
        tbl=doc.add_table(rows=1, cols=3); tbl.alignment=WD_TABLE_ALIGNMENT.CENTER; hdr=tbl.rows[0].cells; set_repeat_table_header(tbl.rows[0])
        for i,t in enumerate(['看到的条件','翻译成的关系','优先使用的模型']):
            set_cell_shading(hdr[i],'404040'); set_cell_borders(hdr[i]); set_cell_margins(hdr[i]); p=hdr[i].paragraphs[0]; set_para(p,after=0,align=WD_ALIGN_PARAGRAPH.CENTER); add_text(p,t,bold=True,color='FFFFFF',size=10)
        for row in rows:
            cells=tbl.add_row().cells
            for cell,text in zip(cells,row): set_cell_borders(cell); set_cell_margins(cell); add_text(cell.paragraphs[0],text,size=10)
    return doc

def build_student_class_v2(data): return build_two_paper_doc('2.4 圆的方程 学生上课版本','课堂学习资料 · 题目卷与解析卷',data,'student')
def build_teacher_v2(data): return build_two_paper_doc('2.4 圆的方程 教师上课版本','课堂备课资料 · 题目卷与解析卷',data,'teacher')
def build_homework_v2(data): return build_two_paper_doc('2.4 圆的方程 学生作业版本','课后巩固 · 题目卷与解析卷 · 数据已更换',data,'homework')

def build_review_v2(data):
    import copy
    compact={}
    for key,prob in data.items():
        compact[key]=copy.deepcopy(prob); compact[key]['chains']=[]
        for chain in prob['chains']:
            compact[key]['chains'].append({'title':chain['title'],'intro':'复习只保留本链最终模型。','nodes':[chain['nodes'][-1]]})
    return build_two_paper_doc('2.4 圆的方程 学生复习版本','考前回顾 · 题目卷与解析卷 · 保留最终模型',compact,'review',review=True)

data=attach_base_diagrams(split_atomic_circle_problems(make_data())); homework=make_homework(data)
paths=[]
paths.append(save(build_student_class_v2(data),'2.4圆的方程_学生上课版本.docx'))
paths.append(save(build_teacher_v2(data),'2.4圆的方程_教师上课版本.docx'))
paths.append(save(build_homework_v2(homework),'2.4圆的方程_学生作业版本.docx'))
paths.append(save(build_review_v2(data),'2.4圆的方程_学生复习版本.docx'))
for p in paths: print(p)
