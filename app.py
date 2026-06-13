"""
app.py - שרת Flask ראשי
"""
import os
from flask import Flask, request, Response, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

load_dotenv()

from fonts import ensure_hebrew_fonts
ensure_hebrew_fonts()

from whatsapp_handler import WhatsAppHandler
from scheduler import setup_scheduler

app = Flask(__name__)
handler = WhatsAppHandler()

TWILIO_TOKEN  = os.environ.get('TWILIO_AUTH_TOKEN', '')
RECEIPTS_DIR  = os.path.join(os.path.dirname(__file__), 'receipts')
REPORTS_DIR   = os.path.join(os.path.dirname(__file__), 'reports')
DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), 'documents')

for d in [RECEIPTS_DIR, REPORTS_DIR, DOCUMENTS_DIR]:
    os.makedirs(d, exist_ok=True)


def _twiml(text: str) -> Response:
    """מחזיר תגובת TwiML תקנית עם encoding נכון."""
    resp = MessagingResponse()
    resp.message(text)
    xml = str(resp).encode('utf-8')
    return Response(xml, content_type='text/xml; charset=utf-8')


@app.route('/webhook', methods=['POST'])
def webhook():
    body       = request.values.get('Body', '').strip()
    sender     = request.values.get('From', '')
    num_media  = int(request.values.get('NumMedia', 0))
    media_url  = request.values.get('MediaUrl0', '') if num_media > 0 else None
    media_type = request.values.get('MediaContentType0', '') if num_media > 0 else None

    # ולידציית Twilio (ניתן לכיבוי עם VALIDATE_TWILIO=false)
    validate = os.environ.get('VALIDATE_TWILIO', 'true').lower() == 'true'
    if validate and TWILIO_TOKEN:
        from twilio.request_validator import RequestValidator
        url = request.url.replace('http://', 'https://')  # Railway proxy fix
        v = RequestValidator(TWILIO_TOKEN)
        if not v.validate(url, request.form,
                          request.headers.get('X-Twilio-Signature', '')):
            print(f'[WARN] Twilio signature validation failed for {sender}')
            return Response('Forbidden', status=403)

    print(f'[IN] {sender}: {body[:80]}')

    try:
        response_text = handler.process_message(
            sender=sender, message=body,
            media_url=media_url, media_type=media_type
        )
    except Exception as e:
        print(f'[ERROR] process_message failed: {e}')
        response_text = 'מצטערים, אירעה שגיאה. נסה שוב.'

    print(f'[OUT] {response_text[:120]}')
    return _twiml(response_text)


@app.route('/receipts/<filename>')
def serve_receipt(filename):
    mime = 'image/png' if filename.endswith('.png') else 'application/pdf'
    return send_from_directory(RECEIPTS_DIR, filename, mimetype=mime)

@app.route('/reports/<filename>')
def serve_report(filename):
    return send_from_directory(REPORTS_DIR, filename, mimetype='application/pdf')

@app.route('/documents/<filename>')
def serve_document(filename):
    mime = 'image/png' if filename.endswith('.png') else 'application/pdf'
    return send_from_directory(DOCUMENTS_DIR, filename, mimetype=mime)

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

@app.route('/')
def index():
    return {'message': 'Agent is live!'}, 200


if __name__ == '__main__':
    setup_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
