"""
receipt_generator.py - מחולל קבלות PDF לעוסק פטור עם פונט עברי
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from bidi.algorithm import get_display

RECEIPTS_DIR = os.path.join(os.path.dirname(__file__), 'receipts')
os.makedirs(RECEIPTS_DIR, exist_ok=True)

PRIMARY = colors.HexColor('#2C3E50')
ACCENT  = colors.HexColor('#27AE60')
LIGHT_GRAY = colors.HexColor('#F5F5F5')
BORDER_COLOR = colors.HexColor('#E0E0E0')

_FONTS_REGISTERED = False

def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return 'Hebrew', 'HebrewBold'
    font_dir = os.path.dirname(__file__)
    regular = os.path.join(font_dir, 'NotoSansHebrew-Regular.ttf')
    bold    = os.path.join(font_dir, 'NotoSansHebrew-Bold.ttf')
    if os.path.exists(regular):
        try:
            pdfmetrics.registerFont(TTFont('Hebrew', regular))
            pdfmetrics.registerFont(TTFont('HebrewBold', bold if os.path.exists(bold) else regular))
            _FONTS_REGISTERED = True
            return 'Hebrew', 'HebrewBold'
        except Exception:
            pass
    return 'Helvetica', 'Helvetica-Bold'

def heb(text):
    """עיבוד טקסט עברי לתצוגה נכונה ב-ReportLab."""
    if not text:
        return ''
    return get_display(text)

def _s(name, font='Hebrew', bold=False, size=10, align=TA_RIGHT,
        color=colors.black, leading=14, space_after=4):
    fn, fb = _register_fonts()
    return ParagraphStyle(
        name,
        fontName=fb if bold else fn,
        fontSize=size,
        alignment=align,
        textColor=color,
        leading=leading,
        spaceAfter=space_after,
        wordWrap='RTL'
    )

def _fmt(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return date_str

def generate_receipt(receipt_number, date, client_name, description,
                     amount, business_info, notes=''):
    _register_fonts()
    filename = f'receipt_{receipt_number.replace("-","_")}.pdf'
    filepath = os.path.join(RECEIPTS_DIR, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    story = []

    # כותרת
    story.append(Paragraph(heb('קבלה'), _s('t1', bold=True, size=22, color=PRIMARY,
                 align=TA_CENTER, leading=28, space_after=2)))
    story.append(Paragraph('Receipt', ParagraphStyle('eng', fontName='Helvetica',
                 fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor('#555'),
                 spaceAfter=4)))
    story.append(HRFlowable(width='100%', thickness=2, color=ACCENT, spaceAfter=6))

    # מספר + תאריך
    hd = [[
        Paragraph(f'{heb("תאריך:")} {_fmt(date)}', _s('dt', size=10)),
        Paragraph(f'{heb("קבלה מספר:")} {receipt_number}', _s('num', bold=True, size=11, color=PRIMARY))
    ]]
    ht = Table(hd, colWidths=[85*mm, 85*mm])
    ht.setStyle(TableStyle([
        ('ALIGN',(0,0),(0,0),'LEFT'), ('ALIGN',(1,0),(1,0),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(0,0),(-1,-1),LIGHT_GRAY),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(ht)
    story.append(Spacer(1, 5*mm))

    # פרטי עסק ↔ לקוח
    biz = business_info
    biz_lines = [heb(biz.get('name',''))]
    if biz.get('address'): biz_lines.append(heb(biz['address']))
    if biz.get('phone'):   biz_lines.append(f'{heb("טל:")} {biz["phone"]}')
    if biz.get('email'):   biz_lines.append(biz['email'])
    if biz.get('id_number'): biz_lines.append(f'{heb("ת.ז./ח.פ.:")} {biz["id_number"]}')

    parties = [
        [Paragraph(heb('פרטי הספק'), _s('lbl', size=9, color=colors.HexColor('#888'))),
         Paragraph(heb('פרטי הלקוח'), _s('lbl2', size=9, color=colors.HexColor('#888')))],
        [Paragraph('<br/>'.join(biz_lines), _s('biz', size=10)),
         Paragraph(heb(client_name), _s('cli', bold=True, size=11, color=PRIMARY))]
    ]
    pt = Table(parties, colWidths=[85*mm, 83*mm])
    pt.setStyle(TableStyle([
        ('ALIGN',(0,0),(-1,-1),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('GRID',(0,0),(-1,-1),0.5,BORDER_COLOR),
        ('BACKGROUND',(0,0),(-1,0),LIGHT_GRAY),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(pt)
    story.append(Spacer(1, 5*mm))

    # שירות
    story.append(Paragraph(heb('פרטי השירות'), _s('lbl3', size=9, color=colors.HexColor('#888'))))
    svc = [
        [Paragraph(heb('סכום'), _s('th', bold=True, size=9, color=colors.white, align=TA_CENTER)),
         Paragraph(heb('תיאור'), _s('th2', bold=True, size=9, color=colors.white, align=TA_RIGHT))],
        [Paragraph(f'₪{amount:,.2f}', _s('amt', bold=True, size=12, color=ACCENT, align=TA_CENTER)),
         Paragraph(heb(description), _s('desc', size=10, align=TA_RIGHT))]
    ]
    st = Table(svc, colWidths=[40*mm, 130*mm])
    st.setStyle(TableStyle([
        ('ALIGN',(0,0),(0,-1),'CENTER'), ('ALIGN',(1,0),(1,-1),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(0,0),(-1,0),PRIMARY),
        ('BACKGROUND',(0,1),(-1,1),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,BORDER_COLOR),
        ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(st)
    story.append(Spacer(1, 4*mm))

    # סה"כ
    tot = [[
        '',
        Paragraph(heb('סה"כ לתשלום:'), _s('tlbl', size=9, color=colors.HexColor('#888'), align=TA_RIGHT)),
        Paragraph(f'₪{amount:,.2f}', _s('tamt', bold=True, size=14, color=ACCENT, align=TA_RIGHT))
    ]]
    tt = Table(tot, colWidths=[80*mm, 60*mm, 30*mm])
    tt.setStyle(TableStyle([
        ('ALIGN',(1,0),(2,0),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(1,0),(-1,0),LIGHT_GRAY),
        ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('RIGHTPADDING',(0,0),(-1,-1),10),
    ]))
    story.append(tt)

    if notes:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(heb(f'הערות: {notes}'),
                     _s('notes', size=9, color=colors.HexColor('#777'))))

    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER_COLOR, spaceAfter=3))
    story.append(Paragraph(
        heb('עוסק פטור ממע"מ לפי סעיף 31 לחוק מס ערך מוסף, תשל"ו-1975'),
        _s('exempt', size=9, color=colors.HexColor('#888'), align=TA_CENTER)
    ))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        heb(f'הופק: {datetime.now().strftime("%d/%m/%Y %H:%M")}'),
        _s('foot', size=8, color=colors.HexColor('#AAAAAA'), align=TA_CENTER)
    ))

    doc.build(story)
    return filepath


def pdf_to_image(pdf_path, zoom=2.5):
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img_path = pdf_path.replace('.pdf', '.png')
        pix.save(img_path)
        doc.close()
        return img_path
    except ImportError:
        raise RuntimeError('pymupdf לא מותקן')
