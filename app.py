# ============================================================
#  SULAFA — سلافة  |  Flask Application
#  Clean & optimised version
# ============================================================

import os
import json
import uuid
import sqlite3
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash, g
)
from werkzeug.utils import secure_filename

# ── App setup ───────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sulafa_secret_2024_secure')#الهدف من السطر ده هو تعيين مفتاح سري (secret key) لتطبيق Flask، والذي يستخدم لتأمين الجلسات (sessions) والكوكيز. بيتم جلب المفتاح السري من مت

# ── Paths ──────────────────────────────────────────────────── #نهتم بتحديد المسارات الأساسية للتطبيق، مثل مسار قاعدة البيانات (DB_PATH) ومجلد التحميلات (UPLOAD_DIR). بيتم بناء هذه المسارات باستخدام os.path لضمان التوافق مع أنظمة التشغيل المختلفة. DB_PATH يشير إلى ملف SQLite الذي سيتم استخدامه لتخزين بيانات التطبيق، بينما UPLOAD_DIR هو المجلد الذي سيتم حفظ الملفات المرفوعة (مثل صور المنتجات) فيه.
BASE_DIR     = os.path.dirname(__file__)
DB_PATH      = os.path.join(BASE_DIR, 'sulafa.db')
UPLOAD_DIR   = os.path.join(BASE_DIR, 'static', 'uploads')

# ── Config ───────────────────────────────────────────────────#هنا بنحدد بعض الإعدادات الأساسية للتطبيق، مثل قائمة الامتدادات المسموح بها للملفات المرفوعة (ALLOWED_EXTENSIONS)، وبيانات تسجيل الدخول الافتراضية للمسؤول (ADMIN_USER وADMIN_PASS). كمان بنحدد مجموعة من الحالات الصالحة للطلبات (VALID_ORDER_STATUSES) اللي ممكن يتم تعيينها للطلبات في النظام.
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ADMIN_USER         = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS         = os.environ.get('ADMIN_PASS', 'sulafa2024')

VALID_ORDER_STATUSES = {'confirmed', 'pending', 'packed', 'shipped', 'delivered', 'cancelled'}


# ════════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════════

def get_db():#الهدف من الدالة دي هو انها ترجع اتصال بقاعدة البيانات SQLite لكل طلب بييجي للفلسك، وبتخزنه في g اللي هو مكان مخصص لتخزين البيانات الخاصة بكل طلب. لو مفيش اتصال موجود بالفعل في g، بيتم إنشاء اتصال جديد وربطه بيه. كمان بيتم تعيين row_factory علشان نقدر نوصل للبيانات باستخدام أسماء الأعمدة بدل من الفهارس.
    """Return a per-request SQLite connection (stored in Flask g)."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc=None):#ثم إغلاق اتصال قاعدة البيانات في نهاية كل طلب. بيتم سحب الاتصال من g وإذا كان موجود، بيتم إغلاقه. ده بيضمن إن مفيش اتصالات مفتوحة بتستهلك موارد بعد ما الطلب انتهى.
    """Close the DB connection at the end of every request."""
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def init_db():#ثم إنشاء الجداول اللازمة في قاعدة البيانات إذا ما كانتش موجودة بالفعل، وتشغيل أي ترحيلات لازمة لإضافة أعمدة جديدة بدون فقدان البيانات، وكمان زراعة بيانات افتراضية زي الإعدادات الأساسية وبعض المنتجات الأولية لو ما كانش فيه منتجات أصلاً. ده بيضمن إن التطبيق يشتغل بشكل صحيح حتى لو كانت قاعدة البيانات جديدة أو تم تحديثها.
    """Create tables, run migrations, and seed default data."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    # ── Tables ──────────────────────────────────────────────
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar        TEXT    NOT NULL,
            name_en        TEXT    NOT NULL,
            desc_ar        TEXT,
            desc_en        TEXT,
            price          REAL    NOT NULL,
            old_price      REAL,
            image          TEXT    DEFAULT '🫒',
            photo          TEXT    DEFAULT NULL,
            category_ar    TEXT    DEFAULT 'بكر ممتاز',
            category_en    TEXT    DEFAULT 'Extra Virgin',
            weight         TEXT    DEFAULT '500ml',
            origin_ar      TEXT    DEFAULT 'مصر',
            origin_en      TEXT    DEFAULT 'egypt',
            stock          INTEGER DEFAULT 0,
            rating         REAL    DEFAULT 4.9,
            reviews_count  INTEGER DEFAULT 0,
            featured       INTEGER DEFAULT 1,
            active         INTEGER DEFAULT 1,
            sort_order     INTEGER DEFAULT 0,
            created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number   TEXT,
            full_name      TEXT,
            phone          TEXT,
            city           TEXT,
            address        TEXT,
            total          REAL,
            tax            REAL,
            grand_total    REAL,
            payment_method TEXT    DEFAULT 'card',
            card_last4     TEXT,
            status         TEXT    DEFAULT 'confirmed',
            lang           TEXT    DEFAULT 'ar',
            created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER,
            product_id INTEGER,
            name       TEXT,
            price      REAL,
            quantity   INTEGER
        );

        CREATE TABLE IF NOT EXISTS cart (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sid        TEXT,
            product_id INTEGER,
            quantity   INTEGER DEFAULT 1
        );
    ''')

    # ── Migrations (safe — ignore if column already exists) ──
    migrations = [
        'ALTER TABLE products ADD COLUMN photo TEXT DEFAULT NULL',
        "ALTER TABLE orders   ADD COLUMN payment_method TEXT DEFAULT 'card'",
    ]
    for sql in migrations:
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            pass

    # ── Default settings ─────────────────────────────────────
    defaults = {
        'site_name_ar':        'سلافة',
        'site_name_en':        'SULAFA',
        'tagline_ar':          'زيت الزيتون الأصيل',
        'tagline_en':          'Pure & Premium Olive Oil',
        'hero_title_ar':       'زيت الزيتون الفاخر',
        'hero_title_en':       'Pure & Premium Olive Oil',
        'hero_sub_ar':         'اذوق جوهر مزارعنا بوادى النطرون طريق العلمين',
        'hero_sub_en':         'Taste the Essence of the Mediterranean',
        'whatsapp':            '201000000000',
        'facebook':            'https://facebook.com/sulafa',
        'instagram':           'https://instagram.com/sulafa',
        'tiktok':              'https://tiktok.com/@sulafa',
        'phone':               '+20 100 000 0000',
        'email':               'info@sulafa.eg',
        'address_ar':          'القاهرة، مصر',
        'address_en':          'Cairo, Egypt',
        'free_shipping_ar':    '0',
        'free_shipping_en':    '0',
        'shipping_cost':       '50',
        'currency_ar':         'جنيه',
        'currency_en':         'EGP',
        'benefit1_ar':         'غنى بمضادات الأكسدة',
        'benefit1_en':         'Rich in Antioxidants',
        'benefit2_ar':         'يدعم صحة القلب',
        'benefit2_en':         'Supports Heart Health',
        'benefit3_ar':         'لذيذ وصحى',
        'benefit3_en':         'Delicious & Healthy',
        'newsletter_title_ar': 'انضم لنشرتنا البريدية',
        'newsletter_title_en': 'Join Our Newsletter',
        'newsletter_sub_ar':   'اشترك للحصول على عروض حصرية وتحديثات',
        'newsletter_sub_en':   'Sign up for exclusive offers & updates',
    }
    cur.executemany(
        'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
        defaults.items()
    )

    # ── Seed products (only if table is empty) ────────────────
    if cur.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
        seed_products = [
            ('زيت الزيتون البكر الممتاز', 'Extra Virgin Olive Oil',
             'زيت زيتون بكر ممتاز معصور على البارد من أجود انواع الزيتون . غنى بمضادات الأكسدة.',
             'Cold pressed extra virgin olive oil from the finest Greek olives. Rich in antioxidants.',
             189.00, 249.00, '🫒', None, 'بكر ممتاز', 'Extra Virgin', '750ml', 'مصر', 'Egypt', 60, 4.9, 312, 1, 1, 1),

            ('زيت الزيتون العضوى', 'Organic Olive Oil',
             'زيت زيتون عضوى معتمد من المركز القومى للبحوث بدون مبيدات أو مواد كيميائية.',
             'Internationally certified organic olive oil. No pesticides or chemicals.',
             229.00, 299.00, '🌿', None, 'عضوى', 'Organic', '500ml', 'تونس', 'Tunisia', 45, 4.8, 198, 1, 1, 2),

            ('زيت الزيتون بالثوم', 'Garlic Infused Olive Oil',
             'مزيج فاخر من زيت الزيتون البكر . رائع للشوايات.',
             'Premium blend of extra virgin olive oil with natural garlic. Perfect for grilling.',
             155.00, 199.00, '🧄', None, 'منكّه', 'Infused', '250ml', 'مصر ', 'Egypt', 80, 4.7, 145, 1, 1, 3),

            ('زيت الزيتون الإيطالى الفاخر', 'Premium Italian Olive Oil',
             'من قلب توسكانا الإيطالية. نكهة استثنائية وعطر رائع.',
             'From the heart of Tuscany, Italy. Exceptional flavor and remarkable aroma.',
             315.00, 395.00, '✨', None, 'فاخر', 'Premium', '500ml', 'مصر ', 'Egypt', 30, 5.0, 445, 1, 1, 4),

            ('زيت الزيتون المصرى ', 'Palestinian Olive Oil',
             'من أشجار الزيتون المعمّرة فى مصر بمزارعنا بوادى النطرون طريق العلمين . طعم عميق وأصيل.',
             'From ancient olive trees in Palestine. Deep and authentic taste.',
             199.00, None, '🌳', None, 'بكر ممتاز', 'Extra Virgin', '750ml', 'مصر ', 'Egypt', 40, 4.9, 521, 1, 1, 5),

            ('طقم سلافة الملكى', 'Sulafa Royal Gift Set',
             'طقم هدايا فاخر يضم 3 أحجام مختلفة فى علبة هدايا راقية.',
             'Luxury gift set featuring 3 different sizes in an elegant gift box.',
             445.00, 560.00, '🎁', None, 'طقم هدايا', 'Gift Set', 'متعدد', 'متعدد', 'Multi', 25, 4.9, 78, 1, 1, 6),
        ]
        cur.executemany(
            '''INSERT INTO products
               (name_ar, name_en, desc_ar, desc_en, price, old_price, image, photo,
                category_ar, category_en, weight, origin_ar, origin_en,
                stock, rating, reviews_count, featured, active, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            seed_products
        )

    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def get_lang():#بترجع اللغة الحالية من الجلسة، أو 'ar' كافتراضي إذا ما تم تعيينها. ده بيستخدم لتحديد اللغة اللي هيتم عرض المحتوى بيها في الواجهة.
    return session.get('lang', 'ar')


def get_setting(key, default=''):#الهدف من الدالة دي هو انها بتاخد مفتاح (key) وبترجع القيمة المرتبطة بيه من جدول الإعدادات في قاعدة البيانات. لو المفتاح مش موجود، بترجع القيمة الافتراضية اللي بتتحدد في المتغير default (اللي هو '' بشكل افتراضي). ده بيستخدم لسهولة الوصول لأي إعداد معين في التطبيق زي اسم الموقع، العنوان، أو أي نصوص تانية.
    row = get_db().execute(
        'SELECT value FROM settings WHERE key=?', (key,)
    ).fetchone()
    return row['value'] if row else default


def get_all_settings():#ثم بتجيب كل الإعدادات من جدول الإعدادات في قاعدة البيانات وترجعها كقاموس (dictionary) حيث المفاتيح هي أسماء الإعدادات والقيم هي القيم المرتبطة بيها. ده بيستخدم لما نحتاج نجيب كل الإعدادات مرة واحدة، زي ما بنعمل في context processor علشان نقدر نستخدمها في كل القوالب.
    rows = get_db().execute('SELECT key, value FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows}


def get_categories():#ثم دمج الفئات المخصصة (اللي ممكن تكون مخزنة في الإعدادات كقيمة JSON) مع الفئات اللي موجودة بالفعل في جدول المنتجات. بيبدأ بجلب الفئات المخصصة من الإعدادات، وبعدين بيجيب الفئات الموجودة في المنتجات (بالعربية والإنجليزية). بعدين بيعمل قائمة جديدة بتضم كل الفئات المخصصة أولاً، وبعدين بيضيف أي فئة من المنتجات مش موجودة بالفعل في القائمة. النتيجة النهائية هي قائمة بكل الفئات المتاحة سواء كانت مخصصة أو موجودة في المنتجات.
    """Merge custom (JSON) categories with those already in products."""
    s      = get_all_settings()
    custom = []
    try:
        raw = s.get('custom_categories', '')
        if raw:
            custom = json.loads(raw)
    except Exception:
        pass

    conn    = get_db()
    rows_ar = [r[0] for r in conn.execute(
        'SELECT DISTINCT category_ar FROM products WHERE active=1 AND category_ar IS NOT NULL'
    ).fetchall()]
    rows_en = [r[0] for r in conn.execute(
        'SELECT DISTINCT category_en FROM products WHERE active=1 AND category_en IS NOT NULL'
    ).fetchall()]

    result = list(custom)#لما هو موجود فى الاعدادات من كاتيجورى مخصصه
    for i, cat_ar in enumerate(rows_ar):
        cat_en = rows_en[i] if i < len(rows_en) else cat_ar #زي ما هو موجود فى المنتج لو مفيش ترجمة
        if not any(c.get('ar') == cat_ar for c in result):
            result.append({'ar': cat_ar, 'en': cat_en})
    return result


def cart_count():#ثم حساب عدد المنتجات في عربة التسوق بناءً على معرف الجلسة (session ID) المخزن في الجلسة. بيبدأ بجلب معرف الجلسة، ولو ما كانش موجود بيرجع 0. بعدين بيعمل استعلام لقاعدة البيانات لحساب مجموع الكميات لكل المنتجات المرتبطة بمعرف الجلسة ده في جدول العربة (cart). النتيجة النهائية هي عدد المنتجات الإجمالي في العربة.
    sid = session.get('sid', '')
    if not sid:
        return 0
    row = get_db().execute(
        'SELECT COALESCE(SUM(quantity),0) FROM cart WHERE sid=?', (sid,)
    ).fetchone()
    return row[0]


def fmt_price(p, lang='ar'):#الهدف من الدالة دي هو تنسيق السعر بشكل مناسب للعرض، مع إضافة رمز العملة بناءً على اللغة المحددة. بتاخد السعر (p) واللغة (lang) كمدخلات، وبترجع السعر منسق مع رمز العملة المناسب. لو اللغة هي الإنجليزية ('en')، بيتم إضافة "EGP" قبل السعر، ولو اللغة هي العربية ('ar')، بيتم إضافة "جنيه" بعد السعر. النتيجة النهائية هي نص يمثل السعر بشكل جميل مع العملة.
    return f"EGP {p:,.0f}" if lang == 'en' else f"{p:,.0f} جنيه"


def _cart_totals(s, items):#ثم حساب المجموع الفرعي (subtotal) والضريبة (tax) وتكلفة الشحن (shipping) والمجموع الكلي (grand total) بناءً على العناصر الموجودة في عربة التسوق والإعدادات المتعلقة بالضرائب والشحن. بيبدأ بحساب المجموع الفرعي عن طريق ضرب سعر كل منتج في كميته وجمعهم مع بعض. بعدين بيحسب الضريبة بناءً على معدل الضريبة المحدد في الإعدادات. بعد كده بيحدد تكلفة الشحن، اللي بتكون مجانية إذا كان المجموع الفرعي أكبر من حد معين (free_shipping_threshold)، أو بتكون تكلفة ثابتة إذا كان أقل من الحد ده. في النهاية، بيجمع كل الأجزاء دي مع بعض للحصول على المجموع الكلي.
    """Calculate subtotal, tax, shipping and grand total from cart items."""
    sub  = sum(i['price'] * i['quantity'] for i in items)
    rate = float(s.get('tax_rate') or 14) / 100
    sc   = float(s.get('shipping_cost') or 50)
    ft   = float(s.get('free_shipping_threshold') or 500)
    tax  = round(sub * rate, 2)
    ship = 0 if sub >= ft else sc
    return sub, tax, ship, sub + tax + ship


def allowed_file(filename):#ث   م التحقق مما إذا كان اسم الملف يحتوي على امتداد مسموح به بناءً على قائمة الامتدادات المحددة في ALLOWED_EXTENSIONS. بيبدأ بالتحقق إذا كان اسم الملف يحتوي على نقطة (.)، وبعدين بيأخذ الجزء بعد آخر نقطة ويحولها إلى حروف صغيرة، وبعدين بيشيك إذا كان هذا الامتداد موجود في مجموعة الامتدادات المسموح بها. النتيجة النهائية هي قيمة بوليانية (True أو False) تشير إلى ما إذا كان الملف مسموح به أم لا.
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_photo(file):#ثم حفظ الملف المرفوع (عادة صورة) في مجلد التحميلات (UPLOAD_DIR) بعد التحقق من أنه ملف صالح ومسموح به. بيبدأ بالتحقق إذا كان الملف موجودًا ولديه اسم ملف، وبعدين بيشيك إذا كان امتداد الملف مسموح به. إذا كانت كل الشروط دي متوفرة، بيقوم بإنشاء مجلد التحميلات إذا ما كانش موجود، وبعدين بيولد اسم ملف جديد باستخدام UUID للحفاظ على تفرده، وبعدين بيحفظ الملف في المجلد ويرجع المسار النسبي للملف المحفوظ لاستخدامه لاحقًا (مثل تخزينه في قاعدة البيانات).
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, filename))
    return f"/static/uploads/{filename}"


def delete_photo_file(photo_url):#ثم حذف ملف الصورة المرتبط بمنتج معين من مجلد التحميلات إذا كان موجودًا. بيبدأ بالتحقق إذا كان URL الصورة موجودًا، وبعدين بيبني المسار الكامل للملف بناءً على BASE_DIR وphoto_url. بعدين بيشيك إذا كان الملف موجود في النظام، وإذا كان موجود بيحاول حذفه باستخدام os.remove. إذا حدث خطأ أثناء الحذف (مثل عدم وجود الملف أو مشاكل في الأذونات)، بيتم تجاهل الخطأ بدون رفع استثناء.
    if not photo_url:
        return
    path = os.path.join(BASE_DIR, photo_url.lstrip('/'))
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _ensure_sid():
    """Create a session ID for the cart if one doesn't exist yet."""
    if 'sid' not in session:
        session['sid'] = os.urandom(16).hex()
    return session['sid']


# ════════════════════════════════════════════════════════════
#  JINJA GLOBALS & CONTEXT PROCESSOR #الهدف من الجزء ده هو إضافة بعض المتغيرات والدوال كعناصر عامة (globals) في بيئة Jinja، بحيث تكون متاحة في كل القوالب بدون الحاجة لتمريرها صراحة في كل مرة. بيتم تحديث globals بإضافة دوال مثل cart_count لحساب عدد المنتجات في العربة، get_setting للوصول إلى الإعدادات، fmt_price لتنسيق الأسعار، وget_lang للحصول على اللغة الحالية. كمان بيتم إضافة فلتر enumerate لاستخدامه في القوالب. بالإضافة إلى ذلك، يتم تعريف context processor يقوم بحقن كل الإعدادات واللغة الحالية في سياق القالب، مما يجعلها متاحة تلقائيًا في كل القوالب دون الحاجة لتمريرها يدويًا.
# ════════════════════════════════════════════════════════════

app.jinja_env.globals.update(#بإضافة المتغيرات والدوال كعناصر عامة في بيئة Jinja
    cart_count  = cart_count,
    get_setting = get_setting,
    fmt_price   = fmt_price,
    get_lang    = get_lang,
)
app.jinja_env.filters['enumerate'] = enumerate


@app.context_processor
def inject_globals():#حقن كل الإعدادات واللغة الحالية في سياق القالب
    return dict(s=get_all_settings(), lang=get_lang())


# ════════════════════════════════════════════════════════════
#  DECORATORS#الهدف من الديكوريتور ده هو حماية بعض المسارات في التطبيق بحيث لا يمكن الوصول إليها إلا إذا كان المستخدم قد قام بتسجيل الدخول كمسؤول (admin). بيتم التحقق من حالة تسجيل الدخول عن طريق فحص وجود مفتاح 'admin_logged_in' في الجلسة. إذا لم يكن المستخدم مسجلاً دخوله كمسؤول، يتم إعادة توجيهه إلى صفحة تسجيل الدخول الخاصة بالمسؤول. إذا كان المستخدم مسجلاً دخوله، يتم السماح له بالوصول إلى الوظيفة الأصلية التي تم تزيينها بالديكوريتور.
# ════════════════════════════════════════════════════════════

def admin_required(f):#بتزيين الوظائف التي تتطلب تسجيل دخول المسؤول
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════════════════════════════
#  PUBLIC ROUTES#الهدف من الجزء ده هو تعريف المسارات العامة للتطبيق، مثل الصفحة الرئيسية، صفحة المتجر، صفحة المنتج، صفحة حولنا، وصفحة الاتصال. كل مسار بيقوم بجلب البيانات اللازمة من قاعدة البيانات (مثل المنتجات المميزة، أو تفاصيل المنتج) وبيعرض القالب المناسب مع البيانات دي. كمان فيه مسار خاص لتغيير اللغة اللي بيتم تخزينها في الجلسة.
# ════════════════════════════════════════════════════════════

@app.route('/lang/<lang>')#مسار لتغيير اللغة
def switch_lang(lang):#ببساطة بيشيك إذا كانت اللغة المطلوبة ('ar' أو 'en')، وإذا كانت صحيحة بيتم تخزينها في الجلسة تحت المفتاح 'lang'. بعد كده بيتم إعادة توجيه المستخدم إلى الصفحة اللي كان فيها قبل ما يغير اللغة (باستخدام request.referrer) أو إلى الصفحة الرئيسية إذا ما كانش فيه صفحة سابقة.
    if lang in ('ar', 'en'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))


@app.route('/')#مسار الصفحة الرئيسية
def index():#بيجلب المنتجات المميزة (featured products) من قاعدة البيانات، اللي هي المنتجات اللي تم تعيينها كميزة (featured=1) ونشطة (active=1)، وبيتم ترتيبها حسب sort_order. بعد كده بيعرض قالب 'index.html' مع قائمة المنتجات المميزة دي.
    featured_products = get_db().execute(
        'SELECT * FROM products WHERE featured=1 AND active=1 ORDER BY sort_order'
    ).fetchall()
    return render_template('index.html', featured_products=featured_products)


@app.route('/shop')#مسار صفحة المتجر
def shop():#بيجلب المنتجات من قاعدة البيانات بناءً على الفئة المحددة (cat) أو استعلام البحث (q) اللي بيتم تمريرهم كمعاملات في URL. بيبدأ ببناء استعلام SQL أساسي لاختيار المنتجات النشطة، وبعدين بيضيف شروط إضافية إذا كان فيه فئة محددة أو استعلام بحث. بعد كده بيجلب المنتجات المتطابقة، وكمان بيجلب الفئات المتاحة من قاعدة البيانات لعرضها في واجهة المتجر. في النهاية، بيعرض قالب 'shop.html' مع قائمة المنتجات والفئات المختارة.
    lang = get_lang()
    cat  = request.args.get('cat', '')
    q    = request.args.get('q',   '')
    conn = get_db()

    sql, params = 'SELECT * FROM products WHERE active=1', []

    if cat:
        col = 'category_ar' if lang == 'ar' else 'category_en'
        sql    += f' AND {col}=?'
        params.append(cat)

    if q:
        sql    += ' AND (name_ar LIKE ? OR name_en LIKE ? OR desc_ar LIKE ? OR desc_en LIKE ?)'
        params += [f'%{q}%'] * 4

    sql += ' ORDER BY sort_order, id'

    products = conn.execute(sql, params).fetchall()
    cats_ar  = conn.execute('SELECT DISTINCT category_ar FROM products WHERE active=1').fetchall()
    cats_en  = conn.execute('SELECT DISTINCT category_en FROM products WHERE active=1').fetchall()

    return render_template('shop.html',
        products=products, cats_ar=cats_ar, cats_en=cats_en,
        sel_cat=cat, q=q)


@app.route('/product/<int:pid>')#مسار صفحة المنتج
def product(pid):#بيجلب تفاصيل منتج معين من قاعدة البيانات بناءً على معرف المنتج (pid) اللي بيتم تمريره في URL. بيبدأ بإنشاء اتصال بقاعدة البيانات، وبعدين بيعمل استعلام لاختيار المنتج النشط اللي يطابق المعرف المحدد. إذا ما تم العثور على المنتج، بيتم إعادة توجيه المستخدم إلى صفحة المتجر. إذا تم العثور على المنتج، بيتم جلب بعض المنتجات ذات الصلة (التي هي نشطة وليست نفس المنتج) بشكل عشوائي لعرضها كاقتراحات. في النهاية، بيعرض قالب 'product.html' مع تفاصيل المنتج والمنتجات ذات الصلة.
    conn = get_db()
    p    = conn.execute('SELECT * FROM products WHERE id=? AND active=1', (pid,)).fetchone()
    if not p:
        return redirect(url_for('shop'))
    rel = conn.execute(
        'SELECT * FROM products WHERE id!=? AND active=1 ORDER BY RANDOM() LIMIT 4', (pid,)
    ).fetchall()
    return render_template('product.html', p=p, rel=rel)


@app.route('/about')#مسار صفحة حولنا
def about():#ببساطة بيعرض قالب 'about.html' اللي بيحتوي على معلومات عن الشركة أو المتجر. ده بيستخدم لعرض قصة المتجر، قيمه، أو أي معلومات تانية حابب تشاركها مع الزوار.
    return render_template('about.html')


@app.route('/contact')#مسار صفحة الاتصال
def contact():#ببساطة بيعرض قالب 'contact.html' اللي بيحتوي على معلومات الاتصال بالشركة أو المتجر، زي العنوان، رقم الهاتف، البريد الإلكتروني، أو حتى نموذج اتصال يمكن للزوار ملؤه للتواصل معك. ده بيستخدم لتسهيل التواصل بين الزوار والشركة.
    return render_template('contact.html')


# ════════════════════════════════════════════════════════════
#  CART ROUTES#الهدف من الجزء ده هو تعريف المسارات المتعلقة بعربة التسوق، مثل إضافة منتج للعربة، عرض محتويات العربة، وتحديث الكميات أو حذف منتجات من العربة. كل مسار بيقوم بالتعامل مع قاعدة البيانات لتحديث حالة العربة بناءً على معرف الجلسة (session ID) الخاص بالمستخدم، وبيعرض القوالب المناسبة لعرض العربة أو إعادة التوجيه بعد التحديثات.
# ════════════════════════════════════════════════════════════

@app.route('/cart/add', methods=['POST'])#مسار لإضافة منتج للعربة
def cart_add():#بداية بيضمن وجود معرف جلسة (session ID) للعربة باستخدام الدالة _ensure_sid، وبعدين بيجلب معرف المنتج (pid) والكمية (qty) من بيانات النموذج المرسلة في الطلب. بعد كده بيعمل اتصال بقاعدة البيانات ويشيك إذا كان المنتج بالفعل موجود في العربة لهذا الجلسة. إذا كان موجود، بيتم تحديث الكمية بإضافة الكمية الجديدة للكمية الموجودة. إذا ما كانش موجود، بيتم إدراج صف جديد في جدول العربة مع معرف الجلسة، معرف المنتج، والكمية. بعد التحديث أو الإدراج، بيتم حساب العدد الإجمالي للمنتجات في العربة وإرجاع استجابة JSON إذا كان الطلب تم عبر Fetch API، أو إعادة توجيه المستخدم إلى الصفحة السابقة إذا كان الطلب عادي.
    sid = _ensure_sid()
    pid = request.form.get('pid', type=int)
    qty = request.form.get('qty', 1, type=int)
    conn = get_db()

    row = conn.execute(
        'SELECT id FROM cart WHERE sid=? AND product_id=?', (sid, pid)
    ).fetchone()

    if row:
        conn.execute('UPDATE cart SET quantity=quantity+? WHERE id=?', (qty, row['id']))
    else:
        conn.execute('INSERT INTO cart (sid, product_id, quantity) VALUES (?,?,?)', (sid, pid, qty))

    conn.commit()
    cnt = conn.execute(
        'SELECT COALESCE(SUM(quantity),0) FROM cart WHERE sid=?', (sid,)
    ).fetchone()[0]

    if request.headers.get('X-Fetch'):
        return jsonify(ok=True, count=cnt)
    return redirect(request.referrer or url_for('index'))


@app.route('/cart')#مسار لعرض محتويات العربة
def cart_view():#بداية بيجلب معرف الجلسة (session ID) الخاص بالعربة، وبعدين بيعمل استعلام لقاعدة البيانات لجلب كل المنتجات الموجودة في العربة لهذا الجلسة، مع تفاصيل المنتج من جدول المنتجات. بعد كده بيجلب الإعدادات اللازمة لحساب المجموع الفرعي والضريبة وتكلفة الشحن والمجموع الكلي باستخدام الدالة _cart_totals. في النهاية، بيعرض قالب 'cart.html' مع قائمة المنتجات في العربة والتكاليف المحسوبة.
    sid   = session.get('sid', '')
    items = get_db().execute(
        '''SELECT c.id, c.quantity,
                  p.id AS pid, p.name_ar, p.name_en,
                  p.price, p.image, p.photo, p.weight
           FROM cart c
           JOIN products p ON c.product_id = p.id
           WHERE c.sid=?''',
        (sid,)
    ).fetchall()

    s                   = get_all_settings()
    sub, tax, ship, total = _cart_totals(s, items)

    return render_template('cart.html',
        items=items, sub=sub, tax=tax, ship=ship, total=total,
        tax_rate   = int(s.get('tax_rate') or 14),
        ship_cost  = float(s.get('shipping_cost') or 50),
        free_thresh= float(s.get('free_shipping_threshold') or 500))


@app.route('/cart/update', methods=['POST'])#مسار لتحديث الكميات أو حذف منتجات من العربة
def cart_update():#بداية بيجلب معرف العنصر في العربة (cid) والإجراء المطلوب (action) من بيانات النموذج المرسلة في الطلب. بعد كده بيعمل اتصال بقاعدة البيانات ويشيك على نوع الإجراء. إذا كان الإجراء هو 'del'، بيتم حذف العنصر من العربة. إذا كان الإجراء هو '+'، بيتم زيادة الكمية بمقدار واحد. إذا كان الإجراء هو '-'، بيتم تقليل الكمية بمقدار واحد، وإذا كانت الكمية تصبح أقل من أو تساوي 1، بيتم حذف العنصر من العربة. بعد التحديث، بيتم حفظ التغييرات في قاعدة البيانات وإعادة توجيه المستخدم إلى صفحة العربة لعرض التحديثات.
    cid    = request.form.get('cid', type=int)
    action = request.form.get('action')
    conn   = get_db()

    if action == 'del':
        conn.execute('DELETE FROM cart WHERE id=?', (cid,))
    elif action == '+':
        conn.execute('UPDATE cart SET quantity=quantity+1 WHERE id=?', (cid,))
    elif action == '-':
        row = conn.execute('SELECT quantity FROM cart WHERE id=?', (cid,)).fetchone()
        if row and row['quantity'] > 1:
            conn.execute('UPDATE cart SET quantity=quantity-1 WHERE id=?', (cid,))
        else:
            conn.execute('DELETE FROM cart WHERE id=?', (cid,))

    conn.commit()
    return redirect(url_for('cart_view'))


# ════════════════════════════════════════════════════════════
#  CHECKOUT & ORDER ROUTES#الهدف من الجزء ده هو تعريف المسارات المتعلقة بعملية الدفع والطلبات، مثل صفحة الدفع (checkout)، معالجة الدفع (pay)، وعرض تفاصيل الطلب (success). كل مسار بيقوم بالتعامل مع قاعدة البيانات لجلب المعلومات اللازمة عن العربة، حساب التكاليف، إنشاء الطلبات وتفاصيلها، وأخيرًا عرض صفحة تأكيد الطلب مع تفاصيله.
# ════════════════════════════════════════════════════════════

@app.route('/checkout')#مسار صفحة الدفع
def checkout():#بداية بيجلب معرف الجلسة (session ID) الخاص بالعربة، وبعدين بيعمل استعلام لقاعدة البيانات لجلب كل المنتجات الموجودة في العربة لهذا الجلسة، مع تفاصيل المنتج من جدول المنتجات. إذا ما كانش فيه منتجات في العربة، بيتم إعادة توجيه المستخدم إلى صفحة العربة. إذا كان فيه منتجات، بيتم جلب الإعدادات اللازمة لحساب المجموع الفرعي والضريبة وتكلفة الشحن والمجموع الكلي باستخدام الدالة _cart_totals. في النهاية، بيعرض قالب 'checkout.html' مع قائمة المنتجات في العربة والتكاليف المحسوبة والإعدادات المتعلقة بالضرائب والشحن.
    sid   = session.get('sid', '')
    items = get_db().execute(
        '''SELECT c.id, c.quantity,
                  p.id AS pid, p.name_ar, p.name_en,
                  p.price, p.image, p.photo
           FROM cart c
           JOIN products p ON c.product_id = p.id
           WHERE c.sid=?''',
        (sid,)
    ).fetchall()

    if not items:
        return redirect(url_for('cart_view'))

    s                    = get_all_settings()
    sub, tax, ship, total = _cart_totals(s, items)

    return render_template('checkout.html',
        items=items, sub=sub, tax=tax, ship=ship, total=total,
        tax_rate   = int(s.get('tax_rate') or 14),
        ship_cost  = float(s.get('shipping_cost') or 50),
        free_thresh= float(s.get('free_shipping_threshold') or 500))


@app.route('/pay', methods=['POST'])#مسار لمعالجة الدفع وإنشاء الطلب
def pay():#بداية بيجلب اللغة الحالية من الجلسة، وبعدين بيجلب معرف الجلسة (session ID) الخاص بالعربة، وبعدين بيعمل استعلام لقاعدة البيانات لجلب كل المنتجات الموجودة في العربة لهذا الجلسة، مع تفاصيل المنتج من جدول المنتجات. إذا ما كانش فيه منتجات في العربة، بيتم إعادة توجيه المستخدم إلى صفحة العربة. إذا كان فيه منتجات، بيتم جلب الإعدادات اللازمة لحساب المجموع الفرعي والضريبة وتكلفة الشحن والمجموع الكلي باستخدام الدالة _cart_totals. بعد كده بيجلب طريقة الدفع المختارة من بيانات النموذج المرسلة في الطلب، وإذا كانت طريقة الدفع هي 'card'، بيتم استخراج آخر 4 أرقام من رقم البطاقة المدخل. بعد كده بيتم إنشاء رقم طلب فريد باستخدام تاريخ اليوم ورموز عشوائية. ثم يتم إدراج الطلب الجديد في جدول الطلبات (orders) مع جميع التفاصيل اللازمة، وبعدها يتم إدراج كل عنصر من عناصر العربة في جدول تفاصيل الطلب (order_items). أخيرًا، يتم حذف كل العناصر من العربة لهذا الجلسة وتأكيد الطلب بنجاح عن طريق إعادة توجيه المستخدم إلى صفحة تأكيد الطلب.
    lang = get_lang()
    sid  = session.get('sid', '')
    conn = get_db()

    items = conn.execute(
        '''SELECT c.quantity, p.id AS pid, p.name_ar, p.name_en, p.price
           FROM cart c
           JOIN products p ON c.product_id = p.id
           WHERE c.sid=?''',
        (sid,)
    ).fetchall()

    if not items:
        return redirect(url_for('cart_view'))

    s                    = get_all_settings()
    sub, tax, ship, grand = _cart_totals(s, items)

    payment_method = request.form.get('payment_method', 'card')
    last4 = None
    if payment_method == 'card':
        card  = request.form.get('card_number', '').replace(' ', '')
        last4 = card[-4:] if len(card) >= 4 else '****'

    order_number = f"SLF-{datetime.now().strftime('%y%m%d')}-{os.urandom(3).hex().upper()}"

    oid = conn.execute(
        '''INSERT INTO orders
           (order_number, full_name, phone, city, address,
            total, tax, grand_total, payment_method, card_last4, lang)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (order_number,
         request.form.get('full_name'), request.form.get('phone'),
         request.form.get('city'),      request.form.get('address'),
         sub, tax, grand, payment_method, last4, lang)
    ).lastrowid

    conn.executemany(
        'INSERT INTO order_items (order_id, product_id, name, price, quantity) VALUES (?,?,?,?,?)',
        [(oid, i['pid'],
          i['name_ar'] if lang == 'ar' else i['name_en'],
          i['price'], i['quantity'])
         for i in items]
    )

    conn.execute('DELETE FROM cart WHERE sid=?', (sid,))
    conn.commit()
    return redirect(url_for('success', oid=oid))


@app.route('/order/<int:oid>')#مسار لعرض تفاصيل الطلب بعد نجاح الدفع
def success(oid):#بداية بيجلب تفاصيل طلب معين من قاعدة البيانات بناءً على معرف الطلب (oid) اللي بيتم تمريره في URL. بيبدأ بإنشاء اتصال بقاعدة البيانات، وبعدين بيعمل استعلام لاختيار الطلب الذي يطابق المعرف المحدد. إذا ما تم العثور على الطلب، بيتم إعادة توجيه المستخدم إلى الصفحة الرئيسية. إذا تم العثور على الطلب، بيتم جلب كل العناصر المرتبطة بهذا الطلب من جدول تفاصيل الطلب (order_items). في النهاية، بيعرض قالب 'success.html' مع تفاصيل الطلب والعناصر المرتبطة به.
    conn  = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not order:
        return redirect(url_for('index'))
    items = conn.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall()
    return render_template('success.html', order=order, items=items)


@app.route('/track')
def track():
    """Order tracking page — customer looks up their order by number + phone."""
    order_number = request.args.get('order_number', '').strip()
    phone        = request.args.get('phone', '').strip()

    if not order_number and not phone:
        # First visit — show empty form
        return render_template('track.html', order=None, error=False)

    conn  = get_db()
    order = conn.execute(
        'SELECT * FROM orders WHERE order_number=? AND phone=?',
        (order_number, phone)
    ).fetchone()

    if not order:
        return render_template('track.html', order=None, error=True)

    return render_template('track.html', order=order, error=False)


# ════════════════════════════════════════════════════════════
#  ADMIN — AUTH#الهدف من الجزء ده هو تعريف المسارات المتعلقة بتسجيل الدخول وتسجيل الخروج للمسؤول (admin). بيتم التحقق من بيانات تسجيل الدخول مقابل القيم المخزنة في المتغيرات ADMIN_USER وADMIN_PASS، وإذا كانت صحيحة، يتم تعيين حالة تسجيل الدخول في الجلسة. كمان فيه مسار لتسجيل الخروج بيقوم بإزالة حالة تسجيل الدخول من الجلسة وإعادة توجيه المستخدم إلى صفحة تسجيل الدخول.
# ════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])#مسار لتسجيل الدخول للمسؤول
def admin_login():#بداية بيشيك إذا كان المستخدم بالفعل مسجلاً دخوله كمسؤول عن طريق فحص وجود مفتاح 'admin_logged_in' في الجلسة. إذا كان المستخدم مسجلاً دخوله، بيتم إعادة توجيهه مباشرة إلى لوحة التحكم الخاصة بالمسؤول (admin_dashboard). إذا ما كانش مسجلاً دخوله، بيتم التحقق إذا كان الطلب هو POST، وفي حالة POST بيتم مقارنة بيانات تسجيل الدخول (اسم المستخدم وكلمة المرور) مع القيم المخزنة في المتغيرات ADMIN_USER وADMIN_PASS. إذا كانت البيانات صحيحة، يتم تعيين حالة تسجيل الدخول في الجلسة وإعادة توجيه المستخدم إلى لوحة التحكم. إذا كانت البيانات غير صحيحة، يتم عرض صفحة تسجيل الدخول مرة أخرى مع رسالة خطأ. إذا كان الطلب هو GET، يتم عرض صفحة تسجيل الدخول بدون رسالة خطأ.
    if request.method == 'POST':
        if (request.form.get('username') == ADMIN_USER and
                request.form.get('password') == ADMIN_PASS):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error=True)
    return render_template('admin/login.html', error=False)


@app.route('/admin/logout')#مسار لتسجيل الخروج للمسؤول
def admin_logout():#ببساطة بيقوم بإزالة مفتاح 'admin_logged_in' من الجلسة باستخدام session.pop، مما يعني أن المستخدم لم يعد مسجلاً دخوله كمسؤول. بعد كده بيتم إعادة توجيه المستخدم إلى صفحة تسجيل الدخول الخاصة بالمسؤول.
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# ════════════════════════════════════════════════════════════
#  ADMIN — DASHBOARD#الهدف من الجزء ده هو تعريف مسار لوحة التحكم الخاصة بالمسؤول (admin_dashboard) اللي بيعرض إحصائيات وأداء المتجر بشكل عام. بيتم جلب بيانات مختلفة من قاعدة البيانات مثل عدد المنتجات، عدد الطلبات، إجمالي الإيرادات، متوسط قيمة الطلب، عدد العملاء، عدد المنتجات المباعة، المدينة الأكثر طلبًا، حالة الطلبات، الإيرادات اليومية لآخر 7 أيام، وأفضل المنتجات. بعد جلب كل البيانات دي، بيتم عرض قالب 'admin/dashboard.html' مع كل الإحصائيات والبيانات دي لتمكين المسؤول من مراقبة أداء المتجر واتخاذ القرارات المناسبة.
# ════════════════════════════════════════════════════════════

@app.route('/admin')#مسار لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_dashboard():#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب مجموعة من الإحصائيات والبيانات المختلفة عن المتجر. بيبدأ بجلب عدد المنتجات النشطة، عدد الطلبات، إجمالي الإيرادات، متوسط قيمة الطلب، عدد العملاء الفريدين، وعدد المنتجات المباعة. بعد كده بيجلب المدينة الأكثر طلبًا بناءً على عدد الطلبات لكل مدينة. بعدين بيجلب عدد الطلبات لكل حالة (مثل "قيد الانتظار"، "تم الشحن"، "تم التسليم"، إلخ). بعد كده بيجلب الإيرادات اليومية لآخر 7 أيام لعرضها في رسم بياني. وأخيرًا، بيجلب أفضل 5 منتجات بناءً على الكمية المباعة والإيرادات. في النهاية، بيعرض قالب 'admin/dashboard.html' مع كل هذه البيانات والإحصائيات.
    conn = get_db()

    # ── Core stats ───────────────────────────────────────────
    total_products   = conn.execute('SELECT COUNT(*) FROM products WHERE active=1').fetchone()[0]#بيجلب عدد المنتجات النشطة من قاعدة البيانات عن طريق تنفيذ استعلام SQL يحسب عدد الصفوف في جدول المنتجات (products) حيث يكون العمود active يساوي 1. النتيجة النهائية هي عدد المنتجات النشطة المتاحة في المتجر.
    total_orders     = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]#
    total_revenue    = conn.execute('SELECT COALESCE(SUM(grand_total),0) FROM orders').fetchone()[0]
    avg_order        = conn.execute('SELECT COALESCE(AVG(grand_total),0) FROM orders').fetchone()[0]
    total_customers  = conn.execute('SELECT COUNT(DISTINCT phone) FROM orders').fetchone()[0]
    total_items_sold = conn.execute('SELECT COALESCE(SUM(quantity),0) FROM order_items').fetchone()[0]

    # ── Top city ─────────────────────────────────────────────
    top_city_row = conn.execute(
        'SELECT city, COUNT(*) as cnt FROM orders GROUP BY city ORDER BY cnt DESC LIMIT 1'
    ).fetchone()
    top_city = top_city_row['city'] if top_city_row else None

    # ── Order status counts ──────────────────────────────────
    status_rows   = conn.execute('SELECT status, COUNT(*) as cnt FROM orders GROUP BY status').fetchall()
    status_counts = {r['status']: r['cnt'] for r in status_rows}

    # ── Daily revenue — last 7 days ──────────────────────────
    daily_rows = conn.execute(
        '''SELECT DATE(created_at) as day, COALESCE(SUM(grand_total),0) as rev
           FROM orders
           WHERE created_at >= DATE('now', '-6 days')
           GROUP BY DATE(created_at)
           ORDER BY day'''
    ).fetchall()
    daily_revenues = [(r['day'][-5:], r['rev']) for r in daily_rows]  # MM-DD format

    # ── Top products ─────────────────────────────────────────
    top_products = conn.execute(
        '''SELECT p.name_ar, p.image,
                  SUM(oi.quantity) as total_qty,
                  SUM(oi.quantity * oi.price) as total_rev
           FROM order_items oi
           JOIN products p ON oi.product_id = p.id
           GROUP BY oi.product_id
           ORDER BY total_qty DESC
           LIMIT 5'''
    ).fetchall()
    top_products = [(r['name_ar'], r['image'], r['total_qty'], r['total_rev']) for r in top_products]

    recent_orders = conn.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 5').fetchall()

    return render_template('admin/dashboard.html',
        total_products   = total_products,
        total_orders     = total_orders,
        total_revenue    = total_revenue,
        avg_order        = avg_order,
        total_customers  = total_customers,
        total_items_sold = total_items_sold,
        top_city         = top_city,
        status_counts    = status_counts,
        daily_revenues   = daily_revenues,
        top_products     = top_products,
        recent_orders    = recent_orders,
    )


# ════════════════════════════════════════════════════════════
#  ADMIN — PRODUCTS#
# ════════════════════════════════════════════════════════════

@app.route('/admin/products')#مسار لإدارة المنتجات في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_products():#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب كل المنتجات من جدول المنتجات (products) مرتبة حسب sort_order ثم id. النتيجة النهائية هي قائمة بكل المنتجات المتاحة في المتجر، والتي يتم تمريرها إلى قالب 'admin/products.html' لعرضها في واجهة إدارة المنتجات في لوحة التحكم الخاصة بالمسؤول.
    products = get_db().execute(
        'SELECT * FROM products ORDER BY sort_order, id'
    ).fetchall()
    return render_template('admin/products.html', products=products)


def _product_fields_from_form():#
    """Extract and coerce product fields from POST form."""
    f = request.form
    return (#بتجميع الحقول المطلوبة لإنشاء أو تحديث منتج من بيانات النموذج المرسلة في الطلب. بيبدأ بإنشاء متغير f للإشارة إلى request.form، وبعدين بيقوم بجلب الحقول المختلفة مثل الاسم بالعربية والإنجليزية، الوصف بالعربية والإنجليزية، السعر، السعر القديم، صورة المنتج، الفئة بالعربية والإنجليزية، الوزن، بلد المنشأ بالعربية والإنجليزية، المخزون، إذا كان المنتج مميزًا أو نشطًا، وترتيب العرض. كل حقل يتم جلبه من النموذج ويتم تحويله إلى النوع المناسب (مثل float للأسعار وint للمخزون) قبل إرجاعها كقائمة مرتبة.
        f.get('name_ar'),  f.get('name_en'),
        f.get('desc_ar'),  f.get('desc_en'),
        float(f.get('price', 0)),
        float(f.get('old_price')) if f.get('old_price') else None,
        f.get('image', '🫒'),
        f.get('category_ar'), f.get('category_en'),
        f.get('weight'),
        f.get('origin_ar'),   f.get('origin_en'),
        int(f.get('stock', 100)),
        1 if f.get('featured') else 0,
        1 if f.get('active')   else 0,
        int(f.get('sort_order', 0)),
    )


@app.route('/admin/products/add', methods=['GET', 'POST'])#مسار لإضافة منتج جديد في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_product_add():#بداية بيشيك إذا كان الطلب هو POST، وفي حالة POST بيتم حفظ الصورة المرفوعة باستخدام الدالة save_uploaded_photo، وبعدين بيتم استخراج الحقول المطلوبة لإنشاء المنتج من بيانات النموذج باستخدام الدالة _product_fields_from_form. بعد كده بيتم إدراج المنتج الجديد في جدول المنتجات (products) مع الحقول المستخرجة، ويتم حفظ التغييرات في قاعدة البيانات. بعد الإنشاء، يتم عرض رسالة نجاح وإعادة توجيه المستخدم إلى صفحة إدارة المنتجات. إذا كان الطلب هو GET، يتم عرض قالب 'admin/product_form.html' مع بعض المتغيرات الافتراضية لعرض نموذج إضافة منتج جديد.
    if request.method == 'POST':
        photo = save_uploaded_photo(request.files.get('photo'))
        fields = _product_fields_from_form()
        get_db().execute(
            '''INSERT INTO products
               (name_ar, name_en, desc_ar, desc_en, price, old_price, image, photo,
                category_ar, category_en, weight, origin_ar, origin_en,
                stock, featured, active, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            fields[:6] + (photo,) + fields[7:]
        )
        get_db().commit()
        flash('تم إضافة المنتج بنجاح! ✅', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html',
                           product=None, action='add', cats=get_categories())


@app.route('/admin/products/edit/<int:pid>', methods=['GET', 'POST'])#مسار لتعديل منتج موجود في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_product_edit(pid):#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب تفاصيل المنتج الذي يطابق معرف المنتج (pid) المحدد. إذا ما تم العثور على المنتج، بيتم إعادة توجيه المستخدم إلى صفحة إدارة المنتجات. إذا تم العثور على المنتج، بيشيك إذا كان الطلب هو POST، وفي حالة POST بيتم حفظ الصورة المرفوعة (إذا كانت موجودة) باستخدام الدالة save_uploaded_photo، وإذا تم رفع صورة جديدة يتم حذف الصورة القديمة باستخدام الدالة delete_photo_file. بعد كده بيتم استخراج الحقول المطلوبة لتحديث المنتج من بيانات النموذج باستخدام الدالة _product_fields_from_form. ثم يتم تحديث المنتج في جدول المنتجات (products) مع الحقول المستخرجة، ويتم حفظ التغييرات في قاعدة البيانات. بعد التحديث، يتم عرض رسالة نجاح وإعادة توجيه المستخدم إلى صفحة إدارة المنتجات. إذا كان الطلب هو GET، يتم عرض قالب 'admin/product_form.html' مع تفاصيل المنتج الحالي لعرض نموذج تعديل المنتج.
    conn = get_db()
    p    = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not p:
        return redirect(url_for('admin_products'))

    if request.method == 'POST':
        photo_url = p['photo']
        new_photo = save_uploaded_photo(request.files.get('photo'))
        if new_photo:
            delete_photo_file(photo_url)
            photo_url = new_photo
        elif request.form.get('remove_photo'):
            delete_photo_file(photo_url)
            photo_url = None

        fields = _product_fields_from_form()
        conn.execute(
            '''UPDATE products SET
               name_ar=?, name_en=?, desc_ar=?, desc_en=?,
               price=?, old_price=?, image=?, photo=?,
               category_ar=?, category_en=?, weight=?,
               origin_ar=?, origin_en=?,
               stock=?, featured=?, active=?, sort_order=?
               WHERE id=?''',
            fields[:6] + (photo_url,) + fields[7:] + (pid,)
        )
        conn.commit()
        flash('تم تعديل المنتج بنجاح! ✅', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html',
                           product=p, action='edit', cats=get_categories())


@app.route('/admin/products/delete/<int:pid>', methods=['POST'])#مسار لحذف منتج موجود في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_product_delete(pid):#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب تفاصيل المنتج الذي يطابق معرف المنتج (pid) المحدد. إذا تم العثور على المنتج، بيتم حذف ملف الصورة المرتبط به باستخدام الدالة delete_photo_file. بعد كده بيتم حذف المنتج من جدول المنتجات (products) بناءً على معرف المنتج. ثم يتم حفظ التغييرات في قاعدة البيانات، وعرض رسالة نجاح، وإعادة توجيه المستخدم إلى صفحة إدارة المنتجات.
    conn = get_db()
    row  = conn.execute('SELECT photo FROM products WHERE id=?', (pid,)).fetchone()
    if row:
        delete_photo_file(row['photo'])
    conn.execute('DELETE FROM products WHERE id=?', (pid,))
    conn.commit()
    flash('تم حذف المنتج نهائياً ✅', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/toggle/<int:pid>', methods=['POST'])#مسار لتفعيل أو إيقاف منتج موجود في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_product_toggle(pid):#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب حالة التفعيل (active) للمنتج الذي يطابق معرف المنتج (pid) المحدد. إذا تم العثور على المنتج، بيتم عكس حالة التفعيل (إذا كانت مفعلة تصبح غير مفعلة، وإذا كانت غير مفعلة تصبح مفعلة). بعد كده بيتم تحديث حالة التفعيل في جدول المنتجات (products) بناءً على معرف المنتج. ثم يتم حفظ التغييرات في قاعدة البيانات، وعرض رسالة نجاح توضح ما إذا تم تفعيل المنتج أو إيقافه، وإعادة توجيه المستخدم إلى صفحة إدارة المنتجات.
    conn = get_db()
    row  = conn.execute('SELECT active FROM products WHERE id=?', (pid,)).fetchone()
    if row:
        new_status = 0 if row['active'] else 1
        conn.execute('UPDATE products SET active=? WHERE id=?', (new_status, pid))
        conn.commit()
        flash('تم تفعيل المنتج ✅' if new_status else 'تم إيقاف المنتج ⏸️', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/upload-photo', methods=['POST'])#مسار لتحميل صورة منتج في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_upload_photo():#بداية بيجلب الملف المرفوع من بيانات الطلب باستخدام request.files.get('photo')، وبعدين بيجلب معرف المنتج (pid) من بيانات النموذج باستخدام request.form.get('pid'). بعد كده بيتم حفظ الصورة المرفوعة باستخدام الدالة save_uploaded_photo، والتي ترجع عنوان URL للصورة المحفوظة. إذا لم يتم دعم صيغة الملف أو حدث خطأ أثناء الحفظ، يتم إرجاع استجابة JSON تحتوي على خطأ. إذا تم رفع الصورة بنجاح، وإذا كان معرف المنتج موجودًا، يتم جلب الصورة القديمة من قاعدة البيانات وحذفها باستخدام الدالة delete_photo_file، ثم يتم تحديث سجل المنتج في قاعدة البيانات بعنوان URL للصورة الجديدة. في النهاية، يتم إرجاع استجابة JSON تحتوي على نجاح العملية وعنوان URL للصورة الجديدة.
    file      = request.files.get('photo')
    pid       = request.form.get('pid', type=int)
    photo_url = save_uploaded_photo(file)

    if not photo_url:
        return jsonify(ok=False, error='صيغة الملف غير مدعومة'), 400

    if pid:
        conn = get_db()
        old  = conn.execute('SELECT photo FROM products WHERE id=?', (pid,)).fetchone()
        if old:
            delete_photo_file(old['photo'])
        conn.execute('UPDATE products SET photo=? WHERE id=?', (photo_url, pid))
        conn.commit()

    return jsonify(ok=True, url=photo_url)


# ════════════════════════════════════════════════════════════
#  ADMIN — ORDERS#الهدف من الجزء ده هو تعريف المسارات المتعلقة بإدارة الطلبات في لوحة التحكم الخاصة بالمسؤول، مثل عرض قائمة الطلبات، تحديث حالة الطلب، وعرض فاتورة الطلب. كل مسار بيقوم بالتعامل مع قاعدة البيانات لجلب المعلومات اللازمة عن الطلبات، تحديث حالتها، وعرض التفاصيل المتعلقة بكل طلب.
# ════════════════════════════════════════════════════════════

@app.route('/admin/orders')#مسار لعرض قائمة الطلبات في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_orders():#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب كل الطلبات من جدول الطلبات (orders) مرتبة حسب معرف الطلب (id) بشكل تنازلي. النتيجة النهائية هي قائمة بكل الطلبات الموجودة في المتجر، والتي يتم تمريرها إلى قالب 'admin/orders.html' لعرضها في واجهة إدارة الطلبات في لوحة التحكم الخاصة بالمسؤول.
    orders = get_db().execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/status/<int:oid>', methods=['POST'])#مسار لتحديث حالة طلب معين في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_order_status(oid):#بداية بيجلب الحالة الجديدة من بيانات النموذج باستخدام request.form.get('status')، وإذا لم يتم توفير حالة جديدة، يتم تعيينها إلى 'confirmed' بشكل افتراضي. بعد كده بيتم التحقق إذا كانت الحالة الجديدة موجودة في قائمة الحالات الصالحة (VALID_ORDER_STATUSES)، وإذا لم تكن موجودة، يتم تعيينها إلى 'confirmed'. ثم يتم عمل اتصال بقاعدة البيانات وتحديث حالة الطلب في جدول الطلبات (orders) بناءً على معرف الطلب (oid). بعد حفظ التغييرات في قاعدة البيانات، يتم عرض رسالة نجاح تفيد بأنه تم تحديث حالة الطلب بنجاح، ويتم إعادة توجيه المستخدم إلى صفحة إدارة الطلبات.
    status = request.form.get('status', 'confirmed')
    if status not in VALID_ORDER_STATUSES:
        status = 'confirmed'
    conn = get_db()
    conn.execute('UPDATE orders SET status=? WHERE id=?', (status, oid))
    conn.commit()
    flash('تم تحديث حالة الطلب ✅', 'success')
    return redirect(url_for('admin_orders'))


@app.route('/admin/orders/invoice/<int:oid>')#مسار لعرض فاتورة طلب معين في لوحة التحكم الخاصة بالمسؤول
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم 
def admin_order_invoice(oid):#بداية بيعمل اتصال بقاعدة البيانات، وبعدين بيجلب تفاصيل الطلب الذي يطابق معرف الطلب (oid) المحدد. إذا ما تم العثور على الطلب، بيتم إعادة توجيه المستخدم إلى صفحة إدارة الطلبات. إذا تم العثور على الطلب، بيتم جلب كل العناصر المرتبطة بهذا الطلب من جدول تفاصيل الطلب (order_items). في النهاية، بيعرض قالب 'admin/invoice.html' مع تفاصيل الطلب والعناصر المرتبطة به لعرض فاتورة الطلب في لوحة التحكم الخاصة بالمسؤول.
    conn  = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not order:
        return redirect(url_for('admin_orders'))
    items = conn.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall()
    return render_template('admin/invoice.html', order=order, items=items)


# ════════════════════════════════════════════════════════════
#  ADMIN — SETTINGS#الهدف من الجزء ده هو تعريف مسار إعدادات المسؤول (admin_settings) اللي بيتيح للمسؤول تعديل الإعدادات العامة للمتجر، مثل الضرائب، الشحن، والفئات المخصصة. بيتم التعامل مع بيانات النموذج المرسلة في الطلب لتحديث الإعدادات في قاعدة البيانات، وبعد التحديث يتم عرض رسالة نجاح وإعادة توجيه المستخدم إلى صفحة الإعدادات. إذا كان الطلب هو GET، يتم عرض قالب 'admin/settings.html' مع الإعدادات الحالية والفئات المتاحة لتمكين المسؤول من تعديلها.
# ════════════════════════════════════════════════════════════

@app.route('/admin/settings', methods=['GET', 'POST'])#
@admin_required#تزيين المسار بالديكوريتور admin_required لضمان أن الوصول له بيكون فقط للمسؤولين المسجلين دخولهم
def admin_settings():#بداية بيشيك إذا كان الطلب هو POST، وفي حالة POST بيتم عمل اتصال بقاعدة البيانات. بعد كده بيتم استخراج الحقول المتعلقة بالفئات المخصصة من بيانات النموذج باستخدام حلقة while لجمع كل الفئات المرسلة في النموذج. ثم يتم تحديث الإعدادات في جدول الإعدادات (settings) مع الحقول المستخرجة، ويتم حفظ التغييرات في قاعدة البيانات. بعد التحديث، يتم عرض رسالة نجاح وإعادة توجيه المستخدم إلى صفحة الإعدادات. إذا كان الطلب هو GET، يتم عرض قالب 'admin/settings.html' مع الإعدادات الحالية والفئات المتاحة لتمكين المسؤول من تعديلها.
    if request.method == 'POST':
        conn = get_db()

        # Parse dynamic category fields
        cats, i = [], 0
        while True:
            ar = request.form.get(f'cat_ar_{i}')
            en = request.form.get(f'cat_en_{i}')
            if ar is None and en is None:
                break
            if ar or en:
                cats.append({'ar': ar or '', 'en': en or ''})
            i += 1

        conn.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)',
            ('custom_categories', json.dumps(cats, ensure_ascii=False))
        )

        cat_keys = {k for k in request.form if k.startswith(('cat_ar_', 'cat_en_'))}
        conn.executemany(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)',
            [(k, v) for k, v in request.form.items() if k not in cat_keys]
        )
        conn.commit()
        flash('تم حفظ الإعدادات بنجاح! ✅', 'success')
        return redirect(url_for('admin_settings'))

    return render_template('admin/settings.html',
                           s=get_all_settings(), cats=get_categories())


# ════════════════════════════════════════════════════════════
#  ENTRY POINT#الهدف من الجزء ده هو نقطة الدخول الرئيسية لتشغيل التطبيق. بيتم استدعاء دالة init_db() لتهيئة قاعدة البيانات، ثم يتم طباعة بعض الرسائل في وحدة التحكم لتوضيح أن التطبيق جاهز للعمل وعرض معلومات حول لوحة التحكم الخاصة بالمسؤول. أخيرًا، يتم تشغيل التطبيق باستخدام app.run() مع تمكين وضع التصحيح (debug) وتحديد المنفذ 5000.
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()
    print("✅  سلافة SULAFA  — http://localhost:5000")
    print("🔧  Admin Panel   — http://localhost:5000/admin")
    print(f"    User: {ADMIN_USER} | Pass: {ADMIN_PASS}")
    app.run(debug=True, port=5000)
