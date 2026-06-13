"""
ai_processor.py - עיבוד תמונות ושפה טבעית עם Claude AI
מזהה הוצאות מתמונות קבלות ומעבד בקשות בשפה טבעית
"""
import os
import base64
import json
import re
import requests
from datetime import datetime
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

EXPENSE_CATEGORIES = [
    'ציוד מקצועי',
    'חומרי גלם / מוצרים',
    'שיווק ופרסום',
    'תחבורה',
    'טלפון ותקשורת',
    'ביגוד מקצועי',
    'השתלמויות / הכשרה',
    'שכירות ומשרד',
    'מזון ואירוח עסקי',
    'ביטוח מקצועי',
    'כללי'
]


def extract_expense_from_image(image_url: str, twilio_sid: str = None,
                                twilio_token: str = None) -> dict:
    """
    מזהה פרטי הוצאה מתמונת קבלה.
    מחזיר: {description, amount, date, category, confidence, raw_text}
    """
    try:
        # הורדת התמונה מ-Twilio (דורש אימות)
        if twilio_sid and twilio_token:
            response = requests.get(image_url, auth=(twilio_sid, twilio_token), timeout=15)
        else:
            response = requests.get(image_url, timeout=15)

        if response.status_code != 200:
            return _error_result('לא ניתן להוריד את התמונה')

        image_data = base64.standard_b64encode(response.content).decode('utf-8')
        content_type = response.headers.get('Content-Type', 'image/jpeg').split(';')[0]

        categories_str = ', '.join(EXPENSE_CATEGORIES)

        result = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': content_type,
                            'data': image_data
                        }
                    },
                    {
                        'type': 'text',
                        'text': f"""נתח את הקבלה/חשבונית בתמונה וחלץ את הפרטים הבאים.
ענה בפורמט JSON בלבד, ללא טקסט נוסף:

{{
  "description": "תיאור קצר של ההוצאה",
  "amount": מספר_בשקלים,
  "date": "YYYY-MM-DD או null אם לא ברור",
  "vendor": "שם הספק / חנות",
  "category": "אחת מהקטגוריות: {categories_str}",
  "confidence": "high/medium/low",
  "raw_text": "טקסט גולמי שזיהית בתמונה"
}}

חשוב:
- amount הוא תמיד מספר (ללא ₪ וללא פסיקים)
- date בפורמט YYYY-MM-DD
- אם יש מע"מ, תן את הסכום הכולל כולל מע"מ
- אם אינך בטוח בסכום, שים null ב-amount
- ענה בעברית לשדות description ו-vendor"""
                    }
                ]
            }]
        )

        raw = result.content[0].text.strip()
        # נסה לחלץ JSON אם יש טקסט מיותר
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(raw)

        # ולידציה
        if not data.get('date') or data['date'] == 'null':
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        if not data.get('category'):
            data['category'] = 'כללי'
        if not data.get('amount'):
            data['amount'] = None

        return data

    except json.JSONDecodeError:
        return _error_result('לא ניתן לפענח את תשובת ה-AI')
    except Exception as e:
        return _error_result(f'שגיאה: {str(e)}')


def parse_receipt_command(text: str) -> dict:
    """
    מנתח פקודת קבלה בשפה טבעית.
    לדוגמה: "קבלה ל-דנה לוי על טיפול פנים 450 שקל"
    מחזיר: {client_name, description, amount, date}
    """
    result = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=300,
        messages=[{
            'role': 'user',
            'content': f"""חלץ פרטי קבלה מהטקסט הבא וענה בפורמט JSON בלבד:

טקסט: "{text}"

{{
  "client_name": "שם הלקוח",
  "description": "תיאור השירות",
  "amount": מספר_בשקלים,
  "date": "YYYY-MM-DD או null להיום"
}}

אם חסר מידע, שים null. amount הוא מספר בלבד."""
        }]
    )

    try:
        raw = result.content[0].text.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(json_match.group() if json_match else raw)
        if not data.get('date') or data.get('date') == 'null':
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        return data
    except Exception:
        return {}


def parse_expense_command(text: str) -> dict:
    """
    מנתח פקודת הוצאה בשפה טבעית.
    לדוגמה: "הוצאה: קרם לטיפולים 120 שקל"
    """
    categories_str = ', '.join(EXPENSE_CATEGORIES)
    result = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=300,
        messages=[{
            'role': 'user',
            'content': f"""חלץ פרטי הוצאה מהטקסט וענה JSON בלבד:

טקסט: "{text}"

{{
  "description": "תיאור ההוצאה",
  "amount": מספר_בשקלים,
  "category": "אחת מ: {categories_str}",
  "date": "YYYY-MM-DD או null להיום"
}}"""
        }]
    )
    try:
        raw = result.content[0].text.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(json_match.group() if json_match else raw)
        if not data.get('date') or data.get('date') == 'null':
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        return data
    except Exception:
        return {}


def understand_intent(text: str) -> str:
    """
    מזהה את כוונת המשתמש.
    מחזיר: new_receipt | new_expense | summary | annual_report |
             monthly_report | help | unknown
    """
    result = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=50,
        system="""אתה עוזר לזיהוי כוונה. ענה במילה אחת בלבד מהרשימה:
new_receipt - רוצה להוציא קבלה ללקוח
new_expense - רוצה לרשום הוצאה
summary - רוצה סיכום / סטטוס
annual_report - רוצה דוח שנתי
monthly_report - רוצה דוח חודשי
help - רוצה עזרה / מה אפשר לעשות
unknown - אחר""",
        messages=[{'role': 'user', 'content': text}]
    )
    intent = result.content[0].text.strip().lower()
    valid = {'new_receipt', 'new_expense', 'summary', 'annual_report',
             'monthly_report', 'help', 'unknown'}
    return intent if intent in valid else 'unknown'


def _error_result(msg: str) -> dict:
    return {
        'description': None,
        'amount': None,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'vendor': None,
        'category': 'כללי',
        'confidence': 'low',
        'error': msg
    }
