"""
document_generator.py - מחולל מסמכים עסקיים
תומך ב: הצעת מחיר | דרישת תשלום | חשבונית מס (לעוסק מורשה)
"""
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

DOCS_DIR = os.path.join(os.path.dirname(__file__), 'documents')
os.makedirs(DOCS_DIR, exist_ok=True)

# ─── צבעים לפי סוג מסמך ────────────────────────────────
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


def _r(text: str) -> str:
    return text[::-1] if text else ''


def _s(name, bold=False, size=10, align=TA_RIGHT, color=colors.black,
        leading=14, space_after=4):
    return ParagraphStyle(
        name,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        fontSize=size,
        alignment=align,
        textColor=color,
        leading=leading,
        spaceAfter=space_after
    )


def _fmt(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return date_str


def generate_document(
    doc_type: str,
    doc_number: str,
    date: str,
    client_name: str,
    items: list,
    business_info: dict,
    client_phone: str = '',
    notes: str = '',
    valid_until: str = '',
    vat_rate: float = 0.0,
) -> str:
    """
    יוצר מסמך PDF.

    items: [{'name': str, 'quantity': int, 'unit_price': float, 'total': float}]
    vat_rate: 0.0 לעוסק פטור, 0.18 לעוסק מורשה
    מחזיר נתיב לקובץ PDF.
    """
    c = COLORS.get(doc_type, COLORS['quote'])
    primary = c['primary']
    accent = c['accent']
    heb_title, eng_title = DOC_TITLES.get(doc_type, ('מסמך', 'Document'))

    filename = f'{doc_type}_{doc_number.replace("-", "_")}.pdf'
    filepath = os.path.join(DOCS_DIR, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    story = []

    # ─── כותרת ─────────────────────────────────────────
    story.append(Paragraph(_r(heb_title), _s('title', bold=True, size=22,
                 color=primary, align=TA_CENTER, leading=28, space_after=2)))
    story.append(Paragraph(eng_title, _s('eng', size=11, align=TA_CENTER,
                 color=colors.HexColor('#777'), space_after=4)))
    story.append(HRFlowable(width='100%', thickness=2, color=accent, spaceAfter=6))

    # ─── מספר מסמך + תאריך ─────────────────────────────
    valid_text = f'בתוקף עד: {_fmt(valid_until)}' if valid_until else ''
    header_data = [[
        Paragraph(_r(valid_text), _s('vd', size=9, color=colors.HexColor('#777'))),
        Paragraph(_r(f'תאריך: {_fmt(date)}'), _s('dt', size=10)),
        Paragraph(_r(f'מספר: {doc_number}'), _s('num', bold=True, size=11, color=primary))
    ]]
    ht = Table(header_data, colWidths=[55*mm, 55*mm, 58*mm])
    ht.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(ht)
    story.append(Spacer(1, 5*mm))

    # ─── פרטי עסק ↔ לקוח ───────────────────────────────
    biz_lines = [_r(business_info.get('name', ''))]
    if business_info.get('address'):
        biz_lines.append(_r(business_info['address']))
    if business_info.get('phone'):
        biz_lines.append(f'טל: {business_info["phone"]}')
    if business_info.get('email'):
        biz_lines.append(business_info['email'])
    if business_info.get('id_number'):
        biz_lines.append(_r(f'ת.ז./ח.פ.: {business_info["id_number"]}'))

    client_lines = [_r(client_name)]
    if client_phone:
        client_lines.append(f'טל: {client_phone}')

    parties = [
        [Paragraph(_r('פרטי הספק'), _s('lbl', bold=False, size=9,
                   color=colors.HexColor('#888'))),
         Paragraph(_r('לכבוד'), _s('lbl2', bold=False, size=9,
                   color=colors.HexColor('#888')))],
        [Paragraph('<br/>'.join(biz_lines), _s('biz', size=10)),
         Paragraph('<br/>'.join(client_lines), _s('cli', bold=True, size=11, color=primary))]
    ]
    pt = Table(parties, colWidths=[85*mm, 83*mm])
    pt.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(pt)
    story.append(Spacer(1, 5*mm))

    # ─── טבלת פריטים ───────────────────────────────────
    has_qty = any(i.get('quantity', 1) != 1 for i in items)

    if has_qty:
        headers = [_r('סה"כ'), _r('מחיר יח\''), _r('כמות'), _r('תיאור')]
        col_w = [28*mm, 28*mm, 18*mm, 94*mm]
    else:
        headers = [_r('סכום'), _r('תיאור')]
        col_w = [35*mm, 133*mm]

    rows = [headers]
    for item in items:
        qty = item.get('quantity', 1)
        unit_price = item.get('unit_price', item.get('total', 0))
        total = item.get('total', unit_price * qty)
        name = _r(item.get('name', ''))
        if has_qty:
            rows.append([f'₪{total:,.0f}', f'₪{unit_price:,.0f}', str(qty), name])
        else:
            rows.append([f'₪{total:,.0f}', name])

    items_table = Table(rows, colWidths=col_w)
    items_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('BACKGROUND', (0, 0), (-1, 0), primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4*mm))

    # ─── סיכום מחירים ──────────────────────────────────
    subtotal = sum(i.get('total', i.get('unit_price', 0) * i.get('quantity', 1)) for i in items)
    vat_amount = round(subtotal * vat_rate, 2)
    total = subtotal + vat_amount

    totals_rows = []
    if vat_rate > 0:
        totals_rows.append(['', _r('סכום לפני מע"מ:'), f'₪{subtotal:,.2f}'])
        totals_rows.append(['', _r(f'מע"מ ({vat_rate*100:.0f}%):'), f'₪{vat_amount:,.2f}'])
    totals_rows.append(['', _r('סה"כ לתשלום:'), f'₪{total:,.2f}'])

    totals_table = Table(totals_rows, colWidths=[90*mm, 55*mm, 23*mm])
    style = [
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONT', (1, -1), (2, -1), 'Helvetica-Bold', 13),
        ('TEXTCOLOR', (2, -1), (2, -1), accent),
        ('BACKGROUND', (1, -1), (2, -1), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    totals_table.setStyle(TableStyle(style))
    story.append(totals_table)
    story.append(Spacer(1, 4*mm))

    # ─── הערות ─────────────────────────────────────────
    if notes:
        story.append(Paragraph(_r(f'הערות: {notes}'),
                     _s('notes', size=9, color=colors.HexColor('#555'), space_after=3)))

    # ─── כיתוב תחתון לפי סוג ───────────────────────────
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=3))

    if doc_type == 'quote':
        footer_text = _r(
            f'הצעה זו תקפה עד {_fmt(valid_until) if valid_until else "30 יום"} | '
            'עוסק פטור ממע"מ'
        )
    elif doc_type == 'payment_request':
        footer_text = _r('אנא העבר את התשלום בתוך 14 יום | עוסק פטור ממע"מ')
    else:
        footer_text = _r(
            'חשבונית מס קבלה | מע"מ כחוק | '
            f'מספר עוסק: {business_info.get("id_number", "")}'
        )

    story.append(Paragraph(footer_text,
                 _s('foot', size=8, align=TA_CENTER,
                    color=colors.HexColor('#999'), space_after=0)))
    story.append(Paragraph(
        _r(f'הופק: {datetime.now().strftime("%d/%m/%Y %H:%M")}'),
        _s('ft2', size=7, align=TA_CENTER,
           color=colors.HexColor('#BBBBBB'), space_after=0)
    ))

    doc.build(story)
    return filepath


def pdf_to_image(pdf_path: str, zoom: float = 2.5) -> str:
    """ממיר PDF לתמונת PNG."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img_path = pdf_path.replace('.pdf', '.png')
        pix.save(img_path)
        doc.close()
        return img_path
    except ImportError:
        raise RuntimeError('pymupdf לא מותקן. הרץ: pip install pymupdf')
