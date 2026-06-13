"""
fonts.py - מוריד פונט עברי אוטומטית בהפעלה ראשונה
"""
import os
import requests

FONT_DIR = os.path.dirname(__file__)
REGULAR = os.path.join(FONT_DIR, 'NotoSansHebrew-Regular.ttf')
BOLD = os.path.join(FONT_DIR, 'NotoSansHebrew-Bold.ttf')

URLS = {
    REGULAR: 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf',
    BOLD:    'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Bold.ttf',
}


def ensure_hebrew_fonts():
    """מוריד פונטים עבריים אם לא קיימים."""
    for path, url in URLS.items():
        if not os.path.exists(path):
            print(f'[FONTS] מוריד {os.path.basename(path)}...')
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                with open(path, 'wb') as f:
                    f.write(r.content)
                print(f'[FONTS] ✅ {os.path.basename(path)} הורד')
            except Exception as e:
                print(f'[FONTS] ❌ שגיאה בהורדת {os.path.basename(path)}: {e}')
        else:
            print(f'[FONTS] ✅ {os.path.basename(path)} קיים')


if __name__ == '__main__':
    ensure_hebrew_fonts()
