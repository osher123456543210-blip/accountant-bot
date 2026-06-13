"""
models.py - מסד נתונים SQLite לסוכן רואה החשבון
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'accounting.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # הכנסות / קבלות
    c.execute('''CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_number TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        client_name TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        pdf_path TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    )''')

    # הוצאות
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT DEFAULT 'כללי',
        receipt_image_path TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    )''')

    # מידע על העסק
    c.execute('''CREATE TABLE IF NOT EXISTS business_info (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    # קטלוג שירותים ומחירים
    c.execute('''CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )''')

    # מסמכים (הצעות מחיר, דרישות תשלום, חשבוניות מס)
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_type TEXT NOT NULL,
        doc_number TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        client_name TEXT NOT NULL,
        client_phone TEXT DEFAULT '',
        items TEXT NOT NULL,
        subtotal REAL NOT NULL,
        vat_amount REAL DEFAULT 0,
        total REAL NOT NULL,
        notes TEXT DEFAULT '',
        valid_until TEXT DEFAULT '',
        pdf_path TEXT DEFAULT '',
        status TEXT DEFAULT 'draft',
        created_at TEXT NOT NULL
    )''')

    # סטטוס שיחה לכל משתמש (לניהול שיחה מרובת-שלבים)
    c.execute('''CREATE TABLE IF NOT EXISTS conversation_state (
        phone TEXT PRIMARY KEY,
        state TEXT DEFAULT 'idle',
        data TEXT DEFAULT '{}',
        updated_at TEXT
    )''')

    conn.commit()
    conn.close()
    print("✅ מסד נתונים אותחל בהצלחה")


# ─── עסק ───────────────────────────────────────────────

def set_business_info(key: str, value: str):
    conn = get_conn()
    conn.execute(
        'INSERT OR REPLACE INTO business_info (key, value) VALUES (?, ?)',
        (key, value)
    )
    conn.commit()
    conn.close()


def get_business_info(key: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        'SELECT value FROM business_info WHERE key = ?', (key,)
    ).fetchone()
    conn.close()
    return row['value'] if row else None


def is_business_setup() -> bool:
    return bool(get_business_info('name'))


def get_all_business_info() -> dict:
    conn = get_conn()
    rows = conn.execute('SELECT key, value FROM business_info').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}


# ─── קבלות / הכנסות ────────────────────────────────────

def get_next_receipt_number() -> str:
    conn = get_conn()
    year = datetime.now().year
    count = conn.execute(
        "SELECT COUNT(*) as c FROM income WHERE date LIKE ?",
        (f'{year}%',)
    ).fetchone()['c']
    conn.close()
    return f'{year}-{count + 1:04d}'


def add_income(client_name: str, description: str, amount: float,
               date: str = None, notes: str = '', pdf_path: str = '') -> dict:
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    receipt_number = get_next_receipt_number()
    created_at = datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        '''INSERT INTO income
           (receipt_number, date, client_name, description, amount, pdf_path, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (receipt_number, date, client_name, description, amount, pdf_path, notes, created_at)
    )
    conn.commit()
    # קרא חזרה את הרשומה
    row = conn.execute(
        'SELECT * FROM income WHERE receipt_number = ?', (receipt_number,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_income_summary(year: int = None, month: int = None) -> dict:
    conn = get_conn()
    query = 'SELECT * FROM income WHERE 1=1'
    params = []
    if year:
        query += ' AND date LIKE ?'
        params.append(f'{year}%')
    if month:
        query += ' AND date LIKE ?'
        params.append(f'%-{month:02d}-%')
    rows = conn.execute(query, params).fetchall()
    conn.close()
    total = sum(r['amount'] for r in rows)
    return {'records': [dict(r) for r in rows], 'total': total, 'count': len(rows)}


# ─── הוצאות ────────────────────────────────────────────

def add_expense(description: str, amount: float, category: str = 'כללי',
                date: str = None, notes: str = '', image_path: str = '') -> dict:
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    created_at = datetime.now().isoformat()
    conn = get_conn()
    cursor = conn.execute(
        '''INSERT INTO expenses
           (date, description, amount, category, receipt_image_path, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (date, description, amount, category, image_path, notes, created_at)
    )
    row_id = cursor.lastrowid
    conn.commit()
    row = conn.execute('SELECT * FROM expenses WHERE id = ?', (row_id,)).fetchone()
    conn.close()
    return dict(row)


def get_expense_summary(year: int = None, month: int = None) -> dict:
    conn = get_conn()
    query = 'SELECT * FROM expenses WHERE 1=1'
    params = []
    if year:
        query += ' AND date LIKE ?'
        params.append(f'{year}%')
    if month:
        query += ' AND date LIKE ?'
        params.append(f'%-{month:02d}-%')
    rows = conn.execute(query, params).fetchall()
    conn.close()
    total = sum(r['amount'] for r in rows)
    by_category = {}
    for r in rows:
        cat = r['category']
        by_category[cat] = by_category.get(cat, 0) + r['amount']
    return {
        'records': [dict(r) for r in rows],
        'total': total,
        'count': len(rows),
        'by_category': by_category
    }


# ─── סטטוס שיחה ────────────────────────────────────────

def get_state(phone: str) -> tuple[str, dict]:
    import json
    conn = get_conn()
    row = conn.execute(
        'SELECT state, data FROM conversation_state WHERE phone = ?', (phone,)
    ).fetchone()
    conn.close()
    if row:
        return row['state'], json.loads(row['data'])
    return 'idle', {}


def set_state(phone: str, state: str, data: dict = None):
    import json
    conn = get_conn()
    conn.execute(
        '''INSERT OR REPLACE INTO conversation_state (phone, state, data, updated_at)
           VALUES (?, ?, ?, ?)''',
        (phone, state, json.dumps(data or {}, ensure_ascii=False),
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def clear_state(phone: str):
    set_state(phone, 'idle', {})


# ─── קטלוג שירותים ─────────────────────────────────────

def add_service(name: str, price: float, description: str = '') -> dict:
    conn = get_conn()
    cursor = conn.execute(
        'INSERT INTO services (name, price, description, created_at) VALUES (?, ?, ?, ?)',
        (name, price, description, datetime.now().isoformat())
    )
    row = conn.execute('SELECT * FROM services WHERE id = ?', (cursor.lastrowid,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


def get_services(active_only: bool = True) -> list:
    conn = get_conn()
    query = 'SELECT * FROM services'
    if active_only:
        query += ' WHERE active = 1'
    query += ' ORDER BY name'
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_service(service_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute('SELECT * FROM services WHERE id = ?', (service_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_service_price(service_id: int, new_price: float):
    conn = get_conn()
    conn.execute('UPDATE services SET price = ? WHERE id = ?', (new_price, service_id))
    conn.commit()
    conn.close()


def delete_service(service_id: int):
    conn = get_conn()
    conn.execute('UPDATE services SET active = 0 WHERE id = ?', (service_id,))
    conn.commit()
    conn.close()


# ─── מסמכים ────────────────────────────────────────────

def get_next_doc_number(doc_type: str) -> str:
    prefixes = {
        'quote': 'HM',       # הצעת מחיר
        'payment_request': 'DT',  # דרישת תשלום
        'tax_invoice': 'HH',  # חשבונית מס
    }
    prefix = prefixes.get(doc_type, 'XX')
    year = datetime.now().year
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM documents WHERE doc_type = ? AND date LIKE ?",
        (doc_type, f'{year}%')
    ).fetchone()['c']
    conn.close()
    return f'{prefix}{year}-{count + 1:04d}'


def add_document(doc_type: str, client_name: str, items: list,
                 client_phone: str = '', notes: str = '',
                 valid_until: str = '', vat_rate: float = 0.0,
                 date: str = None) -> dict:
    """
    items: [{'name': str, 'quantity': int, 'unit_price': float, 'total': float}]
    """
    import json as _json
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    subtotal = sum(i.get('total', i['unit_price'] * i.get('quantity', 1)) for i in items)
    vat_amount = round(subtotal * vat_rate, 2)
    total = subtotal + vat_amount
    doc_number = get_next_doc_number(doc_type)
    created_at = datetime.now().isoformat()
    conn = get_conn()
    cursor = conn.execute(
        '''INSERT INTO documents
           (doc_type, doc_number, date, client_name, client_phone, items,
            subtotal, vat_amount, total, notes, valid_until, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (doc_type, doc_number, date, client_name, client_phone,
         _json.dumps(items, ensure_ascii=False),
         subtotal, vat_amount, total, notes, valid_until, created_at)
    )
    row = conn.execute('SELECT * FROM documents WHERE id = ?', (cursor.lastrowid,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


def get_document(doc_id: int) -> dict | None:
    import json as _json
    conn = get_conn()
    row = conn.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['items'] = _json.loads(d['items'])
    return d


if __name__ == '__main__':
    init_db()
