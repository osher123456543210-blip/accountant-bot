"""
document_generator.py - מחולל מסמכים עסקיים עם פונט עברי
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

DOCS_DIR = os.path.join(os.path.dirname(__file__), 'documents')
os.makedirs(DOCS_DIR, exist_ok=True)

COLORS = {
    'quote':           {'primary': colors.HexColor('#1565C0'), 'accent': colors.HexColor('#42A5F5')},
    'payment_request': {'primary': colors.HexColor('#6A1B9A'), 'accent': colors.HexColor('#AB47BC')},
    'tax_invoice':     {'primary': colors.HexColor('#1B5E20'), 'accent': colors.HexColor('#43A047')},
}
LIGHT_GRAY = colors.HexColor('#F8F9FA')
BORDER = colors.HexColor('#DEE2E6')

DOC_TITLES = {
    'quote':           ('הצעת מחיר', 'Quotation'),
    'payment_request': ('דרישת תשלום', 'Payment Request'),
    'tax_invoice':     ('חשבונית מס קבלה', 'Tax Invoice'),
}

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
    if not text: return ''
    return get_display(str(text))

def _s(name, bold=False, size=10, align=TA_RIGHT, color=colors.black,
        leading=14, space_after=4):
    fn, fb = _register_fonts()
    return ParagraphStyle(name, fontName=fb if bold else fn, fontSize=size,
                          alignment=align, textColor=color, leading=leading,
                          spaceAfter=space_after, wordWrap='RTL')

def _fmt(date_str):
    try: return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return date_str

def generate_document(doc_type, doc_number, date, client_name, items,
                      business_info, client_phone='', notes='',
                      valid_until='', vat_rate=0.0):
    _register_fonts()
    c = COLORS.get(doc_type, COLORS['quote'])
    primary, accent = c['primary'], c['accent']
    heb_title, eng_title = DOC_TITLES.get(doc_type, ('מסמך', 'Document'))

    filename = f'{doc_type}_{doc_number.replace("-","_")}.pdf'
    filepath = os.path.join(DOCS_DIR, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    story = []

    # כותרת
    story.append(Paragraph(heb(heb_title),
                 _s('t1', bold=True, size=22, color=primary, align=TA_CENTER, leading=28, space_after=2)))
    story.append(Paragraph(eng_title,
                 ParagraphStyle('eng', fontName='Helvetica', fontSize=11,
                                alignment=TA_CENTER, textColor=colors.HexColor('#777'), spaceAfter=4)))
    story.append(HRFlowable(width='100%', thickness=2, color=accent, spaceAfter=6))

    # מספר + תאריך
    valid_text = f'{heb("בתוקף עד:")} {_fmt(valid_until)}' if valid_until else ''
    hd = [[
        Paragraph(valid_text, _s('vd', size=9, color=colors.HexColor('#777'))),
        Paragraph(f'{heb("תאריך:")} {_fmt(date)}', _s('dt', size=10)),
        Paragraph(f'{heb("מספר:")} {doc_number}', _s('num', bold=True, size=11, color=primary))
    ]]
    ht = Table(hd, colWidths=[55*mm, 55*mm, 58*mm])
    ht.setStyle(TableStyle([
        ('ALIGN',(0,0),(0,0),'LEFT'), ('ALIGN',(1,0),(1,0),'CENTER'), ('ALIGN',(2,0),(2,0),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'), ('BACKGROUND',(0,0),(-1,-1),LIGHT_GRAY),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),6), ('RIGHTPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(ht)
    story.append(Spacer(1, 5*mm))

    # פרטי עסק ↔ לקוח
    biz = business_info
    biz_lines = [heb(biz.get('name',''))]
    if biz.get('address'):   biz_lines.append(heb(biz['address']))
    if biz.get('phone'):     biz_lines.append(f'{heb("טל:")} {biz["phone"]}')
    if biz.get('email'):     biz_lines.append(biz['email'])
    if biz.get('id_number'): biz_lines.append(f'{heb("ת.ז./ח.פ.:")} {biz["id_number"]}')

    client_lines = [heb(client_name)]
    if client_phone: client_lines.append(f'{heb("טל:")} {client_phone}')

    parties = [
        [Paragraph(heb('פרטי הספק'), _s('l1', size=9, color=colors.HexColor('#888'))),
         Paragraph(heb('לכבוד'), _s('l2', size=9, color=colors.HexColor('#888')))],
        [Paragraph('<br/>'.join(biz_lines), _s('biz', size=10)),
         Paragraph('<br/>'.join(client_lines), _s('cli', bold=True, size=11, color=primary))]
    ]
    pt = Table(parties, colWidths=[85*mm, 83*mm])
    pt.setStyle(TableStyle([
        ('ALIGN',(0,0),(-1,-1),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('GRID',(0,0),(-1,-1),0.5,BORDER), ('BACKGROUND',(0,0),(-1,0),LIGHT_GRAY),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(pt)
    story.append(Spacer(1, 5*mm))

    # פריטים
    rows = [[Paragraph(heb('סכום'), _s('th', bold=True, size=9, color=colors.white, align=TA_CENTER)),
             Paragraph(heb('תיאור'), _s('th2', bold=True, size=9, color=colors.white, align=TA_RIGHT))]]
    for item in items:
        total = item.get('total', item.get('unit_price', 0) * item.get('quantity', 1))
        rows.append([
            Paragraph(f'₪{total:,.0f}', _s('amt', bold=True, size=11, color=accent, align=TA_CENTER)),
            Paragraph(heb(item.get('name', '')), _s('desc', size=10, align=TA_RIGHT))
        ])

    it = Table(rows, colWidths=[35*mm, 133*mm])
    it.setStyle(TableStyle([
        ('ALIGN',(0,0),(0,-1),'CENTER'), ('ALIGN',(1,0),(1,-1),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(0,0),(-1,0),primary),
        ('GRID',(0,0),(-1,-1),0.5,BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, LIGHT_GRAY]),
        ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),6), ('RIGHTPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(it)
    story.append(Spacer(1, 4*mm))

    # סה"כ
    subtotal = sum(i.get('total', i.get('unit_price',0)*i.get('quantity',1)) for i in items)
    vat_amount = round(subtotal * vat_rate, 2)
    total = subtotal + vat_amount

    tot_rows = []
    if vat_rate > 0:
        tot_rows.append(['', Paragraph(heb('סכום לפני מע"מ:'), _s('tl', size=9, align=TA_RIGHT)),
                         Paragraph(f'₪{subtotal:,.2f}', _s('ta', size=10, align=TA_RIGHT))])
        tot_rows.append(['', Paragraph(heb(f'מע"מ ({vat_rate*100:.0f}%):'), _s('tl2', size=9, align=TA_RIGHT)),
                         Paragraph(f'₪{vat_amount:,.2f}', _s('ta2', size=10, align=TA_RIGHT))])
    tot_rows.append(['',
                     Paragraph(heb('סה"כ לתשלום:'), _s('tl3', bold=True, size=10, align=TA_RIGHT)),
                     Paragraph(f'₪{total:,.2f}', _s('ta3', bold=True, size=13, color=accent, align=TA_RIGHT))])

    tt = Table(tot_rows, colWidths=[90*mm, 55*mm, 23*mm])
    tt.setStyle(TableStyle([
        ('ALIGN',(1,0),(2,-1),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(1,-1),(2,-1),LIGHT_GRAY),
        ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(tt)

    if notes:
        story.append(Spacer(1,3*mm))
        story.append(Paragraph(heb(f'הערות: {notes}'),
                     _s('notes', size=9, color=colors.HexColor('#555'))))

    # תחתית
    story.append(Spacer(1,4*mm))
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=3))

    if doc_type == 'quote':
        footer = heb(f'הצעה זו תקפה עד {_fmt(valid_until) if valid_until else "30 יום"} | עוסק פטור ממע"מ')
    elif doc_type == 'payment_request':
        footer = heb('אנא העבר את התשלום בתוך 14 יום | עוסק פטור ממע"מ')
    else:
        footer = heb(f'חשבונית מס קבלה | מספר עוסק: {biz.get("id_number","")}')

    story.append(Paragraph(footer, _s('foot', size=8, align=TA_CENTER,
                 color=colors.HexColor('#999'), space_after=0)))
    story.append(Paragraph(heb(f'הופק: {datetime.now().strftime("%d/%m/%Y %H:%M")}'),
                 _s('ft2', size=7, align=TA_CENTER, color=colors.HexColor('#BBB'), space_after=0)))

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
