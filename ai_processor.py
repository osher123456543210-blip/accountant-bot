"""
ai_processor.py - AI processing with Claude
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
    try:
        if twilio_sid and twilio_token:
            response = requests.get(image_url, auth=(twilio_sid, twilio_token), timeout=15)
        else:
            response = requests.get(image_url, timeout=15)

        if response.status_code != 200:
            return _error_result('Cannot download image')

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
                        'text': (
                            'Analyze this receipt/invoice image and extract details. '
                            'Reply ONLY with valid JSON, no extra text:\n\n'
                            '{\n'
                            '  "description": "short description of the expense in Hebrew",\n'
                            '  "amount": number_in_shekels_or_null,\n'
                            '  "date": "YYYY-MM-DD or null",\n'
                            '  "vendor": "vendor/store name in Hebrew",\n'
                            '  "category": "one of: ' + categories_str + '",\n'
                            '  "confidence": "high/medium/low",\n'
                            '  "raw_text": "raw text found in image"\n'
                            '}\n\n'
                            'Rules: amount is always a number (no currency symbols), '
                            'include VAT in total amount, use null if unsure.'
                        )
                    }
                ]
            }]
        )

        raw = result.content[0].text.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(json_match.group() if json_match else raw)

        if not data.get('date') or data['date'] == 'null':
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        if not data.get('category'):
            data['category'] = 'כללי'
        if not data.get('amount'):
            data['amount'] = None

        return data

    except json.JSONDecodeError:
        return _error_result('Cannot parse AI response')
    except Exception as e:
        return _error_result(f'Error: {str(e)}')


def parse_receipt_command(text: str) -> dict:
    try:
        result = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{
                'role': 'user',
                'content': (
                    'Extract receipt details from this Hebrew text and reply ONLY with JSON:\n\n'
                    f'Text: "{text}"\n\n'
                    '{\n'
                    '  "client_name": "client name",\n'
                    '  "description": "service description",\n'
                    '  "amount": number_or_null,\n'
                    '  "date": "YYYY-MM-DD or null for today"\n'
                    '}\n\n'
                    'Use null for missing fields. amount must be a number only.'
                )
            }]
        )
        raw = result.content[0].text.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(json_match.group() if json_match else raw)
        if not data.get('date') or data.get('date') == 'null':
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        return data
    except Exception:
        return {}


def parse_expense_command(text: str) -> dict:
    categories_str = ', '.join(EXPENSE_CATEGORIES)
    try:
        result = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{
                'role': 'user',
                'content': (
                    'Extract expense details from this Hebrew text and reply ONLY with JSON:\n\n'
                    f'Text: "{text}"\n\n'
                    '{\n'
                    '  "description": "expense description",\n'
                    '  "amount": number_or_null,\n'
                    '  "category": "one of: ' + categories_str + '",\n'
                    '  "date": "YYYY-MM-DD or null for today"\n'
                    '}\n\n'
                    'amount must be a number only.'
                )
            }]
        )
        raw = result.content[0].text.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(json_match.group() if json_match else raw)
        if not data.get('date') or data.get('date') == 'null':
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        return data
    except Exception:
        return {}


def understand_intent(text: str) -> str:
    try:
        result = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=20,
            system=(
                'You classify user intent. Reply with ONE word only from this list:\n'
                'new_receipt - user wants to issue a receipt to a client\n'
                'new_expense - user wants to log an expense\n'
                'summary - user wants income/expense summary\n'
                'annual_report - user wants annual tax report\n'
                'monthly_report - user wants monthly report\n'
                'help - user wants help or menu\n'
                'unknown - anything else'
            ),
            messages=[{'role': 'user', 'content': text}]
        )
        intent = result.content[0].text.strip().lower()
        valid = {'new_receipt', 'new_expense', 'summary', 'annual_report',
                 'monthly_report', 'help', 'unknown'}
        return intent if intent in valid else 'unknown'
    except Exception:
        return 'unknown'


def _error_result(msg: str) -> dict:
    return {
        'description': None, 'amount': None,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'vendor': None, 'category': 'כללי',
        'confidence': 'low', 'error': msg
    }
