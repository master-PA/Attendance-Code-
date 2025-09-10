from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
import random
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'random_secret_key'

# Database setup
DB_PATH = 'attendance.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

# Create necessary tables
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY,
            class_name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT,
            class_id INTEGER,
            UNIQUE(name, class_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS otp (
            id INTEGER PRIMARY KEY,
            code TEXT,
            class_id INTEGER,
            expires_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            otp_id INTEGER,
            timestamp TEXT,
            UNIQUE(student_id, otp_id)
        )
    ''')
    conn.commit()
    conn.close()

@app.before_first_request
def setup():
    if not os.path.exists(DB_PATH):
        init_db()

# Home/Login Route
@app.route('/')
def index():
    return render_template('login.html')

# Teacher Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM teachers WHERE username=? AND password=?', (username, password))
        teacher = c.fetchone()
        if teacher:
            session['teacher'] = teacher['id']
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Invalid credentials')
    return redirect(url_for('index'))

# Teacher Dashboard
@app.route('/teacher/dashboard', methods=['GET', 'POST'])
def teacher_dashboard():
    if 'teacher' not in session:
        return redirect(url_for('index'))
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM classes')
    classes = c.fetchall()
    if request.method == 'POST':
        class_id = request.form['class']
        timer = int(request.form['timer'])
        code = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(seconds=timer)
        c.execute('INSERT INTO otp (code, class_id, expires_at) VALUES (?, ?, ?)', (code, class_id, expires_at))
        conn.commit()
        flash(f'OTP generated: {code} for {timer} seconds')
        return redirect(url_for('teacher_dashboard'))
    return render_template('teacher.html', classes=classes)

# Student Interface to Submit OTP
@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        student_name = request.form['name']
        otp_code = request.form['otp']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM students WHERE name=?', (student_name,))
        student = c.fetchone()
        if not student:
            flash('Student not found')
            return redirect(url_for('student'))
        
        c.execute('SELECT * FROM otp WHERE code=?', (otp_code,))
        otp = c.fetchone()
        if not otp:
            flash('Invalid OTP')
            return redirect(url_for('student'))
        
        if datetime.utcnow() > datetime.fromisoformat(otp['expires_at']):
            flash('OTP expired')
            return redirect(url_for('student'))
        
        c.execute('INSERT INTO attendance (student_id, otp_id, timestamp) VALUES (?, ?, ?)', (student['id'], otp['id'], datetime.utcnow()))
        conn.commit()
        flash('Attendance marked successfully')
    return render_template('student.html')

# Admin Interface for Adding Students, Classes, Teachers
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'add_student' in request.form:
            name = request.form['student_name']
            class_id = request.form['class_id']
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT INTO students (name, class_id) VALUES (?, ?)', (name, class_id))
            conn.commit()
            flash('Student added')
        elif 'add_class' in request.form:
            class_name = request.form['class_name']
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT INTO classes (class_name) VALUES (?)', (class_name,))
            conn.commit()
            flash('Class added')
        elif 'add_teacher' in request.form:
            username = request.form['teacher_username']
            password = request.form['teacher_password']
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT INTO teachers (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            flash('Teacher added')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM students')
    students = c.fetchall()
    return render_template('admin.html', students=students)

if __name__ == '__main__':
    app.run(debug=True)
