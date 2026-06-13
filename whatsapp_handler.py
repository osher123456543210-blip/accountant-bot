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
    'receipt_description': ('receipt_client',     u'מה שם הלקוח?'),
    'receipt_amount':      ('receipt_description', u'מה השירות שניתן?'),
    'expense_amount':      ('expense_description', u'מה ההוצאה?'),
    'expense_category':    ('expense_amount',      u'כמה עלה? (בש"ח)'),
    'doc_items':           ('doc_client',          u'לאיזה לקוח?'),
}


class WhatsAppHandler:

    def __init__(self):
        models.init_db()
        self.twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None

    def process_message(self, sender: str, message: str,
                        media_url: str = None, media_type: str = None) -> str:

        if not models.is_business_setup():
            return self._handle_setup(sender, message)

        state, data = models.get_state(sender)

        if media_url and media_type and 'image' in media_type:
            return self._handle_image(sender, media_url, state, data)

        msg = message.strip()

        if msg in ['ביטול', 'cancel', '❌']:
            models.clear_state(sender)
            return '✅ הפעולה בוטלה.\n\n' + self._menu()

        if msg in ['עזרה', 'help', '?', '❓', 'תפריט', 'menu']:
            models.clear_state(sender)
            return self._menu()

        if msg in ['איפוס', 'reset', '\U0001f504', '0']:
            models.clear_state(sender)
            return '\U0001f504 *השיחה אופסה.*\n\n' + self._menu()

        if msg in ['חזור', 'back', '⬅️']:
            return self._handle_back(sender, state, data)

        if msg in ['תיקון', 'עדכן', '✏️']:
            return self._handle_edit_last(sender)

        # states
        if state == 'receipt_client':
            return self._receipt_got_client(sender, msg, data)
        if state == 'receipt_description':
            return self._receipt_got_description(sender, msg, data)
        if state == 'receipt_amount':
            return self._receipt_got_amount(sender, msg, data)
        if state == 'expense_description':
            return self._expense_got_description(sender, msg, data)
        if state == 'expense_amount':
            return self._expense_got_amount(sender, msg, data)
        if state == 'expense_category':
            return self._expense_got_category(sender, msg, data)
        if state == 'doc_client':
            return self._doc_got_client(sender, msg, data)
        if state == 'doc_items':
            return self._doc_got_items(sender, msg, data)
        if state == 'doc_notes':
            return self._doc_got_notes(sender, msg, data)
        if state == 'catalog_add_name':
            return self._catalog_got_name(sender, msg, data)
        if state == 'catalog_add_price':
            return self._catalog_got_price(sender, msg, data)
        if state == 'catalog_edit':
            return self._catalog_got_edit(sender, msg, data)
        if state == 'edit_last':
            return self._edit_got_field(sender, msg, data)
        if state == 'edit_field_value':
            return self._edit_got_value(sender, msg, data)

        # menu numbers
        if msg == '1': return self._start_receipt(sender)
        if msg == '2': return self._start_expense(sender)
        if msg == '3': return self._show_summary(sender)
        if msg == '4': return self._annual_report(sender)
        if msg == '5': return self._monthly_report(sender)
        if msg == '6': return self._show_tax_reminders()
        if msg == '7': return self._show_business_info(sender)
        if msg == '8': return self._show_catalog(sender)
        if msg == '9': return self._start_quote(sender)
        if msg == '10': return self._start_payment_request(sender)

        catalog_response = self._handle_catalog_command(sender, msg)
        if catalog_response:
            return catalog_response

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
        if intent == 'summary': return self._show_summary(sender)
        if intent == 'annual_report': return self._annual_report(sender)
        if intent == 'monthly_report': return self._monthly_report(sender)
        if intent == 'help': return self._menu()

        return 'שלום! \U0001f44b\n\n' + self._menu()

    def _handle_setup(self, phone: str, message: str) -> str:
        state, data = models.get_state(phone)
        if state == 'idle':
            models.set_state(phone, 'setup_name', {})
            return ('\U0001f44b *ברוך הבא לסוכן רואה החשבון שלך!*\n\n'
                   'בואו נגדיר את פרטי העסק שלך.\n\n'
                   '\U0001f4dd *מה שם העסק שלך?*')
        if state == 'setup_name':
            data['name'] = message
            models.set_state(phone, 'setup_address', data)
            return '✅ מעולי!\n\n\U0001f4cd *מה הכתובת?*'
        if state == 'setup_address':
            data['address'] = message
            models.set_state(phone, 'setup_phone', data)
            return '✅\n\n\U0001f4de *מה מספר הטלפון?*'
        if state == 'setup_phone':
            data['phone'] = message
            models.set_state(phone, 'setup_id', data)
            return '✅\n\n\U0001fab4 *מה מספר הזהות?*'
        if state == 'setup_id':
            data['id_number'] = message
            models.set_state(phone, 'setup_email', data)
            return '✅\n\n\U0001f4e7 *מה האימייל?* (אופציונלי, שלח "דלג" לדילוג)'
        if state == 'setup_email':
            if message.lower() not in ('דלג', 'skip', '-'):
                data['email'] = message
            for key, val in data.items():
                models.set_business_info(key, val)
            models.clear_state(phone)
            return ('\U0001f389 *הגדרת העסק הושלמה!*\n\n'
                    'עכשיו אתה מוכן!\n\n' + self._menu())
        return 'שגיאה. נסה שוב.'

    def _menu(self) -> str:
        return ('*\U0001f4cb מה אפשר לעשות?*\n\n'
                '1️⃣ הוצאת קבלה\n'
                '2️⃣ רישום הוצאה\n'
                '3️⃣ סיכום\n'
                '4️⃣ דוח שנתי\n'
                '5️⃣ דוח חודשי\n'
                '6️⃣ תזכורות\n'
                '7️⃣ פרטי העסק\n'
                '8️⃣ קטלוג\n'
                '9️⃣ הצעת מחיר\n'
                '\U0001f51f דרישת תשלום\n\n'
                '\U0001f504 *איפוס* | ✏️ *תיקון* | ⬅️ *חזור* | ❌ *ביטול*')

    def _start_receipt(self, phone: str) -> str:
        models.set_state(phone, 'receipt_client', {})
        return '\U0001f9fe *הוצאת קבלה*\n\n\U0001f464 מה שם הלקוח?'

    def _receipt_got_client(self, phone: str, msg: str, data: dict) -> str:
        data['client_name'] = msg
        models.set_state(phone, 'receipt_description', data)
        return f'✅ לקוח: *{msg}*\n\n\U0001f4bc מה השירות?'

    def _receipt_got_description(self, phone: str, msg: str, data: dict) -> str:
        data['description'] = msg
        models.set_state(phone, 'receipt_amount', data)
        return f'✅ שירות: *{msg}*\n\n\U0001f4b0 מה הסכום? (בש"ח)'

    def _receipt_got_amount(self, phone: str, msg: str, data: dict) -> str:
        amount = _parse_amount(msg)
        if amount is None:
            return '❗ סכום לא תקין. נסה שוב (לדוגמה: 450)'
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
            conn.execute('UPDATE income SET pdf_path = ? WHERE id = ?', (pdf_path, record['id']))
            conn.commit()
            conn.close()
            try:
                img_path = receipt_generator.pdf_to_image(pdf_path)
                img_url = f'{APP_URL}/receipts/{os.path.basename(img_path)}'
                self._send_media(phone, img_url, f'\U0001f4f8 תמונה ללקוח — קבלה #{record["receipt_number"]}')
            except Exception as e:
                print(f'[IMG] {e}')
            pdf_url = f'{APP_URL}/receipts/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url, f'\U0001f4c4 PDF — קבלה #{record["receipt_number"]}')
            return (f'✅ *קבלה הופקה!*\n\n'
                    f'\U0001f516 {record["receipt_number"]}\n'
                    f'\U0001f464 {record["client_name"]}\n'
                    f'\U0001f4bc {record["description"]}\n'
                    f'\U0001f4b0 ₪{record["amount"]:,.0f}\n\n'
                    f'_שלח "תיקון" אם יש טעות_')
        except Exception as e:
            return f'❌ שגיאה: {str(e)}'

    def _start_expense(self, phone: str) -> str:
        models.set_state(phone, 'expense_description', {})
        return '\U0001f4b8 *רישום הוצאה*\n\n\U0001f4dd מה ההוצאה?'

    def _expense_got_description(self, phone: str, msg: str, data: dict) -> str:
        data['description'] = msg
        models.set_state(phone, 'expense_amount', data)
        return f'✅ הוצאה: *{msg}*\n\n\U0001f4b0 כמה עלה? (בש"ח)'

    def _expense_got_amount(self, phone: str, msg: str, data: dict) -> str:
        amount = _parse_amount(msg)
        if amount is None:
            return '❗ סכום לא תקין.'
        data['amount'] = amount
        models.set_state(phone, 'expense_category', data)
        cats = '\n'.join(f'{i+1}. {c}' for i, c in enumerate(ai_processor.EXPENSE_CATEGORIES))
        return f'✅ סכום: *₪{amount:,.0f}*\n\n\U0001f3f7️ *בחר קטגוריה:*\n{cats}'

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
            return (f'✅ *הוצאה נרשמה!*\n\n'
                    f'\U0001f4dd {record["description"]}\n'
                    f'\U0001f4b0 ₪{record["amount"]:,.0f}\n'
                    f'\U0001f3f7️ {record["category"]}\n'
                    f'\U0001f4c5 {_fmt_date(record["date"])}')
        except Exception as e:
            return f'❌ שגיאה: {str(e)}'

    def _handle_image(self, phone: str, media_url: str, state: str, data: dict) -> str:
        extracted = ai_processor.extract_expense_from_image(
            image_url=media_url, twilio_sid=TWILIO_SID, twilio_token=TWILIO_TOKEN)
        if extracted.get('error'):
            return f'❌ {extracted["error"]}'
        amount = extracted.get('amount')
        desc = extracted.get('description') or extracted.get('vendor', 'קניה')
        exp_date = extracted.get('date', datetime.now().strftime('%Y-%m-%d'))
        category = extracted.get('category', 'כללי')
        confidence = extracted.get('confidence', 'medium')
        conf_emoji = {'high': '✅', 'medium': '⚠️', 'low': '❓'}.get(confidence, '⚠️')
        if not amount:
            models.set_state(phone, 'expense_amount', {'description': desc, 'category': category, 'date': exp_date})
            return (f'\U0001f4f8 *זיהיתי קבלה!*\n\n{conf_emoji} {desc}\n'
                    f'❌ לא זיהיתי סכום. *כמה עלה?*')
        record = models.add_expense(description=desc, amount=float(amount), category=category, date=exp_date)
        return (f'\U0001f4f8 *קבלה נרשמה!* {conf_emoji}\n\n'
                f'\U0001f4dd {record["description"]}\n\U0001f4b0 ₪{record["amount"]:,.0f}\n'
                f'\U0001f3f7️ {record["category"]}\n\U0001f4c5 {_fmt_date(record["date"])}').strip()

    def _show_summary(self, phone: str) -> str:
        year = datetime.now().year
        inc = models.get_income_summary(year=year)
        exp = models.get_expense_summary(year=year)
        profit = inc['total'] - exp['total']
        EXEMPT_THRESHOLD = 120_000
        threshold_pct = (inc['total'] / EXEMPT_THRESHOLD * 100) if inc['total'] else 0
        bar = _progress_bar(min(threshold_pct, 100))
        profit_emoji = '\U0001f4b0' if profit >= 0 else '⚠️'
        warning = '⚠️ *קרוב לרף!*' if threshold_pct > 80 else ''
        return (f'\U0001f4ca *סיכום {year}*\n'
                f'──────────\n'
                f'\U0001f49a הכנסות: ₪{inc["total"]:,.0f} ({inc["count"]} קבלות)\n'
                f'\U0001f534 הוצאות: ₪{exp["total"]:,.0f}\n'
                f'──────────\n'
                f'{profit_emoji} רווח: ₪{profit:,.0f}\n\n'
                f'\U0001f4c8 רף (₪{EXEMPT_THRESHOLD:,})\n{bar} {threshold_pct:.0f}%\n{warning}').strip()

    def _annual_report(self, phone: str) -> str:
        year = datetime.now().year
        try:
            business_info = models.get_all_business_info()
            pdf_path = report_generator.generate_annual_report(year, business_info)
            pdf_url = f'{APP_URL}/reports/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url, f'דוח שנתי {year}')
            inc = models.get_income_summary(year=year)
            exp = models.get_expense_summary(year=year)
            return (f'\U0001f4d1 *דוח {year} נשלח!*\n\n'
                    f'\U0001f49a הכנסות: ₪{inc["total"]:,.0f}\n'
                    f'\U0001f534 הוצאות: ₪{exp["total"]:,.0f}\n'
                    f'\U0001f4b0 רווח: ₪{inc["total"]-exp["total"]:,.0f}')
        except Exception as e:
            return f'❌ שגיאה: {str(e)}'

    def _monthly_report(self, phone: str) -> str:
        year = datetime.now().year
        month = datetime.now().month
        inc = models.get_income_summary(year=year, month=month)
        exp = models.get_expense_summary(year=year, month=month)
        exp_by_cat = '\n'.join(f'  • {cat}: ₪{amt:,.0f}' for cat, amt in exp['by_category'].items()) or '  אין'
        return (f'\U0001f4c5 *דוח {_month_heb(month)} {year}*\n'
                f'\U0001f49a הכנסות: ₪{inc["total"]:,.0f}\n'
                f'\U0001f534 הוצאות: ₪{exp["total"]:,.0f}\n'
                f'\U0001f4b0 רווח: ₪{inc["total"]-exp["total"]:,.0f}\n\n'
                f'*הוצאות לפי קטגוריה:*\n{exp_by_cat}')

    def _show_tax_reminders(self) -> str:
        year = date.today().year
        reminders = [('31/01','דו"ח מקדמות מע"מ - ינואר-פברואר'),
                     ('30/04',f'\U0001f4cc דו"ח שנתי ({year-1})'),
                     ('31/07','דו"ח מקדמות מע"מ - מאי-יוני'),
                     ('30/11','דו"ח מקדמות מע"מ - ספטמבר-אוקטובר')]
        return (f'\U0001f4c5 *מועדי דיווח {year}*\n\n' +
                ''.join(f'\U0001f5d3️ {d} - {r}\n' for d, r in reminders))

    def _show_business_info(self, phone: str) -> str:
        info = models.get_all_business_info()
        if not info:
            return 'לא נמצאו פרטי עסק.'
        return (f'\U0001f3e2 *פרטי העסק*\n\n'
                f'\U0001f4db {info.get("name","-")}\n'
                f'\U0001f4cd {info.get("address","-")}\n'
                f'\U0001f4de {info.get("phone","-")}\n'
                f'\U0001faa4 {info.get("id_number","-")}\n'
                f'\U0001f4e7 {info.get("email","-")}')

    def _show_catalog(self, phone: str) -> str:
        services = models.get_services()
        if not services:
            return '\U0001f4cb *קטלוג ריק*\n\nשלח "הוסף שירות: [שם] [מחיר]"'
        lines = ['\U0001f4cb *השירותים:*\n']
        for s in services:
            lines.append(f'{s["id"]}. {s["name"]} — ₪{s["price"]:,.0f}')
        return '\n'.join(lines)

    def _start_add_service(self, phone: str) -> str:
        models.set_state(phone, 'catalog_add_name', {})
        return 'מה שם השירות?'

    def _catalog_got_name(self, phone: str, msg: str, data: dict) -> str:
        data['name'] = msg
        models.set_state(phone, 'catalog_add_price', data)
        return f'✅ {msg}\n\n\U0001f4b0 מה המחיר?'

    def _catalog_got_price(self, phone: str, msg: str, data: dict) -> str:
        price = _parse_amount(msg)
        if price is None:
            return '❗ מחיר לא תקין.'
        service = models.add_service(data['name'], price)
        models.clear_state(phone)
        return f'✅ *{service["name"]}* נוסף — ₪{service["price"]:,.0f}'

    def _catalog_got_edit(self, phone: str, msg: str, data: dict) -> str:
        price = _parse_amount(msg)
        if price is None:
            return '❗ מחיר לא תקין.'
        models.update_service_price(data['service_id'], price)
        models.clear_state(phone)
        return f'✅ מחיר עודכן ל-₪{price:,.0f}'

    def _handle_catalog_command(self, phone: str, msg: str) -> str | None:
        if msg.startswith('הוסף שירות'):
            rest = msg.replace('הוסף שירות:', '').replace('הוסף שירות', '').strip()
            parts = rest.rsplit(' ', 1)
            if len(parts) == 2:
                name, price_str = parts[0].strip(), parts[1]
                price = _parse_amount(price_str)
                if name and price:
                    svc = models.add_service(name, price)
                    return f'✅ *{svc["name"]}* נוסף — ₪{svc["price"]:,.0f}'
            return self._start_add_service(phone)
        if msg.startswith('ערוך '):
            parts = msg.split()
            if len(parts) >= 3:
                try:
                    sid, price = int(parts[1]), _parse_amount(parts[2])
                    if price:
                        models.update_service_price(sid, price)
                        return f'✅ עודכן ל-₪{price:,.0f}'
                except Exception:
                    pass
        if msg.startswith('מחק ') and msg.split()[1].isdigit():
            sid = int(msg.split()[1])
            svc = models.get_service(sid)
            if svc:
                models.delete_service(sid)
                return f'\U0001f5d1️ "{svc["name"]}" הוסר.'
            return '❗ שירות לא נמצא.'
        return None

    def _start_quote(self, phone: str) -> str:
        return self._start_document(phone, 'quote')

    def _start_payment_request(self, phone: str) -> str:
        return self._start_document(phone, 'payment_request')

    def _start_document(self, phone: str, doc_type: str) -> str:
        doc_names = {'quote': 'הצעת מחיר', 'payment_request': 'דרישת תשלום'}
        models.set_state(phone, 'doc_client', {'doc_type': doc_type})
        return f'\U0001f4c4 *{doc_names[doc_type]}*\n\n\U0001f464 לאיזה לקוח?'

    def _doc_got_client(self, phone: str, msg: str, data: dict) -> str:
        data['client_name'] = msg
        data['items'] = []
        models.set_state(phone, 'doc_items', data)
        return self._show_service_picker(data)

    def _show_service_picker(self, data: dict) -> str:
        services = models.get_services()
        items_so_far = data.get('items', [])
        lines = ['\U0001f6cd️ *בחר שירותים:*\n']
        if services:
            for s in services:
                lines.append(f'{s["id"]}. {s["name"]} — ₪{s["price"]:,.0f}')
            lines.append('\nשלח מספרים מופרדים בפסיק: "1, 3"')
        else:
            lines.append('כתוב שירות ומחיר: "שם שירות 350"')
        if items_so_far:
            lines.append('\n✅ *נבחרו:*')
            for item in items_so_far:
                lines.append(f'• {item["name"]} — ₪{item["total"]:,.0f}')
        lines.append('\nשלח "סיום" לאחר הבחירה')
        return '\n'.join(lines)

    def _doc_got_items(self, phone: str, msg: str, data: dict) -> str:
        if msg.strip() in ('סיום', 'done', 'finish'):
            if not data.get('items'):
                return '❗ לא נבחרו שירותים.'
            models.set_state(phone, 'doc_notes', data)
            total = sum(i['total'] for i in data['items'])
            lines = [f'✅ *{len(data["items"])} שירותים*']
            for item in data['items']:
                lines.append(f'• {item["name"]} — ₪{item["total"]:,.0f}')
            lines.append(f'\n\U0001f4b0 סה"כ: ₪{total:,.0f}')
            lines.append('\n\U0001f4dd הערות? (או "דלג")')
            return '\n'.join(lines)
        services = models.get_services()
        svc_map = {str(s['id']): s for s in services}
        added = []
        parts = [p.strip() for p in msg.replace('،', ',').split(',')]
        for part in parts:
            if part in svc_map:
                s = svc_map[part]
                data['items'].append({'name': s['name'], 'quantity': 1, 'unit_price': s['price'], 'total': s['price']})
                added.append(s['name'])
            else:
                words = part.rsplit(' ', 1)
                if len(words) == 2:
                    price = _parse_amount(words[1])
                    if price:
                        data['items'].append({'name': words[0].strip(), 'quantity': 1, 'unit_price': price, 'total': price})
                        added.append(words[0].strip())
        models.set_state(phone, 'doc_items', data)
        if added:
            return f'✅ נוסף: {", ".join(added)}\n\n' + self._show_service_picker(data)
        return '❗ לא הבנתי.'

    def _doc_got_notes(self, phone: str, msg: str, data: dict) -> str:
        if msg.lower() not in ('דלג', 'skip', '-', ''):
            data['notes'] = msg
        models.clear_state(phone)
        return self._finalize_document(phone, data)

    def _finalize_document(self, phone: str, data: dict) -> str:
        doc_type = data['doc_type']
        doc_names = {'quote': 'הצעת מחיר', 'payment_request': 'דרישת תשלום'}
        try:
            from datetime import timedelta
            business_info = models.get_all_business_info()
            valid_until = ''
            if doc_type == 'quote':
                valid_until = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
            record = models.add_document(doc_type=doc_type, client_name=data['client_name'],
                                         items=data['items'], notes=data.get('notes',''), valid_until=valid_until)
            pdf_path = document_generator.generate_document(
                doc_type=doc_type, doc_number=record['doc_number'], date=record['date'],
                client_name=record['client_name'], items=data['items'], business_info=business_info,
                notes=record['notes'], valid_until=valid_until)
            try:
                img_path = document_generator.pdf_to_image(pdf_path)
                img_url = f'{APP_URL}/documents/{os.path.basename(img_path)}'
                self._send_media(phone, img_url, f'\U0001f4f8 {doc_names[doc_type]} — {record["doc_number"]}')
            except Exception:
                pass
            pdf_url = f'{APP_URL}/documents/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url, f'\U0001f4c4 {doc_names[doc_type]} — {record["doc_number"]}')
            total = sum(i['total'] for i in data['items'])
            items_text = '\n'.join(f'• {i["name"]} ₪{i["total"]:,.0f}' for i in data['items'])
            return (f'✅ *{doc_names[doc_type]} הופקה!*\n\n'
                    f'\U0001f516 {record["doc_number"]}\n\U0001f464 {record["client_name"]}\n\n'
                    f'{items_text}\n\n\U0001f4b0 סה"כ: ₪{total:,.0f}')
        except Exception as e:
            return f'❌ שגיאה: {str(e)}'

    def _handle_back(self, phone: str, state: str, data: dict) -> str:
        if state in _BACK_MAP:
            prev_state, prompt = _BACK_MAP[state]
            models.set_state(phone, prev_state, data)
            return f'⬅️ חזרנו שלב אחד.\n\n{prompt}'
        models.clear_state(phone)
        return '⬅️ חזרנו להתחלה.\n\n' + self._menu()

    def _handle_edit_last(self, phone: str) -> str:
        record = models.get_last_income()
        if not record:
            return '❗ לא נמצאו קבלות לתיקון.'
        models.set_state(phone, 'edit_last', {'edit_id': record['id']})
        return (f'✏️ *תיקון קבלה אחרונה*\n\n'
                f'\U0001f516 {record["receipt_number"]}\n'
                f'\U0001f464 {record["client_name"]}\n'
                f'\U0001f4bc {record["description"]}\n'
                f'\U0001f4b0 ₪{record["amount"]:,.0f}\n\n'
                f'*מה לתקן?*\n'
                f'1. שם לקוח\n2. תיאור שירות\n3. סכום')

    def _edit_got_field(self, phone: str, msg: str, data: dict) -> str:
        field_map = {'1':'client_name','לקוח':'client_name','שם':'client_name',
                     '2':'description','שירות':'description','תיאור':'description',
                     '3':'amount','סכום':'amount','מחיר':'amount'}
        field = field_map.get(msg.strip())
        if not field:
            return '❗ שלח 1, 2, או 3.'
        data['edit_field'] = field
        models.set_state(phone, 'edit_field_value', data)
        prompts = {'client_name':'\U0001f464 שם לקוח חדש?',
                   'description':'\U0001f4bc תיאור שירות חדש?',
                   'amount':'\U0001f4b0 סכום חדש?'}
        return prompts[field]

    def _edit_got_value(self, phone: str, msg: str, data: dict) -> str:
        field = data['edit_field']
        edit_id = data['edit_id']
        if field == 'amount':
            value = _parse_amount(msg)
            if value is None:
                return '❗ סכום לא תקין.'
        else:
            value = msg.strip()
        models.update_income_field(edit_id, field, value)
        models.clear_state(phone)
        record = models.get_income_by_id(edit_id)
        business_info = models.get_all_business_info()
        try:
            pdf_path = receipt_generator.generate_receipt(
                receipt_number=record['receipt_number'], date=record['date'],
                client_name=record['client_name'], description=record['description'],
                amount=record['amount'], business_info=business_info)
            models.update_income_field(edit_id, 'pdf_path', pdf_path)
            try:
                img_path = receipt_generator.pdf_to_image(pdf_path)
                img_url = f'{APP_URL}/receipts/{os.path.basename(img_path)}'
                self._send_media(phone, img_url, f'\U0001f4f8 קבלה מתוקנת #{record["receipt_number"]}')
            except Exception:
                pass
            pdf_url = f'{APP_URL}/receipts/{os.path.basename(pdf_path)}'
            self._send_media(phone, pdf_url, f'\U0001f4c4 PDF מתוקן #{record["receipt_number"]}')
            return (f'✅ *קבלה עודכנה!*\n\n'
                    f'\U0001f516 {record["receipt_number"]}\n'
                    f'\U0001f464 {record["client_name"]}\n'
                    f'\U0001f4bc {record["description"]}\n'
                    f'\U0001f4b0 ₪{record["amount"]:,.0f}\n\n'
                    f'\U0001f4f8 קבלה מתוקנת נשלחה!')
        except Exception as e:
            return f'❌ שגיאה: {str(e)}'

    def _send_media(self, to: str, media_url: str, caption: str = ''):
        if not self.twilio:
            print(f'[TWILIO] would send {media_url} to {to}')
            return
        try:
            self.twilio.messages.create(
                from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}',
                to=to, media_url=[media_url], body=caption)
        except Exception as e:
            print(f'[TWILIO] {e}')


def _parse_amount(text: str) -> float | None:
    cleaned = text.replace(',','').replace('₪','').replace('שח','') \
                  .replace('ש"ח','').replace('שקל','').replace('שקלים','').strip()
    try:
        return float(cleaned.split()[0])
    except Exception:
        return None

def _fmt_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return date_str

def _progress_bar(pct: float, width: int = 10) -> str:
    filled = int(pct / 100 * width)
    return '█' * filled + '░' * (width - filled)

def _month_heb(m: int) -> str:
    months = ['','ינואר','פברואר','מרץ','אפריל',
              'מאי','יוני','יולי','אוגוסט',
              'ספטמבר','אוקטובר','נובמבר','דצמבר']
    return months[m] if 1 <= m <= 12 else str(m)
