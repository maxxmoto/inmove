import requests, json, os, uuid, re, time

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

def dl(url, folder):
    try:
        url = re.sub(r'-/resize/\d+x', '', url)
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        name = uuid.uuid4().hex + ext
        r = s.get(url, timeout=20)
        with open(os.path.join(folder, name), 'wb') as f:
            f.write(r.content)
        return name
    except:
        return ''

urls = [
    ('https://in-move.online/tproduct/597069420-722109516272-yamaha-r3', 'Yamaha R3', 59900, 'moto'),
    ('https://in-move.online/tproduct/597069420-292924365402-ducati-diavel', 'Ducati Diavel', 69000, 'moto'),
    ('https://in-move.online/tproduct/597069420-650328442122-eco-ducati-panigale', 'Eco Ducati Panigale', 59000, 'moto'),
    ('https://in-move.online/tproduct/597069420-383226010242-kavasaki', 'Kawasaki', 35000, 'moto'),
    ('https://in-move.online/tproduct/597069420-338011788832-mikaolin-harley-i7', 'Mikaolin Harley i7', 89900, 'moto'),
    ('https://in-move.online/tproduct/597069420-559034135682-maikaolin-shansu-surron', 'Maikaolin Shansu Surron', 179900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-965965871382-jilong-tank', 'Jilong Tank', 89900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-949833126602-maikaolin-h10', 'Maikaolin H10', 109900, 'pitbike'),
    ('https://in-move.online/tproduct/597069420-386031713832-liming-monster', 'Liming Monster', 159900, 'moped'),
    ('https://in-move.online/tproduct/597069420-550410499302-liming-limusine', 'Liming Limusine', 199900, 'moped'),
    ('https://in-move.online/tproduct/597069420-904550386862-kugoo-kirin-trike', 'Kugoo Kirin Trike', 89900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-120506044562-kugoo-kirin-r2', 'Kugoo Kirin R2', 45900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-962895995252-kugoo-f3-pro', 'Kugoo F3 Pro', 44900, 'scooter'),
    ('https://in-move.online/tproduct/597069420-856047731592-kugoo-u5', 'Kugoo U5', 29900, 'scooter'),
]

products_new = []
for i, (url, name, price, cat) in enumerate(urls, 1):
    print(f'[{i}/{len(urls)}] {name}...')
    try:
        r = s.get(url, timeout=20)
        html = r.text
        start = html.find('var product = {')
        if start == -1:
            print(f'  no JSON')
            continue
        start = html.index('{', start)
        depth = 0
        p = start
        while p < len(html):
            if html[p] == '{': depth += 1
            elif html[p] == '}':
                depth -= 1
                if depth == 0: break
            p += 1
        raw = html[start:p+1]
        prod = json.loads(raw)

        text = prod.get('text', '')
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        brand = prod.get('brand', 'Kugoo')

        gallery = prod.get('gallery', [])
        photos = []
        for img in gallery:
            img_url = img.get('img', '') if isinstance(img, dict) else ''
            if img_url:
                fn = dl(img_url, STATIC_DIR)
                if fn: photos.append(fn)
        if not photos:
            print(f'  no photos')
            continue

        products_new.append({
            'name': name,
            'description': text[:200] + '...' if len(text) > 200 else text,
            'full_description': text,
            'photos': photos,
            'status': 'available',
            'category': cat,
            'views': 0,
            'price': str(price),
            'brand': brand
        })
        print(f'  OK: {len(photos)} photos')
    except Exception as e:
        print(f'  FAIL: {e}')
    time.sleep(0.5)

data_path = os.path.join(BASE_DIR, 'data.json')
with open(data_path, 'r', encoding='utf-8') as f:
    existing = json.load(f)
existing['motos'].extend(products_new)
with open(data_path, 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print(f'\nAdded {len(products_new)} more. Total: {len(existing["motos"])}')
