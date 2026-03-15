from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, os, json, uuid
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sulafa_secret_2024_secure'
DB = os.path.join(os.path.dirname(__file__), 'sulafa.db')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

ADMIN_USER = 'admin'
ADMIN_PASS = 'sulafa2024'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    con = db()
    c = con.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            desc_ar TEXT,
            desc_en TEXT,
            price REAL NOT NULL,
            old_price REAL,
            image TEXT DEFAULT '🫒',
            photo TEXT DEFAULT NULL,
            category_ar TEXT DEFAULT 'بكر ممتاز',
            category_en TEXT DEFAULT 'Extra Virgin',
            weight TEXT DEFAULT '750ml',
            origin_ar TEXT DEFAULT 'اليونان',
            origin_en TEXT DEFAULT 'Greece',
            stock INTEGER DEFAULT 100,
            rating REAL DEFAULT 4.9,
            reviews_count INTEGER DEFAULT 0,
            featured INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            full_name TEXT, phone TEXT, city TEXT, address TEXT,
            total REAL, tax REAL, grand_total REAL,
            payment_method TEXT DEFAULT 'card',
            card_last4 TEXT,
            status TEXT DEFAULT 'confirmed',
            lang TEXT DEFAULT 'ar',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER, product_id INTEGER,
            name TEXT, price REAL, quantity INTEGER
        );
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sid TEXT, product_id INTEGER, quantity INTEGER DEFAULT 1
        );
    ''')

    for migration in [
        'ALTER TABLE products ADD COLUMN photo TEXT DEFAULT NULL',
        "ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'card'",
    ]:
        try:
            c.execute(migration)
            con.commit()
        except Exception:
            pass

    defaults = {
        'site_name_ar': 'سلافة', 'site_name_en': 'SULAFA',
        'tagline_ar': 'زيت الزيتون الأصيل', 'tagline_en': 'Pure & Premium Olive Oil',
        'hero_title_ar': 'زيت الزيتون الفاخر', 'hero_title_en': 'Pure & Premium Olive Oil',
        'hero_sub_ar': 'اذوق جوهر البحر المتوسط', 'hero_sub_en': 'Taste the Essence of the Mediterranean',
        'whatsapp': '201000000000', 'facebook': 'https://facebook.com/sulafa',
        'instagram': 'https://instagram.com/sulafa', 'tiktok': 'https://tiktok.com/@sulafa',
        'phone': '+20 100 000 0000', 'email': 'info@sulafa.eg',
        'address_ar': 'القاهرة، مصر', 'address_en': 'Cairo, Egypt',
        'free_shipping_ar': 0, 'free_shipping_en': 0, 'shipping_cost': '50',
        'currency_ar': 'جنيه', 'currency_en': 'EGP',
        'benefit1_ar': 'غنى بمضادات الأكسدة', 'benefit1_en': 'Rich in Antioxidants',
        'benefit2_ar': 'يدعم صحة القلب', 'benefit2_en': 'Supports Heart Health',
        'benefit3_ar': 'لذيذ وصحى', 'benefit3_en': 'Delicious & Healthy',
        'newsletter_title_ar': 'انضم لنشرتنا البريدية', 'newsletter_title_en': 'Join Our Newsletter',
        'newsletter_sub_ar': 'اشترك للحصول على عروض حصرية وتحديثات',
        'newsletter_sub_en': 'Sign up for exclusive offers & updates',
    }
    for k, v in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, str(v)))

    c.execute('SELECT COUNT(*) FROM products')
    if c.fetchone()[0] == 0:
        prods = [
            ('زيت الزيتون البكر الممتاز','Extra Virgin Olive Oil','زيت زيتون بكر ممتاز معصور على البارد من أجود الزيتون اليونانى. غنى بمضادات الأكسدة.','Cold pressed extra virgin olive oil from the finest Greek olives. Rich in antioxidants.',189.00,249.00,'🫒',None,'بكر ممتاز','Extra Virgin','750ml','اليونان','Greece',60,4.9,312,1,1,1),
            ('زيت الزيتون العضوى','Organic Olive Oil','زيت زيتون عضوى معتمد دولياً، بدون مبيدات أو مواد كيميائية.','Internationally certified organic olive oil. No pesticides or chemicals.',229.00,299.00,'🌿',None,'عضوى','Organic','500ml','تونس','Tunisia',45,4.8,198,1,1,2),
            ('زيت الزيتون بالثوم','Garlic Infused Olive Oil','مزيج فاخر من زيت الزيتون البكر مع الثوم الطبيعى. رائع للشوايات.','Premium blend of extra virgin olive oil with natural garlic. Perfect for grilling.',155.00,199.00,'🧄',None,'منكّه','Infused','250ml','إيطاليا','Italy',80,4.7,145,1,1,3),
            ('زيت الزيتون الإيطالى الفاخر','Premium Italian Olive Oil','من قلب توسكانا الإيطالية. نكهة استثنائية وعطر رائع.','From the heart of Tuscany, Italy. Exceptional flavor and remarkable aroma.',315.00,395.00,'✨',None,'فاخر','Premium','500ml','إيطاليا','Italy',30,5.0,445,1,1,4),
            ('زيت الزيتون الفلسطينى','Palestinian Olive Oil','من أشجار الزيتون المعمّرة فى فلسطين. طعم عميق وأصيل.','From ancient olive trees in Palestine. Deep and authentic taste.',199.00,None,'🌳',None,'بكر ممتاز','Extra Virgin','750ml','فلسطين','Palestine',40,4.9,521,1,1,5),
            ('طقم سلافة الملكى','Sulafa Royal Gift Set','طقم هدايا فاخر يضم 3 أحجام مختلفة فى علبة هدايا راقية.','Luxury gift set featuring 3 different sizes in an elegant gift box.',445.00,560.00,'🎁',None,'طقم هدايا','Gift Set','متعدد','متعدد','Multi',25,4.9,78,1,1,6),
        ]
        c.executemany('''INSERT INTO products (name_ar,name_en,desc_ar,desc_en,price,old_price,image,photo,category_ar,category_en,weight,origin_ar,origin_en,stock,rating,reviews_count,featured,active,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', prods)

    con.commit(); con.close()

def get_setting(key, default=''):
    con = db()
    r = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    con.close()
    return r['value'] if r else default

def get_all_settings():
    con = db()
    rows = con.execute('SELECT key, value FROM settings').fetchall()
    con.close()
    return {r['key']: r['value'] for r in rows}

def get_categories():
    """Get categories: merged from settings (custom) + existing products"""
    s = get_all_settings()
    # Categories defined in settings (JSON list)
    custom = []
    try:
        raw = s.get('custom_categories', '')
        if raw:
            custom = json.loads(raw)
    except Exception:
        custom = []
    # Also get any categories already used in products
    con = db()
    rows_ar = [r[0] for r in con.execute('SELECT DISTINCT category_ar FROM products WHERE active=1 AND category_ar IS NOT NULL').fetchall()]
    rows_en = [r[0] for r in con.execute('SELECT DISTINCT category_en FROM products WHERE active=1 AND category_en IS NOT NULL').fetchall()]
    con.close()
    # Merge: custom list takes priority, then product-existing
    result = list(custom)
    for i, cat_ar in enumerate(rows_ar):
        cat_en = rows_en[i] if i < len(rows_en) else cat_ar
        pair = {'ar': cat_ar, 'en': cat_en}
        if not any(c.get('ar') == cat_ar for c in result):
            result.append(pair)
    return result

def cart_count():
    sid = session.get('sid', '')
    if not sid: return 0
    con = db()
    r = con.execute('SELECT COALESCE(SUM(quantity),0) FROM cart WHERE sid=?', (sid,)).fetchone()
    con.close()
    return r[0]

def fmt_price(p, lang='ar'):
    if lang == 'en': return f"EGP {p:,.0f}"
    return f"{p:,.0f} جنيه"

def save_uploaded_photo(file):
    if not file or not file.filename: return None
    if not allowed_file(file.filename): return None
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return f"/static/uploads/{filename}"

def delete_photo_file(photo_url):
    if photo_url:
        old_path = os.path.join(os.path.dirname(__file__), photo_url.lstrip('/'))
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except Exception: pass

app.jinja_env.globals['cart_count'] = cart_count
app.jinja_env.globals['get_setting'] = get_setting
app.jinja_env.globals['fmt_price'] = fmt_price
app.jinja_env.filters['enumerate'] = enumerate

def get_lang():
    return session.get('lang', 'ar')

app.jinja_env.globals['get_lang'] = get_lang

@app.context_processor
def inject_globals():
    return dict(s=get_all_settings(), lang=get_lang())

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/lang/<lang>')
def switch_lang(lang):
    if lang in ['ar', 'en']: session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    lang = get_lang()
    con = db()
    featured = con.execute('SELECT * FROM products WHERE featured=1 AND active=1 ORDER BY sort_order').fetchall()
    s = get_all_settings(); con.close()
    return render_template('index.html', featured=featured, s=s, lang=lang)

@app.route('/shop')
def shop():
    lang = get_lang(); cat = request.args.get('cat',''); q = request.args.get('q','')
    con = db(); sql = 'SELECT * FROM products WHERE active=1'; params = []
    if cat:
        col = 'category_ar' if lang=='ar' else 'category_en'
        sql += f' AND {col}=?'; params.append(cat)
    if q:
        sql += ' AND (name_ar LIKE ? OR name_en LIKE ? OR desc_ar LIKE ? OR desc_en LIKE ?)'
        params += [f'%{q}%']*4
    sql += ' ORDER BY sort_order, id'
    prods = con.execute(sql, params).fetchall()
    cats_ar = con.execute('SELECT DISTINCT category_ar FROM products WHERE active=1').fetchall()
    cats_en = con.execute('SELECT DISTINCT category_en FROM products WHERE active=1').fetchall()
    s = get_all_settings(); con.close()
    return render_template('shop.html', products=prods, cats_ar=cats_ar, cats_en=cats_en, sel_cat=cat, q=q, s=s, lang=lang)

@app.route('/product/<int:pid>')
def product(pid):
    lang = get_lang(); con = db()
    p = con.execute('SELECT * FROM products WHERE id=? AND active=1', (pid,)).fetchone()
    rel = con.execute('SELECT * FROM products WHERE id!=? AND active=1 ORDER BY RANDOM() LIMIT 4', (pid,)).fetchall()
    s = get_all_settings(); con.close()
    if not p: return redirect(url_for('shop'))
    return render_template('product.html', p=p, rel=rel, s=s, lang=lang)

@app.route('/about')
def about():
    return render_template('about.html', s=get_all_settings(), lang=get_lang())

@app.route('/contact')
def contact():
    return render_template('contact.html', s=get_all_settings(), lang=get_lang())

@app.route('/cart/add', methods=['POST'])
def cart_add():
    if 'sid' not in session: session['sid'] = os.urandom(16).hex()
    sid = session['sid']; pid = request.form.get('pid', type=int); qty = request.form.get('qty',1,type=int)
    con = db()
    row = con.execute('SELECT id FROM cart WHERE sid=? AND product_id=?', (sid,pid)).fetchone()
    if row: con.execute('UPDATE cart SET quantity=quantity+? WHERE id=?', (qty, row['id']))
    else:   con.execute('INSERT INTO cart (sid,product_id,quantity) VALUES (?,?,?)', (sid,pid,qty))
    con.commit()
    cnt = con.execute('SELECT COALESCE(SUM(quantity),0) FROM cart WHERE sid=?', (sid,)).fetchone()[0]
    con.close()
    if request.headers.get('X-Fetch'): return jsonify(ok=True, count=cnt)
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def cart_view():
    lang = get_lang(); sid = session.get('sid','')
    con = db()
    items = con.execute('''SELECT c.id,c.quantity,p.id as pid,p.name_ar,p.name_en,p.price,p.image,p.photo,p.weight
        FROM cart c JOIN products p ON c.product_id=p.id WHERE c.sid=?''', (sid,)).fetchall()
    s = get_all_settings(); con.close()
    sub = sum(i['price']*i['quantity'] for i in items)
    tax = round(sub*0.14,2); ship = 0 if sub>=500 else 50; total = sub+tax+ship
    return render_template('cart.html', items=items, sub=sub, tax=tax, ship=ship, total=total, s=s, lang=lang)

@app.route('/cart/update', methods=['POST'])
def cart_update():
    cid = request.form.get('cid',type=int); action = request.form.get('action')
    con = db()
    if action=='del': con.execute('DELETE FROM cart WHERE id=?',(cid,))
    elif action=='+': con.execute('UPDATE cart SET quantity=quantity+1 WHERE id=?',(cid,))
    elif action=='-':
        row = con.execute('SELECT quantity FROM cart WHERE id=?',(cid,)).fetchone()
        if row and row['quantity']>1: con.execute('UPDATE cart SET quantity=quantity-1 WHERE id=?',(cid,))
        else: con.execute('DELETE FROM cart WHERE id=?',(cid,))
    con.commit(); con.close()
    return redirect(url_for('cart_view'))

@app.route('/checkout')
def checkout():
    lang = get_lang(); sid = session.get('sid','')
    con = db()
    items = con.execute('''SELECT c.id,c.quantity,p.id as pid,p.name_ar,p.name_en,p.price,p.image,p.photo
        FROM cart c JOIN products p ON c.product_id=p.id WHERE c.sid=?''', (sid,)).fetchall()
    s = get_all_settings(); con.close()
    if not items: return redirect(url_for('cart_view'))
    sub = sum(i['price']*i['quantity'] for i in items)
    tax = round(sub*0.14,2); ship = 0 if sub>=500 else 50; total = sub+tax+ship
    return render_template('checkout.html', items=items, sub=sub, tax=tax, ship=ship, total=total, s=s, lang=lang)

@app.route('/pay', methods=['POST'])
def pay():
    lang = get_lang(); sid = session.get('sid','')
    payment_method = request.form.get('payment_method','card')
    con = db()
    items = con.execute('''SELECT c.quantity,p.id as pid,p.name_ar,p.name_en,p.price
        FROM cart c JOIN products p ON c.product_id=p.id WHERE c.sid=?''', (sid,)).fetchall()
    if not items: return redirect(url_for('cart_view'))
    sub = sum(i['price']*i['quantity'] for i in items)
    tax = round(sub*0.14,2); ship = 0 if sub>=500 else 50; grand = sub+tax+ship
    last4 = None
    if payment_method == 'card':
        card = request.form.get('card_number','').replace(' ','')
        last4 = card[-4:] if len(card)>=4 else '****'
    onum = f"SLF-{datetime.now().strftime('%y%m%d')}-{os.urandom(3).hex().upper()}"
    oid = con.execute('''INSERT INTO orders
        (order_number,full_name,phone,city,address,total,tax,grand_total,payment_method,card_last4,lang)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
        onum, request.form.get('full_name'), request.form.get('phone'),
        request.form.get('city'), request.form.get('address'),
        sub, tax, grand, payment_method, last4, lang
    )).lastrowid
    for i in items:
        name = i['name_ar'] if lang=='ar' else i['name_en']
        con.execute('INSERT INTO order_items (order_id,product_id,name,price,quantity) VALUES (?,?,?,?,?)',
                    (oid, i['pid'], name, i['price'], i['quantity']))
    con.execute('DELETE FROM cart WHERE sid=?', (sid,))
    con.commit(); con.close()
    return redirect(url_for('success', oid=oid))

@app.route('/order/<int:oid>')
def success(oid):
    lang = get_lang(); con = db()
    order = con.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    items = con.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall()
    s = get_all_settings(); con.close()
    if not order: return redirect(url_for('index'))
    return render_template('success.html', order=order, items=items, s=s, lang=lang)

# ─── ADMIN ─────────────────────────────────────────────
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        if request.form.get('username')==ADMIN_USER and request.form.get('password')==ADMIN_PASS:
            session['admin_logged_in']=True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error=True)
    return render_template('admin/login.html', error=False)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in',None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    con = db()
    total_products = con.execute('SELECT COUNT(*) FROM products WHERE active=1').fetchone()[0]
    total_orders   = con.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    total_revenue  = con.execute('SELECT COALESCE(SUM(grand_total),0) FROM orders').fetchone()[0]
    avg_order      = con.execute('SELECT COALESCE(AVG(grand_total),0) FROM orders').fetchone()[0]
    recent_orders  = con.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 5').fetchall()
    con.close()
    return render_template('admin/dashboard.html', total_products=total_products,
        total_orders=total_orders, total_revenue=total_revenue,
        avg_order=avg_order, recent_orders=recent_orders)

@app.route('/admin/products')
@admin_required
def admin_products():
    con = db()
    prods = con.execute('SELECT * FROM products ORDER BY sort_order, id').fetchall()
    con.close()
    return render_template('admin/products.html', products=prods)

@app.route('/admin/products/add', methods=['GET','POST'])
@admin_required
def admin_product_add():
    if request.method=='POST':
        photo_url = save_uploaded_photo(request.files.get('photo'))
        con = db()
        con.execute('''INSERT INTO products (name_ar,name_en,desc_ar,desc_en,price,old_price,image,photo,category_ar,category_en,weight,origin_ar,origin_en,stock,featured,active,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            request.form.get('name_ar'), request.form.get('name_en'),
            request.form.get('desc_ar'), request.form.get('desc_en'),
            float(request.form.get('price',0)),
            float(request.form.get('old_price')) if request.form.get('old_price') else None,
            request.form.get('image','🫒'), photo_url,
            request.form.get('category_ar'), request.form.get('category_en'),
            request.form.get('weight'), request.form.get('origin_ar'), request.form.get('origin_en'),
            int(request.form.get('stock',100)),
            1 if request.form.get('featured') else 0,
            1 if request.form.get('active') else 0,
            int(request.form.get('sort_order',0))
        ))
        con.commit(); con.close()
        flash('تم إضافة المنتج بنجاح! ✅','success')
        return redirect(url_for('admin_products'))
    cats = get_categories()
    return render_template('admin/product_form.html', product=None, action='add', cats=cats)

@app.route('/admin/products/edit/<int:pid>', methods=['GET','POST'])
@admin_required
def admin_product_edit(pid):
    con = db()
    p = con.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    if not p: con.close(); return redirect(url_for('admin_products'))
    if request.method=='POST':
        photo_url = p['photo']
        new_photo = save_uploaded_photo(request.files.get('photo'))
        if new_photo: delete_photo_file(photo_url); photo_url = new_photo
        if request.form.get('remove_photo') and not new_photo:
            delete_photo_file(photo_url); photo_url = None
        con.execute('''UPDATE products SET name_ar=?,name_en=?,desc_ar=?,desc_en=?,price=?,old_price=?,image=?,photo=?,category_ar=?,category_en=?,weight=?,origin_ar=?,origin_en=?,stock=?,featured=?,active=?,sort_order=? WHERE id=?''', (
            request.form.get('name_ar'), request.form.get('name_en'),
            request.form.get('desc_ar'), request.form.get('desc_en'),
            float(request.form.get('price',0)),
            float(request.form.get('old_price')) if request.form.get('old_price') else None,
            request.form.get('image','🫒'), photo_url,
            request.form.get('category_ar'), request.form.get('category_en'),
            request.form.get('weight'), request.form.get('origin_ar'), request.form.get('origin_en'),
            int(request.form.get('stock',100)),
            1 if request.form.get('featured') else 0,
            1 if request.form.get('active') else 0,
            int(request.form.get('sort_order',0)), pid
        ))
        con.commit(); con.close()
        flash('تم تعديل المنتج بنجاح! ✅','success')
        return redirect(url_for('admin_products'))
    con.close()
    cats = get_categories()
    return render_template('admin/product_form.html', product=p, action='edit', cats=cats)

@app.route('/admin/products/delete/<int:pid>', methods=['POST'])
@admin_required
def admin_product_delete(pid):
    con = db()
    p = con.execute('SELECT photo FROM products WHERE id=?',(pid,)).fetchone()
    if p: delete_photo_file(p['photo'])
    con.execute('DELETE FROM products WHERE id=?',(pid,))
    con.commit(); con.close()
    flash('تم حذف المنتج نهائياً ✅','success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/toggle/<int:pid>', methods=['POST'])
@admin_required
def admin_product_toggle(pid):
    con = db()
    p = con.execute('SELECT active FROM products WHERE id=?',(pid,)).fetchone()
    if p:
        new_status = 0 if p['active'] else 1
        con.execute('UPDATE products SET active=? WHERE id=?',(new_status,pid))
        con.commit()
        flash('تم تفعيل المنتج ✅' if new_status else 'تم إيقاف المنتج ⏸️','success')
    con.close()
    return redirect(url_for('admin_products'))

@app.route('/admin/products/upload-photo', methods=['POST'])
@admin_required
def admin_upload_photo():
    file = request.files.get('photo'); pid = request.form.get('pid',type=int)
    photo_url = save_uploaded_photo(file)
    if not photo_url: return jsonify(ok=False, error='صيغة الملف غير مدعومة'), 400
    if pid:
        con = db()
        old = con.execute('SELECT photo FROM products WHERE id=?',(pid,)).fetchone()
        if old: delete_photo_file(old['photo'])
        con.execute('UPDATE products SET photo=? WHERE id=?',(photo_url,pid))
        con.commit(); con.close()
    return jsonify(ok=True, url=photo_url)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    con = db()
    orders = con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    con.close()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/orders/status/<int:oid>', methods=['POST'])
@admin_required
def admin_order_status(oid):
    status = request.form.get('status','confirmed')
    if status not in ['confirmed','pending','shipped','cancelled']: status='confirmed'
    con = db()
    con.execute('UPDATE orders SET status=? WHERE id=?',(status,oid))
    con.commit(); con.close()
    flash('تم تحديث حالة الطلب ✅','success')
    return redirect(url_for('admin_orders'))

# ─── ADMIN: INVOICE ────────────────────────────────────
@app.route('/admin/orders/invoice/<int:oid>')
@admin_required
def admin_order_invoice(oid):
    con = db()
    order = con.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    items = con.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall()
    s = get_all_settings(); con.close()
    if not order: return redirect(url_for('admin_orders'))
    return render_template('admin/invoice.html', order=order, items=items, s=s)

@app.route('/admin/settings', methods=['GET','POST'])
@admin_required
def admin_settings():
    if request.method=='POST':
        con = db()
        # Handle custom categories (from dynamic fields)
        cats = []
        i = 0
        while True:
            ar = request.form.get(f'cat_ar_{i}')
            en = request.form.get(f'cat_en_{i}')
            if ar is None and en is None:
                break
            if ar or en:
                cats.append({'ar': ar or '', 'en': en or ''})
            i += 1
        # Save categories as JSON
        con.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)',
                    ('custom_categories', json.dumps(cats, ensure_ascii=False)))
        # Save all other settings
        skip = {k for k in request.form if k.startswith('cat_ar_') or k.startswith('cat_en_')}
        for key, value in request.form.items():
            if key not in skip:
                con.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',(key,value))
        con.commit(); con.close()
        flash('تم حفظ الإعدادات بنجاح! ✅','success')
        return redirect(url_for('admin_settings'))
    s = get_all_settings()
    cats = get_categories()
    return render_template('admin/settings.html', s=s, cats=cats)

if __name__ == '__main__':
    init_db()
    print("✅ سلافة SULAFA - http://localhost:5000")
    print("🔧 Admin Panel  - http://localhost:5000/admin")
    print("   User: admin | Pass: sulafa2024")
    app.run(debug=True, port=5000)
