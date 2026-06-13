"""
scheduler.py - תזכורות אוטומטיות למועדי דיווח מס
"""
import os
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client as TwilioClient

TWILIO_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
OWNER_PHONE = os.environ.get('OWNER_PHONE', '')  # מספר הטלפון שלך עם קידומת בינ"ל


def send_reminder(message: str):
    """שולח הודעת וואטסאפ לבעל העסק."""
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_WHATSAPP_NUMBER, OWNER_PHONE]):
        print(f'[REMINDER] {message}')
        return
    try:
        client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}',
            to=f'whatsapp:{OWNER_PHONE}',
            body=message
        )
        print(f'[REMINDER SENT] {message[:50]}...')
    except Exception as e:
        print(f'[REMINDER ERROR] {e}')


def check_vat_deadlines():
    """בודק מועדי דיווח מע"מ ושולח תזכורת 7 ימים לפני."""
    today = date.today()
    year = today.year

    # מועדי הגשה דו-חודשיים (עוסק פטור עם מחזור מעל 18,000₪)
    deadlines = [
        date(year, 1, 31),
        date(year, 3, 31),
        date(year, 5, 31),
        date(year, 7, 31),
        date(year, 9, 30),
        date(year, 11, 30),
    ]

    for deadline in deadlines:
        days_left = (deadline - today).days
        if days_left == 7:
            send_reminder(
                f'📅 *תזכורת דיווח מע"מ*\n\n'
                f'עוד 7 ימים ({deadline.strftime("%d/%m/%Y")}) הגשת דו"ח מע"מ.\n'
                f'שלח "3" לסיכום הכנסות/הוצאות לתקופה.'
            )
        elif days_left == 1:
            send_reminder(
                f'⚠️ *מחר מועד הגשת דו"ח מע"מ!*\n'
                f'תאריך: {deadline.strftime("%d/%m/%Y")}\n'
                f'שלח "4" לדוח שנתי.'
            )


def check_annual_tax_deadline():
    """תזכורת לדוח השנתי - 30 אפריל."""
    today = date.today()
    deadline = date(today.year, 4, 30)
    days_left = (deadline - today).days

    if days_left == 30:
        send_reminder(
            f'📌 *תזכורת: דו"ח שנתי לרשות המסים*\n\n'
            f'עוד 30 ימים ({deadline.strftime("%d/%m/%Y")}) — '
            f'מועד הגשת הדוח השנתי!\n\n'
            f'שלח "4" לקבלת הדוח השנתי שלך.'
        )
    elif days_left == 7:
        send_reminder(
            f'⚠️ *עוד 7 ימים לדו"ח השנתי!*\n'
            f'שלח "4" עכשיו לקבלת הדוח.'
        )
    elif days_left == 1:
        send_reminder(
            f'🚨 *מחר המועד האחרון לדו"ח שנתי!*\n'
            f'שלח "4" מיד!'
        )


def monthly_summary_reminder():
    """תזכורת חודשית - ב-1 לכל חודש."""
    today = date.today()
    prev_month = today.month - 1 if today.month > 1 else 12
    months_heb = ['', 'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
                   'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']
    send_reminder(
        f'📊 *תזכורת חודשית*\n\n'
        f'חודש {months_heb[prev_month]} הסתיים!\n'
        f'שלח "5" לסיכום חודשי ו-"3" לסיכום שנתי.'
    )


def setup_scheduler():
    """מגדיר את כל התזכורות האוטומטיות."""
    scheduler = BackgroundScheduler(timezone='Asia/Jerusalem')

    # בדיקת מועדי מע"מ - כל יום ב-09:00
    scheduler.add_job(check_vat_deadlines, 'cron', hour=9, minute=0)

    # בדיקת דוח שנתי - כל יום ב-09:05 (מרץ-אפריל)
    scheduler.add_job(check_annual_tax_deadline, 'cron',
                      month='3,4', hour=9, minute=5)

    # סיכום חודשי - ב-1 לכל חודש ב-10:00
    scheduler.add_job(monthly_summary_reminder, 'cron',
                      day=1, hour=10, minute=0)

    scheduler.start()
    print('✅ מתזמן תזכורות הופעל')
    return scheduler
