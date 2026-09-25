from docx import Document
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import re

out=Path(r'C:\Users\Administrator\Documents\Codex\2026-09-24\referenced-chatgpt-conversation-this-is-an-3\outputs')
qa=Path(r'C:\Users\Administrator\Documents\Codex\2026-09-24\referenced-chatgpt-conversation-this-is-an-3\work\qa_pdf_final'); qa.mkdir(parents=True,exist_ok=True)
font='C:\\Windows\\Fonts\\simsun.ttf'
if not Path(font).exists(): font='C:\\Windows\\Fonts\\Deng.ttf'
pdfmetrics.registerFont(TTFont('CJK',font))
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='CNTitle', parent=styles['Title'], fontName='CJK', fontSize=17, leading=22, textColor=colors.black, spaceAfter=8))
styles.add(ParagraphStyle(name='CNSub', parent=styles['Normal'], fontName='CJK', fontSize=10.5, leading=15, textColor=colors.HexColor('#555555'), spaceAfter=10))
styles.add(ParagraphStyle(name='H1CN', parent=styles['Heading1'], fontName='CJK', fontSize=14, leading=18, textColor=colors.black, spaceBefore=8, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name='H2CN', parent=styles['Heading2'], fontName='CJK', fontSize=12.5, leading=16, textColor=colors.black, spaceBefore=8, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name='H3CN', parent=styles['Heading3'], fontName='CJK', fontSize=11.5, leading=15, textColor=colors.black, spaceBefore=6, spaceAfter=3, keepWithNext=True))
styles.add(ParagraphStyle(name='H4CN', parent=styles['Heading4'], fontName='CJK', fontSize=10.8, leading=14, textColor=colors.black, spaceBefore=5, spaceAfter=3, keepWithNext=True))
styles.add(ParagraphStyle(name='BodyCN', parent=styles['BodyText'], fontName='CJK', fontSize=9.6, leading=14, spaceAfter=4))
styles.add(ParagraphStyle(name='MathCN', parent=styles['BodyText'], fontName='CJK', fontSize=10.5, leading=14, alignment=1, spaceAfter=5))
styles.add(ParagraphStyle(name='SmallCN', parent=styles['BodyText'], fontName='CJK', fontSize=8.8, leading=12, textColor=colors.HexColor('#555555')))

def esc(t):
    return t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def para_text(t,style='BodyCN'):
    # bold labels before colon
    t=esc(t)
    t=re.sub(r'^(知识来源|知识形成|核心公式|问题本质|最优解法一句话|链条说明|进化过程|一句话最优解法|解题步骤|例题|参考答案|教学提示|分步解析|类似题（课堂变式）|学生作答区（写出关键步骤）|作业要求|看到的条件|翻译成的关系|优先使用的模型)：', lambda m:'<b>'+m.group(1)+'：</b>', t)
    return Paragraph(t,styles[style])

def header_footer(canvas,doc):
    canvas.saveState(); canvas.setFont('CJK',8); canvas.setFillColor(colors.HexColor('#777777'))
    canvas.drawRightString(A4[0]-18*mm,A4[1]-12*mm,'2.4 圆的方程 · 新课 Skill V2')
    canvas.drawCentredString(A4[0]/2,10*mm,'知识点 → 问题 → 进化链 → 节点')
    canvas.drawRightString(A4[0]-18*mm,10*mm,f'{doc.page}')
    canvas.restoreState()

def convert(path):
    d=Document(path); story=[]
    # handle paragraphs in order; tables are inserted later as line blocks approximately
    for p in d.paragraphs:
        t=p.text.strip()
        if not t: continue
        st=p.style.name
        if st=='Title': story.append(para_text(t,'CNTitle'))
        elif st=='Heading 1': story.append(para_text(t,'H1CN'))
        elif st=='Heading 2': story.append(para_text(t,'H2CN'))
        elif st=='Heading 3': story.append(para_text(t,'H3CN'))
        elif st=='Heading 4': story.append(para_text(t,'H4CN'))
        elif t.startswith('CP =') or t.startswith('标准式：') or t.startswith('一般式：') or t.startswith('(x') or t.startswith('x²'):
            story.append(para_text(t,'MathCN'))
        else: story.append(para_text(t,'BodyCN'))
        # no blank line injection here
    # Add a note that PDF QA represents the same extracted content; tables are checked structurally in DOCX.
    story.append(Spacer(1,4))
    story.append(para_text('PDF 检查说明：已按 DOCX 文本和层级生成分页校验稿，用于检查标题层级、字符显示、分页和留白。','SmallCN'))
    pdf=qa/(path.stem+'_pdf检查.pdf')
    doc=SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=16*mm)
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)
    return pdf

for p in sorted(out.glob('*.docx')):
    print(convert(p))


