# tg_bot.py — Пользовательский бот INMOVE
import telebot
from telebot import apihelper, types
import json
import os
import time
import random
import urllib.parse
import uuid
import threading

# ---------- НАСТРОЙКИ ----------
TOKEN = '8980504185:AAHXsZNvk-KPK-J8nmNxuJZbUfESlbSWzHM'          # <-- замените на реальный токен

bot = telebot.TeleBot(TOKEN)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- ПУТИ К ФАЙЛАМ ----------
DATA_FILE        = os.path.join(BASE_DIR, 'data.json')
REVIEWS_FILE     = os.path.join(BASE_DIR, 'reviews.json')
LEADS_FILE       = os.path.join(BASE_DIR, 'leads.json')
FAVSTATS_FILE    = os.path.join(BASE_DIR, 'favorites_stats.json')
SURVEY_FILE      = os.path.join(BASE_DIR, 'surveys.json')
REFERRALS_FILE   = os.path.join(BASE_DIR, 'referrals.json')
REMINDERS_FILE   = os.path.join(BASE_DIR, 'reminders.json')
BOT_SURVEY_FILE  = os.path.join(BASE_DIR, 'bot_surveys.json')
SUBSCRIBERS_FILE = os.path.join(BASE_DIR, 'subscribers.json')

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_reviews():
    if not os.path.exists(REVIEWS_FILE):
        return []
    with open(REVIEWS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_bot_surveys():
    if not os.path.exists(BOT_SURVEY_FILE):
        return []
    with open(BOT_SURVEY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_bot_surveys(data):
    with open(BOT_SURVEY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_referrals():
    if not os.path.exists(REFERRALS_FILE):
        return {}
    with open(REFERRALS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_referrals(data):
    with open(REFERRALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return {}
    with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_reminders(data):
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_volume(name):
    import re
    match = re.search(r'(\d+)', name)
    if match:
        vol = int(match.group(1))
        if 50 <= vol <= 2000:
            return vol
    return None

# ---------- КЛАВИАТУРЫ ----------
main_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.row('🏍 Каталог', '🔍 Подобрать мотоцикл')
main_keyboard.row('📞 Написать менеджеру')
main_keyboard.row('🎁 Реферальная программа', '⏰ Напоминания')
main_keyboard.row('🌐 Наши ресурсы')

def category_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton('Street', callback_data='cat_street'),
        types.InlineKeyboardButton('Enduro', callback_data='cat_enduro'),
        types.InlineKeyboardButton('Cruiser', callback_data='cat_cruiser'),
        types.InlineKeyboardButton('Sport', callback_data='cat_sport'),
        types.InlineKeyboardButton('Adventure', callback_data='cat_adventure'),
        types.InlineKeyboardButton('Dirt', callback_data='cat_dirt'),
        types.InlineKeyboardButton('🔄 Все', callback_data='cat_all')
    )
    return kb

def resources_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('📱 Telegram-канал', url='https://t.me/inmove12RU'))
    kb.add(types.InlineKeyboardButton('💬 Группа в Max', url='https://max.ru/join/GwPEorWpR-ca9V3g6SY96YtKVYxxxfAs5Ey8oOgs_tE'))
    kb.add(types.InlineKeyboardButton('🛒 Авито', url='https://www.avito.ru/brands/7451b9435ee675beaf3c50bb265f82c4?src=sharing'))
    return kb

# Хранилище ответов квиза (chat_id → ответы)
quiz_answers = {}

# ---------- КОМАНДА /start ----------
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    # Сохранение подписчика для рассылок
    subs = load_json(SUBSCRIBERS_FILE, [])
    if chat_id not in subs:
        subs.append(chat_id)
        save_json(SUBSCRIBERS_FILE, subs)

    bot.send_message(
        chat_id,
        'Добро пожаловать в INMOVE! 🏍\n\nВыберите действие:',
        reply_markup=main_keyboard
    )

    # Запускаем опрос через 10 секунд (один раз)
    def delayed_survey():
        time.sleep(10)
        try:
            send_survey(chat_id)
        except:
            pass

    threading.Thread(target=delayed_survey).start()

# ---------- ОБРАБОТКА КАТЕГОРИЙ ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category(call):
    category = call.data.replace('cat_', '')
    data = load_data()
    motos = data['motos']

    if category != 'all':
        motos = [m for m in motos if m['category'] == category]

    if not motos:
        bot.answer_callback_query(call.id, 'В этой категории пока нет мотоциклов')
        return

    bot.answer_callback_query(call.id)
    for moto in motos:
        status = '✅ В наличии' if moto['status'] == 'available' else '⚠ Под заказ'
        caption = f"*{moto['name']}*\nКатегория: {moto['category']}\n{status}\n\n{moto['description'][:150]}..."

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('📄 Подробнее на сайте', url=f'https://inmove.ru/moto/{moto["id"]}'))
        msg_text = f"Здравствуйте! Заинтересовал {moto['name']}. Хочу узнать цену и наличие."
        encoded_text = urllib.parse.quote(msg_text)
        markup.add(types.InlineKeyboardButton('💬 Узнать цену', url=f'https://t.me/INMOVE812?text={encoded_text}'))
        markup.add(types.InlineKeyboardButton('📋 Все характеристики', callback_data=f'specs_{moto["id"]}'))
        markup.add(types.InlineKeyboardButton('🔔 Напомнить', callback_data=f'remind_{moto["id"]}'))

        if moto.get('photos') and len(moto['photos']) > 0:
            photo_path = os.path.join(BASE_DIR, moto['photos'][0])
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as f:
                    bot.send_photo(call.message.chat.id, f, caption=caption, parse_mode='Markdown', reply_markup=markup)
                continue
        bot.send_message(call.message.chat.id, caption, parse_mode='Markdown', reply_markup=markup)

    bot.send_message(call.message.chat.id, 'Выберите категорию:', reply_markup=category_keyboard())

# ---------- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ----------
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.strip().lower()

    if 'каталог' in text:
        bot.send_message(
            message.chat.id,
            'Выберите категорию мотоциклов:',
            reply_markup=category_keyboard()
        )

    elif 'подобрать' in text:
        quiz_answers[message.chat.id] = {}
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('🏙 Город', callback_data='quiz_city'),
            types.InlineKeyboardButton('🌲 Лес/бездорожье', callback_data='quiz_offroad'),
            types.InlineKeyboardButton('🛣 Трасса', callback_data='quiz_highway'),
            types.InlineKeyboardButton('🌍 Всё вместе', callback_data='quiz_anywhere')
        )
        bot.send_message(message.chat.id, '🔍 *Подбор мотоцикла*\n\n1/4 — Где планируете кататься?', parse_mode='Markdown', reply_markup=markup)

    elif 'написать менеджеру' in text or 'менеджер' in text:
        msg_text = "Здравствуйте! Пишу с сайта INMOVE. Нужна консультация."
        encoded_text = urllib.parse.quote(msg_text)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('💬 Написать в Telegram', url=f'https://t.me/INMOVE812?text={encoded_text}'))
        markup.add(types.InlineKeyboardButton('💬 Написать в Max', url='https://max.ru/join/GwPEorWpR-ca9V3g6SY96YtKVYxxxfAs5Ey8oOgs_tE'))
        bot.send_message(
            message.chat.id,
            'Свяжитесь с менеджером:\n📞 +7-917-705-72-55',
            reply_markup=markup
        )

    elif 'реферальная' in text or 'реферал' in text:
        referrals = load_referrals()
        # Проверяем, есть ли уже код у этого пользователя
        user_code = None
        for code, data in referrals.items():
            if data['owner_chat_id'] == message.chat.id:
                user_code = code
                break

        if user_code:
            used_count = len(referrals[user_code].get('used_by', []))
            bot.send_message(
                message.chat.id,
                f'🎁 *Ваша реферальная программа*\n\n'
                f'Ваш код: `{user_code}`\n'
                f'Друзей приглашено: *{used_count}*\n'
                f'Ваша скидка: *{used_count * 2000}₽*\n\n'
                f'Отправьте этот код другу. Когда друг назовёт его менеджеру при покупке — вы получите скидку 2000₽!',
                parse_mode='Markdown'
            )
        else:
            new_code = f'INMOVE_{message.chat.id}_{uuid.uuid4().hex[:6].upper()}'
            referrals[new_code] = {
                'owner_chat_id': message.chat.id,
                'created_at': time.strftime('%Y-%m-%d'),
                'used_by': []
            }
            save_referrals(referrals)
            bot.send_message(
                message.chat.id,
                f'🎁 *Ваш персональный реферальный код создан!*\n\n'
                f'Ваш код: `{new_code}`\n\n'
                f'Отправьте его другу. Когда друг назовёт этот код менеджеру при покупке мотоцикла — вы получите скидку *2000₽* на следующую покупку или ТО!\n\n'
                f'Скидки суммируются! Привели 5 друзей — скидка 10 000₽!',
                parse_mode='Markdown'
            )

    elif 'напоминания' in text or 'напомни' in text:
        reminders = load_reminders()
        user_reminders = {k: v for k, v in reminders.items() if str(k) == str(message.chat.id)}

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📋 Мои напоминания', callback_data='remind_list'),
            types.InlineKeyboardButton('❌ Очистить все', callback_data='remind_clear')
        )

        if user_reminders:
            r = list(user_reminders.values())[0]
            bot.send_message(
                message.chat.id,
                f'⏰ *Напоминание о просмотре*\n\n'
                f'У вас активно напоминание о модели *{r["moto_name"]}*\n'
                f'Бот напомнит через некоторое время.',
                parse_mode='Markdown',
                reply_markup=markup
            )
        else:
            bot.send_message(
                message.chat.id,
                '⏰ *Напоминания*\n\n'
                'Когда смотрите мотоцикл в каталоге, нажмите «🔔 Напомнить» — и бот пришлёт вам напоминание.',
                parse_mode='Markdown'
            )

    elif 'наши ресурсы' in text:
        bot.send_message(
            message.chat.id,
            'Подписывайтесь на наши ресурсы:',
            reply_markup=resources_keyboard()
        )

    elif 'цена' in text:
        bot.send_message(message.chat.id, 'Цены уточняйте у менеджера. Напишите "Каталог" чтобы посмотреть модели.')

    elif 'доставка' in text:
        bot.send_message(message.chat.id, 'Доставляем по всей России. Свяжитесь с менеджером для расчёта.')

    elif 'гарантия' in text:
        bot.send_message(message.chat.id, 'Гарантия 14 дней на двигатель. Подробности у менеджера.')

    else:
        bot.send_message(message.chat.id, 'Выберите действие на клавиатуре:', reply_markup=main_keyboard)

# ---------- КВИЗ ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_'))
def handle_quiz(call):
    chat_id = call.message.chat.id
    data = call.data

    if chat_id not in quiz_answers:
        quiz_answers[chat_id] = {}

    # Шаг 1: местность
    if data.startswith('quiz_') and 'terrain' not in data and 'exp' not in data and 'volume' not in data and 'stock' not in data:
        terrain = data.replace('quiz_', '')
        quiz_answers[chat_id]['terrain'] = terrain

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('🟢 Новичок', callback_data='quiz_exp_beginner'),
            types.InlineKeyboardButton('🟡 Средний', callback_data='quiz_exp_medium'),
            types.InlineKeyboardButton('🔴 Опытный', callback_data='quiz_exp_expert')
        )
        bot.edit_message_text('🔍 *Подбор мотоцикла*\n\n2/4 — Ваш опыт?', chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

    # Шаг 2: опыт
    elif 'exp' in data:
        exp = data.replace('quiz_exp_', '')
        quiz_answers[chat_id]['exp'] = exp

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('🐣 До 250 кубов', callback_data='quiz_volume_small'),
            types.InlineKeyboardButton('🐎 250-600 кубов', callback_data='quiz_volume_medium'),
            types.InlineKeyboardButton('🦅 600+ кубов', callback_data='quiz_volume_big'),
            types.InlineKeyboardButton('🤷 Не важно', callback_data='quiz_volume_any')
        )
        bot.edit_message_text('🔍 *Подбор мотоцикла*\n\n3/4 — Предпочтительный объём?', chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

    # Шаг 3: объём
    elif 'volume' in data:
        volume = data.replace('quiz_volume_', '')
        quiz_answers[chat_id]['volume'] = volume

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('✅ Да, в наличии', callback_data='quiz_stock_yes'),
            types.InlineKeyboardButton('🔄 Показать все', callback_data='quiz_stock_no')
        )
        bot.edit_message_text('🔍 *Подбор мотоцикла*\n\n4/4 — Только в наличии?', chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

    # Шаг 4: результат
    elif 'stock' in data:
        stock = data.replace('quiz_stock_', '')
        quiz_answers[chat_id]['stock'] = stock

        answers = quiz_answers[chat_id]
        all_motos = load_data()['motos']
        filtered = all_motos

        terrain = answers.get('terrain')
        if terrain == 'city':
            filtered = [m for m in filtered if m['category'] in ['street', 'cruiser', 'retro']]
        elif terrain == 'offroad':
            filtered = [m for m in filtered if m['category'] in ['enduro', 'dirt']]
        elif terrain == 'highway':
            filtered = [m for m in filtered if m['category'] in ['adventure', 'cruiser', 'sport']]
        elif terrain == 'anywhere':
            filtered = [m for m in filtered if m['category'] in ['adventure', 'enduro']]

        exp = answers.get('exp')
        if exp == 'beginner':
            filtered = [m for m in filtered if extract_volume(m['name']) and extract_volume(m['name']) <= 250]
        elif exp == 'medium':
            filtered = [m for m in filtered if extract_volume(m['name']) and 250 <= extract_volume(m['name']) <= 600]

        volume = answers.get('volume')
        if volume == 'small':
            filtered = [m for m in filtered if extract_volume(m['name']) and extract_volume(m['name']) <= 250]
        elif volume == 'medium':
            filtered = [m for m in filtered if extract_volume(m['name']) and 250 <= extract_volume(m['name']) <= 600]
        elif volume == 'big':
            filtered = [m for m in filtered if extract_volume(m['name']) and extract_volume(m['name']) >= 600]

        if stock == 'yes':
            filtered = [m for m in filtered if m['status'] == 'available']

        if not filtered:
            msg_text = "Здравствуйте! Подбирал мотоцикл через бота, но ничего не подошло. Помогите с выбором."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('💬 Написать менеджеру', url=f'https://t.me/INMOVE812?text={msg_text}'))
            bot.edit_message_text('😔 *Подходящих моделей не найдено.*\n\nНе переживайте — менеджер подберёт для вас лучший вариант!', chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.edit_message_text(f'🎯 *Найдено моделей: {len(filtered)}*\n\nВот что подходит под ваши запросы:', chat_id, call.message.message_id, parse_mode='Markdown')
            for moto in filtered[:3]:
                status = '✅ В наличии' if moto['status'] == 'available' else '⚠ Под заказ'
                caption = f"🏍 *{moto['name']}*\n{moto['category']} | {status}\n⭐ {moto['views']} просмотров"

                msg_text = f"Здравствуйте! Подобрал {moto['name']} через квиз в боте. Хочу узнать цену."
                encoded_text = urllib.parse.quote(msg_text)
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('💬 Узнать цену', url=f'https://t.me/INMOVE812?text={encoded_text}'))
                markup.add(types.InlineKeyboardButton('📄 Подробнее', url=f'https://inmove.ru/moto/{moto["id"]}'))

                if moto.get('photos') and len(moto['photos']) > 0:
                    photo_path = os.path.join(BASE_DIR, moto['photos'][0])
                    if os.path.exists(photo_path):
                        with open(photo_path, 'rb') as f:
                            bot.send_photo(chat_id, f, caption=caption, parse_mode='Markdown', reply_markup=markup)
                        continue
                bot.send_message(chat_id, caption, parse_mode='Markdown', reply_markup=markup)

        bot.send_message(chat_id, 'Готовы посмотреть каталог или связаться с менеджером?', reply_markup=main_keyboard)

# ---------- НАПОМИНАНИЯ ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith('remind_'))
def handle_remind(call):
    chat_id = call.message.chat.id
    data = call.data

    if data == 'remind_list':
        reminders = load_reminders()
        user_reminders = {k: v for k, v in reminders.items() if str(k) == str(chat_id)}
        if user_reminders:
            msg = '⏰ *Ваши напоминания:*\n\n'
            for k, r in user_reminders.items():
                msg += f'• {r["moto_name"]}\n'
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, 'У вас нет активных напоминаний')
        return

    if data == 'remind_clear':
        reminders = load_reminders()
        if str(chat_id) in reminders:
            del reminders[str(chat_id)]
            save_reminders(reminders)
        bot.answer_callback_query(call.id, 'Все напоминания удалены')
        bot.edit_message_text('⏰ Напоминания очищены.', chat_id, call.message.message_id)
        return

    # Установка напоминания на конкретный мотоцикл
    moto_id = int(data.replace('remind_', ''))
    all_motos = load_data()['motos']
    moto = next((m for m in all_motos if m['id'] == moto_id), None)

    if moto:
        reminders = load_reminders()
        reminders[str(chat_id)] = {
            'moto_id': moto_id,
            'moto_name': moto['name'],
            'created_at': time.time()
        }
        save_reminders(reminders)
        bot.answer_callback_query(call.id, f'Напомню о {moto["name"]}!')
        bot.send_message(chat_id, f'🔔 *Напоминание установлено!*\n\nЯ напомню вам о модели *{moto["name"]}*. Не забудьте связаться с менеджером!', parse_mode='Markdown')

        # Отправляем напоминание через 1 час (3600 секунд) — для теста можно поставить 60
        def send_reminder():
            time.sleep(60)  # Для теста 1 минута. В реальности: 3600 (1 час) или 86400 (24 часа)
            try:
                markup = types.InlineKeyboardMarkup()
                msg_text = f"Здравствуйте! Напоминание о модели {moto['name']}. Хочу узнать цену."
                encoded_text = urllib.parse.quote(msg_text)
                markup.add(types.InlineKeyboardButton('💬 Узнать цену', url=f'https://t.me/INMOVE812?text={encoded_text}'))
                bot.send_message(chat_id, f'⏰ *Напоминание!*\n\nВы просили напомнить о модели *{moto["name"]}*. Самое время связаться с менеджером!', parse_mode='Markdown', reply_markup=markup)
                # Удаляем напоминание после отправки
                reminders = load_reminders()
                if str(chat_id) in reminders:
                    del reminders[str(chat_id)]
                    save_reminders(reminders)
            except:
                pass

        threading.Thread(target=send_reminder).start()

# ---------- ОПРОС «ОТКУДА УЗНАЛИ» ----------
def send_survey(chat_id):
    """Отправляет опрос пользователю"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton('📱 Telegram-канал', callback_data='survey_telegram'),
        types.InlineKeyboardButton('💬 Группа в Max', callback_data='survey_max'),
        types.InlineKeyboardButton('🛒 Авито', callback_data='survey_avito'),
        types.InlineKeyboardButton('🔍 Яндекс / Поиск', callback_data='survey_yandex'),
        types.InlineKeyboardButton('👥 Знакомые / Друзья', callback_data='survey_friends'),
        types.InlineKeyboardButton('🤷 Другое', callback_data='survey_other')
    )
    bot.send_message(
        chat_id,
        '📋 *Расскажите, откуда вы о нас узнали?*\n\nЭто поможет нам становиться лучше!',
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('survey_'))
def handle_survey(call):
    chat_id = call.message.chat.id
    answer = call.data.replace('survey_', '')

    answer_names = {
        'telegram': 'Telegram-канал',
        'max': 'Группа в Max',
        'avito': 'Авито',
        'yandex': 'Яндекс / Поиск',
        'friends': 'Знакомые / Друзья',
        'other': 'Другое'
    }

    nice_answer = answer_names.get(answer, answer)

    surveys = load_bot_surveys()
    surveys.append({
        'chat_id': chat_id,
        'answer': nice_answer,
        'timestamp': time.strftime('%Y-%m-%d %H:%M')
    })
    save_bot_surveys(surveys)

    bot.answer_callback_query(call.id, 'Спасибо за ответ!')
    bot.edit_message_text(
        f'✅ *Спасибо!*\n\nВы ответили: *{nice_answer}*\n\nЭто поможет нам развиваться и находить новых клиентов! 🏍',
        chat_id,
        call.message.message_id,
        parse_mode='Markdown'
    )
@bot.callback_query_handler(func=lambda call: call.data.startswith('specs_'))
def show_specs(call):
    moto_id = int(call.data.replace('specs_', ''))
    data = load_data()
    moto = next((m for m in data['motos'] if m['id'] == moto_id), None)

    if not moto:
        bot.answer_callback_query(call.id, 'Мотоцикл не найден')
        return

    full_desc = moto.get('full_description', moto['description'])
    status = '✅ В наличии' if moto['status'] == 'available' else '⚠ Под заказ'

    msg = f"📋 *{moto['name']}*\n\n{full_desc}\n\nСтатус: {status}\nПросмотров: {moto['views']}"

    markup = types.InlineKeyboardMarkup()
    msg_text = f"Здравствуйте! Заинтересовал {moto['name']}. Хочу узнать цену."
    encoded_text = urllib.parse.quote(msg_text)
    markup.add(types.InlineKeyboardButton('💬 Узнать цену', url=f'https://t.me/INMOVE812?text={encoded_text}'))

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)




# ---------- ЗАПУСК ----------
if __name__ == '__main__':
    import threading, admin_bot
    t = threading.Thread(target=admin_bot.admin_bot.polling, kwargs={'none_stop': True}, daemon=True)
    t.start()
    print('Бот INMOVE запущен...')
    bot.polling(none_stop=True)
