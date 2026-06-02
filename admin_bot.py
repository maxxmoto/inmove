# admin_bot.py — Админ-бот INMOVE (через API сайта)
import telebot
from telebot import types
import requests
import json
import os
import time
import threading

# ---------- НАСТРОЙКИ ----------
ADMIN_BOT_TOKEN = '8980504185:AAHXsZNvk-KPK-J8nmNxuJZbUfESlbSWzHM'
CLIENT_BOT_TOKEN = '8980504185:AAHXsZNvk-KPK-J8nmNxuJZbUfESlbSWzHM'
REFERRAL_GROUP_ID = -1001234567890
ADMIN_PASSWORD = 'inmove2024'

API_BASE_URL = 'http://localhost:5000'
API_KEY = 'inmove_bot_secret_2026'
HEADERS = {'X-API-Key': API_KEY}

admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)
client_bot = telebot.TeleBot(CLIENT_BOT_TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Локальные файлы (подписчики, опросы бота — остаются на сервере)
LEADS_FILE       = os.path.join(BASE_DIR, 'leads.json')
REVIEWS_FILE     = os.path.join(BASE_DIR, 'reviews.json')
FAVSTATS_FILE    = os.path.join(BASE_DIR, 'favorites_stats.json')
SURVEY_FILE      = os.path.join(BASE_DIR, 'surveys.json')
BOT_SURVEY_FILE  = os.path.join(BASE_DIR, 'bot_surveys.json')
SUBSCRIBERS_FILE = os.path.join(BASE_DIR, 'subscribers.json')
ADMINS_FILE      = os.path.join(BASE_DIR, 'admins.json')
REMINDERS_FILE   = os.path.join(BASE_DIR, 'reminders.json')

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def api_get(endpoint):
    try:
        r = requests.get(API_BASE_URL + endpoint, headers=HEADERS, timeout=10)
        return r.json() if r.ok else None
    except Exception as e:
        print(f'API GET error: {e}')
        return None

def api_post(endpoint, data=None, files=None):
    try:
        r = requests.post(API_BASE_URL + endpoint, headers=HEADERS, data=data, files=files, timeout=60)
        return r.json() if r.ok else None
    except Exception as e:
        print(f'API POST error: {e}')
        return None

def is_admin(chat_id):
    admins = load_json(ADMINS_FILE, [])
    return chat_id in admins

def add_admin(chat_id):
    admins = load_json(ADMINS_FILE, [])
    if chat_id not in admins:
        admins.append(chat_id)
        save_json(ADMINS_FILE, admins)

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row('📊 Сводка', '🏍 Товары')
    kb.row('📋 Лиды', '⭐ Избранное')
    kb.row('📨 Рассылка', '📋 Опросы')
    kb.row('➕ Добавить товар', '➕ Добавить баннер')
    kb.row('➕ Добавить отзыв', '🆕 Уведомить о новинках')
    kb.row('🔔 Вкл/выкл уведомления')
    kb.row('📋 Экспорт каталога')
    return kb

# ---------- СОСТОЯНИЯ ДИАЛОГОВ ----------
conv_state = {}

# ---------- АВТОРИЗАЦИЯ ----------
@admin_bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    if is_admin(chat_id):
        admin_bot.send_message(chat_id, '🔐 Админ-панель INMOVE', reply_markup=main_keyboard())
    else:
        admin_bot.send_message(chat_id, '🔐 Введите пароль для доступа:')
        admin_bot.register_next_step_handler(message, check_password)

def check_password(message):
    if message.text.strip() == ADMIN_PASSWORD:
        add_admin(message.chat.id)
        admin_bot.send_message(message.chat.id, '✅ Доступ разрешён!', reply_markup=main_keyboard())
    else:
        admin_bot.send_message(message.chat.id, '❌ Неверный пароль.')

@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'выйти' in m.text.lower())
def logout(message):
    admins = load_json(ADMINS_FILE, [])
    if message.chat.id in admins:
        admins.remove(message.chat.id)
        save_json(ADMINS_FILE, admins)
    admin_bot.send_message(message.chat.id, '🚪 Вы вышли из админки.',
                           reply_markup=types.ReplyKeyboardRemove())

# ---------- СВОДКА ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'сводка' in m.text.lower())
def summary(message):
    data = api_get('/api/bot/stats')
    if not data:
        admin_bot.send_message(message.chat.id, '❌ Ошибка соединения с сайтом.')
        return
    msg = (
        "📊 *СВОДКА INMOVE*\n\n"
        f"👥 Посещений сайта: *{data['visits']}*\n"
        f"🏍 Товаров: *{data['motos']}* (✅ {data['available']} / ⚠ {data['on_order']})\n"
        f"❤️ В избранном: *{data['favorites']}*\n"
        f"💬 Отзывов: *{data['reviews']}*\n"
        f"📋 Заявок: *{data['leads']}*\n"
    )
    admin_bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ---------- ТОВАРЫ ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and m.text.strip() == '🏍 Товары')
def moto_list(message):
    data = api_get('/api/bot/motos')
    if not data or not data.get('motos'):
        admin_bot.send_message(message.chat.id, '❌ Ошибка или каталог пуст.')
        return
    motos = data['motos']
    for m in motos:
        status_emoji = '✅' if m['status'] == 'available' else '⚠'
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Переключить статус', callback_data=f'toggle_{m["id"]}'))
        admin_bot.send_message(
            message.chat.id,
            f"{status_emoji} *{m['name']}*\n👁 {m['views']} | ❤️ {m.get('fav_count', 0)}",
            parse_mode='Markdown', reply_markup=markup
        )

@admin_bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_'))
def toggle_moto(call):
    if not is_admin(call.message.chat.id):
        return
    moto_id = int(call.data.replace('toggle_', ''))
    result = api_post('/api/bot/toggle_status', data={'id': moto_id})
    if not result:
        admin_bot.answer_callback_query(call.id, '❌ Ошибка')
        return
    new_status = '✅ В наличии' if result['new_status'] == 'available' else '⚠ Под заказ'
    admin_bot.answer_callback_query(call.id, f'Статус изменён: {new_status}')
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Переключить статус', callback_data=f'toggle_{moto_id}'))
    admin_bot.edit_message_text(
        f"{'✅' if result['new_status'] == 'available' else '⚠'} *{result['name']}*\nСтатус: {new_status}",
        call.message.chat.id, call.message.message_id,
        parse_mode='Markdown', reply_markup=markup
    )

@admin_bot.callback_query_handler(func=lambda call: call.data == 'banner_no_link')
def banner_no_link(call):
    if not is_admin(call.message.chat.id):
        return
    chat_id = call.message.chat.id
    s = conv_state.get(chat_id)
    if s:
        s['link'] = ''
    admin_bot.edit_message_text('🔗 Ссылка: *нет*', chat_id, call.message.message_id, parse_mode='Markdown')
    admin_bot.answer_callback_query(call.id)
    admin_bot.send_message(chat_id, '📸 Пришлите *изображение* для баннера:', parse_mode='Markdown')
    admin_bot.register_next_step_handler(call.message, add_banner_image)

# ---------- ЛИДЫ ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'лиды' in m.text.lower())
def leads_list(message):
    data = api_get('/api/bot/stats')
    if not data:
        admin_bot.send_message(message.chat.id, '❌ Ошибка.')
        return
    admin_bot.send_message(message.chat.id, f"📋 Всего заявок: *{data['leads']}*\n(Детали — в веб-админке)", parse_mode='Markdown')

# ---------- ИЗБРАННОЕ ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'избранное' in m.text.lower())
def fav_stats_handler(message):
    data = api_get('/api/bot/motos')
    if not data or not data.get('motos'):
        admin_bot.send_message(message.chat.id, '❌ Ошибка или нет данных.')
        return
    sorted_motos = sorted(data['motos'], key=lambda m: m.get('fav_count', 0), reverse=True)
    msg = "⭐ *Топ избранного*\n\n"
    for m in sorted_motos[:10]:
        msg += f"• {m['name']}: *{m.get('fav_count', 0)}* ❤️\n"
    if not sorted_motos:
        msg += "Нет данных."
    admin_bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ---------- РАССЫЛКА ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'рассылка' in m.text.lower())
def broadcast_start(message):
    admin_bot.send_message(message.chat.id, 'Введите текст рассылки:')
    admin_bot.register_next_step_handler(message, broadcast_send)

def broadcast_send(message):
    if not is_admin(message.chat.id):
        return
    text = message.text
    subs = load_json(SUBSCRIBERS_FILE, [])
    sent = 0; failed = 0
    for chat_id in subs:
        try:
            client_bot.send_message(chat_id, f"📢 *INMOVE:*\n{text}", parse_mode='Markdown')
            sent += 1
            time.sleep(0.05)
        except:
            failed += 1
    admin_bot.send_message(message.chat.id, f'✅ Рассылка завершена. Отправлено: {sent}, ошибок: {failed}')

# ---------- ОПРОСЫ ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'опросы' in m.text.lower())
def surveys_handler(message):
    surveys_site = load_json(SURVEY_FILE, [])
    bot_surveys = load_json(BOT_SURVEY_FILE, [])
    from collections import Counter
    msg = "📋 *Результаты опросов*\n\n"
    if surveys_site:
        counter_site = Counter(s['answer'] for s in surveys_site)
        msg += "*На сайте:*\n"
        for answer, count in counter_site.most_common():
            msg += f"• {answer}: *{count}*\n"
        msg += f"Всего: *{len(surveys_site)}*\n\n"
    if bot_surveys:
        counter_bot = Counter(s['answer'] for s in bot_surveys)
        msg += "*В Telegram-боте:*\n"
        for answer, count in counter_bot.most_common():
            msg += f"• {answer}: *{count}*\n"
        msg += f"Всего: *{len(bot_surveys)}*\n\n"
    if not surveys_site and not bot_surveys:
        msg += "Никто ещё не проходил опрос."
    admin_bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ---------- ДОБАВИТЬ ТОВАР ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'добавить товар' in m.text.lower())
def add_moto_start(message):
    conv_state[message.chat.id] = {'action': 'add_moto'}
    admin_bot.send_message(message.chat.id, '🏍 Введите *название* товара:', parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_moto_name)

def add_moto_name(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['name'] = message.text.strip()
    admin_bot.send_message(message.chat.id, '📝 Введите *описание*:', parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_moto_desc)

def add_moto_desc(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['desc'] = message.text.strip()
    admin_bot.send_message(message.chat.id, '📝 Введите *подробное описание* (или отправьте пустое):', parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_moto_full_desc)

def add_moto_full_desc(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['full_desc'] = message.text.strip() if message.text else ''
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in ['Scooter', 'Pitbike', 'Moped', 'Moto', 'Ebike']:
        markup.add(cat)
    admin_bot.send_message(message.chat.id, '📂 Выберите *категорию*:', reply_markup=markup, parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_moto_cat)

def add_moto_cat(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['cat'] = message.text.strip().lower()
    admin_bot.send_message(message.chat.id, '📸 Пришлите *фото* (можно несколько одним сообщением).\nИли нажмите /done когда закончите:', parse_mode='Markdown', reply_markup=types.ReplyKeyboardRemove())
    conv_state[message.chat.id]['photos'] = []
    admin_bot.register_next_step_handler(message, add_moto_photos)

def add_moto_photos(message):
    if not is_admin(message.chat.id):
        return
    if message.text and message.text.strip() == '/done':
        return finish_add_moto(message)
    if message.photo:
        chat_id = message.chat.id
        s = conv_state[chat_id]
        if message.media_group_id:
            if s.get('mg_id') != message.media_group_id:
                s['mg_id'] = message.media_group_id
                s['mg_photos'] = []
            s['mg_photos'].append(message.photo[-1].file_id)
            admin_bot.send_message(chat_id, f'📸 Фото #{len(s["mg_photos"])} в альбоме')
            admin_bot.register_next_step_handler(message, add_moto_photos_check)
        else:
            s['photos'].append(message.photo[-1].file_id)
            count = len(s['photos'])
            admin_bot.send_message(chat_id, f'✅ Фото #{count} получено. Пришлите ещё или /done')
            admin_bot.register_next_step_handler(message, add_moto_photos)
    else:
        admin_bot.send_message(message.chat.id, '❌ Пришлите фото или /done')
        admin_bot.register_next_step_handler(message, add_moto_photos)

def add_moto_photos_check(message):
    if not is_admin(message.chat.id):
        return
    chat_id = message.chat.id
    s = conv_state.get(chat_id)
    if not s:
        return
    if message.photo and message.media_group_id == s.get('mg_id'):
        s['mg_photos'].append(message.photo[-1].file_id)
        admin_bot.send_message(chat_id, f'📸 Фото #{len(s["mg_photos"])} в альбоме')
        admin_bot.register_next_step_handler(message, add_moto_photos_check)
        return
    if s.get('mg_photos'):
        s['photos'].extend(s['mg_photos'])
        s.pop('mg_id', None)
        s.pop('mg_photos', None)
    if message.text and message.text.strip() == '/done':
        return finish_add_moto(message)
    if message.photo:
        s['photos'].append(message.photo[-1].file_id)
    count = len(s['photos'])
    admin_bot.send_message(chat_id, f'✅ Всего {count} фото. Пришлите ещё или /done')
    admin_bot.register_next_step_handler(message, add_moto_photos)

def finish_add_moto(message):
    chat_id = message.chat.id
    s = conv_state.get(chat_id)
    if not s:
        return
    if not s['photos']:
        admin_bot.send_message(chat_id, '❌ Нужно хотя бы одно фото.')
        admin_bot.register_next_step_handler(message, add_moto_photos)
        return
    admin_bot.send_message(chat_id, '⏳ Загружаю фото и сохраняю...')
    try:
        files = []
        for fid in s['photos']:
            file_info = admin_bot.get_file(fid)
            downloaded = admin_bot.download_file(file_info.file_path)
            ext = os.path.splitext(file_info.file_path)[1] or '.jpg'
            files.append(('photos', (f'photo{ext}', downloaded)))
        result = api_post('/api/bot/add_moto',
            data={'name': s['name'], 'description': s['desc'], 'full_description': s.get('full_desc', ''), 'category': s['cat']},
            files=files)
        if result and result.get('success'):
            admin_bot.send_message(chat_id, f'✅ {result["message"]}', reply_markup=main_keyboard())
        else:
            msg = '❌ Ошибка сервера' if result is None else f'❌ Ошибка: {result.get("message", "неизвестно")}'
            admin_bot.send_message(chat_id, msg, reply_markup=main_keyboard())
    except Exception as e:
        admin_bot.send_message(chat_id, f'❌ Ошибка: {e}', reply_markup=main_keyboard())
    finally:
        conv_state.pop(chat_id, None)

# ---------- ДОБАВИТЬ БАННЕР ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'добавить баннер' in m.text.lower())
def add_banner_start(message):
    conv_state[message.chat.id] = {'action': 'add_banner'}
    admin_bot.send_message(message.chat.id, '📝 Введите *текст* баннера (или отправьте пустое):', parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_banner_text)

def add_banner_text(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['text'] = message.text.strip() if message.text else ''
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('🚫 Нет ссылки', callback_data='banner_no_link'))
    admin_bot.send_message(message.chat.id, '🔗 Введите *ссылку* баннера или нажмите кнопку ниже:', reply_markup=markup, parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_banner_link)

def add_banner_link(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['link'] = message.text.strip() if message.text else ''
    admin_bot.send_message(message.chat.id, '📸 Пришлите *изображение* для баннера:')
    admin_bot.register_next_step_handler(message, add_banner_image)

def add_banner_image(message):
    if not is_admin(message.chat.id):
        return
    if not message.photo:
        admin_bot.send_message(message.chat.id, '❌ Пришлите изображение:')
        admin_bot.register_next_step_handler(message, add_banner_image)
        return
    chat_id = message.chat.id
    s = conv_state.get(chat_id)
    admin_bot.send_message(chat_id, '⏳ Загружаю...')
    try:
        file_info = admin_bot.get_file(message.photo[-1].file_id)
        downloaded = admin_bot.download_file(file_info.file_path)
        ext = os.path.splitext(file_info.file_path)[1] or '.jpg'
        result = api_post('/api/bot/add_banner',
            data={'text': s['text'], 'link': s['link']},
            files={'image': (f'banner{ext}', downloaded)})
        if result and result.get('success'):
            admin_bot.send_message(chat_id, '✅ Баннер добавлен!', reply_markup=main_keyboard())
        else:
            msg = '❌ Ошибка сервера' if result is None else f'❌ Ошибка: {result.get("message", "неизвестно")}'
            admin_bot.send_message(chat_id, msg, reply_markup=main_keyboard())
    except Exception as e:
        admin_bot.send_message(chat_id, f'❌ Ошибка: {e}', reply_markup=main_keyboard())
    finally:
        conv_state.pop(chat_id, None)

# ---------- ДОБАВИТЬ ОТЗЫВ ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'добавить отзыв' in m.text.lower())
def add_review_start(message):
    conv_state[message.chat.id] = {'action': 'add_review'}
    admin_bot.send_message(message.chat.id, '👤 Введите *имя* автора отзыва:', parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_review_name)

def add_review_name(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['name'] = message.text.strip()
    admin_bot.send_message(message.chat.id, '📝 Введите *текст* отзыва:', parse_mode='Markdown')
    admin_bot.register_next_step_handler(message, add_review_text)

def add_review_text(message):
    if not is_admin(message.chat.id):
        return
    conv_state[message.chat.id]['text'] = message.text.strip()
    admin_bot.send_message(message.chat.id, '📸 Пришлите *фото* (или отправьте /skip):')
    admin_bot.register_next_step_handler(message, add_review_photo)

def add_review_photo(message):
    if not is_admin(message.chat.id):
        return
    chat_id = message.chat.id
    s = conv_state.get(chat_id)
    admin_bot.send_message(chat_id, '⏳ Сохраняю...')
    try:
        files = {}
        data = {'name': s['name'], 'text': s['text']}
        if message.photo:
            file_info = admin_bot.get_file(message.photo[-1].file_id)
            downloaded = admin_bot.download_file(file_info.file_path)
            ext = os.path.splitext(file_info.file_path)[1] or '.jpg'
            files['photo'] = (f'review{ext}', downloaded)
        result = api_post('/api/bot/add_review', data=data, files=files)
        if result and result.get('success'):
            admin_bot.send_message(chat_id, '✅ Отзыв добавлен!', reply_markup=main_keyboard())
        else:
            msg = '❌ Ошибка сервера' if result is None else f'❌ Ошибка: {result.get("message", "неизвестно")}'
            admin_bot.send_message(chat_id, msg, reply_markup=main_keyboard())
    except Exception as e:
        admin_bot.send_message(chat_id, f'❌ Ошибка: {e}', reply_markup=main_keyboard())
    finally:
        conv_state.pop(chat_id, None)

# ---------- УВЕДОМИТЬ О НОВИНКАХ ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'новинк' in m.text.lower())
def notify_new_moto(message):
    data = api_get('/api/bot/notify_new')
    if not data or not data.get('moto'):
        admin_bot.send_message(message.chat.id, '❌ Нет товаров в каталоге.')
        return
    moto = data['moto']
    status_str = '✅ В наличии' if moto['status'] == 'available' else '⚠ Под заказ'
    msg = f"🆕 *НОВОЕ ПОСТУПЛЕНИЕ!*\n\n*{moto['name']}*\nКатегория: {moto['category']}\nСтатус: {status_str}\n\n{moto.get('description', '')[:200]}..."
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📄 Открыть на сайте', url=f'http://localhost:5000/moto/{moto["id"]}'))
    try:
        if moto.get('photos'):
            client_bot.send_photo(REFERRAL_GROUP_ID, f'{API_BASE_URL}/static/{moto["photos"][0]}',
                                  caption=msg, parse_mode='Markdown', reply_markup=markup)
        else:
            client_bot.send_message(REFERRAL_GROUP_ID, msg, parse_mode='Markdown', reply_markup=markup)
    except:
        try:
            client_bot.send_message(REFERRAL_GROUP_ID, msg, parse_mode='Markdown', reply_markup=markup)
        except:
            pass
    admin_bot.send_message(message.chat.id, '✅ Уведомление о новинке отправлено в группу.')

# ---------- ЭКСПОРТ КАТАЛОГА ----------
@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'экспорт' in m.text.lower())
def export_catalog(message):
    data = api_get('/api/bot/motos')
    if not data or not data.get('motos'):
        admin_bot.send_message(message.chat.id, '❌ Ошибка или каталог пуст.')
        return
    motos = data['motos']
    msg = "📋 *ЭКСПОРТ КАТАЛОГА*\n\n"
    for m in motos:
        status = '✅' if m['status'] == 'available' else '⚠'
        msg += f"{status} {m['name']} | {m['category']} | 👁 {m['views']}\n"
    admin_bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ---------- УВЕДОМЛЕНИЯ ----------
notify_enabled = False

@admin_bot.message_handler(func=lambda m: is_admin(m.chat.id) and 'уведомления' in m.text.lower())
def toggle_notifications(message):
    global notify_enabled
    notify_enabled = not notify_enabled
    state = 'включены' if notify_enabled else 'выключены'
    admin_bot.send_message(message.chat.id, f'🔔 Уведомления {state}.')

def watch_leads():
    last_count = 0
    while True:
        time.sleep(30)
        if not notify_enabled:
            continue
        data = api_get('/api/bot/stats')
        if data and data['leads'] > last_count and last_count > 0:
            try:
                admin_bot.send_message(REFERRAL_GROUP_ID, f'🆕 Новая заявка! Всего: {data["leads"]}')
            except:
                pass
        if data:
            last_count = data['leads']

threading.Thread(target=watch_leads, daemon=True).start()

# ---------- ЗАПУСК ----------
if __name__ == '__main__':
    print('🔐 Админ-бот INMOVE запущен...')
    admin_bot.polling(none_stop=True)
