# 🤖 מדריך התקנה — סוכן רואה החשבון בוואטסאפ

## מה הסוכן עושה?

- ✅ מוציא קבלות PDF מקצועיות ללקוחות
- 📸 מזהה הוצאות מתמונות קבלות אוטומטית
- 📊 מפיק דוחות שנתיים וחודשיים
- 📅 שולח תזכורות לפני מועדי דיווח מס
- 💰 עוקב אחר הכנסות והוצאות

---

## שלב 1 — יצירת חשבון Twilio (חינמי)

1. גש ל-**https://www.twilio.com/try-twilio** ופתח חשבון חינמי
2. לאחר הרשמה, כנס ל-**Console Dashboard**
3. העתק את:
   - `Account SID` (מתחיל ב-AC...)
   - `Auth Token`
4. בתפריט שמאל → **Messaging → Try it out → Send a WhatsApp message**
5. עקוב אחרי ההוראות לחיבור מספר ה-WhatsApp שלך ל-sandbox של Twilio
6. המספר של ה-sandbox יהיה כמו: `+14155238886`

---

## שלב 2 — יצירת חשבון Claude API

1. גש ל-**https://console.anthropic.com**
2. צור חשבון ← לחץ **API Keys** ← **Create Key**
3. העתק את המפתח (מתחיל ב-`sk-ant-...`)
4. הוסף **$5 credit** (שיספיק לאלפי שיחות)

---

## שלב 3 — פריסה ב-Railway (חינמי)

Railway הוא שרת ענן שישמור את הסוכן דולק 24/7.

1. גש ל-**https://railway.app** ← כנס עם GitHub
2. לחץ **New Project → Deploy from GitHub repo**
3. העלה את תיקיית `accountant_bot` ל-GitHub:

```bash
cd accountant_bot
git init
git add .
git commit -m "first commit"
# צור repo חדש ב-github.com ואז:
git remote add origin https://github.com/USERNAME/accountant-bot.git
git push -u origin main
```

4. ב-Railway ← חבר את ה-repo שיצרת
5. Railway יזהה אוטומטית את `Procfile` ויפעיל את השרת

---

## שלב 4 — הגדרת משתני סביבה ב-Railway

ב-Railway → הפרויקט שלך → **Variables** → הוסף:

| שם | ערך |
|---|---|
| `TWILIO_ACCOUNT_SID` | ה-SID מ-Twilio |
| `TWILIO_AUTH_TOKEN` | ה-Token מ-Twilio |
| `TWILIO_WHATSAPP_NUMBER` | המספר של ה-sandbox (+14155238886) |
| `ANTHROPIC_API_KEY` | המפתח מ-Anthropic |
| `OWNER_PHONE` | המספר שלך עם +972 (לדוגמה: +972501234567) |
| `APP_URL` | ה-URL שנתן לך Railway (לדוגמה: https://accountant-bot.up.railway.app) |

---

## שלב 5 — חיבור Twilio ל-Webhook שלך

1. ב-Twilio Console → **Messaging → Settings → WhatsApp sandbox settings**
2. בשדה **"When a message comes in"** הכנס:

```
https://YOUR_RAILWAY_URL.up.railway.app/webhook
```

3. שיטה: **HTTP POST**
4. לחץ **Save**

---

## שלב 6 — הפעלה ראשונה

1. שלח **"שלום"** לוואטסאפ של Twilio sandbox
2. הסוכן יברך אותך ויבקש פרטי העסק (שם, כתובת, ת.ז.)
3. לאחר ההגדרה — תוכל להשתמש בכל הפונקציות!

---

## פקודות מהירות

| פקודה | פעולה |
|---|---|
| `1` | הוצאת קבלה ללקוח |
| `2` | רישום הוצאה |
| `3` | סיכום שנתי |
| `4` | דוח שנתי PDF |
| `5` | דוח חודשי |
| `6` | מועדי דיווח מס |
| `עזרה` | תפריט מלא |
| שלח תמונה | זיהוי הוצאה אוטומטי |

---

## הוספת פונט עברי (אופציונלי — לקבלות יפות יותר)

הורד את פונט Noto Sans Hebrew:
```
https://fonts.google.com/noto/specimen/Noto+Sans+Hebrew
```

שים את הקבצים `NotoSansHebrew-Regular.ttf` ו-`NotoSansHebrew-Bold.ttf`
בתיקיית `accountant_bot/` ועשה push מחדש ל-Railway.

---

## הגבלות עוסק פטור שהסוכן עוקב אחריהן

| פרמטר | ערך |
|---|---|
| רף שנתי לפטור ממע"מ | ₪120,000 |
| מועד דוח שנתי | 30 אפריל |
| דיווח מע"מ (דו-חודשי) | 31 לחודש |

> ⚠️ הסוכן מיועד לשימוש עצמי בלבד. לצרכים משפטיים או מורכבים, מומלץ להתייעץ עם רואה חשבון.

---

## עלויות משוערות לחודש

| שירות | עלות |
|---|---|
| Railway (Hobby plan) | $5/חודש |
| Twilio WhatsApp | $0.005 להודעה |
| Anthropic Claude | ~$1-3 לחודש |
| **סה"כ** | **~$7-10/חודש** |

_לעומת רואה חשבון = חיסכון של מאות שקלים בחודש!_

---

## שאלות נפוצות

**ש: האם זה בטוח?**
ת: כן. הנתונים נשמרים בשרת הפרטי שלך בלבד. אין שיתוף עם גורם שלישי.

**ש: מה אם הגעתי לרף ₪120,000?**
ת: הסוכן יתריע אוטומטית כשתגיע ל-80% מהרף.

**ש: אפשר להוסיף עוד לקוחות לאותו סוכן?**
ת: כרגע הסוכן מותאם לעסק יחיד. לשימוש מרובה משתמשים — צור issue ב-GitHub.
