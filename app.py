from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, random, string, datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"   # change this in production


# ===============================
# Database Initialization
# ===============================
def init_db_function():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    # Teachers table
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    username TEXT UNIQUE,
                    password TEXT
                )''')

    # Classes table
    c.execute('''CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT,
                    teacher_id INTEGER,
                    FOREIGN KEY(teacher_id) REFERENCES teachers(id)
                )''')

    # Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    username TEXT UNIQUE,
                    password TEXT,
                    class_id INTEGER,
                    FOREIGN KEY(class_id) REFERENCES classes(id)
                )''')

    # Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    class_id INTEGER,
                    date TEXT,
                    status TEXT,
                    FOREIGN KEY(student_id) REFERENCES students(id),
                    FOREIGN KEY(class_id) REFERENCES classes(id)
                )''')

    # OTP codes table
    c.execute('''CREATE TABLE IF NOT EXISTS otps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER,
                    code TEXT,
                    expires_at DATETIME,
                    FOREIGN KEY(class_id) REFERENCES classes(id)
                )''')

    conn.commit()
    conn.close()


# ===============================
# Helper Functions
# ===============================
def get_db():
    return sqlite3.connect("attendance.db")

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))


# ===============================
# Routes
# ===============================
@app.route("/")
def index():
    return render_template("login.html")


# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        c = conn.cursor()

        # First check admin
        c.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        if user:
            session["user"] = user[0]
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))

        # Then check teacher
        c.execute("SELECT * FROM teachers WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        if user:
            session["user"] = user[0]
            session["role"] = "teacher"
            return redirect(url_for("teacher_dashboard"))

        # Then check student
        c.execute("SELECT * FROM students WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        if user:
            session["user"] = user[0]
            session["role"] = "student"
            return redirect(url_for("student_dashboard"))

        conn.close()

        flash("❌ Invalid credentials. Please try again.")
        return redirect(url_for("login"))

    return render_template("login.html")


# ---------- Teacher ----------
@app.route("/teacher/view_attendance", methods=["POST"])
def view_attendance():
    if session.get("role") != "teacher":
        return redirect(url_for("index"))

    class_id = request.form.get("class_id")
    selected_date = request.form.get("date")

    conn = get_db()
    c = conn.cursor()

    # Fetch classes again
    c.execute("SELECT * FROM classes WHERE teacher_id=?", (session["user"],))
    classes = c.fetchall()

    # Fetch attendance
    c.execute("""SELECT students.name, attendance.status
                 FROM students
                 LEFT JOIN attendance ON students.id = attendance.student_id
                 AND attendance.date = ?
                 WHERE students.class_id=?""", (selected_date, class_id))
    records = c.fetchall()

    # Get class name
    c.execute("SELECT class_name FROM classes WHERE id=?", (class_id,))
    class_name = c.fetchone()[0]

    conn.close()
    return render_template("teacher.html",
                           classes=classes,
                           attendance_records=records,
                           selected_class_name=class_name,
                           selected_date=selected_date,
                           today=datetime.date.today().isoformat())
    
# ---------- Student ----------
@app.route("/student", methods=["GET", "POST"])
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("index"))

    student_id = session["user"]
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        code = request.form["otp"]

        c.execute("SELECT * FROM otps WHERE code=? ORDER BY id DESC LIMIT 1", (code,))
        otp = c.fetchone()
        if otp:
            otp_id, class_id, otp_code, expires_at = otp
            if datetime.datetime.now() < datetime.datetime.fromisoformat(expires_at):
                today = datetime.date.today().isoformat()
                c.execute("INSERT INTO attendance (student_id, class_id, date, status) VALUES (?, ?, ?, ?)",
                          (student_id, class_id, today, "Present"))
                conn.commit()
                flash("Attendance marked successfully!")
            else:
                flash("OTP expired!")
        else:
            flash("Invalid OTP!")

    # show attendance history
    c.execute("""SELECT date, status FROM attendance 
                 WHERE student_id=? ORDER BY date DESC""", (student_id,))
    records = c.fetchall()
    conn.close()
    return render_template("student.html", records=records)


# ---------- Admin ----------
@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("index"))

    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        if "add_teacher" in request.form:
            name = request.form["t_name"]
            username = request.form["t_username"]
            password = request.form["t_password"]
            c.execute("INSERT INTO teachers (name, username, password) VALUES (?, ?, ?)",
                      (name, username, password))
            conn.commit()

        if "add_class" in request.form:
            class_name = request.form["c_name"]
            teacher_id = request.form["teacher_id"]
            c.execute("INSERT INTO classes (class_name, teacher_id) VALUES (?, ?)",
                      (class_name, teacher_id))
            conn.commit()

        if "add_student" in request.form:
            name = request.form["s_name"]
            username = request.form["s_username"]
            password = request.form["s_password"]
            class_id = request.form["class_id"]
            c.execute("INSERT INTO students (name, username, password, class_id) VALUES (?, ?, ?, ?)",
                      (name, username, password, class_id))
            conn.commit()

    # fetch for display
    c.execute("SELECT * FROM teachers")
    teachers = c.fetchall()
    c.execute("SELECT * FROM classes")
    classes = c.fetchall()

    # fetch students with their class name
    c.execute("""SELECT students.id, students.name, students.username, classes.class_name
                 FROM students
                 LEFT JOIN classes ON students.class_id = classes.id""")
    students = c.fetchall()

    conn.close()
    return render_template("admin.html", teachers=teachers, classes=classes, students=students)


# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ===============================
# Run App
# ===============================
if __name__ == "__main__":
    init_db_function()   # ✅ create tables if not exist
    app.run(debug=True)
