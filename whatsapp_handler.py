"""
whatsapp_handler.py - לוגיקת שיחת וואטסאפ
מנהל את כל ההודעות הנכנסות, מצבי השיחה, ופקודות המשתמש
"""
import os
import json
from datetime import datetime, date
from twilio.rest import Client as TwilioClient

import models
import ai_processor
import receipt_generator
import report_generator
import document_generator

TWILIO_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')

# מיפוי מצבים ל-"מצב הקודם" + שאלה לחזרה
_BACK_MAP = {
    'receipt_description': ('receipt_client',    '👤 מה שם הלקוח?'),
    'receipt_amount':      ('receipt_description','💼 מה השירות שניתן?\n(לדוגמה: "טיפול פנים מלא")'),
    'expense_amount':      ('expense_description','📝 מה ההוצאה?'),
    'expense_category':    ('expense_amount',     '💰 כמה עלה? (בש"ח)'),
    'doc_items':           ('doc_client',         '👤 לאיזה לקוח?'),
}


class WhatsAppHandler:

    def __init__(self):
        models.init_db()
        self.twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None

    # ─── נקודת כניסה ───────────────────────────────────

    def process_message(self, sender: str, message: str,
                        media_url: str = None, media_type: str = None) -> str:
        """מנתב הודעה נכנסת לפי הקשר השיחה."""

        # הגדרה ראשונית של פרטי העסק
        if not models.is_business_setup():
            return self._handle_setup(sender, message)

        state, data = models.get_state(sender)

        # תמונה נכנסת
        if media_url and media_type and 'image' in media_type:
            return self._handle_image(sender, media_url, state, data)

        msg = message.strip()

        # ─── פקודות מהירות (עובדות בכל מצב) ──────────
        if msg in ['ביטול', 'cancel', '❌']:
            models.clear_state(sender)
            return '✅ הפעולה בוטלה. מה תרצה לעשות?\n\n' + self._menu()

        if msg in ['עזרה', 'help', '?', '❓', 'תפריט', 'menu']:
            models.clear_state(sender)
            return self._menu()

        # איפוס שיחה
        if msg in ['איפוס', 'reset', '🔄', '0']:
            models.clear_state(sender)
            return '🔄 *השיחה אופסה.*\n\n' + self._menu()

        # חזרה שלב אחד
        if msg in ['חזור', 'back', '⬅️']:
            return self._handle_back(sender, state, data)

        # תיקון הרישום האחרון
        if msg in ['תיקון', 'עדכן', '✏️']:
            return self._handle_edit_last(sender)

        # ─── ניהול מצבי שיחה ────────────────────────────

        # קבלה
        if state == 'receipt_client':
            return self._receipt_got_client(sender, msg, data)
        if state == 'receipt_description':
            return self._receipt_got_description(sender, msg, data)
        if state == 'receipt_amount':
            return self._receipt_got_amount(sender, msg, data)

        # הוצאה
        if state == 'expense_description':
            return self._expense_got_description(sender, msg, data)
        if state == 'expense_amount':
            return self._expense_got_amount(sender, msg, data)
        if state == 'expense_category':
            return self._expense_got_category(sender, msg, data)

        # מסמכים
        if state == 'doc_client':
            return self._doc_got_client(sender, msg, data)
        if state == 'doc_items':
            return self._doc_got_items(sender, msg, data)
        if state == 'doc_notes':
            return self._doc_got_notes(sender, msg, data)

        # קטלוג
        if state == 'catalog_add_name':
            return self._catalog_got_name(sender, msg, data)
        if state == 'catalog_add_price':
            return self._catalog_got_price(sender, msg, data)
        if state == 'catalog_edit':
            return self._catalog_got_edit(sender, msg, data)

        # תיקון קבלה
        if state == 'edit_last':
            return self._edit_got_field(sender, msg, data)
        if state == 'edit_field_value':
            return self._edit_got_value(sender, msg, data)

        # ─── פקודות מספריות מהתפריט ─────────────────────
        if msg == '1':
            return self._start_receipt(sender)
        if msg == '2':
            return self._start_expense(sender)
        if msg == '3':
            return self._show_summary(sender)
        if msg == '4':
            return self._annual_report(sender)
        if msg == '5':
            return self._monthly_report(sender)
        if msg == '6':
            return self._show_tax_reminders()
        if msg == '7':
            return self._show_business_info(sender)
        if msg == '8':
            return self._show_catalog(sender)
        if msg == '9':
            return self._start_quote(sender)
        if msg == '10':
            return self._start_payment_request(sender)

        # פקודות קטלוג מהירות
        catalog_response = self._handle_catalog_command(sender, msg)
        if catalog_response:
            return catalog_response

        # ניסיון להבין כוונה חופשית
        intent = ai_processor.understand_intent(msg)
        if intent == 'new_receipt':
            parsed = ai_processor.parse_receipt_command(msg)
            if parsed.get('client_name') and parsed.get('amount') and parsed.get('description'):
                return self._create_receipt_direct(sender, parsed)
            return self._start_receipt(sender)

        if intent == 'new_expense':
            parsed = ai_processor.parse_expense_command(msg)
            if parsed.get('description') and parsed.get('amount'):
                return self._create_expense_direct(sender, parsed)
            return self._start_expense(sender)

        if intent == 'summary':
            return self._show_summary(sender)
        if intent == 'annual_report':
            return self._annual_report(sender)
        if intent == 'monthly_report':
            return self._monthly_report(sender)
        if intent == 'help':
            return self._menu()

        # ברירת מחדל
        return 'שלום! 👋\n\n' + self._menu()

    # ─── הגדרת עסק ─────────────────────────────────────

    def _handle_setup(self, phone: str, message: str) -> str:
        state, data = models.get_state(phone)

        if state == 'idle':
            models.set_state(phone, 'setup_name', {})
            return (
                '👋 *ברוך הבא לסוכן רואה החשבון שלך!*\n\n'
                'בואו נגדיר את פרטי העסק שלך.\n'
                'אלה ייופיעו על כל קבלה שתוציא.\n\n'
                '📝 *מה שם העסק שלך?*\n'
                '(לדוגמה: "שרה כהן - טיפולי יופי")'
            )

        if state == 'setup_name':
            data['name'] = message
            models.set_state(phone, 'setup_address', data)
            return '✅ מעולה!\n\n📍 *מה הכתובת שלך?*\n(רחוב, עיר)'

        if state == 'setup_address':
            data['address'] = message
            models.set_state(phone, 'setup_phone', data)
            return '✅ \n\n📞 *מה מספר הטלפון שלך?*\n(יופיע על הקבלות)'

        if state == 'setup_phone':
            data['phone'] = message
            models.set_state(phone, 'setup_id', data)
            return '✅\n\n🪪 *מה מספר הזהות שלך?*\n(ת.ז. לעוסק יחיד / ח.פ. לחברה)'

        if state == 'setup_id':
            data['id_number'] = message
            models.set_state(phone, 'setup_email', data)
            return '✅\n\n📧 *מה האימייל שלך?* (אופציונלי, שלח "דלג" לדילוג)'

        if state == 'setup_email':
            if message.lower() not in ('דלג', 'skip', '-'):
                data['email'] = message
            for key, val in data.items():
                models.set_business_info(key, val)
            models.clear_state(phone)
            return (
                '🎉 *הגדרת העסק הושלמה בהצלחה!*\n\n'
                f'🏢 שם: {data.get("name", "")}\n'
                f'📍 כתובת: {data.get("address", "")}\n'
                f'📞 טלפון: {data.get("phone", "")}\n\n'
                'עכשיו אתה מוכן להתחיל!\n\n' + self._menu()
            )

        return 'שגיאה בהגדרה. נסה שוב.'

    # ─── תפריט ─────────────────────────────────────────

    def _menu(self) -> str:
        return (
            '*📋 מה אפשר לעשות?*\n\n'
            '1️⃣ הוצאת קבלה ללקוח\n'
            '2️⃣ רישום הוצאה\n'
            '3️⃣ סיכום הכנסות/הוצאות\n'
            '4️⃣ דוח שנתי לרשות המסים\n'
            '5️⃣ דוח חודשי\n'
            '6️⃣ תזכורות ומועדי דיווח\n'
            '7️⃣ פרטי העסק שלי\n'
            '8️⃣ קטלוג שירותים ומחירים\n'
            '9️⃣ הצעת מחיר\n'
            '🔟 דרישת תשלום\n\n'
            '📸 *שלח תמונה של קבלה להוצאה אוטומטית*\n'
            '💬 *אפשר גם לכתוב בחופשי:* "קבלה לדנה לוי על טיפול פנים 450 ש"ח"\n\n'
            '─────────────────\n'
            '🔄 *איפוס* — מאפס את השיחה\n'
            '✏️ *תיקון* — עורך את הרישום האחרון\n'
            '⬅️ *חזור* — חוזר שלב אחד אחורה\n'
            '❌ *ביטול* — מבטל פעולה נוכחית'
        )

    # ─── קבלה ─────────────────────────────────────────

    def _start_receipt(self, phone: str) -> str:
        models.set_state(phone, 'receipt_client', {})
        return '🧾 *הוצאת קבלה*\n\n👤 מה שם הלקוח?\n\n_שלח "ביטול" לביטול_'

    def _receipt_got_client(self, phone: str, msg: str, data: dict) -> str:
        data['client_name'] = msg
        models.set_state(phone, 'receipt_description', data)
        return f'✅ לקוח: *{msg}*\n\n💼 מה השירות שניתן?\n(לדוגמה: "טיפול פנים מלא", "צביעת שיער")'

    def _receipt_got_description(self, phone: str, msg: str, data: dict) -> str:
        data['description'] = msg
        models.set_state(phone, 'receipt_amount', data)
        return f'✅ שירות: *{msg}*\n\n💰 מה הסכום? (בש"ח)'

    def _receipt_got_amount(self, phone: str, msg: str, data: dict) -> str:
        amount = _parse_amount(msg)
        if amount is None:
            return '❗ לא הצלחתי לקרוא את הסכום. נסה שוב (לדוגמה: 450 או 350.50)'
        data['amount'] = amount
        models.clear_state(phone)
        return self._finalize_receipt(phone, data)

    def _create_receipt_direct(self, phone: str, parsed: dict) -> str:
        return self._finalize_receipt(phone, parsed)

    def _finalize_receipt(self, phone: str, data: dict) -> str:
        try:
            business_info = models.get_all_business_info()
            record = models.add_income(
                client_name=data['client_name'],
                description=data['description'],
                amount=float(data['amount']),
                date=data.get('date', datetime.now().strftime('%Y-%m-%d'))
            )

            pdf_path = receipt_generator.generate_receipt(
                receipt_number=record['receipt_number'],
                date=record['date'],
                client_name=record['client_name'],
                description=record['description'],
                amount=record['amount'],
                business_info=business_info
            )

            conn = models.get_conn()
            conn.execute('UPDATE income SET pdf_path = ? WHERE id = ?',
                         (pdf_path, record['id']))
            conn.commit()
            conn.close()

            try:
                img_path = receipt_generator.pdf_to_image(pdf_path)
                img_url = f'{APP_URL}/receipts/{os.path.basename(img_path)}'
                self._send_media(
                    phone, img_url,
                    f'📸 תמונה להעברה ללקוח — קבלה #{record["receipt_number"]}'
                )
            except Exception as img_err:
                print(f'[IMG] שגיאה בהמרה לתמונה: {img_err}')

            pdf_url = f'{APP_URL}/receipts/{os.path.basename(pdf_path)}'
            self._send_media(
                phone, pdf_url,
                f'📄 PDF לארכיון — קבלה #{record["receipt_number"]}'
            )

            return (
                f'✅ *קבלה הופקה!*\n\n'
                f'🔖 מספר: {record["receipt_number"]}\n'
                f'👤 לקוח: {record["client_name"]}\n'
                f'💼 שירות: {record["description"]}\n'
                f'💰 סכום: ₪{record["amount"]:,.0f}\n'
                f'📅 תאריך: {_fmt_date(record["date"])}\n\n'
                f'📸 תמונה — העבר ישירות ללקוח\n'
                f'📄 PDF — שמור לארכיון\n\n'
                f'_שלח "תיקון" אם יש טעות_'
            )
        except Exception as e:
            return f'❌ שגיאה ביצירת קבלה: {str(e)}'

    # ─── הוצאה ─────────────────────────────────────────

    def _start_expense(self, phone: str) -> str:
        models.set_state(phone, 'expense_description', {})
        return (
            '💸 *רישום הוצאה*\n\n'
            '📝 מה ההוצאה?\n'
            '(לדוגמה: "קרם לטיפולים", "שכירות משרד")\n\n'
            '💡 *טיפ:* אפשר גם לשלוח תמונה של הקבלה!'
        )

    def _expense_got_description(self, phone: str, msg: str, data: dict) -> str:
        data['description'] = msg
        models.set_state(phone, 'expense_amount', data)
        return f'✅ הוצאה: *{msg}*\n\n💰 כמה עלה? (בש"ח)'

    def _expense_got_amount(self, phone: str, msg: str, data: dict) -> str:
        amount = _parse_amount(msg)
        if amount is None:
            return '❗ לא הצלחתי לקרוא את הסכום. נסה שוב.'
        data['amount'] = amount
        models.set_state(phone, 'expense_category', data)

        cats = '\n'.join(f'{i+1}. {c}' for i, c in
                         enumerate(ai_processor.EXPENSE_CATEGORIES))
        return f'✅ סכום: *₪{amount:,.0f}*\n\n🏷️ *בחר קטגוריה:*\n{cats}'

    def _expense_got_category(self, phone: str, msg: str, data: dict) -> str:
        cats = ai_processor.EXPENSE_CATEGORIES
        category = 'כללי'
        if msg.isdigit():
            idx = int(msg) - 1
            if 0 <= idx < len(cats):
                category = cats[idx]
        else:
            for c in cats:
                if msg in c or c in msg:
                    category = c
                    break
        data['category'] = category
        models.clear_state(phone)
        return self._finalize_expense(phone, data)

    def _create_expense_direct(self, phone: str, parsed: dict) -> str:
        return self._finalize_expense(phone, parsed)

    def _finalize_expense(self, phone: str, data: dict) -> str:
        try:
            record = models.add_expense(
                description=data['description'],
                amount=float(data['amount']),
                category=data.get('category', 'כללי'),
                date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
                notes=data.get('notes', '')
            )
            return (
                f'✅ *הוצאה נרשמה!*\n\n'
                f'📝 {record["description"]}\n'
                f'💰 ₪{record["amount"]:,.0f}\n'
                f'🏷️ {record["category"]}\n'
                f'📅 {_fmt_date(record["date"])}'
            )
        except Exception as e:
            return f'❌ שגיאה ברישום הוצאה: {str(e)}'

    # ─── עיבוד תמונה ───────────────────────────────────

    def _handle_image(self, phone: str, media_url: str,
                      state: str, data: dict) -> str:
        extracted = ai_processor.extract_expense_from_image(
            image_url=media_url,
            twilio_sid=TWILIO_SID,
            twilio_token=TWILIO_TOKEN
        )

        if extracted.get('error'):
            return f'❌ {extracted["error"]}\n\nנסה שוב או הכנס את הפרטים ידנית.'

        amount = extracted.get('amount')
        desc = extracted.get('description') or extracted.get('vendor', 'קניה')
        exp_date = extracted.get('date', datetime.now().strftime('%Y-%m-%d'))
        category = extracted.get('category', 'כללי')
        confidence = extracted.get('confidence', 'medium')

        conf_emoji = {'high': '✅', 'medium': '⚠️', 'low': '❓'}.get(confidence, '⚠️')

        if not amount:
            models.set_state(phone, 'expense_amount', {
                'description': desc,
                'category': category,
                'date': exp_date
            })
            return (
                f'📸 *זיהיתי קבלה!*\n\n'
                f'{conf_emoji} ספק: {desc}\n'
                f'📅 תאריך: {_fmt_date(exp_date)}\n'
                f'🏷️ קטגוריה: {category}\n\n'
                f'❓ לא הצלחתי לקרוא את הסכום.\n*כמה עלה?* (בש"ח)'
            )

        record = models.add_expense(
            description=desc,
            amount=float(amount),
            category=category,
            date=exp_date
        )

        return (
            f'📸 *קבלה זוהתה ונרשמה!* {conf_emoji}\n\n'
            f'📝 {record["description"]}\n'
            f'💰 ₪{record["amount"]:,.0f}\n'
            f'🏷️ {record["category"]}\n'
            f'📅 {_fmt_date(record["date"])}\n\n'
            f'{"⚠️ שים לב: רמת הוודאות בינונית, בדוק שהפרטים נכונים" if confidence != "high" else ""}'
        ).strip()

    # ─── דוחות ─────────────────────────────────────────

    def _show_summary(self, phone: str) -> str:
        year = datetime.now().year
        inc = models.get_income_summary(year=year)
        exp = models.get_expense_summary(year=year)
        profit = inc['total'] - exp['total']

        EXEMPT_THRESHOLD = 120_000
        threshold_pct = (inc['total'] / EXEMPT_THRESHOLD * 100) if inc['total'] else 0

        bar = _progress_bar(min(threshold_pct, 100))
        profit_emoji = '💰' if profit >= 0 else '⚠️'
        threshold_warning = '⚠️ *קרוב לרף!* שקול מעבר לעוסק מורשה' if threshold_pct > 80 else ''

        return (
            f'📊 *סיכום {year}*\n'
            f'──────────────────\n'
            f'💚 הכנסות: ₪{inc["total"]:,.0f} ({inc["count"]} קבלות)\n'
            f'🔴 הוצאות: ₪{exp["total"]:,.0f} ({exp["count"]} פריטים)\n'
            f'──────────────────\n'
            f'{profit_emoji} רווח: ₪{profit:,.0f}\n\n'
            f'📈 *רף עוסק פטור* (₪{EXEMPT_THRESHOLD:,})\n'
            f'{bar} {threshold_pct:.0f}%\n'
            f'{threshold_warning}\n\n'
            f'_לדוח מפורט שלח: 4 (שנתי) או 5 (חודשי)_'
        ).strip()

    def _annual_report(self, phone: str) -> str:
        year = datetime.now().year
        try:
            business_info = models.get_all_business_info()
            pdf_path = report_generator.generate_annual_report(year, business_info)
            pdf_url = f'{APP_URL}/reports/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url, f'דוח שנתי {year}')
            inc = models.get_income_summary(year=year)
            exp = models.get_expense_summary(year=year)
            return (
                f'📑 *דוח שנתי {year} נשלח!*\n\n'
                f'💚 סה"כ הכנסות: ₪{inc["total"]:,.0f}\n'
                f'🔴 סה"כ הוצאות: ₪{exp["total"]:,.0f}\n'
                f'💰 רווח נקי: ₪{inc["total"] - exp["total"]:,.0f}\n\n'
                f'📄 הדוח ב-PDF מוכן להגשה!'
            )
        except Exception as e:
            return f'❌ שגיאה ביצירת דוח: {str(e)}'

    def _monthly_report(self, phone: str) -> str:
        year = datetime.now().year
        month = datetime.now().month
        month_name = _month_heb(month)
        inc = models.get_income_summary(year=year, month=month)
        exp = models.get_expense_summary(year=year, month=month)

        exp_by_cat = '\n'.join(
            f'  • {cat}: ₪{amt:,.0f}'
            for cat, amt in exp['by_category'].items()
        ) if exp['by_category'] else '  אין הוצאות החודש'

        return (
            f'📅 *דוח {month_name} {year}*\n'
            f'──────────────────\n'
            f'💚 הכנסות: ₪{inc["total"]:,.0f}\n'
            f'🔴 הוצאות: ₪{exp["total"]:,.0f}\n'
            f'💰 רווח: ₪{inc["total"] - exp["total"]:,.0f}\n\n'
            f'*הוצאות לפי קטגוריה:*\n{exp_by_cat}'
        )

    def _show_tax_reminders(self) -> str:
        today = date.today()
        year = today.year

        reminders = [
            ('31/01', 'דו"ח מקדמות מע"מ - ינואר-פברואר'),
            ('31/03', 'דו"ח מקדמות מע"מ - ינואר-פברואר (הגשה מאוחרת)'),
            ('30/04', f'📌 דו"ח שנתי לרשות המסים ({year-1})'),
            ('31/05', 'דו"ח מקדמות מע"מ - מרץ-אפריל'),
            ('31/07', 'דו"ח מקדמות מע"מ - מאי-יוני'),
            ('30/09', 'דו"ח מקדמות מע"מ - יולי-אוגוסט'),
            ('30/11', 'דו"ח מקדמות מע"מ - ספטמבר-אוקטובר'),
        ]

        return (
            f'📅 *מועדי דיווח {year}*\n\n'
            ''.join(f'🗓️ {d} - {r}\n' for d, r in reminders) +
            f'\n⚠️ *עוסק פטור* אינו גובה מע"מ אך חייב\n'
            f'לדווח לרשות המסים אחת לשנה.\n\n'
            f'💡 אם ההכנסה עולה על ₪120,000 בשנה —\n'
            f'חובה לעבור לעוסק מורשה!'
        )

    def _show_business_info(self, phone: str) -> str:
        info = models.get_all_business_info()
        if not info:
            return 'לא נמצאו פרטי עסק. שלח "עזרה" להתחלה.'
        return (
            f'🏢 *פרטי העסק שלי*\n\n'
            f'📛 שם: {info.get("name", "-")}\n'
            f'📍 כתובת: {info.get("address", "-")}\n'
            f'📞 טלפון: {info.get("phone", "-")}\n'
            f'🪪 ת.ז./ח.פ.: {info.get("id_number", "-")}\n'
            f'📧 אימייל: {info.get("email", "-")}\n\n'
            f'_לשינוי פרטים שלח "עדכן פרטים"_'
        )

    # ─── קטלוג שירותים ─────────────────────────────────

    def _show_catalog(self, phone: str) -> str:
        services = models.get_services()
        if not services:
            return (
                '📋 *קטלוג שירותים ריק*\n\n'
                'כדי להוסיף שירות שלח:\n'
                '"הוסף שירות: [שם] [מחיר]"\n\n'
                'לדוגמה:\n'
                '"הוסף שירות: טיפול פנים מלא 350"\n'
                '"הוסף שירות: עיסוי גב 200"'
            )
        lines = ['📋 *השירותים שלך:*\n']
        for s in services:
            lines.append(f'{s["id"]}. {s["name"]} — ₪{s["price"]:,.0f}')
        lines.append('\n*פקודות:*')
        lines.append('✏️ שלח "ערוך [מספר] [מחיר חדש]" לשינוי מחיר')
        lines.append('❌ שלח "מחק [מספר]" להסרת שירות')
        lines.append('➕ שלח "הוסף שירות: [שם] [מחיר]"')
        return '\n'.join(lines)

    def _start_add_service(self, phone: str) -> str:
        models.set_state(phone, 'catalog_add_name', {})
        return '➕ *הוספת שירות חדש*\n\nמה שם השירות?'

    def _catalog_got_name(self, phone: str, msg: str, data: dict) -> str:
        data['name'] = msg
        models.set_state(phone, 'catalog_add_price', data)
        return f'✅ שירות: *{msg}*\n\n💰 מה המחיר? (בש"ח)'

    def _catalog_got_price(self, phone: str, msg: str, data: dict) -> str:
        price = _parse_amount(msg)
        if price is None:
            return '❗ מחיר לא תקין. נסה שוב (לדוגמה: 350)'
        service = models.add_service(data['name'], price)
        models.clear_state(phone)
        return (
            f'✅ *שירות נוסף לקטלוג!*\n\n'
            f'📌 {service["name"]} — ₪{service["price"]:,.0f}\n\n'
            f'שלח "8" לצפייה בקטלוג המלא.'
        )

    def _catalog_got_edit(self, phone: str, msg: str, data: dict) -> str:
        price = _parse_amount(msg)
        if price is None:
            return '❗ מחיר לא תקין.'
        models.update_service_price(data['service_id'], price)
        models.clear_state(phone)
        return f'✅ מחיר עודכן ל-₪{price:,.0f}'

    def _handle_catalog_command(self, phone: str, msg: str) -> str | None:
        """מטפל בפקודות קטלוג מהירות: הוסף שירות, ערוך, מחק."""

        if msg.startswith('הוסף שירות:') or msg.startswith('הוסף שירות '):
            rest = msg.replace('הוסף שירות:', '').replace('הוסף שירות', '').strip()
            parts = rest.rsplit(' ', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                price = _parse_amount(parts[1])
                if name and price:
                    service = models.add_service(name, price)
                    return f'✅ *{service["name"]}* נוסף בקטלוג — ₪{service["price"]:,.0f}'
            return self._start_add_service(phone)

        if msg.startswith('ערוך '):
            parts = msg.split()
            if len(parts) >= 3:
                try:
                    sid = int(parts[1])
                    price = _parse_amount(parts[2])
                    if price:
                        models.update_service_price(sid, price)
                        return f'✅ מחיר עודכן ל-₪{price:,.0f}'
                except Exception:
                    pass
            models.set_state(phone, 'catalog_edit', {
                'service_id': int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            })
            return '💰 מה המחיר החדש?'

        if msg.startswith('מחק ') and msg.split()[1].isdigit():
            sid = int(msg.split()[1])
            svc = models.get_service(sid)
            if svc:
                models.delete_service(sid)
                return f'🗑️ "{svc["name"]}" הוסר מהקטלוג.'
            return '❗ שירות לא נמצא.'

        return None

    # ─── הצעת מחיר / דרישת תשלום ────────────────────────

    def _start_quote(self, phone: str) -> str:
        return self._start_document(phone, 'quote')

    def _start_payment_request(self, phone: str) -> str:
        return self._start_document(phone, 'payment_request')

    def _start_document(self, phone: str, doc_type: str) -> str:
        doc_names = {
            'quote': 'הצעת מחיר',
            'payment_request': 'דרישת תשלום'
        }
        models.set_state(phone, 'doc_client', {'doc_type': doc_type})
        return f'📄 *{doc_names[doc_type]}*\n\n👤 לאיזה לקוח?'

    def _doc_got_client(self, phone: str, msg: str, data: dict) -> str:
        data['client_name'] = msg
        data['items'] = []
        models.set_state(phone, 'doc_items', data)
        return self._show_service_picker(data)

    def _show_service_picker(self, data: dict) -> str:
        services = models.get_services()
        items_so_far = data.get('items', [])

        lines = ['🛍️ *בחר שירותים:*\n']
        if services:
            for s in services:
                lines.append(f'{s["id"]}. {s["name"]} — ₪{s["price"]:,.0f}')
            lines.append('\nשלח מספרי שירותים מופרדים בפסיק: "1, 3"')
            lines.append('או כתוב שירות מיוחד: "שירות מיוחד 500"')
        else:
            lines.append('אין שירותים בקטלוג עדיין.')
            lines.append('כתוב שירות ומחיר: "שם שירות 350"')

        if items_so_far:
            lines.append(f'\n✅ *נבחרו כבר:*')
            for item in items_so_far:
                lines.append(f'• {item["name"]} — ₪{item["total"]:,.0f}')
            lines.append('\nשלח "סיום" לסיום הבחירה')
        else:
            lines.append('\nשלח "סיום" אחרי הבחירה')

        return '\n'.join(lines)

    def _doc_got_items(self, phone: str, msg: str, data: dict) -> str:
        if msg.strip() in ('סיום', 'done', 'finish'):
            if not data.get('items'):
                return '❗ לא נבחרו שירותים. בחר לפחות אחד.'
            models.set_state(phone, 'doc_notes', data)
            total = sum(i['total'] for i in data['items'])
            lines = [f'✅ *נבחרו {len(data["items"])} שירותים*']
            for item in data['items']:
                lines.append(f'• {item["name"]} — ₪{item["total"]:,.0f}')
            lines.append(f'\n💰 סה"כ: ₪{total:,.0f}')
            lines.append('\n📝 הערות? (או שלח "דלג")')
            return '\n'.join(lines)

        services = models.get_services()
        svc_map = {str(s['id']): s for s in services}
        added = []

        parts = [p.strip() for p in msg.replace('،', ',').split(',')]
        for part in parts:
            if part in svc_map:
                s = svc_map[part]
                data['items'].append({
                    'name': s['name'],
                    'quantity': 1,
                    'unit_price': s['price'],
                    'total': s['price']
                })
                added.append(s['name'])
            else:
                words = part.rsplit(' ', 1)
                if len(words) == 2:
                    price = _parse_amount(words[1])
                    if price:
                        data['items'].append({
                            'name': words[0].strip(),
                            'quantity': 1,
                            'unit_price': price,
                            'total': price
                        })
                        added.append(words[0].strip())

        models.set_state(phone, 'doc_items', data)

        if added:
            return (
                f'✅ נוסף: {", ".join(added)}\n\n'
                + self._show_service_picker(data)
            )
        return '❗ לא הבנתי. שלח מספר שירות או "שם שירות מחיר".'

    def _doc_got_notes(self, phone: str, msg: str, data: dict) -> str:
        if msg.lower() not in ('דלג', 'skip', '-', ''):
            data['notes'] = msg
        models.clear_state(phone)
        return self._finalize_document(phone, data)

    def _finalize_document(self, phone: str, data: dict) -> str:
        doc_type = data['doc_type']
        doc_names = {
            'quote': 'הצעת מחיר',
            'payment_request': 'דרישת תשלום'
        }
        try:
            from datetime import timedelta
            business_info = models.get_all_business_info()

            valid_until = ''
            if doc_type == 'quote':
                from datetime import date
                valid_until = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')

            record = models.add_document(
                doc_type=doc_type,
                client_name=data['client_name'],
                items=data['items'],
                notes=data.get('notes', ''),
                valid_until=valid_until,
                client_phone=data.get('client_phone', '')
            )

            pdf_path = document_generator.generate_document(
                doc_type=doc_type,
                doc_number=record['doc_number'],
                date=record['date'],
                client_name=record['client_name'],
                items=data['items'],
                business_info=business_info,
                notes=record['notes'],
                valid_until=valid_until
            )

            try:
                img_path = document_generator.pdf_to_image(pdf_path)
                img_url = f'{APP_URL}/documents/{os.path.basename(img_path)}'
                self._send_media(phone, img_url,
                                 f'📸 {doc_names[doc_type]} — {record["doc_number"]}')
            except Exception:
                pass

            pdf_url = f'{APP_URL}/documents/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url,
                             f'📄 {doc_names[doc_type]} — {record["doc_number"]}')

            total = sum(i['total'] for i in data['items'])
            items_text = '\n'.join(f'• {i["name"]} ₪{i["total"]:,.0f}' for i in data['items'])

            return (
                f'✅ *{doc_names[doc_type]} הופקה!*\n\n'
                f'🔖 מספר: {record["doc_number"]}\n'
                f'👤 לקוח: {record["client_name"]}\n\n'
                f'{items_text}\n\n'
                f'💰 סה"כ: ₪{total:,.0f}\n\n'
                f'📸 תמונה + 📄 PDF נשלחו!'
            )
        except Exception as e:
            return f'❌ שגיאה ביצירת המסמך: {str(e)}'

    # ─── חזרה שלב אחד ──────────────────────────────────

    def _handle_back(self, phone: str, state: str, data: dict) -> str:
        """חוזר שלב אחד אחורה בכל זרימת שיחה."""
        if state in _BACK_MAP:
            prev_state, prompt = _BACK_MAP[state]
            # מנקה את השדה שהוזן בשלב הנוכחי
            fields_to_clear = {
                'receipt_description': 'client_name',
                'receipt_amount': 'description',
                'expense_amount': 'description',
                'expense_category': 'amount',
                'doc_items': 'client_name',
            }
            field = fields_to_clear.get(state)
            if field:
                data.pop(field, None)
            models.set_state(phone, prev_state, data)
            if state == 'doc_items':
                return f'⬅️ חזרנו שלב אחד.\n\n{prompt}'
            return f'⬅️ חזרנו שלב אחד.\n\n{prompt}'

        if state == 'idle':
            return self._menu()

        # כל מצב אחר — חזור לתפריט
        models.clear_state(phone)
        return '⬅️ חזרנו להתחלה.\n\n' + self._menu()

    # ─── תיקון רישום אחרון ─────────────────────────────

    def _handle_edit_last(self, phone: str) -> str:
        """מציג את הקבלה האחרונה לעריכה."""
        record = models.get_last_income()
        if not record:
            return '❗ לא נמצאו קבלות לתיקון.\n\nשלח "תפריט" להתחלה.'

        models.set_state(phone, 'edit_last', {'edit_id': record['id']})
        return (
            f'✏️ *תיקון קבלה אחרונה*\n\n'
            f'🔖 {record["receipt_number"]}\n'
            f'👤 לקוח: {record["client_name"]}\n'
            f'💼 שירות: {record["description"]}\n'
            f'💰 סכום: ₪{record["amount"]:,.0f}\n'
            f'📅 תאריך: {_fmt_date(record["date"])}\n\n'
            f'*מה לתקן?*\n'
            f'1. שם לקוח\n'
            f'2. תיאור שירות\n'
            f'3. סכום\n\n'
            f'שלח "ביטול" לחזרה'
        )

    def _edit_got_field(self, phone: str, msg: str, data: dict) -> str:
        """מקבל את בחירת השדה לתיקון."""
        field_map = {
            '1': 'client_name', 'לקוח': 'client_name', 'שם': 'client_name',
            '2': 'description',  'שירות': 'description', 'תיאור': 'description',
            '3': 'amount',       'סכום': 'amount',       'מחיר': 'amount',
        }
        field = field_map.get(msg.strip())
        if not field:
            return '❗ שלח 1, 2, או 3 לבחירת השדה לתיקון.'

        data['edit_field'] = field
        models.set_state(phone, 'edit_field_value', data)

        prompts = {
            'client_name': '👤 שם הלקוח החדש?',
            'description': '💼 תיאור השירות החדש?',
            'amount':      '💰 הסכום החדש? (בש"ח)',
        }
        return prompts[field]

    def _edit_got_value(self, phone: str, msg: str, data: dict) -> str:
        """מחיל את התיקון ומפיק קבלה מחדש."""
        field = data['edit_field']
        edit_id = data['edit_id']

        if field == 'amount':
            value = _parse_amount(msg)
            if value is None:
                return '❗ סכום לא תקין. נסה שוב (לדוגמה: 450)'
        else:
            value = msg.strip()
            if not value:
                return '❗ ערך ריק. נסה שוב.'

        models.update_income_field(edit_id, field, value)
        models.clear_state(phone)

        # הפקת קבלה מחדש
        record = models.get_income_by_id(edit_id)
        business_info = models.get_all_business_info()
        try:
            pdf_path = receipt_generator.generate_receipt(
                receipt_number=record['receipt_number'],
                date=record['date'],
                client_name=record['client_name'],
                description=record['description'],
                amount=record['amount'],
                business_info=business_info
            )
            models.update_income_field(edit_id, 'pdf_path', pdf_path)

            try:
                img_path = receipt_generator.pdf_to_image(pdf_path)
                img_url = f'{APP_URL}/receipts/{os.path.basename(img_path)}'
                self._send_media(phone, img_url,
                                 f'📸 קבלה מתוקנת #{record["receipt_number"]}')
            except Exception:
                pass

            pdf_url = f'{APP_URL}/receipts/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url,
                             f'📄 PDF מתוקן #{record["receipt_number"]}')

            field_names = {'client_name': 'שם לקוח', 'description': 'תיאור שירות', 'amount': 'סכום'}
            return (
                f'✅ *קבלה עודכנה!*\n\n'
                f'🔖 {record["receipt_number"]}\n'
                f'👤 {record["client_name"]}\n'
                f'💼 {record["description"]}\n'
                f'💰 ₪{record["amount"]:,.0f}\n\n'
                f'✏️ {field_names.get(field, field)} שונה.\n'
                f'📸 קבלה מתוקנת נשלחה!'
            )
        except Exception as e:
            return f'❌ שגיאה בעדכון: {str(e)}'

    # ─── שליחת מדיה ────────────────────────────────────

    def _send_media(self, to: str, media_url: str, caption: str = ''):
        if not self.twilio:
            print(f'[TWILIO] would send media {media_url} to {to}')
            return
        try:
            self.twilio.messages.create(
                from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}',
                to=to,
                media_url=[media_url],
                body=caption
            )
        except Exception as e:
            print(f'[TWILIO] שגיאה בשליחת מדיה: {e}')


# ─── עזרים ─────────────────────────────────────────────

def _parse_amount(text: str) -> float | None:
    """חולץ מספר מטקסט: "450 ש\"ח", "₪350.5", "200" וכו'"""
    cleaned = text.replace(',', '').replace('₪', '').replace('שח', '') \
                  .replace('ש"ח', '').replace('שקל', '').replace('שקלים', '').strip()
    try:
        return float(cleaned.split()[0])
    except Exception:
        return None


def _fmt_date(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%d/%m/%Y')
    except Exception:
        return date_str


def _progress_bar(pct: float, width: int = 10) -> str:
    filled = int(pct / 100 * width)
    return '█' * filled + '░' * (width - filled)


def _month_heb(m: int) -> str:
    months = ['', 'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
              'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']
    return months[m] if 1 <= m <= 12 else str(m)
