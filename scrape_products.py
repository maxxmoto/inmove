import requests
import json
import re
import os
import uuid
import time
from urllib.parse import urljoin

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
SITEMAP_URL = 'https://in-move.online/sitemap-store.xml'

sess = requests.Session()
sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

def get_product_urls():
    r = sess.get(SITEMAP_URL, timeout=30)
    r.encoding = 'utf-8'
    urls = re.findall(r'<loc>(https://in-move\.online/tproduct/[^<]+)</loc>', r.text)
    return urls

def extract_product_json(html):
    # Find var product = { ... };
    start = html.find('var product = {')
    if start == -1:
        return None
    start = html.index('{', start)
    depth = 0
    i = start
    while i < len(html):
        if html[i] == '{':
            depth += 1
        elif html[i] == '}':
            depth -= 1
            if depth == 0:
                # Found end
                raw = html[start:i+1]
                try:
                    return json.loads(raw)
                except:
                    return None
        elif html[i] == ';' and depth == 0:
            break
        i += 1
    return None

def download_image(url, folder):
    if not url or 'static.tildacdn.com' not in url:
        return ''
    try:
        # Clean URL - remove resize directives
        url = re.sub(r'-/resize/\d+x', '', url)
        url = re.sub(r'-/proce?ss/', '', url)
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            ext = '.jpg'
        name = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(folder, name)
        r = sess.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        return name
    except Exception as e:
        return ''

def clean_specs(text):
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines)

def process_product(url, idx):
    print(f"[{idx}] {url.split('/')[-1][:40]}...")
    try:
        r = sess.get(url, timeout=30)
        r.encoding = 'utf-8'
        html = r.text
    except:
        print(f"  FAIL: request error")
        return None

    p = extract_product_json(html)
    if not p:
        print(f"  FAIL: no product JSON")
        return None

    title = p.get('title', '').strip()
    brand = p.get('brand', '').strip()
    price = p.get('price', '').strip()
    description = clean_specs(p.get('text', ''))
    
    gallery = p.get('gallery', [])
    if not gallery and 'images' in p:
        gallery = p['images']

    photos = []
    for img in gallery:
        if isinstance(img, dict):
            url = img.get('origin', img.get('img', img.get('url', '')))
        elif isinstance(img, str):
            url = img
        else:
            continue
        if url:
            fname = download_image(url, STATIC_DIR)
            if fname:
                photos.append(fname)

    if not photos:
        # Try fallback: meta image
        meta_match = re.search(r'<meta itemprop="image" content="([^"]+)"', html)
        if meta_match:
            fname = download_image(meta_match.group(1), STATIC_DIR)
            if fname:
                photos.append(fname)

    if not photos:
        print(f"  FAIL: no photos for {title}")
        return None

    # Determine category
    t = (title + ' ' + description).lower()
    if any(w in t for w in ['электросамокат', 'scooter', 'kugoo', 'самокат', 'ninebot', 'hiperscooter']):
        category = 'scooter'
    elif any(w in t for w in ['электровелосипед', 'e-bike', 'ebike', 'велосипед', 'electro bike']):
        category = 'ebike'
    elif any(w in t for w in ['питбайк', 'pitbike', 'pit bike', 'эндуро', 'enduro', 'cross']):
        category = 'pitbike'
    elif any(w in t for w in ['мотоцикл', 'motorcycle', 'ducati', 'yamaha', 'kawasaki']):
        category = 'moto'
    elif any(w in t for w in ['квадроцикл', 'atv', 'quad']):
        category = 'atv'
    elif any(w in t for w in ['скутер', 'moped', 'электроскутер']):
        category = 'moped'
    elif any(w in t for w in ['запчасти', 'части', 'аксессуар', 'защита']):
        category = 'parts'
    else:
        category = 'scooter'

    desc_short = description[:200] + '...' if len(description) > 200 else description

    result = {
        'name': title,
        'description': desc_short,
        'full_description': description,
        'photos': photos,
        'status': 'available',
        'category': category,
        'views': 0,
        'price': price,
        'brand': brand
    }
    print(f"  OK: {title} ({len(photos)} photos, cat: {category})")
    return result

def main():
    urls = get_product_urls()
    print(f"Found {len(urls)} product URLs. Fetching first 30...\n")
    
    all_products = []
    for i, url in enumerate(urls[:30], 1):
        prod = process_product(url, i)
        if prod:
            all_products.append(prod)
        time.sleep(0.7)

    data = {
        'motos': all_products,
        'stats': {'total_visits': 0}
    }
    with open(os.path.join(BASE_DIR, 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nDone! Saved {len(all_products)} products to data.json")

if __name__ == '__main__':
    main()
