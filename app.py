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
app.secret_key = os.environ.get('SECRET_KEY', 'sulafa_secret_2024_secure')

# ── Paths ────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
DB_PATH      = os.path.join(BASE_DIR, 'sulafa.db')
UPLOAD_DIR   = os.path.join(BASE_DIR, 'static', 'uploads')

# ── Config ───────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ADMIN_USER         = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS         = os.environ.get('ADMIN_PASS', 'sulafa2024')

VALID_ORDER_STATUSES = {'confirmed', 'pending', 'shipped', 'cancelled'}


# ════════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════════

def get_db():
    """Return a per-request SQLite connection (stored in Flask g)."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    """Close the DB connection at the end of every request."""
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def init_db():
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
            weight         TEXT    DEFAULT '750ml',
            origin_ar      TEXT    DEFAULT 'اليونان',
            origin_en      TEXT    DEFAULT 'Greece',
            stock          INTEGER DEFAULT 100,
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
        'hero_sub_ar':         'اذوق جوهر البحر المتوسط',
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
             'زيت زيتون بكر ممتاز معصور على البارد من أجود الزيتون اليونانى. غنى بمضادات الأكسدة.',
             'Cold pressed extra virgin olive oil from the finest Greek olives. Rich in antioxidants.',
             189.00, 249.00, '🫒', None, 'بكر ممتاز', 'Extra Virgin', '750ml', 'اليونان', 'Greece', 60, 4.9, 312, 1, 1, 1),

            ('زيت الزيتون العضوى', 'Organic Olive Oil',
             'زيت زيتون عضوى معتمد دولياً، بدون مبيدات أو مواد كيميائية.',
             'Internationally certified organic olive oil. No pesticides or chemicals.',
             229.00, 299.00, '🌿', None, 'عضوى', 'Organic', '500ml', 'تونس', 'Tunisia', 45, 4.8, 198, 1, 1, 2),

            ('زيت الزيتون بالثوم', 'Garlic Infused Olive Oil',
             'مزيج فاخر من زيت الزيتون البكر مع الثوم الطبيعى. رائع للشوايات.',
             'Premium blend of extra virgin olive oil with natural garlic. Perfect for grilling.',
             155.00, 199.00, '🧄', None, 'منكّه', 'Infused', '250ml', 'إيطاليا', 'Italy', 80, 4.7, 145, 1, 1, 3),

            ('زيت الزيتون الإيطالى الفاخر', 'Premium Italian Olive Oil',
             'من قلب توسكانا الإيطالية. نكهة استثنائية وعطر رائع.',
             'From the heart of Tuscany, Italy. Exceptional flavor and remarkable aroma.',
             315.00, 395.00, '✨', None, 'فاخر', 'Premium', '500ml', 'إيطاليا', 'Italy', 30, 5.0, 445, 1, 1, 4),

            ('زيت الزيتون الفلسطينى', 'Palestinian Olive Oil',
             'من أشجار الزيتون المعمّرة فى فلسطين. طعم عميق وأصيل.',
             'From ancient olive trees in Palestine. Deep and authentic taste.',
             199.00, None, '🌳', None, 'بكر ممتاز', 'Extra Virgin', '750ml', 'فلسطين', 'Palestine', 40, 4.9, 521, 1, 1, 5),

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

def get_lang():
    return session.get('lang', 'ar')


def get_setting(key, default=''):
    row = get_db().execute(
        'SELECT value FROM settings WHERE key=?', (key,)
    ).fetchone()
    return row['value'] if row else default


def get_all_settings():
    rows = get_db().execute('SELECT key, value FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows}


def get_categories():
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

    result = list(custom)
    for i, cat_ar in enumerate(rows_ar):
        cat_en = rows_en[i] if i < len(rows_en) else cat_ar
        if not any(c.get('ar') == cat_ar for c in result):
            result.append({'ar': cat_ar, 'en': cat_en})
    return result


def cart_count():
    sid = session.get('sid', '')
    if not sid:
        return 0
    row = get_db().execute(
        'SELECT COALESCE(SUM(quantity),0) FROM cart WHERE sid=?', (sid,)
    ).fetchone()
    return row[0]


def fmt_price(p, lang='ar'):
    return f"EGP {p:,.0f}" if lang == 'en' else f"{p:,.0f} جنيه"


def _cart_totals(s, items):
    """Calculate subtotal, tax, shipping and grand total from cart items."""
    sub  = sum(i['price'] * i['quantity'] for i in items)
    rate = float(s.get('tax_rate') or 14) / 100
    sc   = float(s.get('shipping_cost') or 50)
    ft   = float(s.get('free_shipping_threshold') or 500)
    tax  = round(sub * rate, 2)
    ship = 0 if sub >= ft else sc
    return sub, tax, ship, sub + tax + ship


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_photo(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, filename))
    return f"/static/uploads/{filename}"


def delete_photo_file(photo_url):
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
#  JINJA GLOBALS & CONTEXT PROCESSOR
# ════════════════════════════════════════════════════════════

app.jinja_env.globals.update(
    cart_count  = cart_count,
    get_setting = get_setting,
    fmt_price   = fmt_price,
    get_lang    = get_lang,
)
app.jinja_env.filters['enumerate'] = enumerate


@app.context_processor
def inject_globals():
    return dict(s=get_all_settings(), lang=get_lang())


# ════════════════════════════════════════════════════════════
#  DECORATORS
# ════════════════════════════════════════════════════════════

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ════════════════════════════════════════════════════════════

@app.route('/lang/<lang>')
def switch_lang(lang):
    if lang in ('ar', 'en'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))


@app.route('/')
def index():
    featured_products = get_db().execute(
        'SELECT * FROM products WHERE featured=1 AND active=1 ORDER BY sort_order'
    ).fetchall()
    return render_template('index.html', featured_products=featured_products)


@app.route('/shop')
def shop():
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


@app.route('/product/<int:pid>')
def product(pid):
    conn = get_db()
    p    = conn.execute('SELECT * FROM products WHERE id=? AND active=1', (pid,)).fetchone()
    if not p:
        return redirect(url_for('shop'))
    rel = conn.execute(
        'SELECT * FROM products WHERE id!=? AND active=1 ORDER BY RANDOM() LIMIT 4', (pid,)
    ).fetchall()
    return render_template('product.html', p=p, rel=rel)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


# ════════════════════════════════════════════════════════════
#  CART ROUTES
# ════════════════════════════════════════════════════════════

@app.route('/cart/add', methods=['POST'])
def cart_add():
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


@app.route('/cart')
def cart_view():
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


@app.route('/cart/update', methods=['POST'])
def cart_update():
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
#  CHECKOUT & ORDER ROUTES
# ════════════════════════════════════════════════════════════

@app.route('/checkout')
def checkout():
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


@app.route('/pay', methods=['POST'])
def pay():
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


@app.route('/order/<int:oid>')
def success(oid):
    conn  = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not order:
        return redirect(url_for('index'))
    items = conn.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall()
    return render_template('success.html', order=order, items=items)


# ════════════════════════════════════════════════════════════
#  ADMIN — AUTH
# ════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if (request.form.get('username') == ADMIN_USER and
                request.form.get('password') == ADMIN_PASS):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error=True)
    return render_template('admin/login.html', error=False)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# ════════════════════════════════════════════════════════════
#  ADMIN — DASHBOARD
# ════════════════════════════════════════════════════════════

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()

    # ── Core stats ───────────────────────────────────────────
    total_products   = conn.execute('SELECT COUNT(*) FROM products WHERE active=1').fetchone()[0]
    total_orders     = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
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
#  ADMIN — PRODUCTS
# ════════════════════════════════════════════════════════════

@app.route('/admin/products')
@admin_required
def admin_products():
    products = get_db().execute(
        'SELECT * FROM products ORDER BY sort_order, id'
    ).fetchall()
    return render_template('admin/products.html', products=products)


def _product_fields_from_form():
    """Extract and coerce product fields from POST form."""
    f = request.form
    return (
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


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_product_add():
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


@app.route('/admin/products/edit/<int:pid>', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(pid):
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


@app.route('/admin/products/delete/<int:pid>', methods=['POST'])
@admin_required
def admin_product_delete(pid):
    conn = get_db()
    row  = conn.execute('SELECT photo FROM products WHERE id=?', (pid,)).fetchone()
    if row:
        delete_photo_file(row['photo'])
    conn.execute('DELETE FROM products WHERE id=?', (pid,))
    conn.commit()
    flash('تم حذف المنتج نهائياً ✅', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/toggle/<int:pid>', methods=['POST'])
@admin_required
def admin_product_toggle(pid):
    conn = get_db()
    row  = conn.execute('SELECT active FROM products WHERE id=?', (pid,)).fetchone()
    if row:
        new_status = 0 if row['active'] else 1
        conn.execute('UPDATE products SET active=? WHERE id=?', (new_status, pid))
        conn.commit()
        flash('تم تفعيل المنتج ✅' if new_status else 'تم إيقاف المنتج ⏸️', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/upload-photo', methods=['POST'])
@admin_required
def admin_upload_photo():
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
#  ADMIN — ORDERS
# ════════════════════════════════════════════════════════════

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = get_db().execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/status/<int:oid>', methods=['POST'])
@admin_required
def admin_order_status(oid):
    status = request.form.get('status', 'confirmed')
    if status not in VALID_ORDER_STATUSES:
        status = 'confirmed'
    conn = get_db()
    conn.execute('UPDATE orders SET status=? WHERE id=?', (status, oid))
    conn.commit()
    flash('تم تحديث حالة الطلب ✅', 'success')
    return redirect(url_for('admin_orders'))


@app.route('/admin/orders/invoice/<int:oid>')
@admin_required
def admin_order_invoice(oid):
    conn  = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not order:
        return redirect(url_for('admin_orders'))
    items = conn.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall()
    return render_template('admin/invoice.html', order=order, items=items)


# ════════════════════════════════════════════════════════════
#  ADMIN — SETTINGS
# ════════════════════════════════════════════════════════════

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
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
#  ENTRY POINT
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()
    print("✅  سلافة SULAFA  — http://localhost:5000")
    print("🔧  Admin Panel   — http://localhost:5000/admin")
    print(f"    User: {ADMIN_USER} | Pass: {ADMIN_PASS}")
    app.run(debug=True, port=5000)
