import requests, json, os, uuid, re, time

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

def dl(url, folder):
    if not url: return ''
    try:
        url = re.sub(r'-/resize/\d+x', '', url)
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        name = uuid.uuid4().hex + ext
        path = os.path.join(folder, name)
        r = s.get(url, timeout=20)
        with open(path, 'wb') as f: f.write(r.content)
        return name
    except: return ''

def parse_product_html(html, url_name, default_price, default_cat):
    start = html.find('var product = {')
    if start == -1: return None
    start = html.index('{', start)
    depth, p = 0, start
    while p < len(html):
        if html[p] == '{': depth += 1
        elif html[p] == '}':
            depth -= 1
            if depth == 0: break
        p += 1
    try:
        prod = json.loads(html[start:p+1])
    except: return None

    title = prod.get('title', url_name).strip()
    brand = prod.get('brand', '')
    price = prod.get('price', str(default_price))
    text = prod.get('text', '')
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)

    # Build short selling description from key specs
    short_desc = build_short_desc(text, title, brand, price)

    # Gallery
    gallery = prod.get('gallery', [])
    photos = []
    for img in gallery:
        img_url = img.get('img', '') if isinstance(img, dict) else ''
        if img_url:
            fn = dl(img_url, STATIC_DIR)
            if fn: photos.append(fn)

    # Editions (color variants)
    editions = prod.get('editions', [])
    options = prod.get('options', [])
    
    edition_data = []
    for ed in editions:
        ed_img_url = ed.get('img', '') if isinstance(ed, dict) else ''
        ed_img = dl(ed_img_url, STATIC_DIR) if ed_img_url else (photos[0] if photos else '')
        ed_data = {
            'uid': ed.get('uid', ''),
            'sku': ed.get('sku', ''),
            'price': ed.get('price', price),
            'price_old': ed.get('priceold', ''),
            'img': ed_img,
            'quantity': ed.get('quantity', '')
        }
        edition_data.append(ed_data)

    # Determine category
    cat = detect_category(title, text, default_cat)

    result = {
        'name': title,
        'brand': brand,
        'price': price,
        'short_description': short_desc,
        'full_description': text,
        'photos': photos,
        'status': 'available',
        'category': cat,
        'views': 0,
        'editions': edition_data,
        'options': options
    }
    return result

def build_short_desc(text, title, brand, price):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    # Extract key specs
    specs = []
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in ['мощность', 'аккумулятор', 'скорость', 'пробег', 'нагрузка', 'вес', 'колес', 'двигатель', 'объём']):
            specs.append(line[:100])
    if specs:
        prefix = f"{brand + ' ' if brand else ''}{title} — "
        return prefix + '; '.join(specs[:4]) + '.'
    return text[:200] + '...' if len(text) > 200 else text

def detect_category(title, text, default_cat):
    t = (title + ' ' + text).lower()
    if any(w in t for w in ['электросамокат', 'scooter', 'kugoo', 'самокат', 'ninebot']): return 'scooter'
    if any(w in t for w in ['электровелосипед', 'e-bike', 'ebike', 'велосипед']): return 'ebike'
    if any(w in t for w in ['питбайк', 'pitbike', 'эндуро', 'enduro']): return 'pitbike'
    if any(w in t for w in ['мотоцикл', 'ducati', 'yamaha', 'kawasaki']): return 'moto'
    if any(w in t for w in ['квадроцикл', 'atv', 'quad']): return 'atv'
    if any(w in t for w in ['скутер', 'moped', 'электроскутер']): return 'moped'
    return default_cat

# Product URLs to scrape - first 40
product_list = [
    ('https://in-move.online/tproduct/597069420-215761054481-kugoo-s3', 'Kugoo S3', 22900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-994522382301-kugoo-m2-pro', 'Kugoo M2 Pro', 29900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-543196323931-kugoo-m4-pro', 'Kugoo M4 Pro', 45900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-895823456231-kugoo-m4-pro', 'Kugoo M4 Pro+', 51900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-288123355861-kugoo-m5', 'Kugoo M5', 69900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-732869674421-kugoo-m5-pro', 'Kugoo M5 Pro', 73900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-145137592291-kugoo-v1', 'Kugoo V1', 14900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-610182294251-kugoo-max-speed', 'Kugoo Max Speed', 59900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-265652591682-kugoo-m4-pro-max', 'Kugoo M4 Pro Max', 55900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-635451839802-kugoo-f3-pro-max', 'Kugoo F3 Pro Max', 64900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-799880174942-kugoo-c1-plus', 'Kugoo C1 Plus', 24900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-406179440412-kugoo-s3-pro', 'Kugoo S3 Pro', 32900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-264912104592-kugoo-v5', 'Kugoo V5', 49900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-123672906852-kugoo-s4', 'Kugoo S4', 27900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-552752542562-kugoo-a2', 'Kugoo A2', 16900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-249543777842-kugoo-ec02', 'Kugoo EC02', 119900, 'moto'),
    ('https://in-move.online/tproduct/597069420-277412531352-kugoo-lx10-plus', 'Kugoo LX10 Plus', 79900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-383287280562-kugoo-wish-01', 'Kugoo Wish 01', 13990, 'scooter'),
    ('https://in-move.online/tproduct/597069420-965972032872-kugoo-v6', 'Kugoo V6', 59900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-978165346372-kugoo-g-booster', 'Kugoo G-Booster', 199000, 'moto'),
    ('https://in-move.online/tproduct/597069420-722109516272-yamaha-r3', 'Yamaha R3', 59900, 'moto'),
    ('https://in-move.online/tproduct/597069420-650328442122-eco-ducati-panigale', 'Eco Ducati Panigale', 59000, 'moto'),
    ('https://in-move.online/tproduct/597069420-383226010242-kavasaki', 'Kawasaki', 35000, 'moto'),
    ('https://in-move.online/tproduct/597069420-338011788832-mikaolin-harley-i7', 'Mikaolin Harley i7', 89900, 'moto'),
    ('https://in-move.online/tproduct/597069420-559034135682-maikaolin-shansu-surron', 'Maikaolin Shansu Surron', 179900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-965965871382-jilong-tank', 'Jilong Tank', 89900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-949833126602-maikaolin-h10', 'Maikaolin H10', 109900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-550410499302-liming-limusine', 'Liming Limusine', 199900, 'moped'),
    ('https://in-move.online/tproduct/597069420-904550386862-kugoo-kirin-trike', 'Kugoo Kirin Trike', 89900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-120506044562-kugoo-kirin-r2', 'Kugoo Kirin R2', 45900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-962895995252-kugoo-f3-pro', 'Kugoo F3 Pro', 44900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-856047731592-kugoo-u5', 'Kugoo U5', 29900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-386031713832-liming-monster', 'Liming Monster', 159900, 'moped'),
    ('https://in-move.online/tproduct/597069420-640909135622-ducati-diavel', 'Ducati Diavel', 69000, 'moto'),
    ('https://in-move.online/tproduct/597069420-292924365402-ducati-diavel', 'Ducati Diavel V2', 69000, 'moto'),
    ('https://in-move.online/tproduct/597069420-403069139212-jilong-tank', 'Jilong Tank (black)', 89900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-777895900812-kugoo-m4', 'Kugoo M4', 39900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-129882852472-kugoo-m3-pro', 'Kugoo M3 Pro', 39900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-291901023212-kugoo-l2-pro', 'Kugoo L2 Pro', 34900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-764840363282-kugoo-s4', 'Kugoo S4 (2)', 27900, 'scooter'),
]

products = []
errors = []
for i, (url, name, price, cat) in enumerate(product_list, 1):
    print(f"[{i}/{len(product_list)}] {name}...")
    try:
        r = s.get(url, timeout=25)
        html = r.text
        result = parse_product_html(html, name, price, cat)
        if result:
            result['id'] = i
            products.append(result)
            print(f"  OK: {result['name']} - {len(result['photos'])} photos, {len(result['editions'])} editions")
        else:
            errors.append(name)
            print(f"  FAIL: no JSON")
    except Exception as e:
        errors.append(name)
        print(f"  FAIL: {e}")
    time.sleep(0.7)

data = {'motos': products, 'stats': {'total_visits': 0}}
with open(os.path.join(BASE_DIR, 'data.json'), 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"\nDone! {len(products)} products saved. Errors: {errors}")
