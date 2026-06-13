"""
report_generator.py - מחולל דוחות שנתיים/חודשיים
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
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

import models

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

PRIMARY = colors.HexColor('#2C3E50')
ACCENT = colors.HexColor('#27AE60')
RED = colors.HexColor('#E74C3C')
LIGHT_GRAY = colors.HexColor('#F8F9FA')
BORDER = colors.HexColor('#DEE2E6')


def _s(name, font='Helvetica', bold=False, size=10, align=TA_RIGHT,
        color=colors.black, leading=14, space_after=4):
    return ParagraphStyle(
        name,
        fontName='Helvetica-Bold' if bold else font,
        fontSize=size,
        alignment=align,
        textColor=color,
        leading=leading,
        spaceAfter=space_after
    )


def _r(text):
    """Reverse for RTL display."""
    return text[::-1] if text else text


def generate_annual_report(year: int, business_info: dict) -> str:
    """יוצר דוח שנתי PDF ומחזיר נתיב."""
    inc_data = models.get_income_summary(year=year)
    exp_data = models.get_expense_summary(year=year)

    filename = f'annual_report_{year}.pdf'
    filepath = os.path.join(REPORTS_DIR, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    story = []

    # כותרת
    story.append(Paragraph(_r(f'דוח הכנסות והוצאות שנתי'), _s('h1', bold=True, size=20,
                 color=PRIMARY, align=TA_CENTER, space_after=2)))
    story.append(Paragraph(_r(f'שנת {year}'), _s('h2', size=13, align=TA_CENTER,
                 color=colors.HexColor('#555'), space_after=4)))
    story.append(HRFlowable(width='100%', thickness=2, color=ACCENT, spaceAfter=6))

    # פרטי עסק
    biz_name = business_info.get('name', '')
    biz_id = business_info.get('id_number', '')
    story.append(Paragraph(
        _r(f'{biz_name}  |  ת.ז./ח.פ.: {biz_id}  |  עוסק פטור'),
        _s('biz', size=9, align=TA_CENTER, color=colors.HexColor('#777'), space_after=8)
    ))

    # סיכום עליון
    profit = inc_data['total'] - exp_data['total']
    summary_data = [
        [_r('סה"כ הכנסות'), _r('סה"כ הוצאות'), _r('רווח נקי')],
        [f'₪{inc_data["total"]:,.2f}', f'₪{exp_data["total"]:,.2f}',
         f'₪{profit:,.2f}']
    ]
    summary_table = Table(summary_data, colWidths=[56*mm, 56*mm, 56*mm])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, 1), 'Helvetica-Bold', 14),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 1), (0, 1), ACCENT),
        ('TEXTCOLOR', (1, 1), (1, 1), RED),
        ('TEXTCOLOR', (2, 1), (2, 1), ACCENT if profit >= 0 else RED),
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_GRAY),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6*mm))

    # ── טבלת הכנסות ────────────────────────────────────
    story.append(Paragraph(_r('הכנסות'), _s('sec', bold=True, size=13,
                 color=PRIMARY, space_after=3)))

    inc_rows = [[_r('סכום'), _r('תיאור'), _r('לקוח'), _r('תאריך'), _r('קבלה #')]]
    for r in inc_data['records']:
        inc_rows.append([
            f'₪{r["amount"]:,.0f}',
            _r(r['description'][:30]),
            _r(r['client_name'][:20]),
            _fmt(r['date']),
            r['receipt_number']
        ])
    inc_rows.append(['', '', '', _r('סה"כ:'), f'₪{inc_data["total"]:,.2f}'])

    inc_table = Table(inc_rows, colWidths=[28*mm, 55*mm, 40*mm, 27*mm, 22*mm])
    inc_table.setStyle(_income_style())
    story.append(inc_table)
    story.append(Spacer(1, 6*mm))

    # ── טבלת הוצאות ────────────────────────────────────
    story.append(Paragraph(_r('הוצאות'), _s('sec2', bold=True, size=13,
                 color=RED, space_after=3)))

    exp_rows = [[_r('סכום'), _r('קטגוריה'), _r('תיאור'), _r('תאריך')]]
    for r in exp_data['records']:
        exp_rows.append([
            f'₪{r["amount"]:,.0f}',
            _r(r['category']),
            _r(r['description'][:35]),
            _fmt(r['date'])
        ])
    exp_rows.append(['', '', _r('סה"כ:'), f'₪{exp_data["total"]:,.2f}'])

    exp_table = Table(exp_rows, colWidths=[28*mm, 40*mm, 72*mm, 28*mm])
    exp_table.setStyle(_expense_style())
    story.append(exp_table)
    story.append(Spacer(1, 6*mm))

    # ── הוצאות לפי קטגוריה ─────────────────────────────
    if exp_data['by_category']:
        story.append(Paragraph(_r('הוצאות לפי קטגוריה'), _s('sec3', bold=True, size=11,
                     color=PRIMARY, space_after=3)))
        cat_rows = [[_r('אחוז'), _r('סכום'), _r('קטגוריה')]]
        total_exp = exp_data['total'] or 1
        for cat, amt in sorted(exp_data['by_category'].items(),
                               key=lambda x: -x[1]):
            pct = amt / total_exp * 100
            cat_rows.append([f'{pct:.1f}%', f'₪{amt:,.0f}', _r(cat)])
        cat_table = Table(cat_rows, colWidths=[25*mm, 40*mm, 60*mm])
        cat_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 6*mm))

    # ── הצהרה ───────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=4))
    story.append(Paragraph(
        _r(f'דוח זה הופק אוטומטית ביום {datetime.now().strftime("%d/%m/%Y")} '
           f'| עוסק פטור ממע"מ | לצרכי מעקב עצמי בלבד'),
        _s('foot', size=8, align=TA_CENTER, color=colors.HexColor('#AAAAAA'), space_after=0)
    ))

    doc.build(story)
    return filepath


def _income_style():
    return TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 10),
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F5E9')),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ])


def _expense_style():
    return TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 10),
        ('BACKGROUND', (0, 0), (-1, 0), RED),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFEBEE')),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ])


def _fmt(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%y')
    except Exception:
        return date_str
