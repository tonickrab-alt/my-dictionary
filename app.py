import os
import sqlite3
import string
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_opendict_ultimate'

# ==========================================
# 1. ระบบฐานข้อมูล (Database Setup)
# ==========================================
THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(THIS_FOLDER, 'opendict.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # ตารางผู้ใช้งาน
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    username TEXT UNIQUE NOT NULL, 
                    password TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    bio TEXT DEFAULT '')''')
    # ตารางคำศัพท์
    c.execute('''CREATE TABLE IF NOT EXISTS words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    term TEXT NOT NULL, 
                    definition TEXT NOT NULL, 
                    user_id INTEGER NOT NULL,
                    reported INTEGER DEFAULT 0,
                    voting_disabled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # ตารางคอมเมนต์
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    word_id INTEGER, 
                    user_id INTEGER, 
                    text TEXT)''')
    # ตารางโหวต
    c.execute('''CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    word_id INTEGER, 
                    user_id INTEGER, 
                    vote_type INTEGER)''') # 1=Like, 2=Dislike
    # ตาราง WOTW
    c.execute('''CREATE TABLE IF NOT EXISTS wotw_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    word_id INTEGER, 
                    year INTEGER, 
                    week_num INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS wotw_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    candidate_id INTEGER, 
                    user_id INTEGER)''')
    # ตาราง Logs
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    action TEXT,
                    target TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def log_activity(username, action, target):
    conn = get_db_connection()
    conn.execute('INSERT INTO activity_logs (username, action, target) VALUES (?, ?, ?)', (username, action, target))
    conn.commit()
    conn.close()

def get_current_week():
    return datetime.now().isocalendar()[0:2]

def get_prev_week():
    return (datetime.now() - timedelta(days=7)).isocalendar()[0:2]

# ==========================================
# 2. HTML Templates (UI / UX / CSS)
# ==========================================
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>พจนานุกรมเสรี (OpenDict)</title>
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Prompt', sans-serif; background-color: #f4f7f6; margin: 0; padding: 0; color: #333; overflow-x: hidden; }
        .container { max-width: 850px; margin: auto; padding: 20px; }
        .nav { background: linear-gradient(135deg, #1a252f, #2c3e50); padding: 15px 20px; color: white; display: flex; justify-content: space-between; align-items: center; border-radius: 0 0 15px 15px; flex-wrap: wrap; gap: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .nav-logo { display: flex; align-items: center; gap: 10px; font-size: 24px; font-weight: bold; text-decoration: none; color: white; transition: transform 0.3s; }
        .nav-logo:hover { transform: scale(1.05); }
        .nav-logo img { height: 40px; border-radius: 8px; }
        .nav-links a { color: #ecf0f1; text-decoration: none; margin-left: 15px; font-weight: 500; font-size: 15px; padding: 5px 10px; border-radius: 5px; transition: all 0.3s; }
        .nav-links a:hover { background: rgba(255,255,255,0.1); color: #34db98; }
        
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-top: 20px; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); animation: slideUp 0.6s ease-out backwards; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.12); }
        @keyframes slideUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        
        input, textarea { width: 100%; padding: 12px; margin: 8px 0; border: 2px solid #ecf0f1; border-radius: 8px; box-sizing: border-box; font-family: 'Prompt', sans-serif; transition: border-color 0.3s; }
        input:focus, textarea:focus { outline: none; border-color: #3498db; }
        
        button, .btn-link { display: inline-block; text-align: center; background-color: #3498db; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none; transition: all 0.2s; box-sizing: border-box; }
        button:hover, .btn-link:hover { background-color: #2980b9; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(52, 152, 219, 0.3); }
        button:active, .btn-link:active { transform: scale(0.95); }
        
        .btn-green { background-color: #2ecc71; } .btn-green:hover { background-color: #27ae60; box-shadow: 0 5px 15px rgba(46, 204, 113, 0.3); }
        .btn-red { background-color: #e74c3c; } .btn-red:hover { background-color: #c0392b; box-shadow: 0 5px 15px rgba(231, 76, 60, 0.3); }
        .btn-gray { background-color: #95a5a6; } .btn-gray:hover { background-color: #7f8c8d; }
        
        .alphabets { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0; justify-content: center; }
        .alphabets a { padding: 8px 15px; background: #ecf0f1; color: #2c3e50; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 500; transition: all 0.2s; }
        .alphabets a:hover { background: #3498db; color: white; transform: scale(1.1); }
        
        .word-title { font-size: 28px; font-weight: bold; color: #2c3e50; text-decoration: none; transition: color 0.3s; }
        .word-title:hover { color: #3498db; }
        .word-def { font-size: 17px; margin: 15px 0; white-space: pre-wrap; line-height: 1.7; color: #444; }
        
        .vote-btn { padding: 8px 20px; margin-right: 5px; border-radius: 30px; font-size: 14px; }
        .like { background-color: #2ecc71; } .dislike { background-color: #e74c3c; }
        .wotw-btn { background: linear-gradient(45deg, #f1c40f, #f39c12); color: white; }
        .wotw-btn:hover { background: linear-gradient(45deg, #f39c12, #e67e22); }
        
        .comment-box { background: #fdfdfd; padding: 15px; margin-top: 15px; border-left: 5px solid #3498db; border-radius: 0 8px 8px 0; transition: transform 0.2s; }
        .comment-box:hover { transform: translateX(5px); border-color: #2ecc71; }
        
        .winner-card { background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); color: white; border: none; animation: pulse-glow 2s infinite; text-align: center; padding: 40px 20px;}
        @keyframes pulse-glow { 0% { box-shadow: 0 0 0 0 rgba(246, 211, 101, 0.6); } 70% { box-shadow: 0 0 0 15px rgba(246, 211, 101, 0); } 100% { box-shadow: 0 0 0 0 rgba(246, 211, 101, 0); } }
        
        .alert { padding: 15px; background-color: #d4edda; color: #155724; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #28a745; animation: slideDown 0.4s ease-out; font-weight: bold;}
        .alert-error { background-color: #f8d7da; color: #721c24; border-left-color: #e74c3c; }
        @keyframes slideDown { from { opacity:0; transform:translateY(-10px); } to { opacity:1; transform:translateY(0); } }
        
        .badge-admin { background: #e67e22; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; margin-left: 5px; vertical-align: middle;}
        .reported-card { border: 2px solid #e74c3c; background: #fff5f5; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; } th, td { border: 1px solid #ecf0f1; padding: 12px; text-align: left; } th { background-color: #f8f9fa; color: #2c3e50; }
    </style>
</head>
<body>
    <div class="nav container">
        <a href="/" class="nav-logo">
            <img src="/static/logo.png" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';" style="display:inline;">
            <span style="display:none;">📚</span>
            พจนานุกรมเสรี
        </a>
        <div class="nav-links">
            {% if session.get('user_id') %}
                <a href="/wotw">🏆 แชมป์สัปดาห์</a>
                <a href="/add">➕ บัญญัติศัพท์</a>
                <a href="/profile/{{ session.get('username') }}">👤 โปรไฟล์</a>
                {% if session.get('role') == 'admin' %}
                    <a href="/admin" style="background:#e67e22; border-radius:15px; padding:5px 12px;">🛡️ Admin</a>
                {% endif %}
                <a href="/logout">🚪 ออก</a>
            {% else %}
                <a href="/login">เข้าสู่ระบบ</a>
                <a href="/signup">สมัครสมาชิก</a>
            {% endif %}
        </div>
    </div>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert {% if category == 'error' %}alert-error{% endif %}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <!-- CONTENT_PLACEHOLDER -->
    </div>
</body>
</html>
"""

HTML_LOGIN = """
<div class="card" style="max-width: 400px; margin: 50px auto; text-align: center;">
    <h2 style="color: #2c3e50; margin-bottom: 25px;">เข้าสู่ระบบ</h2>
    <form method="POST" action="/login">
        <input type="text" name="username" required placeholder="ชื่อผู้ใช้ (Username)">
        <input type="password" name="password" required placeholder="รหัสผ่าน (Password)">
        <button type="submit" style="margin-top: 15px; width: 100%;">🚀 เข้าสู่ระบบ</button>
    </form>
    <p style="margin-top: 20px;">ยังไม่มีบัญชีใช่ไหม? <a href="/signup" style="color: #3498db; font-weight: bold; text-decoration: none;">สมัครสมาชิกเลย!</a></p>
</div>
"""

HTML_SIGNUP = """
<div class="card" style="max-width: 400px; margin: 50px auto; text-align: center;">
    <h2 style="color: #2c3e50; margin-bottom: 25px;">✨ สมัครสมาชิก</h2>
    <form method="POST" action="/signup">
        <input type="text" name="username" required placeholder="ตั้งชื่อผู้ใช้เท่ๆ (พิมพ์ admin เพื่อเป็นผู้ดูแล)">
        <input type="password" name="password" required placeholder="ตั้งรหัสผ่าน">
        <button type="submit" class="btn-green" style="margin-top: 15px; width: 100%;">🎉 สมัครสมาชิก</button>
    </form>
    <p style="margin-top: 20px;">มีบัญชีอยู่แล้ว? <a href="/login" style="color: #3498db; font-weight: bold; text-decoration: none;">เข้าสู่ระบบ</a></p>
</div>
"""

HTML_INDEX = """
<div class="card" style="text-align: center;">
    <h3 style="margin-top: 0; color: #2c3e50;">🔍 ค้นหาตามหมวดหมู่อักษร</h3>
    <div class="alphabets">
        <a href="/" style="background: #3498db; color: white;">ทั้งหมด</a>
        {% for letter in alphabets %}<a href="/alphabet/{{ letter }}">{{ letter }}</a>{% endfor %}
    </div>
</div>

<h2 style="margin-top: 30px; color: #2c3e50; border-bottom: 3px solid #3498db; display: inline-block; padding-bottom: 5px;">{{ title }}</h2>
{% for word in words %}
<div class="card {% if word['reported'] %}reported-card{% endif %}">
    <a href="/word/{{ word['id'] }}" class="word-title">{{ word['term'] }}</a>
    {% if word['reported'] %}<span style="color:red; font-size:12px; font-weight:bold; margin-left:10px;">🚨 ถูกรายงาน</span>{% endif %}
    <p class="word-def">{{ word['definition'][:120] }}...</p>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px; border-top: 1px solid #eee; padding-top: 15px;">
        <span style="font-size: 14px; color: #7f8c8d;">ผู้บัญญัติ: <a href="/profile/{{ word['username'] }}" style="color: #3498db; text-decoration: none; font-weight: bold;">{{ word['username'] }}</a></span>
        <div>
            <span style="color: #27ae60; font-weight: bold; background: #e8f8f5; padding: 5px 10px; border-radius: 15px;">👍 {{ word['likes'] }}</span> 
            <span style="color: #c0392b; font-weight: bold; background: #fdedec; padding: 5px 10px; border-radius: 15px; margin-left: 5px;">👎 {{ word['dislikes'] }}</span>
        </div>
    </div>
</div>
{% else %}
<div class="card" style="text-align: center; padding: 50px 20px;">
    <p style="font-size: 18px; color: #7f8c8d;">ยังไม่มีคำศัพท์ในหมวดหมู่นี้ 😢</p>
    {% if session.get('user_id') %}<a href="/add" class="btn-link" style="margin-top:10px;">✨ บัญญัติศัพท์คำแรกเลย!</a>{% endif %}
</div>
{% endfor %}
"""

HTML_WORD = """
<div class="card">
    <a href="/" style="text-decoration: none; color: #3498db; font-weight: bold; font-size: 15px;">&larr; ย้อนกลับ</a>
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-top: 15px;">
        <div>
            <h1 class="word-title" style="font-size: 40px; margin: 0 0 5px 0;">{{ word['term'] }}</h1>
            <p style="color: #7f8c8d; margin-top: 0;">บัญญัติโดย: <a href="/profile/{{ word['username'] }}" style="color: #3498db; text-decoration: none;"><b>{{ word['username'] }}</b></a></p>
        </div>
        {% if session.get('user_id') %}
            <form action="/report/{{ word['id'] }}" method="POST" style="margin: 0;" onsubmit="return confirm('คุณต้องการรายงานคำศัพท์นี้ว่าไม่เหมาะสมใช่หรือไม่?');">
                <button type="submit" class="btn-red" style="padding: 6px 12px; font-size: 12px; border-radius: 20px;">🚨 รายงาน</button>
            </form>
        {% endif %}
    </div>
    
    <div class="word-def" style="background: #f8f9fa; padding: 25px; border-radius: 12px; font-size: 18px; border-left: 5px solid #2ecc71; margin: 25px 0;">
        {{ word['definition'] }}
    </div>
    
    <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center; border-top: 1px solid #eee; padding-top: 20px;">
        {% if word['voting_disabled'] == 0 %}
            <form action="/vote/{{ word['id'] }}/1" method="POST" style="margin: 0;"><button class="vote-btn like">👍 ถูกใจ ({{ word['likes'] }})</button></form>
            <form action="/vote/{{ word['id'] }}/2" method="POST" style="margin: 0;"><button class="vote-btn dislike">👎 ไม่ถูกใจ ({{ word['dislikes'] }})</button></form>
        {% else %}
            <span style="color: #e74c3c; font-weight: bold; background: #fdedec; padding: 8px 15px; border-radius: 20px;">🔒 การโหวตถูกปิดโดย Admin</span>
        {% endif %}
        <div style="flex-grow: 1;"></div>
        <form action="/nominate/{{ word['id'] }}" method="POST" style="margin: 0;"><button class="vote-btn wotw-btn">⭐ เสนอชื่อชิงแชมป์สัปดาห์</button></form>
    </div>
</div>

<div class="card">
    <h3 style="margin-top: 0; color: #2c3e50;">💬 แสดงความคิดเห็น</h3>
    {% if session.get('user_id') %}
        <form action="/comment/{{ word['id'] }}" method="POST">
            <textarea name="comment" rows="3" placeholder="ร่วมแสดงความคิดเห็นเกี่ยวกับศัพท์คำนี้..." required></textarea>
            <button type="submit" style="width: auto; padding: 10px 25px; border-radius: 20px;">ส่งความเห็น</button>
        </form>
    {% else %}
        <p>กรุณา <a href="/login">เข้าสู่ระบบ</a> เพื่อแสดงความคิดเห็น</p>
    {% endif %}

    <h4 style="margin-top: 35px; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; color: #7f8c8d;">ความคิดเห็นทั้งหมด ({{ comments|length }})</h4>
    {% for c in comments %}
        <div class="comment-box">
            <b><a href="/profile/{{ c['username'] }}" style="color: #2c3e50; text-decoration: none;">@{{ c['username'] }}</a></b><br>
            <span style="color: #555; margin-top: 8px; display: inline-block;">{{ c['text'] }}</span>
        </div>
    {% else %}<p style="color: #bdc3c7; text-align: center; padding: 20px 0;">ยังไม่มีคอมเมนต์ มาเป็นคนแรกสิ! 🥳</p>{% endfor %}
</div>
"""

HTML_PROFILE = """
<div class="card" style="text-align: center;">
    <div style="font-size: 80px; margin-bottom: 10px;">👤</div>
    <h1 style="margin: 0; color: #2c3e50; font-size: 36px;">{{ profile_user['username'] }} {% if profile_user['role'] == 'admin' %}<span class="badge-admin">ADMIN</span>{% endif %}</h1>
    <p style="color: #7f8c8d; margin: 5px 0 20px 0;">🌟 สมาชิกพจนานุกรมเสรี 🌟</p>
    
    <div style="background: #f8f9fa; padding: 20px; border-radius: 12px; text-align: left;">
        <h3 style="margin-top: 0; color: #3498db;">✍️ คำแนะนำตัว (Bio)</h3>
        {% if is_owner %}
            <form action="/update_bio" method="POST">
                <textarea name="bio" rows="3" placeholder="เขียนแนะนำตัวเท่ๆ ของคุณที่นี่เลย...">{{ profile_user['bio'] }}</textarea>
                <button type="submit" style="width: auto; padding: 8px 20px; border-radius: 20px;">บันทึก</button>
            </form>
        {% else %}
            <p style="font-size: 16px; color: #444; white-space: pre-wrap;">{{ profile_user['bio'] or 'ผู้ใช้นี้มีความลับ ยังไม่ได้เขียนแนะนำตัว 🤫' }}</p>
        {% endif %}
    </div>

    <div style="margin-top: 30px; text-align: left;">
        <h3 style="margin-bottom: 15px;">🏅 เหรียญตราเกียรติยศ (Badges)</h3>
        <div style="background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%); border: 2px dashed #ffeeba; padding: 20px; border-radius: 12px; text-align: center; color: #856404; font-weight: 500;">
            <i>[ พื้นที่สำหรับเหรียญตราในอนาคต เช่น "นักบัญญัติมือทอง" ]</i>
        </div>
    </div>
</div>

<h2 style="margin-top: 40px; color: #2c3e50;">📚 ศัพท์ที่บัญญัติโดยคุณ {{ profile_user['username'] }}</h2>
{% for word in words %}
<div class="card">
    <a href="/word/{{ word['id'] }}" class="word-title">{{ word['term'] }}</a>
    <p class="word-def">{{ word['definition'][:100] }}...</p>
</div>
{% else %}<p style="text-align: center; color: #7f8c8d;">ยังไม่ได้บัญญัติศัพท์ใดๆ 😢</p>{% endfor %}
"""

HTML_WOTW = """
<div style="text-align: center; margin-bottom: 40px; background: linear-gradient(135deg, #2c3e50, #3498db); padding: 40px 20px; border-radius: 15px; color: white; box-shadow: 0 10px 20px rgba(0,0,0,0.1);">
    <h1 style="margin: 0; font-size: 38px;">🏆 ที่สุดของสัปดาห์</h1>
    <p style="font-size: 18px; margin-top: 10px; opacity: 0.9;">ร่วมโหวตคำศัพท์สุดเจ๋ง ประกาศผลแชมป์ใหม่ทุกวันอาทิตย์!</p>
</div>

{% if winner %}
<div class="card winner-card">
    <h2 style="margin-top: 0; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">👑 แชมป์ศัพท์สัปดาห์ที่แล้ว 👑</h2>
    <h1 style="font-size: 50px; margin: 15px 0; text-shadow: 0 3px 6px rgba(0,0,0,0.3);">
        <a href="/word/{{ winner['word_id'] }}" style="color: white; text-decoration: none;">"{{ winner['term'] }}"</a>
    </h1>
    <p style="font-size: 18px; font-weight: bold; background: rgba(0,0,0,0.1); display: inline-block; padding: 8px 20px; border-radius: 20px;">บัญญัติโดย: {{ winner['username'] }} &nbsp;|&nbsp; 🌟 คะแนนโหวต: {{ winner['votes'] }}</p>
</div>
{% endif %}

<h2 style="margin-top: 40px; color: #2c3e50; border-left: 5px solid #f39c12; padding-left: 15px;">🔥 ศัพท์ที่เข้าชิงสัปดาห์นี้</h2>
{% for cand in candidates %}
<div class="card" style="border-left: 6px solid #f1c40f; padding: 20px 25px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
        <div style="flex: 1; min-width: 200px;">
            <a href="/word/{{ cand['word_id'] }}" class="word-title" style="font-size: 32px;">{{ cand['term'] }}</a>
            <p style="font-size: 15px; margin-top: 5px; color: #7f8c8d;">เสนอโดย: <span style="color: #3498db; font-weight: bold;">{{ cand['username'] }}</span></p>
        </div>
        <div style="text-align: center; background: #fff9e6; padding: 15px 25px; border-radius: 12px; border: 1px solid #ffeeba;">
            <h2 style="margin: 0; color: #f39c12; font-size: 36px;">{{ cand['votes'] }}</h2>
            <span style="font-size: 13px; color: #b8860b; font-weight: bold;">คะแนนโหวต</span>
        </div>
    </div>
    {% if session.get('user_id') %}
    <form action="/vote_wotw/{{ cand['candidate_id'] }}" method="POST" style="margin-top: 20px;">
        <button type="submit" class="wotw-btn" style="width: 100%; font-size: 18px; padding: 12px; border-radius: 10px;">⭐ โหวตให้คำนี้เลย!</button>
    </form>
    {% endif %}
</div>
{% else %}
<div class="card" style="text-align: center; color: #7f8c8d; padding: 40px;">
    <span style="font-size: 40px;">😴</span>
    <p style="font-size: 18px; margin-top: 15px;">สัปดาห์นี้ยังไม่มีคำศัพท์ถูกเสนอชื่อเข้าชิง</p>
</div>
{% endfor %}
"""

HTML_ADMIN = """
<div class="card" style="background: #2c3e50; color: white;">
    <h1 style="margin: 0;">🛡️ Admin Dashboard</h1>
    <p style="margin: 5px 0 0 0; opacity: 0.8;">แผงควบคุมระบบพจนานุกรมเสรี</p>
</div>

<h2 style="margin-top: 30px; color: #2c3e50;">🚀 จัดการคำศัพท์</h2>
<div style="overflow-x:auto;">
    <table>
        <tr><th>ID</th><th>คำศัพท์</th><th>ผู้บัญญัติ</th><th>สถานะ</th><th>จัดการ</th></tr>
        {% for w in words %}
        <tr class="{% if w['reported'] %}reported-card{% endif %}">
            <td>{{ w['id'] }}</td>
            <td><b><a href="/word/{{ w['id'] }}">{{ w['term'] }}</a></b></td>
            <td>{{ w['username'] }}</td>
            <td>
                {% if w['reported'] %}<span style="color:red; font-weight:bold;">🚨 ถูกรายงาน</span><br>{% endif %}
                {% if w['voting_disabled'] %}<span style="color:gray;">🔒 ปิดโหวต</span>{% else %}<span style="color:green;">✅ ปกติ</span>{% endif %}
            </td>
            <td>
                <form action="/admin/toggle_vote/{{ w['id'] }}" method="POST" style="display:inline;">
                    <button type="submit" class="btn-blue" style="padding: 5px 10px; font-size:12px;">{% if w['voting_disabled'] %}เปิดโหวต{% else %}ปิดโหวต{% endif %}</button>
                </form>
                <form action="/admin/delete/{{ w['id'] }}" method="POST" style="display:inline;" onsubmit="return confirm('ลบคำนี้ถาวร แน่ใจหรือไม่?');">
                    <button type="submit" class="btn-red" style="padding: 5px 10px; font-size:12px;">ลบ</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
</div>

<h2 style="margin-top: 40px; color: #2c3e50;">📜 ประวัติการใช้งาน (Activity Logs)</h2>
<div style="height: 400px; overflow-y: auto; background: white; padding: 10px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
    <table style="margin: 0; font-size: 14px;">
        <tr><th>เวลา</th><th>ผู้ใช้</th><th>การกระทำ</th><th>เป้าหมาย</th></tr>
        {% for log in logs %}
        <tr><td style="color:gray;">{{ log['timestamp'] }}</td><td><b>{{ log['username'] }}</b></td><td>{{ log['action'] }}</td><td>{{ log['target'] }}</td></tr>
        {% endfor %}
    </table>
</div>
"""

# ==========================================
# 3. Routes & Logic (เส้นทางหน้าเว็บ)
# ==========================================
def render(template_string, **context):
    full_template = BASE_TEMPLATE.replace("<!-- CONTENT_PLACEHOLDER -->", template_string)
    return render_template_string(full_template, alphabets=list(string.ascii_uppercase) + ["ก","ข","ค","ง","จ","ฉ","ช","ซ","ญ","ด","ต","ถ","ท","ธ","น","บ","ป","ผ","ฝ","พ","ฟ","ภ","ม","ย","ร","ล","ว","ศ","ษ","ส","ห","อ","ฮ"], **context)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (request.form['username'].strip(),)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], request.form['password'].strip()):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            log_activity(user['username'], 'เข้าสู่ระบบ', '-')
            return redirect(url_for('index'))
        else:
            flash('❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error')
    return render(HTML_LOGIN)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role = 'user'
        
        # กฎของ Admin!
        if username.lower() == 'admin':
            if password == '11333355555577777777':
                role = 'admin'
            else:
                flash('❌ รหัสผ่านสำหรับสิทธิ์ Admin ไม่ถูกต้อง!', 'error')
                return redirect(url_for('signup'))
                
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, hashed_password, role))
            conn.commit()
            log_activity(username, 'สมัครสมาชิก', f'สิทธิ์: {role}')
            flash(f'🎉 สมัครสมาชิกสำเร็จ! (สถานะ: {role})', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('❌ Username นี้มีคนใช้งานแล้ว โปรดเลือกชื่ออื่น', 'error')
        finally:
            conn.close()
    return render(HTML_SIGNUP)

@app.route('/logout')
def logout():
    if 'username' in session:
        log_activity(session['username'], 'ออกจากระบบ', '-')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    conn = get_db_connection()
    query = '''SELECT w.*, u.username,
        IFNULL(SUM(CASE WHEN v.vote_type = 1 THEN 1 ELSE 0 END), 0) as likes,
        IFNULL(SUM(CASE WHEN v.vote_type = 2 THEN 1 ELSE 0 END), 0) as dislikes
        FROM words w JOIN users u ON w.user_id = u.id
        LEFT JOIN votes v ON w.id = v.word_id GROUP BY w.id ORDER BY w.id DESC'''
    words = conn.execute(query).fetchall()
    conn.close()
    return render(HTML_INDEX, words=words, title="✨ คำศัพท์มาใหม่ล่าสุด")

@app.route('/alphabet/<letter>')
def by_alphabet(letter):
    conn = get_db_connection()
    query = '''SELECT w.*, u.username,
        IFNULL(SUM(CASE WHEN v.vote_type = 1 THEN 1 ELSE 0 END), 0) as likes,
        IFNULL(SUM(CASE WHEN v.vote_type = 2 THEN 1 ELSE 0 END), 0) as dislikes
        FROM words w JOIN users u ON w.user_id = u.id
        LEFT JOIN votes v ON w.id = v.word_id WHERE w.term LIKE ? GROUP BY w.id ORDER BY w.term ASC'''
    words = conn.execute(query, (letter + '%',)).fetchall()
    conn.close()
    return render(HTML_INDEX, words=words, title=f"📂 หมวดหมู่: '{letter}'")

@app.route('/add', methods=['GET', 'POST'])
def add_word():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        term = request.form['term'].strip()
        conn = get_db_connection()
        conn.execute('INSERT INTO words (term, definition, user_id) VALUES (?, ?, ?)', (term, request.form['definition'].strip(), session['user_id']))
        conn.commit()
        conn.close()
        log_activity(session['username'], 'บัญญัติศัพท์', term)
        flash('💾 บัญญัติศัพท์ใหม่สำเร็จ!', 'success')
        return redirect(url_for('index'))
    return render("""<div class="card"><h2>➕ บัญญัติศัพท์ใหม่</h2>
    <form action="/add" method="POST"><label style="font-weight: bold;">คำศัพท์ (Term)</label><input type="text" name="term" required>
    <label style="font-weight: bold;">ความหมาย (Definition)</label><textarea name="definition" rows="5" required></textarea>
    <button type="submit" style="margin-top: 15px; width: 100%;">💾 บันทึกคำศัพท์</button></form></div>""")

@app.route('/word/<int:word_id>')
def view_word(word_id):
    conn = get_db_connection()
    word = conn.execute('''SELECT w.*, u.username,
        IFNULL(SUM(CASE WHEN v.vote_type = 1 THEN 1 ELSE 0 END), 0) as likes,
        IFNULL(SUM(CASE WHEN v.vote_type = 2 THEN 1 ELSE 0 END), 0) as dislikes
        FROM words w JOIN users u ON w.user_id = u.id LEFT JOIN votes v ON w.id = v.word_id
        WHERE w.id = ? GROUP BY w.id''', (word_id,)).fetchone()
    comments = conn.execute('SELECT c.text, u.username FROM comments c JOIN users u ON c.user_id = u.id WHERE c.word_id = ? ORDER BY c.id ASC', (word_id,)).fetchall()
    conn.close()
    if word is None: return "ไม่พบคำศัพท์นี้", 404
    return render(HTML_WORD, word=word, comments=comments)

@app.route('/vote/<int:word_id>/<int:vote_type>', methods=['POST'])
def vote(word_id, vote_type):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    word = conn.execute('SELECT term, voting_disabled FROM words WHERE id = ?', (word_id,)).fetchone()
    if word['voting_disabled']:
        flash('🔒 คำศัพท์นี้ถูกปิดการโหวตโดย Admin', 'error')
        conn.close()
        return redirect(url_for('view_word', word_id=word_id))
    
    user_id = session['user_id']
    existing = conn.execute('SELECT id, vote_type FROM votes WHERE word_id = ? AND user_id = ?', (word_id, user_id)).fetchone()
    if existing:
        if existing['vote_type'] == vote_type: conn.execute('DELETE FROM votes WHERE id = ?', (existing['id'],))
        else: conn.execute('UPDATE votes SET vote_type = ? WHERE id = ?', (vote_type, existing['id']))
    else:
        conn.execute('INSERT INTO votes (word_id, user_id, vote_type) VALUES (?, ?, ?)', (word_id, user_id, vote_type))
    conn.commit()
    conn.close()
    v_type = 'Like' if vote_type == 1 else 'Dislike'
    log_activity(session['username'], f'โหวต {v_type}', word['term'])
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/report/<int:word_id>', methods=['POST'])
def report(word_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('UPDATE words SET reported = 1 WHERE id = ?', (word_id,))
    word = conn.execute('SELECT term FROM words WHERE id = ?', (word_id,)).fetchone()
    conn.commit()
    conn.close()
    log_activity(session['username'], 'รายงานความไม่เหมาะสม', word['term'])
    flash('🚨 รายงานคำศัพท์นี้สำเร็จ ทีมงานจะรีบตรวจสอบครับ!', 'success')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/comment/<int:word_id>', methods=['POST'])
def add_comment(word_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('INSERT INTO comments (word_id, user_id, text) VALUES (?, ?, ?)', (word_id, session['user_id'], request.form['comment'].strip()))
    conn.commit()
    conn.close()
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/profile/<username>')
def profile(username):
    conn = get_db_connection()
    profile_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if not profile_user:
        conn.close()
        return "ไม่พบผู้ใช้งานนี้", 404
    words = conn.execute('SELECT id, term, definition FROM words WHERE user_id = ? ORDER BY id DESC', (profile_user['id'],)).fetchall()
    conn.close()
    is_owner = (session.get('user_id') == profile_user['id'])
    return render(HTML_PROFILE, profile_user=profile_user, words=words, is_owner=is_owner)

@app.route('/update_bio', methods=['POST'])
def update_bio():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('UPDATE users SET bio = ? WHERE id = ?', (request.form['bio'].strip(), session['user_id']))
    conn.commit()
    conn.close()
    flash('อัปเดตข้อมูลแนะนำตัวสำเร็จ', 'success')
    return redirect(url_for('profile', username=session['username']))

@app.route('/wotw')
def wotw():
    curr_y, curr_w = get_current_week()
    prev_y, prev_w = get_prev_week()
    conn = get_db_connection()
    winner = conn.execute('''SELECT w.id as word_id, w.term, u.username, COUNT(wv.id) as votes
        FROM wotw_candidates c JOIN words w ON c.word_id = w.id JOIN users u ON w.user_id = u.id
        LEFT JOIN wotw_votes wv ON c.id = wv.candidate_id WHERE c.year = ? AND c.week_num = ?
        GROUP BY c.id ORDER BY votes DESC LIMIT 1''', (prev_y, prev_w)).fetchone()
    candidates = conn.execute('''SELECT c.id as candidate_id, w.id as word_id, w.term, u.username, COUNT(wv.id) as votes
        FROM wotw_candidates c JOIN words w ON c.word_id = w.id JOIN users u ON w.user_id = u.id
        LEFT JOIN wotw_votes wv ON c.id = wv.candidate_id WHERE c.year = ? AND c.week_num = ?
        GROUP BY c.id ORDER BY votes DESC''', (curr_y, curr_w)).fetchall()
    conn.close()
    return render(HTML_WOTW, winner=winner, candidates=candidates)

@app.route('/nominate/<int:word_id>', methods=['POST'])
def nominate(word_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    curr_y, curr_w = get_current_week()
    conn = get_db_connection()
    exist = conn.execute('SELECT id FROM wotw_candidates WHERE word_id = ? AND year = ? AND week_num = ?', (word_id, curr_y, curr_w)).fetchone()
    word = conn.execute('SELECT term FROM words WHERE id = ?', (word_id,)).fetchone()
    if not exist:
        conn.execute('INSERT INTO wotw_candidates (word_id, year, week_num) VALUES (?, ?, ?)', (word_id, curr_y, curr_w))
        log_activity(session['username'], 'เสนอชื่อเข้าชิง WOTW', word['term'])
        flash('🎉 เสนอชื่อคำศัพท์เข้าชิงแชมป์สัปดาห์สำเร็จ!', 'success')
    else: flash('คำศัพท์นี้ถูกเสนอชื่อไปแล้ว ไปช่วยโหวตที่หน้า "ที่สุดของสัปดาห์" ได้เลย!', 'error')
    conn.commit()
    conn.close()
    return redirect(url_for('wotw'))

@app.route('/vote_wotw/<int:candidate_id>', methods=['POST'])
def vote_wotw(candidate_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    exist = conn.execute('SELECT id FROM wotw_votes WHERE candidate_id = ? AND user_id = ?', (candidate_id, user_id)).fetchone()
    if not exist:
        conn.execute('INSERT INTO wotw_votes (candidate_id, user_id) VALUES (?, ?)', (candidate_id, user_id))
        flash('⭐ โหวตให้ศัพท์นี้สำเร็จ!', 'success')
    else:
        conn.execute('DELETE FROM wotw_votes WHERE id = ?', (exist['id'],))
        flash('ยกเลิกการโหวตแล้ว', 'error')
    conn.commit()
    conn.close()
    return redirect(url_for('wotw'))

# ----------------- ADMIN ROUTES -----------------
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('❌ เฉพาะ Admin เท่านั้นที่เข้าหน้านี้ได้!', 'error')
        return redirect(url_for('index'))
    conn = get_db_connection()
    words = conn.execute('''SELECT w.*, u.username FROM words w JOIN users u ON w.user_id = u.id ORDER BY w.reported DESC, w.id DESC''').fetchall()
    logs = conn.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT 100').fetchall()
    conn.close()
    return render(HTML_ADMIN, words=words, logs=logs)

@app.route('/admin/delete/<int:word_id>', methods=['POST'])
def admin_delete(word_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db_connection()
    word = conn.execute('SELECT term FROM words WHERE id = ?', (word_id,)).fetchone()
    conn.execute('DELETE FROM words WHERE id = ?', (word_id,))
    conn.execute('DELETE FROM votes WHERE word_id = ?', (word_id,))
    conn.execute('DELETE FROM comments WHERE word_id = ?', (word_id,))
    conn.commit()
    conn.close()
    log_activity(session['username'], 'ลบคำศัพท์ (Admin)', word['term'])
    flash(f'ลบคำศัพท์ "{word["term"]}" ออกจากระบบแล้ว', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_vote/<int:word_id>', methods=['POST'])
def admin_toggle_vote(word_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db_connection()
    word = conn.execute('SELECT term, voting_disabled FROM words WHERE id = ?', (word_id,)).fetchone()
    new_status = 0 if word['voting_disabled'] == 1 else 1
    conn.execute('UPDATE words SET voting_disabled = ? WHERE id = ?', (new_status, word_id))
    conn.commit()
    conn.close()
    action = "เปิดการโหวต" if new_status == 0 else "ปิดการโหวต"
    log_activity(session['username'], f'{action} (Admin)', word['term'])
    flash(f'{action} สำหรับคำว่า "{word["term"]}" สำเร็จ', 'success')
    return redirect(url_for('admin_dashboard'))

# แบบใหม่ที่ใช้บน Railway
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

