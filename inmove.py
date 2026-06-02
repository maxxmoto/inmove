import os
import json
import uuid
import sqlite3
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory

app = Flask(__name__)
app.secret_key = 'InMoVe_SeCrEt_2026!'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'inmove.db')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static')
app.config['MANUAL_FOLDER'] = os.path.join(BASE_DIR, 'static', 'manuals')

@app.template_filter('photo_url')
def photo_url(path):
    if not path:
        return '/static/inmove_logo.png'
    if path.startswith(('http://', 'https://')):
        return path
    if path.startswith('/'):
        return path
    if path.startswith('static/'):
        return '/' + path
    return '/static/' + path

def compress_image(filepath, max_dim=1200, quality=85):
    try:
        from PIL import Image
        img = Image.open(filepath)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        w, h = img.size
        if w > max_dim or h > max_dim:
            if w > h:
                new_w = max_dim
                new_h = int(h * max_dim / w)
            else:
                new_h = max_dim
                new_w = int(w * max_dim / h)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        img.save(filepath, optimize=True, quality=quality)
    except Exception:
        pass
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    return {'cart_count': sum(cart.values()) if cart else 0}


def get_cart_items(db):
    cart = session.get('cart', {})
    if not cart:
        return [], 0
    ids = [int(k) for k in cart.keys()]
    placeholders = ','.join('?' for _ in ids)
    rows = db.execute(f"SELECT id, name, price, photos FROM motos WHERE id IN ({placeholders})", ids).fetchall()
    items = []
    total = 0
    for r in rows:
        d = dict(r)
        qty = cart.get(str(d['id']), 0)
        if qty <= 0:
            continue
        photos = json.loads(d.get('photos', '[]'))
        price = int(float(d.get('price', 0)))
        items.append({'id': d['id'], 'name': d['name'], 'price': price, 'photo': photos[0] if photos else 'inmove_logo.png', 'quantity': qty})
        total += price * qty
    return items, total

ADMIN_LOGIN = 'Adm1nInMove7'
ADMIN_PASSWORD = 'InMoveP@ss2026'

ALLOWED_MANUAL_EXTENSIONS = {'.pdf'}

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS motos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                full_description TEXT DEFAULT '',
                category TEXT DEFAULT 'street',
                status TEXT DEFAULT 'available',
                views INTEGER DEFAULT 0,
                manual TEXT DEFAULT '',
                photos TEXT DEFAULT '[]',
                price TEXT DEFAULT '',
                short_description TEXT DEFAULT '',
                editions TEXT DEFAULT '[]',
                options TEXT DEFAULT '[]',
                sku TEXT DEFAULT '',
                externalid TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                photo TEXT DEFAULT '',
                visible INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                page TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS fav_stats (
                moto_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            );
            INSERT OR IGNORE INTO stats (key, value) VALUES ('total_visits', 0);
            CREATE TABLE IF NOT EXISTS banners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT NOT NULL DEFAULT '',
                text TEXT DEFAULT '',
                link TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer TEXT,
                timestamp TEXT
            );
        """)

def migrate_from_json():
    """Migrate data from JSON files to SQLite if DB is empty."""
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM motos").fetchone()[0]
    if count > 0:
        db.close()
        return

    data_file = os.path.join(BASE_DIR, 'data.json')
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i, m in enumerate(data.get('motos', []), 1):
            mid = m.get('id', i)
            db.execute("""INSERT INTO motos (id, name, description, full_description, category, status, views, manual, photos, price, short_description, editions, options, sku, externalid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mid, m['name'], m.get('description', ''), m.get('full_description', ''),
                 m.get('category', 'street'), m.get('status', 'available'), m.get('views', 0),
                 m.get('manual', ''), json.dumps(m.get('photos', []), ensure_ascii=False),
                 m.get('price', ''), m.get('short_description', ''),
                 json.dumps(m.get('editions', []), ensure_ascii=False),
                 json.dumps(m.get('options', []), ensure_ascii=False),
                 m.get('sku', ''), m.get('externalid', '')))
        s = data.get('stats', {})
        if 'total_visits' in s:
            db.execute("UPDATE stats SET value=? WHERE key='total_visits'", (s['total_visits'],))

    reviews_file = os.path.join(BASE_DIR, 'reviews.json')
    if os.path.exists(reviews_file):
        with open(reviews_file, 'r', encoding='utf-8') as f:
            reviews = json.load(f)
        for r in reviews:
            db.execute("INSERT INTO reviews (id, name, text, photo, visible) VALUES (?, ?, ?, ?, ?)",
                (r.get('id', 0), r.get('name', ''), r.get('text', ''),
                 r.get('photo', ''), 1 if r.get('visible', True) else 0))

    leads_file = os.path.join(BASE_DIR, 'leads.json')
    if os.path.exists(leads_file):
        with open(leads_file, 'r', encoding='utf-8') as f:
            leads = json.load(f)
        for lead in leads.get('history', []):
            db.execute("INSERT INTO leads (date, page) VALUES (?, ?)", (lead.get('date', ''), lead.get('page', '')))

    fav_file = os.path.join(BASE_DIR, 'favorites_stats.json')
    if os.path.exists(fav_file):
        with open(fav_file, 'r', encoding='utf-8') as f:
            favs = json.load(f)
        for mid, cnt in favs.items():
            db.execute("INSERT OR REPLACE INTO fav_stats (moto_id, count) VALUES (?, ?)", (int(mid), cnt))

    db.commit()
    db.close()

def row_to_moto(row):
    d = dict(row)
    d['photos'] = json.loads(d.get('photos', '[]'))
    d['editions'] = json.loads(d.get('editions', '[]'))
    d['options'] = json.loads(d.get('options', '[]'))
    return d

def parse_specs(text):
    if not text:
        return []
    specs = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        for sep in [': ', ' — ', ' – ', ' - ', ':']:
            if sep in line:
                key, val = line.split(sep, 1)
                specs.append({'key': key.strip(), 'val': val.strip()})
                break
    return specs

@app.route('/health')
def health():
    return 'ok'

@app.route('/')
def index():
    db = get_db()
    db.execute("UPDATE stats SET value=value+1 WHERE key='total_visits'")
    db.commit()
    sort = request.args.get('sort', 'default')
    category = request.args.get('category', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 12

    order = "id"
    if sort == 'price_asc':
        order = "CAST(price AS INTEGER) ASC, id"
    elif sort == 'price_desc':
        order = "CAST(price AS INTEGER) DESC, id"

    # Build query with optional category filter
    if category and category != 'all':
        rows = db.execute(f"SELECT * FROM motos WHERE category=? ORDER BY {order}", (category,)).fetchall()
    else:
        rows = db.execute(f"SELECT * FROM motos ORDER BY {order}").fetchall()
        category = 'all'

    all_motos = [row_to_moto(r) for r in rows]
    total = len(all_motos)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    start = (page - 1) * per_page
    motos = all_motos[start:start + per_page]

    review_rows = db.execute("SELECT * FROM reviews WHERE visible=1 ORDER BY id").fetchall()
    reviews = [dict(r) for r in review_rows]
    banner_rows = db.execute("SELECT * FROM banners ORDER BY sort_order").fetchall()
    banners = [dict(r) for r in banner_rows]
    db.close()
    return render_template('index.html', motos=motos, reviews=reviews, banners=banners, sort=sort, page=page, total_pages=total_pages, total_products=total, current_category=category)

@app.template_filter('specs_table')
def specs_table_filter(text):
    return parse_specs(text)

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/requisites')
def requisites():
    return render_template('requisites.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        login = request.form.get('login', '')
        password = request.form.get('password', '')
        if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        return render_template('manage.html', error='Неверный логин или пароль', logged_in=False)
    if session.get('logged_in'):
        db = get_db()
        rows = db.execute("SELECT * FROM motos ORDER BY id").fetchall()
        motos = [row_to_moto(r) for r in rows]
        visits = db.execute("SELECT value FROM stats WHERE key='total_visits'").fetchone()
        stats = {"total_visits": visits[0] if visits else 0}
        review_rows = db.execute("SELECT * FROM reviews ORDER BY id").fetchall()
        reviews = [dict(r) for r in review_rows]
        fav_rows = db.execute("SELECT * FROM fav_stats ORDER BY moto_id").fetchall()
        fav_stats = {str(r['moto_id']): r['count'] for r in fav_rows}
        banner_rows = db.execute("SELECT * FROM banners ORDER BY sort_order").fetchall()
        banners = [dict(r) for r in banner_rows]
        db.close()
        return render_template('manage.html', logged_in=True, motos=motos, stats=stats, reviews=reviews, fav_stats=fav_stats, banners=banners)
    return render_template('manage.html', logged_in=False)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin'))

@app.route('/api/add_moto', methods=['POST'])
def add_moto():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', 'scooter').strip()
    full_description = request.form.get('full_description', '').strip()
    price = request.form.get('price', '').strip()
    sku = request.form.get('sku', '').strip()
    short_description = request.form.get('short_description', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Название обязательно'}), 400
    photo_files = request.files.getlist('photos')
    if not photo_files or all(f.filename == '' for f in photo_files):
        return jsonify({'success': False, 'message': 'Нужно хотя бы одно фото'}), 400
    saved_photos = []
    for photo_file in photo_files:
        if photo_file.filename == '':
            continue
        ext = os.path.splitext(photo_file.filename)[1]
        if ext.lower() not in ['.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp']:
            continue
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        photo_file.save(filepath)
        compress_image(filepath)
        saved_photos.append(unique_name)
    if not saved_photos:
        return jsonify({'success': False, 'message': 'Не удалось сохранить ни одного фото'}), 400
    manual_filename = ''
    manual_file = request.files.get('manual')
    if manual_file and manual_file.filename != '':
        ext = os.path.splitext(manual_file.filename)[1].lower()
        if ext in ALLOWED_MANUAL_EXTENSIONS:
            manual_filename = f"manual_{uuid.uuid4().hex}{ext}"
            manual_file.save(os.path.join(app.config['MANUAL_FOLDER'], manual_filename))
    db = get_db()
    db.execute("""INSERT INTO motos (name, description, full_description, category, status, manual, photos, price, sku, short_description)
        VALUES (?, ?, ?, ?, 'available', ?, ?, ?, ?, ?)""",
        (name, description or 'Описание отсутствует', full_description or description,
         category, manual_filename, json.dumps(saved_photos, ensure_ascii=False),
         price, sku, short_description))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Мотоцикл добавлен'})

@app.route('/api/delete_moto', methods=['POST'])
def delete_moto():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False, 'message': 'Не указан ID'}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'ID должен быть числом'}), 400
    db = get_db()
    row = db.execute("SELECT * FROM motos WHERE id=?", (moto_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False, 'message': 'Мотоцикл не найден'}), 404
    moto = row_to_moto(row)
    for photo in moto.get('photos', []):
        p = os.path.join(app.config['UPLOAD_FOLDER'], photo)
        if os.path.exists(p): os.remove(p)
    if moto.get('manual'):
        p = os.path.join(app.config['MANUAL_FOLDER'], moto['manual'])
        if os.path.exists(p): os.remove(p)
    db.execute("DELETE FROM motos WHERE id=?", (moto_id,))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Мотоцикл удалён'})

@app.route('/api/toggle_status', methods=['POST'])
def toggle_status():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False, 'message': 'Не указан ID'}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'ID должен быть числом'}), 400
    db = get_db()
    row = db.execute("SELECT status FROM motos WHERE id=?", (moto_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False, 'message': 'Мотоцикл не найден'}), 404
    new_status = 'on_order' if row['status'] == 'available' else 'available'
    db.execute("UPDATE motos SET status=? WHERE id=?", (new_status, moto_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Статус обновлён', 'new_status': new_status})

@app.route('/api/increment_view', methods=['POST'])
def increment_view():
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False}), 400
    db = get_db()
    db.execute("UPDATE motos SET views=views+1 WHERE id=?", (moto_id,))
    row = db.execute("SELECT views FROM motos WHERE id=?", (moto_id,)).fetchone()
    db.commit()
    db.close()
    if row:
        return jsonify({'success': True, 'views': row['views']})
    return jsonify({'success': False}), 404

@app.route('/static/<path:filename>')
def static_files(filename):
    resp = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    if any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']):
        resp.headers['Cache-Control'] = 'public, max-age=604800, immutable'
    return resp

@app.route('/moto/<int:moto_id>')
def moto_detail(moto_id):
    import random
    db = get_db()
    row = db.execute("SELECT * FROM motos WHERE id=?", (moto_id,)).fetchone()
    if not row:
        db.close()
        return "Мотоцикл не найден", 404
    moto = row_to_moto(row)
    same = db.execute("SELECT * FROM motos WHERE category=? AND id!=?", (moto['category'], moto_id)).fetchall()
    same_list = [row_to_moto(r) for r in same]
    related = random.sample(same_list, min(3, len(same_list)))
    db.close()
    return render_template('moto_detail.html', moto=moto, related=related)

@app.route('/favorites')
def favorites():
    ids_param = request.args.get('ids', '')
    if ids_param:
        try:
            ids = [int(i) for i in ids_param.split(',')]
        except ValueError:
            ids = []
    else:
        ids = []
    db = get_db()
    if ids:
        placeholders = ','.join('?' for _ in ids)
        rows = db.execute(f"SELECT * FROM motos WHERE id IN ({placeholders}) ORDER BY id", ids).fetchall()
    else:
        rows = []
    motos = [row_to_moto(r) for r in rows]
    db.close()
    return render_template('favorites.html', motos=motos)

@app.route('/api/edit_moto', methods=['POST'])
def edit_moto():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False, 'message': 'Не указан ID'}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'ID должен быть числом'}), 400
    db = get_db()
    row = db.execute("SELECT * FROM motos WHERE id=?", (moto_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False, 'message': 'Мотоцикл не найден'}), 404
    moto = row_to_moto(row)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    full_description = request.form.get('full_description', '').strip()
    category = request.form.get('category', 'scooter').strip()
    status = request.form.get('status', 'available').strip()
    manual_file = request.files.get('manual')
    price = request.form.get('price', '').strip()
    sku = request.form.get('sku', '').strip()
    short_description = request.form.get('short_description', '').strip()
    if name:
        moto['name'] = name
    moto['description'] = description
    moto['full_description'] = full_description
    moto['category'] = category
    moto['status'] = status
    if price:
        moto['price'] = price
    if sku:
        moto['sku'] = sku
    if short_description:
        moto['short_description'] = short_description
    if manual_file and manual_file.filename != '':
        ext = os.path.splitext(manual_file.filename)[1].lower()
        if ext in ALLOWED_MANUAL_EXTENSIONS:
            if moto.get('manual'):
                old = os.path.join(app.config['MANUAL_FOLDER'], moto['manual'])
                if os.path.exists(old): os.remove(old)
            manual_filename = f"manual_{uuid.uuid4().hex}{ext}"
            manual_file.save(os.path.join(app.config['MANUAL_FOLDER'], manual_filename))
            moto['manual'] = manual_filename
    db.execute("""UPDATE motos SET name=?, description=?, full_description=?, category=?, status=?, manual=?, price=?, sku=?, short_description=?
        WHERE id=?""",
        (moto['name'], moto['description'], moto['full_description'],
         moto['category'], moto['status'], moto.get('manual', ''),
         moto.get('price', ''), moto.get('sku', ''), moto.get('short_description', ''), moto_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Мотоцикл обновлён'})

@app.route('/api/add_review', methods=['POST'])
def add_review():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    name = request.form.get('name', '').strip()
    text = request.form.get('text', '').strip()
    if not name or not text:
        return jsonify({'success': False, 'message': 'Имя и текст обязательны'}), 400
    photo_file = request.files.get('photo')
    photo_name = ''
    if photo_file and photo_file.filename != '':
        ext = os.path.splitext(photo_file.filename)[1]
        if ext.lower() in ['.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp']:
            unique_name = f"review_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            photo_file.save(filepath)
            compress_image(filepath, max_dim=600)
            photo_name = unique_name
    db = get_db()
    db.execute("INSERT INTO reviews (name, text, photo, visible) VALUES (?, ?, ?, 1)", (name, text, photo_name))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Отзыв добавлен'})

@app.route('/api/toggle_review', methods=['POST'])
def toggle_review():
    if not session.get('logged_in'):
        return jsonify({'success': False}), 403
    review_id = request.form.get('id')
    if not review_id:
        return jsonify({'success': False}), 400
    try:
        review_id = int(review_id)
    except ValueError:
        return jsonify({'success': False}), 400
    db = get_db()
    row = db.execute("SELECT visible FROM reviews WHERE id=?", (review_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False}), 404
    new_visible = 0 if row['visible'] else 1
    db.execute("UPDATE reviews SET visible=? WHERE id=?", (new_visible, review_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'visible': bool(new_visible)})

@app.route('/api/delete_review', methods=['POST'])
def delete_review():
    if not session.get('logged_in'):
        return jsonify({'success': False}), 403
    review_id = request.form.get('id')
    if not review_id:
        return jsonify({'success': False}), 400
    try:
        review_id = int(review_id)
    except ValueError:
        return jsonify({'success': False}), 400
    db = get_db()
    row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False}), 404
    r = dict(row)
    if r.get('photo'):
        p = os.path.join(app.config['UPLOAD_FOLDER'], r['photo'])
        if os.path.exists(p): os.remove(p)
    db.execute("DELETE FROM reviews WHERE id=?", (review_id,))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Отзыв удалён'})

@app.route('/reviews')
def reviews_page():
    db = get_db()
    rows = db.execute("SELECT * FROM reviews WHERE visible=1 ORDER BY id").fetchall()
    reviews = [dict(r) for r in rows]
    db.close()
    return render_template('reviews_page.html', reviews=reviews)

@app.route('/cart')
def cart_page():
    db = get_db()
    items, total = get_cart_items(db)
    db.close()
    cart = session.get('cart', {})
    return render_template('cart.html', cart_items=items, cart_total=total, cart_count=sum(cart.values()))

@app.route('/api/cart/add', methods=['POST'])
def cart_add():
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False, 'cart_count': 0}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False, 'cart_count': 0}), 400
    cart = session.get('cart', {})
    cart[str(moto_id)] = cart.get(str(moto_id), 0) + 1
    session['cart'] = cart
    return jsonify({'success': True, 'cart_count': sum(cart.values())})

@app.route('/api/cart/remove', methods=['POST'])
def cart_remove():
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False}), 400
    cart = session.get('cart', {})
    cart.pop(str(moto_id), None)
    session['cart'] = cart
    db = get_db()
    items, total = get_cart_items(db)
    db.close()
    count = sum(cart.values())
    return jsonify({'success': True, 'cart_count': count, 'cart_total': total, 'items': items})

@app.route('/api/cart/update', methods=['POST'])
def cart_update():
    moto_id = request.form.get('id')
    delta = request.form.get('delta', '1')
    if not moto_id:
        return jsonify({'success': False}), 400
    try:
        moto_id = int(moto_id)
        delta = int(delta)
    except ValueError:
        return jsonify({'success': False}), 400
    cart = session.get('cart', {})
    current = cart.get(str(moto_id), 0) + delta
    if current <= 0:
        cart.pop(str(moto_id), None)
        item_removed = True
    else:
        cart[str(moto_id)] = current
        item_removed = False
    session['cart'] = cart
    db = get_db()
    items, total = get_cart_items(db)
    db.close()
    count = sum(cart.values())
    return jsonify({'success': True, 'cart_count': count, 'cart_total': total, 'items': items, 'item_removed': item_removed})

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/api/fav_add', methods=['POST'])
def fav_add():
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False}), 400
    db = get_db()
    row = db.execute("SELECT count FROM fav_stats WHERE moto_id=?", (moto_id,)).fetchone()
    if row:
        db.execute("UPDATE fav_stats SET count=count+1 WHERE moto_id=?", (moto_id,))
        new_count = row['count'] + 1
    else:
        db.execute("INSERT INTO fav_stats (moto_id, count) VALUES (?, 1)", (moto_id,))
        new_count = 1
    db.commit()
    db.close()
    return jsonify({'success': True, 'count': new_count})

@app.route('/api/add_banner', methods=['POST'])
def add_banner():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    text = request.form.get('text', '').strip()
    link = request.form.get('link', '').strip()
    image_file = request.files.get('image')
    if not image_file or image_file.filename == '':
        return jsonify({'success': False, 'message': 'Изображение обязательно'}), 400
    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp']:
        return jsonify({'success': False, 'message': 'Недопустимый формат изображения'}), 400
    unique_name = f"banner_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    image_file.save(filepath)
    compress_image(filepath)
    db = get_db()
    max_order = db.execute("SELECT COALESCE(MAX(sort_order), -1) FROM banners").fetchone()[0]
    db.execute("INSERT INTO banners (image, text, link, sort_order) VALUES (?, ?, ?, ?)",
        (unique_name, text, link, max_order + 1))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Баннер добавлен'})

@app.route('/api/delete_banner', methods=['POST'])
def delete_banner():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Не авторизован'}), 403
    banner_id = request.form.get('id')
    if not banner_id:
        return jsonify({'success': False, 'message': 'Не указан ID'}), 400
    try:
        banner_id = int(banner_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'ID должен быть числом'}), 400
    db = get_db()
    row = db.execute("SELECT * FROM banners WHERE id=?", (banner_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False, 'message': 'Баннер не найден'}), 404
    img_path = os.path.join(app.config['UPLOAD_FOLDER'], row['image'])
    if row['image'] and os.path.exists(img_path):
        os.remove(img_path)
    db.execute("DELETE FROM banners WHERE id=?", (banner_id,))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Баннер удалён'})

@app.route('/api/get_banners', methods=['GET'])
def get_banners():
    if not session.get('logged_in'):
        return jsonify({'success': False}), 403
    db = get_db()
    rows = db.execute("SELECT * FROM banners ORDER BY sort_order").fetchall()
    banners = [dict(r) for r in rows]
    db.close()
    return jsonify({'success': True, 'banners': banners})

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.config['UPLOAD_FOLDER'], 'robots.txt')

@app.route('/sitemap.xml')
def sitemap_xml():
    base = 'http://localhost:5000'
    urls = [
        {'loc': base + '/', 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': base + '/reviews', 'priority': '0.8', 'changefreq': 'weekly'},
        {'loc': base + '/favorites', 'priority': '0.5', 'changefreq': 'weekly'},
        {'loc': base + '/admin', 'priority': '0.3', 'changefreq': 'monthly'},
    ]
    db = get_db()
    rows = db.execute("SELECT id, name FROM motos ORDER BY id").fetchall()
    db.close()
    for r in rows:
        urls.append({
            'loc': f'{base}/moto/{r["id"]}',
            'priority': '0.9',
            'changefreq': 'weekly',
            'title': r['name']
        })
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(f'  <url>')
        lines.append(f'    <loc>{u["loc"]}</loc>')
        if 'title' in u:
            lines.append(f'    <xhtml:link rel="alternate" hreflang="ru" href="{u["loc"]}"/>')
        lines.append(f'    <changefreq>{u["changefreq"]}</changefreq>')
        lines.append(f'    <priority>{u["priority"]}</priority>')
        lines.append(f'  </url>')
    lines.append('</urlset>')
    return '\n'.join(lines), 200, {'Content-Type': 'application/xml'}

@app.route('/api/lead', methods=['POST'])
def add_lead():
    db = get_db()
    db.execute("INSERT INTO leads (date, page) VALUES (?, ?)",
        (str(date.today()), request.headers.get("Referer", "неизвестно")))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/bot/stats')
def bot_stats():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    db = get_db()
    visits = db.execute("SELECT value FROM stats WHERE key='total_visits'").fetchone()
    moto_count = db.execute("SELECT COUNT(*) FROM motos").fetchone()[0]
    available = db.execute("SELECT COUNT(*) FROM motos WHERE status='available'").fetchone()[0]
    on_order = moto_count - available
    leads = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    favs = db.execute("SELECT COALESCE(SUM(count), 0) FROM fav_stats").fetchone()[0]
    reviews = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    db.close()
    return jsonify({
        'success': True,
        'visits': visits[0] if visits else 0,
        'motos': moto_count, 'available': available, 'on_order': on_order,
        'leads': leads, 'favorites': favs, 'reviews': reviews
    })

@app.route('/api/bot/motos')
def bot_motos():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    db = get_db()
    rows = db.execute("SELECT * FROM motos ORDER BY id").fetchall()
    motos = [row_to_moto(r) for r in rows]
    fav_rows = db.execute("SELECT * FROM fav_stats ORDER BY moto_id").fetchall()
    fav_stats = {str(r['moto_id']): r['count'] for r in fav_rows}
    db.close()
    for m in motos:
        m['fav_count'] = int(fav_stats.get(str(m['id']), 0))
    return jsonify({'success': True, 'motos': motos})

@app.route('/api/bot/toggle_status', methods=['POST'])
def bot_toggle_status():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    moto_id = request.form.get('id')
    if not moto_id:
        return jsonify({'success': False, 'message': 'Не указан ID'}), 400
    try:
        moto_id = int(moto_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'ID должен быть числом'}), 400
    db = get_db()
    row = db.execute("SELECT status, name FROM motos WHERE id=?", (moto_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False, 'message': 'Мотоцикл не найден'}), 404
    new_status = 'on_order' if row['status'] == 'available' else 'available'
    db.execute("UPDATE motos SET status=? WHERE id=?", (new_status, moto_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'new_status': new_status, 'name': row['name']})

@app.route('/api/bot/add_moto', methods=['POST'])
def bot_add_moto():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    full_description = request.form.get('full_description', '').strip()
    category = request.form.get('category', 'scooter').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Название обязательно'}), 400
    photo_files = request.files.getlist('photos')
    saved_photos = []
    for photo_file in photo_files:
        if photo_file.filename == '':
            continue
        ext = os.path.splitext(photo_file.filename)[1]
        if ext.lower() not in ['.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp']:
            continue
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        photo_file.save(filepath)
        compress_image(filepath)
        saved_photos.append(unique_name)
    if not saved_photos:
        return jsonify({'success': False, 'message': 'Нужно хотя бы одно фото'}), 400
    db = get_db()
    db.execute("""INSERT INTO motos (name, description, full_description, category, status, photos)
        VALUES (?, ?, ?, ?, 'available', ?)""",
        (name, description or 'Описание отсутствует', full_description or description, category,
         json.dumps(saved_photos, ensure_ascii=False)))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': f'Мотоцикл «{name}» добавлен'})

@app.route('/api/bot/add_banner', methods=['POST'])
def bot_add_banner():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    text = request.form.get('text', '').strip()
    link = request.form.get('link', '').strip()
    image_file = request.files.get('image')
    if not image_file or image_file.filename == '':
        return jsonify({'success': False, 'message': 'Изображение обязательно'}), 400
    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp']:
        return jsonify({'success': False, 'message': 'Недопустимый формат'}), 400
    unique_name = f"banner_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    image_file.save(filepath)
    compress_image(filepath)
    db = get_db()
    max_order = db.execute("SELECT COALESCE(MAX(sort_order), -1) FROM banners").fetchone()[0]
    db.execute("INSERT INTO banners (image, text, link, sort_order) VALUES (?, ?, ?, ?)",
        (unique_name, text, link, max_order + 1))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Баннер добавлен'})

@app.route('/api/bot/add_review', methods=['POST'])
def bot_add_review():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    name = request.form.get('name', '').strip()
    text = request.form.get('text', '').strip()
    if not name or not text:
        return jsonify({'success': False, 'message': 'Имя и текст обязательны'}), 400
    photo_file = request.files.get('photo')
    photo_name = ''
    if photo_file and photo_file.filename != '':
        ext = os.path.splitext(photo_file.filename)[1]
        if ext.lower() in ['.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp']:
            unique_name = f"review_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            photo_file.save(filepath)
            compress_image(filepath, max_dim=600)
            photo_name = unique_name
    db = get_db()
    db.execute("INSERT INTO reviews (name, text, photo, visible) VALUES (?, ?, ?, 1)", (name, text, photo_name))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Отзыв добавлен'})

@app.route('/api/bot/notify_new')
def bot_notify_new():
    if not bot_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    db = get_db()
    row = db.execute("SELECT * FROM motos ORDER BY id DESC LIMIT 1").fetchone()
    db.close()
    if not row:
        return jsonify({'success': False, 'message': 'Нет мотоциклов'}), 404
    moto = row_to_moto(row)
    return jsonify({'success': True, 'moto': moto})

# Initialize database on import (for WSGI)
try:
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['MANUAL_FOLDER']):
        os.makedirs(app.config['MANUAL_FOLDER'])
    init_db()
    migrate_from_json()

    # Seed default banner if none exist
    bdb = get_db()
    bc = bdb.execute("SELECT COUNT(*) FROM banners").fetchone()[0]
    if bc == 0:
        bdb.execute("INSERT INTO banners (image, text, link, sort_order) VALUES (?, ?, ?, ?)",
            ('', 'Добро пожаловать в INMOVE! Широкий выбор электротранспорта', 'https://t.me/INMOVE812', 0))
    bdb.commit()
    bdb.close()
except Exception as e:
    print(f'Startup init error: {e}')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
