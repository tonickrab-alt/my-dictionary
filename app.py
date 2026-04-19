import os
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'krian_dictionary_secret_super_safe'

# ==========================================
# 1. ระบบฐานข้อมูล (Database) & ประวัติ (Audit)
# ==========================================
def get_db_connection():
    conn = sqlite3.connect('opendict.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_action(username, action):
    conn = get_db_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute('INSERT INTO audit_logs (username, action, timestamp) VALUES (?, ?, ?)', 
                 (username, action, timestamp))
    conn.commit()
    conn.close()

def init_db():
    conn = get_db_connection()
    # ตารางผู้ใช้ (มีโปรไฟล์และ bio)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, bio TEXT
    )''')
    # ตารางคำศัพท์
    conn.execute('''CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT, meaning TEXT, first_letter TEXT, 
        nominated_by TEXT, likes INTEGER DEFAULT 0, dislikes INTEGER DEFAULT 0, status TEXT DEFAULT 'normal'
    )''')
    # ตารางคอมเมนต์
    conn.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, username TEXT, comment TEXT, created_at TEXT
    )''')
    # ตารางโหวต (ป้องกันคนโหวตซ้ำ)
    conn.execute('''CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, username TEXT, vote_type TEXT
    )''')
    # ตารางเก็บบันทึกระบบ (Audit)
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, timestamp TEXT
    )''')
    
    # สร้างแอดมินอัตโนมัติ ตามโจทย์
    admin = conn.execute("SELECT * FROM users WHERE username='Admin'").fetchone()
    if not admin:
        hashed = generate_password_hash('113333555555')
        conn.execute("INSERT INTO users (username, password, role, bio) VALUES (?, ?, ?, ?)",
                     ('Admin', hashed, 'admin', 'ผู้คุมกฎสูงสุดแห่งพจนานุเกรียน!'))
    
    conn.commit()
    conn.close()

# ==========================================
# 2. โครงสร้างหน้าเว็บ (HTML Templates)
# ==========================================
base_html = '''
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>พจนานุเกรียน</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Chakra Petch', sans-serif; }
        .navbar { background: #000; border-bottom: 2px solid #00ffcc; }
        .navbar-brand { color: #00ffcc !important; font-size: 1.5rem; text-shadow: 0 0 10px #00ffcc; }
        .card { background-color: #1e1e1e; border: 1px solid #333; border-radius: 15px; }
        .card-body, .card-footer { color: #fff; }
        .text-primary { color: #00ffcc !important; }
        .btn-primary { background-color: #00ffcc; color: #000; border: none; font-weight: bold; }
        .btn-primary:hover { background-color: #00ccaa; color: #000; }
        
        /* ช่องใส่เหรียญตรา */
        .badge-slot { width: 45px; height: 45px; background: #2a2a2a; border-radius: 50%; display: inline-block; margin: 5px; border: 2px dashed #555; }
        
        /* เอฟเฟกต์ไฟกะพริบมุมขวาบน */
        .day-indicator {
            background: rgba(0,0,0,0.5); border-radius: 20px; padding: 5px 15px; margin-left: auto;
            color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc;
            box-shadow: 0 0 10px #00ffcc; animation: pulse 2s infinite; font-size: 0.9rem;
        }
        @keyframes pulse { 0% { box-shadow: 0 0 5px #00ffcc; } 50% { box-shadow: 0 0 20px #00ffcc; } 100% { box-shadow: 0 0 5px #00ffcc; } }
        
        .sunday-mode { color: #ff0055 !important; border-color: #ff0055 !important; box-shadow: 0 0 10px #ff0055 !important; animation: pulseRed 2s infinite !important;}
        @keyframes pulseRed { 0% { box-shadow: 0 0 5px #ff0055; } 50% { box-shadow: 0 0 20px #ff0055; } 100% { box-shadow: 0 0 5px #ff0055; } }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('home') }}">🤡 พจนานุเกรียน</a>
            
            <!-- ป้ายบอกวันสุดเก๋ -->
            <div id="dayDisplay" class="day-indicator d-none d-lg-block me-3">กำลังเชื่อมต่อ...</div>

            <div class="d-flex align-items-center">
                {% if session.get('username') %}
                    <a href="{{ url_for('profile', username=session['username']) }}" class="text-white text-decoration-none me-3">
                        👾 {{ session['username'] }}
                    </a>
                    <a href="{{ url_for('wotw') }}" class="btn btn-outline-warning btn-sm me-2">🏆 ศัพท์ประจำสัปดาห์</a>
                    <a href="{{ url_for('nominate') }}" class="btn btn-light btn-sm me-2">+ บัญญัติศัพท์</a>
                    {% if session.get('role') == 'admin' %}
                        <a href="{{ url_for('admin_panel') }}" class="btn btn-danger btn-sm me-2">⚙️ Admin</a>
                    {% endif %}
                    <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">ออก</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-4 mb-5" style="max-width: 900px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show shadow-sm fw-bold bg-{{ category }} text-white border-0">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <!-- CONTENT_PLACEHOLDER -->
        
    </div>

    <script>
        const days = ['วันอาทิตย์', 'วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี', 'วันศุกร์', 'วันเสาร์'];
        const today = new Date().getDay();
        const el = document.getElementById('dayDisplay');
        if(today === 0) {
            el.classList.add('sunday-mode');
            el.innerText = '🚨 วันอาทิตย์: ประกาศผลศัพท์แห่งสัปดาห์! (งดบัญญัติ)';
        } else {
            el.innerText = '✨ วันนี้: ' + days[today];
        }
    </script>
</body>
</html>
'''

auth_html = '''
<div class="card mx-auto mt-5 border-0 shadow" style="max-width: 400px;">
    <div class="card-body p-5">
        <h2 class="text-center mb-4 fw-bold text-primary">{{ title }}</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label text-muted">ชื่อผู้ใช้ (Username)</label>
                <input type="text" class="form-control bg-dark text-white border-secondary" name="username" required>
            </div>
            <div class="mb-4">
                <label class="form-label text-muted">รหัสผ่าน (Password)</label>
                <input type="password" class="form-control bg-dark text-white border-secondary" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-2 fw-bold fs-5">{{ btn_text }}</button>
        </form>
        <div class="text-center mt-4">
            <a href="{{ alt_link }}" class="text-secondary text-decoration-none">{{ alt_text }}</a>
        </div>
    </div>
</div>
'''

home_html = '''
<div class="text-center mb-4">
    <h1 class="fw-bold text-primary" style="text-shadow: 0 0 15px #00ffcc;">พจนานุเกรียน</h1>
    <p class="text-secondary">พื้นที่บัญญัติศัพท์ไร้สาระของมวลมนุษยชาติ</p>
</div>

<!-- หมวดหมู่ตัวอักษร -->
<div class="card p-3 mb-4 shadow-sm text-center border-secondary">
    <div>
        {% for letter in "กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ" %}
            <a href="?letter={{ letter }}" class="btn btn-sm btn-outline-light m-1">{{ letter }}</a>
        {% endfor %}
    </div>
    <hr class="border-secondary">
    <div>
        {% for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" %}
            <a href="?letter={{ letter }}" class="btn btn-sm btn-outline-light m-1">{{ letter }}</a>
        {% endfor %}
        <a href="{{ url_for('home') }}" class="btn btn-sm btn-primary m-1 text-dark">ดูทั้งหมด</a>
    </div>
</div>

<div class="row">
    {% for word in words %}
    <div class="col-md-6 mb-3">
        <div class="card h-100 shadow-sm border-secondary">
            <div class="card-body">
                <h3 class="fw-bold"><a href="{{ url_for('view_word', word_id=word.id) }}" class="text-primary text-decoration-none">{{ word.word }}</a></h3>
                <p class="text-light text-truncate">{{ word.meaning }}</p>
            </div>
            <div class="card-footer bg-transparent border-secondary d-flex justify-content-between align-items-center">
                <small class="text-secondary">โดย: <a href="{{ url_for('profile', username=word.nominated_by) }}" class="text-info">{{ word.nominated_by }}</a></small>
                <div>
                    <span class="text-success me-2">👍 {{ word.likes }}</span>
                    <span class="text-danger">👎 {{ word.dislikes }}</span>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center py-5"><p class="text-secondary fs-5">ยังไม่มีศัพท์เกรียนๆ ในหมวดนี้</p></div>
    {% endfor %}
</div>
'''

word_detail_html = '''
<div class="card shadow border-secondary mb-4">
    <div class="card-body p-5">
        <div class="d-flex justify-content-between align-items-start">
            <h1 class="display-4 fw-bold text-primary" style="text-shadow: 0 0 10px #00ffcc;">{{ word.word }}</h1>
            <a href="{{ url_for('report_word', word_id=word.id) }}" class="btn btn-outline-danger btn-sm" onclick="return confirm('แจ้งแอดมินลบคำนี้?')">🚩 Report</a>
        </div>
        <hr class="border-secondary">
        <p class="fs-4 text-light">{{ word.meaning }}</p>
        <div class="mt-4 p-3 rounded d-flex justify-content-between align-items-center" style="background: rgba(255,255,255,0.05);">
            <span class="text-secondary">ผู้บัญญัติ: <a href="{{ url_for('profile', username=word.nominated_by) }}" class="text-info">{{ word.nominated_by }}</a></span>
            <div>
                {% if is_sunday %}
                    <span class="badge bg-danger fs-6 p-2">วันอาทิตย์ งดโหวตนะจ๊ะ!</span>
                {% else %}
                    <a href="{{ url_for('vote_word', word_id=word.id, type='like') }}" class="btn btn-outline-success">👍 ({{ word.likes }})</a>
                    <a href="{{ url_for('vote_word', word_id=word.id, type='dislike') }}" class="btn btn-outline-danger">👎 ({{ word.dislikes }})</a>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="card shadow border-secondary">
    <div class="card-body p-4">
        <h4 class="fw-bold mb-4 text-info">💬 ลานประลองคอมเมนต์</h4>
        <form method="POST" action="{{ url_for('add_comment', word_id=word.id) }}" class="mb-4">
            <div class="input-group">
                <input type="text" class="form-control bg-dark text-white border-secondary" name="comment" placeholder="พิมพ์ด่า หรือ อวย ได้ที่นี่..." required>
                <button class="btn btn-primary" type="submit">ส่งความคิดเห็น</button>
            </div>
        </form>
        
        {% for c in comments %}
        <div class="border-bottom border-secondary pb-2 mb-3">
            <strong><a href="{{ url_for('profile', username=c.username) }}" class="text-warning">{{ c.username }}</a></strong> 
            <small class="text-secondary ms-2">{{ c.created_at }}</small>
            <p class="mb-0 text-light mt-1">{{ c.comment }}</p>
        </div>
        {% else %}
        <p class="text-secondary text-center">ยังเงียบกริบ... มาประเดิมคอมเมนต์แรกกันหน่อย!</p>
        {% endfor %}
    </div>
</div>
'''

profile_html = '''
<div class="card shadow border-secondary mx-auto" style="max-width: 600px;">
    <div class="card-body p-5 text-center">
        <div class="mb-3">
            <span class="display-1" style="text-shadow: 0 0 20px #00ffcc;">👾</span>
        </div>
        <h2 class="fw-bold text-white">{{ user.username }}</h2>
        <span class="badge bg-primary text-dark mb-4">คลาส: {{ user.role }}</span>
        
        <div class="p-4 rounded mb-4 text-start" style="background: rgba(0,255,204,0.05); border: 1px solid rgba(0,255,204,0.2);">
            <h5 class="fw-bold text-primary">📝 แนะนำตัวเกรียนๆ</h5>
            <p class="text-light">{{ user.bio if user.bio else 'ยังไม่ได้ใส่คำคมบาดจิต...' }}</p>
            {% if session.get('username') == user.username %}
                <form method="POST" class="mt-3">
                    <textarea class="form-control bg-dark text-white border-secondary mb-2" name="bio" rows="2" placeholder="เปลี่ยนคำแนะนำตัวของคุณ...">{{ user.bio }}</textarea>
                    <button type="submit" class="btn btn-sm btn-outline-info w-100">บันทึกการตั้งค่า</button>
                </form>
            {% endif %}
        </div>

        <div class="text-start p-3 bg-dark rounded">
            <h5 class="fw-bold text-warning">🏅 เหรียญตราเกียรติยศ (Coming Soon)</h5>
            <div class="mt-3 d-flex justify-content-center">
                <div class="badge-slot"></div> <div class="badge-slot"></div>
                <div class="badge-slot"></div> <div class="badge-slot"></div>
                <div class="badge-slot"></div>
            </div>
            <p class="text-center text-secondary small mt-2">พื้นที่สำหรับสะสมตราประทับในอนาคต</p>
        </div>
    </div>
</div>
'''

add_word_html = '''
<div class="card shadow mx-auto border-secondary" style="max-width: 600px;">
    <div class="card-body p-5">
        <h2 class="fw-bold mb-4 text-center text-primary">✍️ บัญญัติศัพท์ไร้สาระ</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label fw-bold text-light">คำศัพท์</label>
                <input type="text" class="form-control form-control-lg bg-dark text-white border-secondary" name="word" required>
            </div>
            <div class="mb-4">
                <label class="form-label fw-bold text-light">ความหมาย (แปลให้มนุษย์เข้าใจ)</label>
                <textarea class="form-control bg-dark text-white border-secondary" name="meaning" rows="4" required></textarea>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-3 fw-bold fs-5 text-dark">จารึกคำศัพท์!</button>
        </form>
    </div>
</div>
'''

wotw_html = '''
<div class="text-center mb-5">
    <h1 class="display-4 fw-bold text-warning" style="text-shadow: 0 0 20px #ffcc00;">🏆 ศัพท์เก๋ประจำสัปดาห์</h1>
    {% if is_sunday %}
        <div class="alert alert-danger mt-4 border-0" style="background: rgba(255,0,85,0.2);">
            <h3 class="fw-bold text-danger mb-0">🚨 วันนี้วันอาทิตย์! ประกาศผลผู้ชนะแล้ว! 🚨</h3>
        </div>
    {% else %}
        <p class="fs-5 text-secondary">โหวตดันศัพท์ที่ใช่ (ระบบจะตัดสินผู้ชนะในวันอาทิตย์)</p>
    {% endif %}
</div>

<div class="row justify-content-center">
    {% for word in words %}
    <div class="col-md-8 mb-4">
        <div class="card shadow {% if loop.index == 1 and is_sunday %}border-warning border-3{% else %}border-secondary{% endif %}">
            <div class="card-body text-center p-5">
                {% if loop.index == 1 and is_sunday %}
                    <h2 class="text-warning mb-3" style="text-shadow: 0 0 10px #ffcc00;">👑 เดอะเบสท์แห่งสัปดาห์ 👑</h2>
                {% endif %}
                <h2 class="fw-bold text-primary">{{ word.word }}</h2>
                <p class="fs-5 text-light">{{ word.meaning }}</p>
                <div class="mt-4">
                    <span class="fs-4 me-3 text-success">👍 {{ word.likes }} โหวต</span>
                    <a href="{{ url_for('view_word', word_id=word.id) }}" class="btn btn-outline-info">เข้าไปดูคอมเมนต์</a>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center"><p class="text-secondary">ยังไม่มีใครส่งเข้าประกวดสัปดาห์นี้</p></div>
    {% endfor %}
</div>
'''

admin_html = '''
<h2 class="fw-bold mb-4 text-danger">⚙️ แผงควบคุม (ห้องเชือด)</h2>

<div class="card shadow border-danger mb-4">
    <div class="card-header bg-danger text-white fw-bold">🚩 บัญชีดำ (คำที่ถูก Report)</div>
    <div class="card-body p-0">
        <table class="table table-dark table-hover mb-0">
            <tr><th>คำศัพท์</th><th>ผู้บัญญัติ</th><th>จัดการ</th></tr>
            {% for w in reported %}
            <tr>
                <td><a href="{{ url_for('view_word', word_id=w.id) }}" class="text-warning">{{ w.word }}</a></td>
                <td>{{ w.nominated_by }}</td>
                <td>
                    <a href="{{ url_for('admin_action', action='clear', word_id=w.id) }}" class="btn btn-sm btn-success">ปกติ (ยกเลิก Report)</a>
                    <a href="{{ url_for('admin_action', action='delete', word_id=w.id) }}" class="btn btn-sm btn-danger" onclick="return confirm('ลบถาวร แน่ใจนะแอด?')">ลบทิ้ง</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="3" class="text-center text-secondary py-4">ความสงบสุขบังเกิด ไม่มีคำโดนรีพอร์ต</td></tr>
            {% endfor %}
        </table>
    </div>
</div>

<div class="card shadow border-secondary">
    <div class="card-header bg-dark text-white fw-bold">👁️ ระบบสอดส่อง (Audit Logs)</div>
    <div class="card-body p-0" style="max-height: 400px; overflow-y: auto;">
        <table class="table table-dark table-striped mb-0 text-sm">
            <tr><th>เวลา</th><th>ผู้ใช้</th><th>สิ่งที่ทำลงไป</th></tr>
            {% for log in logs %}
            <tr>
                <td class="text-secondary">{{ log.timestamp }}</td>
                <td class="text-info fw-bold">{{ log.username }}</td>
                <td>{{ log.action }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</div>
'''

# ==========================================
# 3. Logic & Routes
# ==========================================
def render_page(template_string, **kwargs):
    full_template = base_html.replace('<!-- CONTENT_PLACEHOLDER -->', template_string)
    return render_template_string(full_template, **kwargs)

def is_sunday():
    return datetime.now().weekday() == 6  # 0=Mon, ..., 6=Sun

# ระบบประตูหน้า (บังคับ Login)
@app.before_request
def require_login():
    allowed = ['login', 'signup', 'static']
    if request.endpoint not in allowed and 'username' not in session:
        flash('ไม่พบบัญชีนี้ครับ รบกวน login ก่อนนะครับ', 'danger')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if not user:
            flash('ไม่พบบัญชีนี้ครับ รบกวน login ก่อนนะครับ', 'danger')
        elif not check_password_hash(user['password'], password):
            flash('ขออภัยด้วยครับ username หรือ รหัสผ่านของคุณไม่ถูกต้อง', 'danger')
        else:
            session['username'] = user['username']
            session['role'] = user['role']
            log_action(username, 'เข้าสู่ระบบแล้ว')
            return redirect(url_for('home'))
            
    return render_page(auth_html, title='ประตูสู่ความเกรียน (Login)', btn_text='เข้าสู่ระบบ', 
                       alt_link=url_for('signup'), alt_text='หน้าใหม่หรอ? ไป Sign up สิ (สมัครสมาชิก)')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, role, bio) VALUES (?, ?, ?, ?)', 
                         (username, hashed_pw, 'user', ''))
            conn.commit()
            log_action(username, 'จุติบัญชีใหม่บนพจนานุเกรียน')
            flash('สร้างบัญชีสำเร็จ! ลองเข้าสู่ระบบดูสิ', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ช้าไปต๋อย! Username นี้มีคนจองแล้ว', 'warning')
        finally:
            conn.close()
    return render_page(auth_html, title='ลงทะเบียนคนเกรียน (Sign Up)', btn_text='สร้างบัญชี', 
                       alt_link=url_for('login'), alt_text='มีของอยู่แล้ว? กลับไปเข้าสู่ระบบ (Login)')

@app.route('/logout')
def logout():
    log_action(session.get('username', 'Ghost'), 'ออกจากระบบไปเผชิญโลกความจริง')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    letter = request.args.get('letter')
    conn = get_db_connection()
    if letter:
        words = conn.execute("SELECT * FROM words WHERE first_letter = ? ORDER BY id DESC", (letter.upper(),)).fetchall()
    else:
        words = conn.execute("SELECT * FROM words ORDER BY id DESC").fetchall()
    conn.close()
    return render_page(home_html, words=words)

@app.route('/word/<int:word_id>')
def view_word(word_id):
    conn = get_db_connection()
    word = conn.execute('SELECT * FROM words WHERE id = ?', (word_id,)).fetchone()
    comments = conn.execute('SELECT * FROM comments WHERE word_id = ? ORDER BY id DESC', (word_id,)).fetchall()
    conn.close()
    if not word: return redirect(url_for('home'))
    return render_page(word_detail_html, word=word, comments=comments, is_sunday=is_sunday())

@app.route('/nominate', methods=['GET', 'POST'])
def nominate():
    if is_sunday():
        flash('วันอาทิตย์ศักดิ์สิทธิ์! ระบบปิดรับคำศัพท์และปิดโหวตเพื่อประกาศผลนะจ๊ะ', 'danger')
        return redirect(url_for('wotw'))
        
    if request.method == 'POST':
        word_text = request.form['word']
        meaning = request.form['meaning']
        first_letter = word_text[0].upper() if word_text else ''
        
        conn = get_db_connection()
        conn.execute('INSERT INTO words (word, meaning, first_letter, nominated_by) VALUES (?, ?, ?, ?)',
                     (word_text, meaning, first_letter, session['username']))
        conn.commit()
        conn.close()
        log_action(session['username'], f'บัญญัติคำว่า: {word_text}')
        flash('จารึกคำศัพท์ลงพจนานุเกรียนเรียบร้อย!', 'success')
        return redirect(url_for('home'))
    return render_page(add_word_html)

@app.route('/vote/<int:word_id>/<type>')
def vote_word(word_id, type):
    if is_sunday():
        flash('วันอาทิตย์งดลงคะแนนเสียง!', 'danger')
        return redirect(url_for('view_word', word_id=word_id))
        
    username = session['username']
    conn = get_db_connection()
    exist_vote = conn.execute('SELECT * FROM votes WHERE word_id = ? AND username = ?', (word_id, username)).fetchone()
    if exist_vote:
        flash('คุณลงคะแนนให้คำนี้ไปแล้ว เปลี่ยนใจไม่ได้หรอกนะ!', 'warning')
    else:
        conn.execute('INSERT INTO votes (word_id, username, vote_type) VALUES (?, ?, ?)', (word_id, username, type))
        if type == 'like':
            conn.execute('UPDATE words SET likes = likes + 1 WHERE id = ?', (word_id,))
            log_action(username, f'ปา Like ใส่คำศัพท์ ID:{word_id}')
        elif type == 'dislike':
            conn.execute('UPDATE words SET dislikes = dislikes + 1 WHERE id = ?', (word_id,))
            log_action(username, f'แจก Dislike ให้คำศัพท์ ID:{word_id}')
        conn.commit()
        flash('บันทึกคะแนนโหวตเรียบร้อย!', 'success')
    conn.close()
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/comment/<int:word_id>', methods=['POST'])
def add_comment(word_id):
    comment_text = request.form['comment']
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_db_connection()
    conn.execute('INSERT INTO comments (word_id, username, comment, created_at) VALUES (?, ?, ?, ?)',
                 (word_id, session['username'], comment_text, timestamp))
    conn.commit()
    conn.close()
    log_action(session['username'], f'พ่นคอมเมนต์ในคำศัพท์ ID:{word_id}')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    conn = get_db_connection()
    if request.method == 'POST' and session.get('username') == username:
        conn.execute('UPDATE users SET bio = ? WHERE username = ?', (request.form['bio'], username))
        conn.commit()
        log_action(username, 'เปลี่ยนคำแนะนำตัวใหม่')
        flash('อัปเดตโปรไฟล์เรียบร้อย', 'success')
        
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if not user: return redirect(url_for('home'))
    return render_page(profile_html, user=user)

@app.route('/wotw')
def wotw():
    conn = get_db_connection()
    # หา Top 5 ที่คนไลค์เยอะสุด
    top_words = conn.execute('SELECT * FROM words ORDER BY likes DESC LIMIT 5').fetchall()
    conn.close()
    return render_page(wotw_html, words=top_words, is_sunday=is_sunday())

@app.route('/report/<int:word_id>')
def report_word(word_id):
    conn = get_db_connection()
    conn.execute("UPDATE words SET status='reported' WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    log_action(session['username'], f'แหกปาก Report คำศัพท์ ID:{word_id}')
    flash('รายงานไปถึงหูแอดมินแล้ว!', 'info')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash('เห้ย! นี่มันห้องลับของแอดมิน ออกไปเลย!', 'danger')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    reported = conn.execute("SELECT * FROM words WHERE status='reported'").fetchall()
    logs = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return render_page(admin_html, reported=reported, logs=logs)

@app.route('/admin/action/<action>/<int:word_id>')
def admin_action(action, word_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = get_db_connection()
    if action == 'clear':
        conn.execute("UPDATE words SET status='normal' WHERE id=?", (word_id,))
        log_action('Admin', f'ปลดคำร้องเรียนคำศัพท์ ID:{word_id}')
    elif action == 'delete':
        conn.execute("DELETE FROM words WHERE id=?", (word_id,))
        conn.execute("DELETE FROM comments WHERE word_id=?", (word_id,))
        conn.execute("DELETE FROM votes WHERE word_id=?", (word_id,))
        log_action('Admin', f'ใช้พลังเทพเจ้าลบคำศัพท์ ID:{word_id} ทิ้งจากโลก')
    conn.commit()
    conn.close()
    flash('ระบบลงทัณฑ์เรียบร้อย!', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
