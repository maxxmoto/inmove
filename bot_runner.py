import threading
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def start_user_bot():
    try:
        import tg_bot
        tg_bot.bot.polling(none_stop=True)
    except Exception as e:
        print(f'User bot error: {e}')

def start_admin_bot():
    try:
        import admin_bot
        admin_bot.admin_bot.polling(none_stop=True)
    except Exception as e:
        print(f'Admin bot error: {e}')

def start_bots():
    t1 = threading.Thread(target=start_user_bot, daemon=True)
    t2 = threading.Thread(target=start_admin_bot, daemon=True)
    t1.start()
    t2.start()
    print('Bots started!')

if __name__ == '__main__':
    start_bots()
    while True:
        import time
        time.sleep(60)
