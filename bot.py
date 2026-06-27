import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import requests
import random
import os
import json
import sqlite3
import re
import yadisk
from datetime import datetime

# ============================================================
# 1. НАСТРОЙКИ (ТВОИ ДАННЫЕ)
# ============================================================

TOKEN = "vk1.a.ZKXnT8bImPyWRbF3TatyyDxVhnbxg1_9RFO6yCLVojZe7MT6M2R8WvfCpnLflN5lu0ZWeAyPV9gdKIPH8N-6_VrlpOfjcA9xuxTpHOxR1HVAoy2ynx5ZUle3Ljg_7dOjAxIofIXXmGH6qJMS1LaULcQDGN2lDAwpogzGOvxzisW4gM9FX0fHTQ2Nq9uLOovM6ENUSQVBiP0cMc9td-XNVQ"
GROUP_ID = -239890913
SUPER_ADMIN_ID = 600605993
YANDEX_TOKEN = "y0__wgBEMDS1t0IGNuWAyDl9bmJGGqjUNo--zbVic_MgERQUGK5PMlY"

YANDEX_BASE_PATH = "/Бот"

print("✅ Бот запускается...")
print(f"VK_TOKEN: {TOKEN[:20]}...")
print(f"GROUP_ID: {GROUP_ID}")
print(f"SUPER_ADMIN_ID: {SUPER_ADMIN_ID}")
print(f"YANDEX_TOKEN: {YANDEX_TOKEN[:20]}...")

# ============================================================
# 2. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================================

def init_db():
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            text TEXT,
            attachments TEXT,
            yandex_links TEXT,
            time TEXT,
            has_files INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_time TEXT
        )
    ''')
    
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, added_by, added_time) VALUES (?, ?, ?)',
                   (SUPER_ADMIN_ID, SUPER_ADMIN_ID, datetime.now().strftime("%d.%m.%Y %H:%M")))
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def is_admin(user_id):
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_admins_list():
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, added_time FROM admins ORDER BY added_time')
    admins = cursor.fetchall()
    conn.close()
    return admins

def add_admin(user_id, added_by):
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO admins (user_id, added_by, added_time)
        VALUES (?, ?, ?)
    ''', (user_id, added_by, datetime.now().strftime("%d.%m.%Y %H:%M")))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    if user_id == SUPER_ADMIN_ID:
        return False
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def get_user_messages(user_id, limit=50, offset=0):
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, text, attachments, yandex_links, time, has_files
        FROM messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    ''', (user_id, limit, offset))
    messages = cursor.fetchall()
    conn.close()
    return messages

def get_all_users():
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT user_id, user_name, COUNT(*) as count
        FROM messages
        GROUP BY user_id
        ORDER BY MAX(id) DESC
    ''')
    users = cursor.fetchall()
    conn.close()
    return users

def get_total_stats():
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM messages')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_msgs = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM messages WHERE has_files = 1')
    total_files = cursor.fetchone()[0]
    conn.close()
    return total_users, total_msgs, total_files

def save_message(user_id, user_name, text, attachments, yandex_links):
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()
    has_files = 1 if attachments else 0
    cursor.execute('''
        INSERT INTO messages (user_id, user_name, text, attachments, yandex_links, time, has_files)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, user_name, text, attachments, yandex_links, 
          datetime.now().strftime("%d.%m.%Y %H:%M"), has_files))
    conn.commit()
    conn.close()

init_db()

# ============================================================
# 3. ИНИЦИАЛИЗАЦИЯ VK
# ============================================================

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id=str(GROUP_ID).replace("-", ""))

# ============================================================
# 4. ИНИЦИАЛИЗАЦИЯ ЯНДЕКС.ДИСКА
# ============================================================

yandex_client = yadisk.Client(token=YANDEX_TOKEN)

def upload_to_yandex(user_id, user_name, local_path, original_filename, text):
    try:
        with yandex_client:
            user_folder = f"{YANDEX_BASE_PATH}/{user_name} (ID: {user_id})"
            try:
                yandex_client.mkdir(user_folder)
            except yadisk.exceptions.PathExistsError:
                pass
            
            date_folder = datetime.now().strftime("%Y-%m-%d")
            full_folder = f"{user_folder}/{date_folder}"
            try:
                yandex_client.mkdir(full_folder)
            except yadisk.exceptions.PathExistsError:
                pass
            
            timestamp = datetime.now().strftime("%H-%M-%S")
            
            if text:
                desc_filename = f"{timestamp}_описание.txt"
                desc_path = f"/tmp/{desc_filename}"
                with open(desc_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                desc_remote = f"{full_folder}/{desc_filename}"
                yandex_client.upload(desc_path, desc_remote)
                os.remove(desc_path)
            
            remote_filename = f"{timestamp}_{original_filename}"
            remote_path = f"{full_folder}/{remote_filename}"
            
            yandex_client.upload(local_path, remote_path)
            
            try:
                yandex_client.publish(remote_path)
                public_url = yandex_client.get_meta(remote_path).public_url
            except:
                public_url = "Ссылка недоступна"
            
            return {
                'path': remote_path,
                'url': public_url,
                'folder': full_folder
            }
    except Exception as e:
        print(f"❌ Ошибка загрузки на Яндекс.Диск: {e}")
        return None

# ============================================================
# 5. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

user_names_cache = {}

def get_user_name(user_id):
    if user_id in user_names_cache:
        return user_names_cache[user_id]
    try:
        user = vk.users.get(user_ids=user_id)[0]
        name = f"{user['first_name']} {user['last_name']}"
        user_names_cache[user_id] = name
        return name
    except:
        return f"Пользователь {user_id}"

def get_user_by_mention(text):
    match = re.search(r'@([a-zA-Z0-9_.]+)', text)
    if match:
        screen_name = match.group(1)
        try:
            user = vk.users.get(user_ids=screen_name)[0]
            return user['id']
        except:
            return None
    
    match = re.search(r'vk\.com/(id)?([a-zA-Z0-9_.]+)', text)
    if match:
        screen_name = match.group(2)
        try:
            if match.group(1) == 'id':
                return int(screen_name)
            else:
                user = vk.users.get(user_ids=screen_name)[0]
                return user['id']
        except:
            return None
    
    match = re.search(r'\b(\d{5,10})\b', text)
    if match:
        return int(match.group(1))
    
    return None

def download_and_upload_file(url, peer_id):
    try:
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            ext = url.split('.')[-1].split('?')[0]
            if not ext or len(ext) > 5:
                ext = 'file'
            filename = f"temp_{random.randint(1, 999999)}.{ext}"
            
            with open(filename, 'wb') as f:
                f.write(r.content)
            
            upload_url = vk.docs.getMessagesUploadServer(peer_id=peer_id)['upload_url']
            with open(filename, 'rb') as f:
                files = {'file': f}
                response = requests.post(upload_url, files=files).json()
            
            os.remove(filename)
            
            doc = vk.docs.save(file=response['file'])[0]
            return f"doc{doc['owner_id']}_{doc['id']}"
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
    return None

# ============================================================
# 6. КЛАВИАТУРЫ
# ============================================================

def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('📤 Отправить файл', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('📋 Правила', color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_admin_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('👥 Список пользователей', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('📊 Статистика', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('👑 Управление админами', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('🗑 Очистить БД', color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def get_admin_management_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('📋 Список админов', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('➕ Добавить админа', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('➖ Удалить админа', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('🏠 В меню', color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_user_list_keyboard(page=0, items_per_page=5):
    keyboard = VkKeyboard(one_time=False)
    users = get_all_users()
    start = page * items_per_page
    end = start + items_per_page
    page_users = users[start:end]
    
    for i, (user_id, user_name, count) in enumerate(page_users, start=1):
        keyboard.add_button(
            f"{i}. {user_name} ({count})", 
            color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({'action': 'view_user', 'user_id': user_id})
        )
        keyboard.add_line()
    
    if page > 0:
        keyboard.add_button('⬅️ Назад', color=VkKeyboardColor.SECONDARY, 
                           payload=json.dumps({'action': 'users_page', 'page': page-1}))
    if end < len(users):
        keyboard.add_button('Вперед ➡️', color=VkKeyboardColor.SECONDARY,
                           payload=json.dumps({'action': 'users_page', 'page': page+1}))
    
    keyboard.add_line()
    keyboard.add_button('🏠 В меню', color=VkKeyboardColor.NEGATIVE,
                       payload=json.dumps({'action': 'to_menu'}))
    return keyboard.get_keyboard()

def get_user_detail_keyboard(user_id, page=0):
    keyboard = VkKeyboard(one_time=False)
    messages = get_user_messages(user_id, limit=1, offset=page)
    
    if messages:
        msg = messages[0]
        msg_id, text, attachments, yandex_links, time, has_files = msg
        file_status = "📎 с файлом" if has_files else "📝 без файла"
        keyboard.add_button(f'📄 {file_status} {time}', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        
        if yandex_links:
            keyboard.add_button('☁️ Ссылка на Яндекс.Диск', color=VkKeyboardColor.PRIMARY,
                               payload=json.dumps({'action': 'show_yandex_link', 'links': yandex_links}))
            keyboard.add_line()
        
        total_msgs = len(get_user_messages(user_id, limit=9999))
        
        if page > 0:
            keyboard.add_button('⬅️ Пред.', color=VkKeyboardColor.SECONDARY,
                               payload=json.dumps({'action': 'user_msg', 'user_id': user_id, 'page': page-1}))
        if page < total_msgs - 1:
            keyboard.add_button('След. ➡️', color=VkKeyboardColor.SECONDARY,
                               payload=json.dumps({'action': 'user_msg', 'user_id': user_id, 'page': page+1}))
    
    keyboard.add_line()
    keyboard.add_button('⬅️ К списку', color=VkKeyboardColor.NEGATIVE,
                       payload=json.dumps({'action': 'back_to_list'}))
    return keyboard.get_keyboard()

# ============================================================
# 7. ОТПРАВКА СООБЩЕНИЙ
# ============================================================

def send_welcome_message(peer_id):
    welcome_text = """📤 Как работать со мной:
1. Напиши текст (описание файла)
2. Прикрепи фото, видео или документ
3. Отправь всё одним сообщением

Остались вопросы? Жми "Помощь" """
    
    vk.messages.send(
        peer_id=peer_id,
        message=welcome_text,
        keyboard=get_main_keyboard(),
        random_id=random.randint(1, 2**31)
    )

def send_help(peer_id):
    help_text = """Прикрепи файл и напиши текст в одном сообщении
Бот принимает: фото, видео, документы, аудио
Максимальный размер: 50 МБ"""
    
    vk.messages.send(
        peer_id=peer_id,
        message=help_text,
        keyboard=get_main_keyboard(),
        random_id=random.randint(1, 2**31)
    )

def send_rules(peer_id):
    rules_text = """Запрещено отправлять запрещённый контент
Не спамить, не злоупотреблять
Не использовать в личных целях"""
    
    vk.messages.send(
        peer_id=peer_id,
        message=rules_text,
        keyboard=get_main_keyboard(),
        random_id=random.randint(1, 2**31)
    )

def send_admin_menu(peer_id):
    if not is_admin(peer_id):
        vk.messages.send(
            peer_id=peer_id,
            message="⛔ У вас нет прав администратора",
            keyboard=get_main_keyboard(),
            random_id=random.randint(1, 2**31)
        )
        return
    
    total_users, total_msgs, total_files = get_total_stats()
    admins = get_admins_list()
    
    menu_text = f"""👑 Админ-панель

📊 Статистика:
• Всего пользователей: {total_users}
• Всего сообщений: {total_msgs}
• Файлов загружено: {total_files}
• Администраторов: {len(admins)}

Выбери действие:"""
    
    vk.messages.send(
        peer_id=peer_id,
        message=menu_text,
        keyboard=get_admin_keyboard(),
        random_id=random.randint(1, 2**31)
    )

def send_yandex_link(peer_id, links_json):
    try:
        links = json.loads(links_json)
        if isinstance(links, list):
            text = "☁️ Ссылки на Яндекс.Диск:\n\n"
            for link in links:
                text += f"• {link}\n"
        else:
            text = f"☁️ Ссылка на Яндекс.Диск:\n{links}"
        
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            keyboard=get_admin_keyboard(),
            random_id=random.randint(1, 2**31)
        )
    except:
        pass

# ============================================================
# 8. ОСНОВНОЙ ЦИКЛ БОТА
# ============================================================

print("🤖 Бот запущен и готов к работе!")
print(f"📱 Группа ID: {GROUP_ID}")
print(f"👑 Главный админ: {SUPER_ADMIN_ID}")

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.message
                if not msg:
                    continue
                
                peer_id = msg.peer_id
                text = msg.text or ""
                text_lower = text.lower()
                payload = msg.payload if hasattr(msg, 'payload') else None
                
                # ================================================
                # 8.1 КОМАНДЫ ПОЛЬЗОВАТЕЛЯ
                # ================================================
                
                if text_lower == "отправить файл" or text_lower == "📤 отправить файл":
                    vk.messages.send(
                        peer_id=peer_id,
                        message="📎 Напиши описание и прикрепи файл в одном сообщении",
                        keyboard=get_main_keyboard(),
                        random_id=random.randint(1, 2**31)
                    )
                    continue
                
                elif text_lower == "помощь" or text_lower == "ℹ️ помощь":
                    send_help(peer_id)
                    continue
                
                elif text_lower == "правила" or text_lower == "📋 правила":
                    send_rules(peer_id)
                    continue
                
                # ================================================
                # 8.2 АДМИН-КОМАНДЫ
                # ================================================
                
                if is_admin(peer_id):
                    
                    if text_lower == "админ панель" or text_lower == "👑 админ панель" or text_lower == "/admin":
                        send_admin_menu(peer_id)
                        continue
                    
                    elif text_lower == "👥 список пользователей" or text_lower == "список пользователей":
                        users = get_all_users()
                        if not users:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="📭 Пока нет ни одного сообщения",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                        else:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="👥 Список пользователей:",
                                keyboard=get_user_list_keyboard(0),
                                random_id=random.randint(1, 2**31)
                            )
                        continue
                    
                    elif text_lower == "📊 статистика" or text_lower == "статистика":
                        total_users, total_msgs, total_files = get_total_stats()
                        vk.messages.send(
                            peer_id=peer_id,
                            message=f"📊 Статистика:\nПользователей: {total_users}\nСообщений: {total_msgs}\nФайлов: {total_files}",
                            keyboard=get_admin_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower == "👑 управление админами" or text_lower == "управление админами":
                        if peer_id != SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Только главный администратор может управлять админами",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message="👑 Управление администраторами:\n\n"
                                   "• Нажми «Список админов» — увидишь всех\n"
                                   "• Нажми «Добавить админа» — отправь команду /addadmin @username\n"
                                   "• Нажми «Удалить админа» — отправь команду /removeadmin @username",
                            keyboard=get_admin_management_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower == "📋 список админов" or text_lower == "список админов":
                        admins = get_admins_list()
                        if not admins:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="📭 Список админов пуст",
                                keyboard=get_admin_management_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        admin_text = "👑 Список администраторов:\n\n"
                        for admin_id, added_time in admins:
                            name = get_user_name(admin_id)
                            is_super = "⭐ (главный)" if admin_id == SUPER_ADMIN_ID else ""
                            admin_text += f"• {name} (ID: {admin_id}) {is_super}\n"
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message=admin_text,
                            keyboard=get_admin_management_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower == "➕ добавить админа" or text_lower == "добавить админа":
                        if peer_id != SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Только главный администратор может добавлять админов",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message="✏️ Отправь команду:\n/addadmin @username\n\n"
                                   "Например: /addadmin @durov\n"
                                   "Или: /addadmin 123456789",
                            keyboard=get_admin_management_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower == "➖ удалить админа" or text_lower == "удалить админа":
                        if peer_id != SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Только главный администратор может удалять админов",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message="✏️ Отправь команду:\n/removeadmin @username\n\n"
                                   "Например: /removeadmin @durov\n"
                                   "Или: /removeadmin 123456789",
                            keyboard=get_admin_management_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower.startswith("/addadmin"):
                        if peer_id != SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Только главный администратор может добавлять админов",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        target_id = get_user_by_mention(text)
                        if not target_id:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="❌ Не удалось найти пользователя. Используй @username или ID",
                                keyboard=get_admin_management_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        if is_admin(target_id):
                            vk.messages.send(
                                peer_id=peer_id,
                                message=f"⚠️ Пользователь {get_user_name(target_id)} уже является админом",
                                keyboard=get_admin_management_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        add_admin(target_id, peer_id)
                        
                        try:
                            vk.messages.send(
                                peer_id=target_id,
                                message="👑 Поздравляю! Теперь ты администратор этого бота.\n"
                                       "Напиши «Админ панель» или /admin для управления.",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                        except:
                            pass
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message=f"✅ Пользователь {get_user_name(target_id)} добавлен в админы",
                            keyboard=get_admin_management_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower.startswith("/removeadmin"):
                        if peer_id != SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Только главный администратор может удалять админов",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        target_id = get_user_by_mention(text)
                        if not target_id:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="❌ Не удалось найти пользователя. Используй @username или ID",
                                keyboard=get_admin_management_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        if target_id == SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Нельзя удалить главного администратора",
                                keyboard=get_admin_management_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        if not is_admin(target_id):
                            vk.messages.send(
                                peer_id=peer_id,
                                message=f"⚠️ Пользователь {get_user_name(target_id)} не является админом",
                                keyboard=get_admin_management_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        remove_admin(target_id)
                        vk.messages.send(
                            peer_id=peer_id,
                            message=f"✅ Пользователь {get_user_name(target_id)} удалён из админов",
                            keyboard=get_admin_management_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                    
                    elif text_lower == "🗑 очистить бд" or text_lower == "очистить бд":
                        if peer_id != SUPER_ADMIN_ID:
                            vk.messages.send(
                                peer_id=peer_id,
                                message="⛔ Только главный администратор может очищать БД",
                                keyboard=get_admin_keyboard(),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        conn = sqlite3.connect('messages.db')
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM messages')
                        conn.commit()
                        conn.close()
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message="🗑 База данных очищена",
                            keyboard=get_admin_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        continue
                
                # ================================================
                # 8.3 ОБРАБОТКА PAYLOAD (нажатий на кнопки)
                # ================================================
                if payload:
                    try:
                        data = json.loads(payload)
                        action = data.get('action')
                        
                        if action == 'users_page':
                            page = data.get('page', 0)
                            vk.messages.send(
                                peer_id=peer_id,
                                message=f"👥 Список пользователей (страница {page+1}):",
                                keyboard=get_user_list_keyboard(page),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        elif action == 'view_user':
                            user_id = data.get('user_id')
                            vk.messages.send(
                                peer_id=peer_id,
                                message=f"👤 Просмотр сообщений пользователя {get_user_name(user_id)}:",
                                keyboard=get_user_detail_keyboard(user_id, page=0),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        elif action == 'user_msg':
                            user_id = data.get('user_id')
                            page = data.get('page', 0)
                            
                            messages = get_user_messages(user_id, limit=1, offset=page)
                            if messages:
                                msg = messages[0]
                                msg_id, msg_text, attachments, yandex_links, msg_time, has_files = msg
                                name = get_user_name(user_id)
                                
                                display_text = f"""👤 {name}
🕐 {msg_time}
📝 {msg_text or '(без текста)'}"""
                                
                                if yandex_links:
                                    display_text += "\n\n☁️ Файл сохранён на Яндекс.Диске"
                                
                                vk.messages.send(
                                    peer_id=peer_id,
                                    message=display_text,
                                    attachment=attachments if attachments else None,
                                    keyboard=get_user_detail_keyboard(user_id, page=page),
                                    random_id=random.randint(1, 2**31)
                                )
                            continue
                        
                        elif action == 'show_yandex_link':
                            links = data.get('links')
                            send_yandex_link(peer_id, links)
                            continue
                        
                        elif action == 'back_to_list':
                            vk.messages.send(
                                peer_id=peer_id,
                                message="👥 Список пользователей:",
                                keyboard=get_user_list_keyboard(0),
                                random_id=random.randint(1, 2**31)
                            )
                            continue
                        
                        elif action == 'to_menu':
                            send_admin_menu(peer_id)
                            continue
                            
                    except Exception as e:
                        print(f"Ошибка обработки payload: {e}")
                        pass
                
                # ================================================
                # 8.4 ОБРАБОТКА ВЛОЖЕНИЙ
                # ================================================
                attachments = []
                yandex_links = []
                temp_files = []
                
                if hasattr(msg, 'attachments') and msg.attachments:
                    for att in msg.attachments:
                        if att['type'] == 'photo':
                            sizes = att['photo']['sizes']
                            largest = max(sizes, key=lambda x: x['width'] * x['height'])
                            url = largest['url']
                            
                            attach = download_and_upload_file(url, peer_id)
                            if attach:
                                attachments.append(attach)
                            
                            try:
                                r = requests.get(url, stream=True)
                                if r.status_code == 200:
                                    ext = 'jpg'
                                    filename = f"temp_{random.randint(1, 999999)}.{ext}"
                                    with open(filename, 'wb') as f:
                                        f.write(r.content)
                                    
                                    original_filename = f"photo_{datetime.now().strftime('%H%M%S')}.jpg"
                                    result = upload_to_yandex(peer_id, get_user_name(peer_id), 
                                                             filename, original_filename, text)
                                    if result:
                                        yandex_links.append(result['url'])
                                    os.remove(filename)
                            except Exception as e:
                                print(f"Ошибка загрузки фото на Яндекс.Диск: {e}")
                        
                        elif att['type'] == 'doc':
                            doc = att['doc']
                            attach = f"doc{doc['owner_id']}_{doc['id']}"
                            attachments.append(attach)
                            
                            try:
                                url = doc['url']
                                r = requests.get(url, stream=True)
                                if r.status_code == 200:
                                    ext = doc['ext'] or 'file'
                                    filename = f"temp_{random.randint(1, 999999)}.{ext}"
                                    with open(filename, 'wb') as f:
                                        f.write(r.content)
                                    
                                    original_filename = doc['title'] or f"document.{ext}"
                                    result = upload_to_yandex(peer_id, get_user_name(peer_id),
                                                             filename, original_filename, text)
                                    if result:
                                        yandex_links.append(result['url'])
                                    os.remove(filename)
                            except Exception as e:
                                print(f"Ошибка загрузки документа на Яндекс.Диск: {e}")
                        
                        elif att['type'] == 'video':
                            video = att['video']
                            attachments.append(f"video{video['owner_id']}_{video['id']}")
                            yandex_links.append(f"Видео ID: {video['owner_id']}_{video['id']}")
                        
                        elif att['type'] == 'audio':
                            audio = att['audio']
                            attachments.append(f"audio{audio['owner_id']}_{audio['id']}")
                
                # ================================================
                # 8.5 СОХРАНЕНИЕ СООБЩЕНИЯ
                # ================================================
                if attachments or text.strip():
                    if not is_admin(peer_id):
                        user_name = get_user_name(peer_id)
                        attach_str = ",".join(attachments) if attachments else ''
                        yandex_links_str = json.dumps(yandex_links) if yandex_links else ''
                        
                        save_message(peer_id, user_name, text, attach_str, yandex_links_str)
                        
                        response_text = "✅ Сообщение получено и отправлено администратору"
                        if attachments and text.strip():
                            response_text = "✅ Файл с описанием получен и отправлен администратору"
                        elif attachments:
                            response_text = "✅ Файл получен и отправлен администратору"
                        
                        if yandex_links:
                            response_text += "\n\n☁️ Файл также сохранён на Яндекс.Диске"
                        
                        vk.messages.send(
                            peer_id=peer_id,
                            message=response_text,
                            keyboard=get_main_keyboard(),
                            random_id=random.randint(1, 2**31)
                        )
                        
                        admins = get_admins_list()
                        for admin_id, _ in admins:
                            try:
                                admin_text = f"📁 Новое сообщение от {user_name} (ID: {peer_id})"
                                if text.strip():
                                    admin_text += f"\n📝 {text}"
                                admin_text += f"\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                                if attachments:
                                    admin_text += f"\n📎 Файлов: {len(attachments)}"
                                if yandex_links:
                                    admin_text += f"\n☁️ Яндекс.Диск: {len(yandex_links)} файлов"
                                
                                vk.messages.send(
                                    peer_id=admin_id,
                                    message=admin_text,
                                    attachment=attach_str if attachments else None,
                                    keyboard=get_admin_keyboard(),
                                    random_id=random.randint(1, 2**31)
                                )
                            except:
                                pass
                
    except Exception as e:
        print(f"Ошибка: {e}")
