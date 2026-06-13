"""
app.py - שרת Flask ראשי לסוכן רואה החשבון בוואטסאפ
"""
import os
from flask import Flask, request, Response, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv

load_dotenv()

from whatsapp_handler import WhatsAppHandler
from scheduler import setup_scheduler

app = Flask(__name__)
handler = WhatsAppHandler()

TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
RECEIPTS_DIR = os.path.join(os.path.dirname(__file__), 'receipts')
REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'reports')
DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), 'documents')

os.makedirs(RECEIPTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)


# ─── Webhook Twilio ─────────────────────────────────────

@app.route('/webhook', methods=['POST'])
def webhook():
    """נקודת הכניסה לכל הודעת וואטסאפ מ-Twilio."""

    # אימות חתימת Twilio (הגנת אבטחה)
    if TWILIO_TOKEN and os.environ.get('VALIDATE_TWILIO', 'true') == 'true':
        validator = RequestValidator(TWILIO_TOKEN)
        url = request.url
        signature = request.headers.get('X-Twilio-Signature', '')
        if not validator.validate(url, request.form, signature):
            return Response('Forbidden', status=403)

    # פרטי ההודעה
    body = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    num_media = int(request.values.get('NumMedia', 0))
    media_url = request.values.get('MediaUrl0', '') if num_media > 0 else None
    media_type = request.values.get('MediaContentType0', '') if num_media > 0 else None

    print(f'[IN] {sender}: {body[:60]}{"..." if len(body) > 60 else ""}',
          f'| media: {bool(media_url)}')

    # עיבוד ההודעה
    response_text = handler.process_message(
        sender=sender,
        message=body,
        media_url=media_url,
        media_type=media_type
    )

    print(f'[OUT] → {response_text[:80]}...')

    # תשובת TwiML
    resp = MessagingResponse()
    resp.message(response_text)
    return Response(str(resp), content_type='application/xml')


# ─── הגשת קבצי PDF ─────────────────────────────────────

@app.route('/receipts/<filename>')
def serve_receipt(filename):
    """הגשת קבלות PDF."""
    return send_from_directory(RECEIPTS_DIR, filename,
                               mimetype='application/pdf')


@app.route('/reports/<filename>')
def serve_report(filename):
    """הגשת דוחות PDF."""
    return send_from_directory(REPORTS_DIR, filename,
                               mimetype='application/pdf')


@app.route('/documents/<filename>')
def serve_document(filename):
    """הגשת מסמכים (הצעות מחיר, דרישות תשלום)."""
    mime = 'image/png' if filename.endswith('.png') else 'application/pdf'
    return send_from_directory(DOCUMENTS_DIR, filename, mimetype=mime)


# ─── בריאות ────────────────────────────────────────────

@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'accountant-bot'}, 200


@app.route('/')
def index():
    return {'message': 'סוכן רואה החשבון פעיל! 🚀'}, 200


# ─── הפעלה ─────────────────────────────────────────────

if __name__ == '__main__':
    # הפעל מתזמן תזכורות
    setup_scheduler()

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'

    print(f'🚀 שרת עולה על פורט {port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
