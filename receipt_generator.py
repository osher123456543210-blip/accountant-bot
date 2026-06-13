"""
receipt_generator.py - מחולל קבלות PDF לעוסק פטור
יוצר מסמכי קבלה תקניים בעברית לפי דרישות רשות המסים
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

RECEIPTS_DIR = os.path.join(os.path.dirname(__file__), 'receipts')
os.makedirs(RECEIPTS_DIR, exist_ok=True)

# ─── צבעים ────────────────────────────────────────────

PRIMARY = colors.HexColor('#2C3E50')
ACCENT = colors.HexColor('#27AE60')
LIGHT_GRAY = colors.HexColor('#F5F5F5')
BORDER_COLOR = colors.HexColor('#E0E0E0')


def _get_font():
    """
    מנסה לטעון פונט עברי.
    אם אין — משתמש ב-Helvetica (עברית תופיע כ-RTL ב-PDF).
    להתקנת פונט: pip install reportlab
    ולהוסיף קובץ NotoSansHebrew-Regular.ttf לתיקיית הפרויקט.
    """
    font_path = os.path.join(os.path.dirname(__file__), 'NotoSansHebrew-Regular.ttf')
    bold_path = os.path.join(os.path.dirname(__file__), 'NotoSansHebrew-Bold.ttf')

    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('Hebrew', font_path))
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont('HebrewBold', bold_path))
            else:
                pdfmetrics.registerFont(TTFont('HebrewBold', font_path))
            return 'Hebrew', 'HebrewBold'
        except Exception:
            pass
    return 'Helvetica', 'Helvetica-Bold'


def _reverse_hebrew(text: str) -> str:
    """היפוך טקסט עברי ל-RTL בסיסי לתצוגה נכונה ב-ReportLab."""
    if not text:
        return text
    return text[::-1]


def generate_receipt(
    receipt_number: str,
    date: str,
    client_name: str,
    description: str,
    amount: float,
    business_info: dict,
    notes: str = ''
) -> str:
    """
    יוצר קבלה PDF ומחזיר את הנתיב אליה.

    business_info keys: name, address, phone, id_number (ת.ז. / ח.פ.), email
    """
    font_regular, font_bold = _get_font()

    filename = f'receipt_{receipt_number.replace("-", "_")}.pdf'
    filepath = os.path.join(RECEIPTS_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    # ─── סגנונות ───────────────────────────────────────

    def style(name, font=font_regular, size=10, align=TA_RIGHT, color=colors.black,
              leading=14, space_after=4):
        return ParagraphStyle(
            name,
            fontName=font,
            fontSize=size,
            alignment=align,
            textColor=color,
            leading=leading,
            spaceAfter=space_after
        )

    s_title = style('title', font=font_bold, size=22, color=PRIMARY,
                    align=TA_CENTER, leading=28, space_after=2)
    s_subtitle = style('subtitle', size=11, align=TA_CENTER,
                       color=colors.HexColor('#555555'), space_after=6)
    s_label = style('label', font=font_bold, size=9, color=colors.HexColor('#888888'),
                    space_after=2)
    s_value = style('value', font=font_bold, size=11, color=PRIMARY, space_after=6)
    s_normal = style('normal', size=10, space_after=3)
    s_small = style('small', size=8, color=colors.HexColor('#777777'), space_after=2)
    s_total = style('total', font=font_bold, size=14, color=ACCENT,
                    align=TA_RIGHT, space_after=4)
    s_exempt = style('exempt', size=9, color=colors.HexColor('#888888'),
                     align=TA_CENTER, space_after=2)
    s_footer = style('footer', size=8, color=colors.HexColor('#AAAAAA'),
                     align=TA_CENTER, space_after=0)

    story = []

    # ─── כותרת ─────────────────────────────────────────
    story.append(Paragraph(_reverse_hebrew('קבלה'), s_title))
    story.append(Paragraph(_reverse_hebrew('Receipt'), s_subtitle))
    story.append(HRFlowable(width='100%', thickness=2, color=ACCENT, spaceAfter=8))

    # ─── מספר קבלה + תאריך ─────────────────────────────
    header_data = [
        [
            Paragraph(_reverse_hebrew(f'תאריך: {_format_date_heb(date)}'), s_normal),
            Paragraph(_reverse_hebrew(f'קבלה מספר: {receipt_number}'), s_value)
        ]
    ]
    header_table = Table(header_data, colWidths=[85 * mm, 85 * mm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # ─── פרטי עסק ─────────────────────────────────────
    biz_name = business_info.get('name', '')
    biz_addr = business_info.get('address', '')
    biz_phone = business_info.get('phone', '')
    biz_id = business_info.get('id_number', '')
    biz_email = business_info.get('email', '')

    biz_lines = [_reverse_hebrew(biz_name)]
    if biz_addr:
        biz_lines.append(_reverse_hebrew(biz_addr))
    if biz_phone:
        biz_lines.append(f'טל: {biz_phone}')
    if biz_email:
        biz_lines.append(biz_email)
    if biz_id:
        biz_lines.append(_reverse_hebrew(f'ת.ז. / ח.פ.: {biz_id}'))

    biz_section = [
        [Paragraph(_reverse_hebrew('פרטי הספק'), s_label),
         Paragraph(_reverse_hebrew('פרטי הלקוח'), s_label)],
        [
            Paragraph('<br/>'.join(biz_lines), s_normal),
            Paragraph(_reverse_hebrew(client_name), s_value)
        ]
    ]
    biz_table = Table(biz_section, colWidths=[85 * mm, 85 * mm])
    biz_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(biz_table)
    story.append(Spacer(1, 6 * mm))

    # ─── פרטי השירות ───────────────────────────────────
    story.append(Paragraph(_reverse_hebrew('פרטי השירות'), s_label))

    service_data = [
        [
            Paragraph(_reverse_hebrew('סכום'), style('th', font=font_bold, size=9,
                      color=PRIMARY, align=TA_CENTER)),
            Paragraph(_reverse_hebrew('תיאור'), style('th2', font=font_bold, size=9,
                      color=PRIMARY, align=TA_RIGHT)),
        ],
        [
            Paragraph(f'₪{amount:,.2f}',
                      style('amt', font=font_bold, size=12, color=ACCENT,
                            align=TA_CENTER)),
            Paragraph(_reverse_hebrew(description),
                      style('desc', size=10, align=TA_RIGHT)),
        ]
    ]
    service_table = Table(service_data, colWidths=[40 * mm, 130 * mm])
    service_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(service_table)
    story.append(Spacer(1, 4 * mm))

    # ─── סה"כ ──────────────────────────────────────────
    total_data = [
        ['', Paragraph(_reverse_hebrew('סה"כ לתשלום:'), s_label),
         Paragraph(f'₪{amount:,.2f}', s_total)]
    ]
    total_table = Table(total_data, colWidths=[80 * mm, 60 * mm, 30 * mm])
    total_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (1, 0), (-1, 0), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 3 * mm))

    # ─── הערות ─────────────────────────────────────────
    if notes:
        story.append(Paragraph(_reverse_hebrew(f'הערות: {notes}'), s_small))
        story.append(Spacer(1, 3 * mm))

    # ─── כיתוב עוסק פטור ───────────────────────────────
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER_COLOR, spaceAfter=4))
    story.append(Paragraph(
        _reverse_hebrew('עוסק פטור ממע"מ לפי סעיף 31 לחוק מס ערך מוסף, תשל"ו-1975'),
        s_exempt
    ))
    story.append(Spacer(1, 4 * mm))

    # ─── תחתית ─────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER_COLOR, spaceAfter=3))
    story.append(Paragraph(
        _reverse_hebrew(f'מסמך זה הופק אוטומטית ב-{datetime.now().strftime("%d/%m/%Y %H:%M")}'),
        s_footer
    ))

    doc.build(story)
    return filepath


def _format_date_heb(date_str: str) -> str:
    """2024-03-15 → 15/03/2024"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%d/%m/%Y')
    except Exception:
        return date_str


def pdf_to_image(pdf_path: str, zoom: float = 2.5) -> str:
    """
    ממיר עמוד ראשון של PDF לתמונת PNG ברזולוציה גבוהה.
    מחזיר נתיב לקובץ ה-PNG.
    zoom=2.5 → ~595*2.5 = ~1488px רוחב (איכות גבוהה לנייד)
    """
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = pdf_path.replace('.pdf', '.png')
        pix.save(img_path)
        doc.close()
        return img_path
    except ImportError:
        raise RuntimeError(
            'pymupdf לא מותקן. הרץ: pip install pymupdf'
        )


if __name__ == '__main__':
    # בדיקה
    path = generate_receipt(
        receipt_number='2024-0001',
        date='2024-03-15',
        client_name='דנה לוי',
        description='טיפול פנים מלא + עיסוי',
        amount=450.0,
        business_info={
            'name': 'שרה כהן - טיפולי יופי',
            'address': 'רחוב הרצל 10, תל אביב',
            'phone': '050-1234567',
            'id_number': '123456789',
            'email': 'sarah@example.com'
        }
    )
    print(f'קבלה נוצרה: {path}')
