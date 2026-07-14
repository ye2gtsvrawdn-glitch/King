import os
import shutil
import zipfile
import datetime
import threading
import json
import random
import string
from telebot import TeleBot, types
from flask import Flask, send_from_directory, request

TOKEN = "8696833882:AAEssBCrX4jgo5LoVnxtrCqkWayzK0dAA7k"
bot = TeleBot(TOKEN)

OWNER_ID = 8394089237
ADMIN_IDS = [8394089237]

# ====== إعدادات السيرفر (تتغير تلقائياً عند النشر) ======
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
PORT = int(os.environ.get("PORT", 5000))

BASE_DIR = "web_hosting"
os.makedirs(BASE_DIR, exist_ok=True)

USERS_FILE = os.path.join(BASE_DIR, "users.json")
PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")
SITES_DIR = os.path.join(BASE_DIR, "sites")
os.makedirs(SITES_DIR, exist_ok=True)
CODES_FILE = os.path.join(BASE_DIR, "codes.json")

# ====== تحميل البيانات ======
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_projects():
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_projects(projects):
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=2)

def load_codes():
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, 'r') as f:
            return json.load(f)
    return {"codes": {}}

def save_codes(codes):
    with open(CODES_FILE, 'w') as f:
        json.dump(codes, f, indent=2)

users = load_users()
projects = load_projects()
user_data = {}

# ====== دوال مساعدة ======
def is_admin(user_id):
    return user_id == OWNER_ID or user_id in ADMIN_IDS

def get_user_data(user_id):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "id": user_id,
            "username": "",
            "first_name": "",
            "join_date": str(datetime.datetime.now()),
            "plan": "free",
            "free_days": 3,
            "projects": [],
            "used_projects": 0,
            "max_projects": 1
        }
        save_users(users)
    return users[uid]

def update_user(user_id, data):
    users[str(user_id)] = data
    save_users(users)

def get_user_projects(user_id):
    user = get_user_data(user_id)
    return [p for p in projects.values() if p['owner_id'] == user_id]

def is_site_name_available(site_name):
    return site_name not in projects

# ====== رفع الملفات ======
def extract_and_deploy_with_name(user_id, file_path, site_name, privacy):
    user = get_user_data(user_id)
    if user['used_projects'] >= user['max_projects']:
        return False, "لقد تجاوزت الحد الأقصى للمشاريع المسموح بها!"

    project_id = site_name
    project_folder = os.path.join(SITES_DIR, project_id)
    
    if os.path.exists(project_folder):
        return False, "هذا الاسم مستخدم بالفعل! اختر اسماً آخر."

    os.makedirs(project_folder, exist_ok=True)

    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(project_folder)
    except:
        shutil.rmtree(project_folder, ignore_errors=True)
        return False, "الملف ليس ZIP صالح!"

    index_path = os.path.join(project_folder, 'index.html')
    if not os.path.exists(index_path):
        for root, dirs, files in os.walk(project_folder):
            if 'index.html' in files:
                index_path = os.path.join(root, 'index.html')
                break
        if not os.path.exists(index_path):
            shutil.rmtree(project_folder, ignore_errors=True)
            return False, "لا يوجد ملف index.html في المشروع!"

    project_url = f"{BASE_URL}/{site_name}/"

    project_data = {
        "id": project_id,
        "site_name": site_name,
        "name": site_name,
        "owner_id": user_id,
        "folder": project_folder,
        "created_at": str(datetime.datetime.now()),
        "url": project_url,
        "privacy": privacy,
        "status": "active"
    }
    projects[project_id] = project_data
    save_projects(projects)

    user['used_projects'] += 1
    user['projects'].append(project_id)
    update_user(user_id, user)

    return True, project_data

def delete_project(user_id, project_id):
    if project_id not in projects:
        return False, "المشروع غير موجود!"
    project = projects[project_id]
    if project['owner_id'] != user_id and not is_admin(user_id):
        return False, "ليس لديك صلاحية حذف هذا المشروع!"
    shutil.rmtree(project['folder'], ignore_errors=True)
    del projects[project_id]
    save_projects(projects)
    user = get_user_data(user_id)
    if project_id in user['projects']:
        user['projects'].remove(project_id)
        user['used_projects'] -= 1
        update_user(user_id, user)
    return True, "تم حذف المشروع بنجاح!"

# ====== تشغيل المواقع عبر Flask ======
flask_app = Flask(__name__)

@flask_app.route('/<path:site_name>/<path:filename>')
def serve_file(site_name, filename):
    project_folder = os.path.join(SITES_DIR, site_name)
    if os.path.exists(project_folder):
        return send_from_directory(project_folder, filename)
    return "الموقع غير موجود", 404

@flask_app.route('/<path:site_name>/')
@flask_app.route('/<path:site_name>')
def serve_site(site_name):
    project_folder = os.path.join(SITES_DIR, site_name)
    if os.path.exists(project_folder):
        if os.path.exists(os.path.join(project_folder, 'index.html')):
            return send_from_directory(project_folder, 'index.html')
    return "الموقع غير موجود", 404

@flask_app.route('/')
def home():
    return """
    <h1>🚀 بوت استضافة المواقع</h1>
    <p>المواقع المستضافة:</p>
    <ul>
    """ + "".join([f"<li><a href='/{p}/'>{p}</a></li>" for p in projects.keys()]) + "</ul>"

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()

# ====== واجهة البوت ======
def get_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("📤 رفع مشروع", callback_data="upload")
    btn2 = types.InlineKeyboardButton("📁 مشاريعي", callback_data="my_projects")
    btn3 = types.InlineKeyboardButton("👤 معلومات حسابي", callback_data="my_info")
    btn4 = types.InlineKeyboardButton("🔑 استخدم كود", callback_data="use_code")
    btn5 = types.InlineKeyboardButton("📋 خطط الاشتراك", callback_data="plans")
    btn6 = types.InlineKeyboardButton("🆓 الوضع المجاني", callback_data="free_mode")
    btn7 = types.InlineKeyboardButton("📢 قناة المبرمج", callback_data="channel")
    btn8 = types.InlineKeyboardButton("👨‍💻 المبرمج", callback_data="developer")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)
    markup.add(btn6)
    markup.add(btn7, btn8)
    
    return markup

# ====== أوامر البوت ======
@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    user = get_user_data(user_id)
    user['username'] = username
    user['first_name'] = first_name
    update_user(user_id, user)
    
    total_users = len(users)
    active_users = len([u for u in users.values() if (datetime.datetime.now() - datetime.datetime.strptime(u['join_date'], '%Y-%m-%d %H:%M:%S.%f')).seconds < 82800])
    
    welcome_text = f"""
🌟 مرحباً بك في بوت استضافة المواقع

📊 **إحصائيات:**
- 👥 مشترك: {total_users}
- ⏳ مشترك - 23 ساعة: {active_users}
- 📁 المشاريع: {user['used_projects']}/{user['max_projects']}

🛡️ **مستوى الحماية:**
- الوضع المجاني: {user['plan']}
- الأيام المجانية: {user['free_days']} يوم

✨ **مميزات البوت:**
- استضافة حقيقية للمواقع
- روابط مباشرة لكل مشروع
- واجهة متطورة
"""

    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu())

# ====== معالجة الأزرار ======
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.from_user.id
    
    if call.data == "upload":
        user = get_user_data(user_id)
        if user['used_projects'] >= user['max_projects']:
            bot.answer_callback_query(call.id, f"تجاوزت الحد الأقصى ({user['max_projects']})!", show_alert=True)
            return
        bot.send_message(call.message.chat.id, "📤 أرسل ملف المشروع (ZIP) الذي يحتوي على index.html")
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("privacy_"):
        data_parts = call.data.split("_")
        privacy = data_parts[1]
        user_id_from_callback = int(data_parts[2])
        
        if user_id != user_id_from_callback:
            bot.answer_callback_query(call.id, "هذا ليس طلبك!", show_alert=True)
            return
        
        if user_id not in user_data:
            bot.answer_callback_query(call.id, "حدث خطأ! حاول مرة أخرى.", show_alert=True)
            return
        
        temp_path = user_data[user_id]["temp_path"]
        site_name = user_data[user_id]["site_name"]
        
        del user_data[user_id]
        
        success, result = extract_and_deploy_with_name(user_id, temp_path, site_name, privacy)
        os.remove(temp_path)
        
        if success:
            bot.edit_message_text(
                f"""
✅ **تم رفع الموقع بنجاح!**

🌐 **الاسم:** {site_name}
🔗 **الرابط:** {result['url']}
🔐 **الخصوصية:** {'عام' if privacy == 'public' else 'خاص'}
📅 **التاريخ:** {result['created_at']}

💡 يمكنك مشاركة الرابط مع أي شخص!
""",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_main_menu()
            )
        else:
            bot.edit_message_text(
                f"❌ فشل الرفع: {result}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_main_menu()
            )
        
        bot.answer_callback_query(call.id)
    
    elif call.data == "my_projects":
        user_projects = get_user_projects(user_id)
        if not user_projects:
            bot.send_message(call.message.chat.id, "📭 ليس لديك أي مشاريع حالياً!")
            bot.answer_callback_query(call.id)
            return
        text = "📁 **مشاريعي:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for p in user_projects:
            text += f"📌 **{p['name']}**\n"
            text += f"🔗 {p['url']}\n"
            text += f"🔐 {'عام' if p.get('privacy') == 'public' else 'خاص'}\n"
            text += f"📅 {p['created_at']}\n\n"
            markup.add(types.InlineKeyboardButton(f"🗑️ حذف {p['name']}", callback_data=f"del_{p['id']}"))
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "use_code":
        bot.send_message(call.message.chat.id, "🔑 أرسل الكود الخاص بك:")
        bot.answer_callback_query(call.id)
    
    elif call.data == "my_info":
        user = get_user_data(user_id)
        text = f"""
👤 **معلومات حسابي**

🆔 المعرف: `{user_id}`
👤 الاسم: {user['first_name']}
📛 المعرف: @{user['username'] or 'بدون'}
📅 تاريخ الانضمام: {user['join_date']}

📊 **الإحصائيات:**
- 📁 المشاريع: {user['used_projects']}/{user['max_projects']}
- 🛡️ الخطة: {user['plan']}
- 📅 الأيام المجانية: {user['free_days']} يوم
"""
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "plans":
        text = """
💎 **خطط الاشتراك**

• ✦ خطة تجريبية ✦
  ⭐ 15 نجمة
  📁 3 مشروع
  📅 1 يوم

• ✦ خطة أساسية ✦
  ⭐ 40 نجمة
  📁 10 مشروع
  📅 3 يوم

• ✦ خطة أسبوعية ✦
  ⭐ 80 نجمة
  📁 25 مشروع
  📅 7 يوم

• ✦ خطة شهرية ✦
  ⭐ 250 نجمة
  📁 100 مشروع
  📅 30 يوم

• ✦ خطة 3 شهور ✦
  ⭐ 600 نجمة
  📁 300 مشروع
  📅 90 يوم

• ✦ خطة سنوية ✦
  ⭐ 2000 نجمة
  📁 1000 مشروع
  📅 365 يوم

💰 **طريقة الدفع:**
1. اختر الخطة المناسبة
2. اضغط على الخطة
3. أرسل النجوم للبوت
4. سيصلك الكود فوراً
"""

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📌 تجريبية", callback_data="plan_trial"),
            types.InlineKeyboardButton("📌 أساسية", callback_data="plan_basic"),
            types.InlineKeyboardButton("📌 أسبوعية", callback_data="plan_weekly"),
            types.InlineKeyboardButton("📌 شهرية", callback_data="plan_monthly"),
            types.InlineKeyboardButton("📌 3 شهور", callback_data="plan_3months"),
            types.InlineKeyboardButton("📌 سنوية", callback_data="plan_yearly"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("plan_"):
        plan_data = {
            "plan_trial": {"name": "تجريبية", "stars": 15, "projects": 3, "days": 1},
            "plan_basic": {"name": "أساسية", "stars": 40, "projects": 10, "days": 3},
            "plan_weekly": {"name": "أسبوعية", "stars": 80, "projects": 25, "days": 7},
            "plan_monthly": {"name": "شهرية", "stars": 250, "projects": 100, "days": 30},
            "plan_3months": {"name": "3 شهور", "stars": 600, "projects": 300, "days": 90},
            "plan_yearly": {"name": "سنوية", "stars": 2000, "projects": 1000, "days": 365}
        }
        
        plan = plan_data.get(call.data)
        if not plan:
            return
        
        text = f"""
✅ **تم اختيار خطة {plan['name']}**

📋 **تفاصيل الخطة:**
- ⭐ النجوم: {plan['stars']}
- 📁 المشاريع: {plan['projects']}
- 📅 المدة: {plan['days']} يوم

💰 **طريقة الدفع:**
1. أرسل {plan['stars']} نجمة للبوت
2. انتظر حتى يصلك كود التفعيل
"""

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 دفع الآن", callback_data=f"pay_{call.data}"),
            types.InlineKeyboardButton("🔙 رجوع للخطط", callback_data="plans")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("pay_"):
        plan_type = call.data.replace("pay_", "")
        
        plan_data = {
            "plan_trial": {"name": "تجريبية", "stars": 15, "projects": 3},
            "plan_basic": {"name": "أساسية", "stars": 40, "projects": 10},
            "plan_weekly": {"name": "أسبوعية", "stars": 80, "projects": 25},
            "plan_monthly": {"name": "شهرية", "stars": 250, "projects": 100},
            "plan_3months": {"name": "3 شهور", "stars": 600, "projects": 300},
            "plan_yearly": {"name": "سنوية", "stars": 2000, "projects": 1000}
        }
        
        plan = plan_data.get(plan_type)
        if not plan:
            return
        
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        codes = load_codes()
        codes["codes"][code] = {
            "projects": plan['projects'],
            "used": False,
            "created_by": call.from_user.id,
            "created_at": str(datetime.datetime.now()),
            "plan": plan['name']
        }
        save_codes(codes)
        
        text = f"""
✅ **تم الدفع بنجاح!**

🎉 **كود التفعيل الخاص بك:**
`{code}`

📋 **تفاصيل الخطة:**
- 📁 المشاريع: {plan['projects']}
- ⭐ النجوم: {plan['stars']}
- 🏷️ الخطة: {plan['name']}

💡 **طريقة الاستخدام:**
1. انسخ الكود
2. اضغط على زر "استخدم كود"
3. الصق الكود
"""

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 نسخ الكود", callback_data=f"copy_{code}"),
            types.InlineKeyboardButton("🔙 رجوع للخطط", callback_data="plans"),
            types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_menu")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "تم إنشاء الكود بنجاح!")
    
    elif call.data.startswith("copy_"):
        code = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, f"تم نسخ الكود: {code}", show_alert=True)
    
    elif call.data == "back_to_menu":
        user = get_user_data(user_id)
        total_users = len(users)
        active_users = len([u for u in users.values() if (datetime.datetime.now() - datetime.datetime.strptime(u['join_date'], '%Y-%m-%d %H:%M:%S.%f')).seconds < 82800])
        
        welcome_text = f"""
🌟 مرحباً بك في بوت استضافة المواقع

📊 **إحصائيات:**
- 👥 مشترك: {total_users}
- ⏳ مشترك - 23 ساعة: {active_users}
- 📁 المشاريع: {user['used_projects']}/{user['max_projects']}

🛡️ **مستوى الحماية:**
- الوضع المجاني: {user['plan']}
- الأيام المجانية: {user['free_days']} يوم

✨ **مميزات البوت:**
- استضافة حقيقية للمواقع
- روابط مباشرة لكل مشروع
- واجهة متطورة
"""
        bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
        bot.answer_callback_query(call.id)
    
    elif call.data == "free_mode":
        user = get_user_data(user_id)
        text = f"""
🆓 **الوضع المجاني**

✅ مفعل حالياً
📅 الأيام المتبقية: {user['free_days']} يوم

💡 يمكنك استخدام مشروع واحد مجاناً!
"""
        bot.send_message(call.message.chat.id, text)
        bot.answer_callback_query(call.id)
    
    elif call.data == "developer":
        bot.send_message(call.message.chat.id, "👨‍💻 المبرمج")
        bot.answer_callback_query(call.id)
    
    elif call.data == "channel":
        bot.send_message(call.message.chat.id, "📢 قناة المبرمج")
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("del_"):
        project_id = call.data.replace("del_", "")
        success, result = delete_project(user_id, project_id)
        bot.answer_callback_query(call.id, result)
        if success:
            bot.edit_message_text("🗑️ تم حذف المشروع!", call.message.chat.id, call.message.message_id)

# ====== رفع الملفات ======
@bot.message_handler(content_types=['document'])
def handle_upload(msg):
    user_id = msg.from_user.id
    file_name = msg.document.file_name
    
    if not file_name.endswith('.zip'):
        bot.reply_to(msg, "⚠️ يرجى إرسال ملف ZIP فقط!", reply_markup=get_main_menu())
        return
    
    file_info = bot.get_file(msg.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_path = os.path.join(BASE_DIR, f"temp_{user_id}_{int(datetime.datetime.now().timestamp())}.zip")
    with open(temp_path, 'wb') as f:
        f.write(downloaded_file)
    
    bot.reply_to(msg, "📥 جاري استقبال الملف...")
    
    msg = bot.reply_to(msg, "✏️ أرسل اسم الموقع الذي تريده (مثال: king):")
    bot.register_next_step_handler(msg, ask_privacy, temp_path)

def ask_privacy(msg, temp_path):
    user_id = msg.from_user.id
    site_name = msg.text.strip().lower()
    
    if not site_name or not site_name.isalnum():
        bot.reply_to(msg, "❌ الاسم غير صالح! استخدم حروف وأرقام فقط.", reply_markup=get_main_menu())
        os.remove(temp_path)
        return
    
    if not is_site_name_available(site_name):
        bot.reply_to(msg, f"❌ الاسم '{site_name}' مستخدم بالفعل! اختر اسم آخر.", reply_markup=get_main_menu())
        os.remove(temp_path)
        return
    
    user_data[user_id] = {"temp_path": temp_path, "site_name": site_name}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🌍 عام", callback_data=f"privacy_public_{user_id}"),
        types.InlineKeyboardButton("🔒 خاص", callback_data=f"privacy_private_{user_id}")
    )
    bot.reply_to(msg, "🔐 اختر نوع الموقع:", reply_markup=markup)

# ====== استخدم كود ======
@bot.message_handler(func=lambda m: m.text and len(m.text) >= 6)
def handle_code(msg):
    user_id = msg.from_user.id
    code = msg.text.strip()
    
    codes = load_codes()
    if code in codes.get("codes", {}):
        code_data = codes["codes"][code]
        if code_data.get("used", False):
            bot.reply_to(msg, "❌ هذا الكود مستخدم بالفعل!", reply_markup=get_main_menu())
            return
        user = get_user_data(user_id)
        user['max_projects'] += code_data.get('projects', 1)
        update_user(user_id, user)
        codes["codes"][code]["used"] = True
        save_codes(codes)
        bot.reply_to(msg, f"✅ تم تفعيل الكود بنجاح! تمت إضافة {code_data.get('projects', 1)} مشروع إضافي.", reply_markup=get_main_menu())
    else:
        bot.reply_to(msg, "❌ كود غير صالح!", reply_markup=get_main_menu())

# ====== لوحة الأدمن ======
@bot.message_handler(commands=['admin'])
def admin_panel(msg):
    if not is_admin(msg.from_user.id):
        bot.reply_to(msg, "⛔️ ليس لديك صلاحية!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users"),
        types.InlineKeyboardButton("📁 المشاريع", callback_data="admin_projects"),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 إشعار عام", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🔑 إنشاء كود", callback_data="admin_create_code"),
        types.InlineKeyboardButton("📋 الكود المستخدمة", callback_data="admin_codes")
    )
    bot.reply_to(msg, "👨‍💻 لوحة تحكم الأدمن", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔️ ليس لديك صلاحية!")
        return
    
    if call.data == "admin_users":
        text = f"👥 **المستخدمين:** {len(users)}\n\n"
        for i, (uid, u) in enumerate(list(users.items())[:20], 1):
            text += f"{i}. {u['first_name']} (@{u['username'] or 'بدون'}) - {u['plan']} - {u['used_projects']}/{u['max_projects']}\n"
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    
    elif call.data == "admin_projects":
        text = f"📁 **المشاريع:** {len(projects)}\n\n"
        for p in list(projects.values())[:20]:
            text += f"📌 {p['name']} - {p['owner_id']}\n🔗 {p['url']}\n🔐 {p.get('privacy', 'عام')}\n\n"
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    
    elif call.data == "admin_stats":
        total_projects = len(projects)
        free_users = len([u for u in users.values() if u['plan'] == 'free'])
        premium_users = len(users) - free_users
        text = f"""
📊 **إحصائيات البوت**

👥 المستخدمين: {len(users)}
🆓 مجاني: {free_users}
⭐ مميز: {premium_users}
📁 المشاريع: {total_projects}
"""
        bot.send_message(call.message.chat.id, text)
    
    elif call.data == "admin_broadcast":
        bot.send_message(call.message.chat.id, "📢 أرسل الرسالة للإشعار العام:")
        bot.register_next_step_handler(call.message, broadcast_message)
    
    elif call.data == "admin_create_code":
        bot.send_message(call.message.chat.id, "✏️ أرسل عدد المشاريع التي يمنحها الكود (رقم):")
        bot.register_next_step_handler(call.message, create_code)
    
    elif call.data == "admin_codes":
        codes = load_codes()
        text = "📋 **الكود المستخدمة:**\n\n"
        for code, data in codes.get("codes", {}).items():
            status = "✅ مستخدم" if data.get("used", False) else "❌ غير مستخدم"
            text += f"🔑 {code} - {data.get('projects', 1)} مشاريع - {status}\n"
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    
    bot.answer_callback_query(call.id)

def broadcast_message(msg):
    if not is_admin(msg.from_user.id):
        return
    text = msg.text
    sent = 0
    for user_id in users:
        try:
            bot.send_message(int(user_id), f"📢 إشعار من الأدمن\n\n{text}")
            sent += 1
        except:
            pass
    bot.reply_to(msg, f"✅ تم إرسال الإشعار لـ {sent} مستخدم", reply_markup=get_main_menu())

def create_code(msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        projects_count = int(msg.text.strip())
        if projects_count < 1:
            raise ValueError
    except:
        bot.reply_to(msg, "❌ يرجى إدخال رقم صحيح أكبر من 0!", reply_markup=get_main_menu())
        return
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    codes = load_codes()
    codes["codes"][code] = {
        "projects": projects_count,
        "used": False,
        "created_by": msg.from_user.id,
        "created_at": str(datetime.datetime.now())
    }
    save_codes(codes)
    bot.reply_to(msg, f"""
✅ **تم إنشاء الكود بنجاح!**

🔑 الكود: `{code}`
📁 عدد المشاريع: {projects_count}
""", parse_mode='Markdown', reply_markup=get_main_menu())

print("🚀 البوت شغال على المنفذ:", PORT)
print("🔗 رابط المواقع: {BASE_URL}")
bot.infinity_polling()
