"""Student Attendance & Leave Approval System - Flask + SQLite application.
Run:  python init_db.py   then   python app.py   ->  http://127.0.0.1:5000
Author: Faisal Mohammed (25WU0101161)"""
import os, sqlite3
from datetime import date
from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from jinja2 import DictLoader

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "attendance.db")
app = Flask(__name__)
app.secret_key = "pbl-project-26-demo"

# ------------------------------ database layer ---------------------------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")          # enforce referential integrity
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=()):            # parameterised read (prevents SQL injection)
    return db().execute(sql, args).fetchall()

def run(sql, args=(), ok=None):  # parameterised write in a transaction with rollback on error
    try:
        with db():
            db().execute(sql, args)
        if ok: flash(ok, "ok")
        return True
    except sqlite3.Error as e:   # constraint / trigger messages are shown to the user
        flash("Rejected by database rule: " + str(e), "err")
        return False

def need(role):
    if session.get("role") != role:
        return redirect(url_for("login"))

# --------------------------------- login ---------------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role, uid = request.form["role"], request.form.get("uid")
        session.clear(); session["role"] = role
        if role != "admin": session["uid"] = int(uid)
        return redirect(url_for(role))
    return render_template("login.html", students=q("SELECT student_id,roll_no,name FROM student ORDER BY name"),
                           faculty=q("SELECT faculty_id,name FROM faculty ORDER BY name"))

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

# --------------------------------- admin ---------------------------------
@app.route("/admin")
def admin():
    if need("admin"): return need("admin")
    c = {t: q(f"SELECT COUNT(*) n FROM {t}")[0]["n"] for t in
         ["student", "faculty", "course", "section", "class_session", "attendance", "leave_application", "alert"]}
    c["shortage"] = q("SELECT COUNT(*) n FROM v_shortage")[0]["n"]
    c["pending"] = q("SELECT COUNT(*) n FROM leave_application WHERE status='PENDING'")[0]["n"]
    return render_template("admin.html", c=c)

@app.route("/students")
def students():
    if need("admin"): return need("admin")
    s = request.args.get("q", "").strip()
    rows = q("SELECT * FROM student WHERE name LIKE ? OR roll_no LIKE ? OR email LIKE ? ORDER BY roll_no",
             (f"%{s}%",) * 3)
    edit = q("SELECT * FROM student WHERE student_id=?", (request.args.get("edit"),)) if request.args.get("edit") else []
    return render_template("students.html", rows=rows, s=s, edit=edit[0] if edit else None)

@app.route("/students/save", methods=["POST"])
def student_save():
    if need("admin"): return need("admin")
    f = request.form
    try:
        year, sem = int(f["year"]), int(f["semester"])
    except ValueError:
        flash("Year and semester must be numbers.", "err"); return redirect(url_for("students"))
    if not f["name"].strip() or "@" not in f["email"]:
        flash("Name and a valid e-mail are required.", "err"); return redirect(url_for("students"))
    if f.get("student_id"):
        run("UPDATE student SET roll_no=?,name=?,email=?,department=?,year=?,semester=? WHERE student_id=?",
            (f["roll_no"], f["name"], f["email"], f["department"], year, sem, f["student_id"]), "Student updated.")
    else:
        run("INSERT INTO student(roll_no,name,email,department,year,semester) VALUES(?,?,?,?,?,?)",
            (f["roll_no"], f["name"], f["email"], f["department"], year, sem), "Student added.")
    return redirect(url_for("students"))

@app.route("/students/<int:sid>/delete", methods=["POST"])
def student_delete(sid):
    if need("admin"): return need("admin")
    run("DELETE FROM student WHERE student_id=?", (sid,), "Student removed.")   # RESTRICT blocks if attendance exists
    return redirect(url_for("students"))

@app.route("/reports")
def reports():
    if need("admin"): return need("admin")
    views = {"attendance": ("Attendance percentage", "SELECT roll_no,student_name,course_code,counted_sessions,attended,excused,attendance_pct FROM v_attendance_summary ORDER BY roll_no,course_code"),
             "shortage": ("Attendance shortage", "SELECT roll_no,student_name,course_code,attendance_pct,min_attendance_pct,ROUND(min_attendance_pct-attendance_pct,2) AS shortfall FROM v_shortage ORDER BY shortfall DESC"),
             "leave": ("Leave history", "SELECT leave_id,roll_no,student_name,type_name,from_date,to_date,days,status,decided_by FROM v_leave_history ORDER BY from_date"),
             "course": ("Course summary", "SELECT course_code,section_name,faculty_name,sessions_held,students,avg_attendance_pct,students_in_shortage FROM v_course_summary"),
             "trend": ("Monthly trend", "SELECT course_code,month,marked,attended,attendance_pct FROM v_monthly_trend ORDER BY course_code,month"),
             "makeup": ("Makeup attendance", "SELECT course_code,section_name,original_date,makeup_date,present_count,marked_count FROM v_makeup_report")}
    key = request.args.get("r", "attendance"); title, sql = views.get(key, views["attendance"])
    cur = db().execute(sql); rows = cur.fetchall()
    return render_template("reports.html", views=views, key=key, title=title, cols=[d[0] for d in cur.description], rows=rows)

@app.route("/alerts/generate", methods=["POST"])
def gen_alerts():
    if need("admin"): return need("admin")
    before = q("SELECT COUNT(*) n FROM alert")[0]["n"]
    run("""INSERT INTO alert(student_id,section_id,alert_type,message)
           SELECT v.student_id,v.section_id,'SHORTAGE','Attendance in '||v.course_code||' is '||v.attendance_pct||'% (minimum '||v.min_attendance_pct||'%).'
           FROM v_shortage v WHERE NOT EXISTS (SELECT 1 FROM alert a WHERE a.student_id=v.student_id AND a.section_id=v.section_id
                 AND a.alert_type='SHORTAGE' AND a.is_read=0)""")
    flash(f"{q('SELECT COUNT(*) n FROM alert')[0]['n'] - before} new shortage alert(s) generated.", "ok")
    return redirect(url_for("admin"))

# -------------------------------- faculty --------------------------------
def fac_sections():
    return q("""SELECT s.section_id,c.course_code,c.course_name,s.section_name,
                (SELECT COUNT(*) FROM class_session x WHERE x.section_id=s.section_id) sessions
                FROM section s JOIN course c ON c.course_id=s.course_id WHERE s.faculty_id=? ORDER BY c.course_code""",
             (session["uid"],))

@app.route("/faculty")
def faculty():
    if need("faculty"): return need("faculty")
    me = q("SELECT * FROM faculty WHERE faculty_id=?", (session["uid"],))[0]
    sessions = q("""SELECT cs.*,c.course_code,s.section_name,(SELECT COUNT(*) FROM attendance a WHERE a.session_id=cs.session_id) marked
                    FROM class_session cs JOIN section s ON s.section_id=cs.section_id JOIN course c ON c.course_id=s.course_id
                    WHERE s.faculty_id=? ORDER BY cs.session_date DESC,cs.start_time LIMIT 12""", (session["uid"],))
    return render_template("faculty.html", me=me, secs=fac_sections(), sessions=sessions, today=date.today().isoformat())

@app.route("/sessions/new", methods=["POST"])
def session_new():
    if need("faculty"): return need("faculty")
    f = request.form
    if not q("SELECT 1 FROM section WHERE section_id=? AND faculty_id=?", (f["section_id"], session["uid"])):
        flash("You can only create sessions for your own sections.", "err")
    else:
        run("INSERT INTO class_session(section_id,session_date,start_time,end_time,session_type) VALUES(?,?,?,?,?)",
            (f["section_id"], f["session_date"], f["start_time"], f["end_time"], f["session_type"]), "Class session created.")
    return redirect(url_for("faculty"))

@app.route("/sessions/<int:sid>/mark", methods=["GET", "POST"])
def mark(sid):
    if need("faculty"): return need("faculty")
    info = q("""SELECT cs.*,c.course_code,c.course_name,s.section_name,s.faculty_id FROM class_session cs
                JOIN section s ON s.section_id=cs.section_id JOIN course c ON c.course_id=s.course_id WHERE cs.session_id=?""", (sid,))
    if not info or info[0]["faculty_id"] != session["uid"]:
        flash("Session not found for your sections.", "err"); return redirect(url_for("faculty"))
    if request.method == "POST":
        try:
            with db():                                   # all marks saved in one transaction
                for key, status in request.form.items():
                    if key.startswith("s_"):
                        st = int(key[2:])
                        db().execute("""INSERT INTO attendance(student_id,session_id,status) VALUES(?,?,?)
                                        ON CONFLICT(student_id,session_id) DO UPDATE SET status=excluded.status,marked_at=datetime('now')""",
                                     (st, sid, status))
                        if status == "ABSENT":           # approved leave => EXCUSED
                            db().execute("""UPDATE attendance SET status='EXCUSED' WHERE student_id=? AND session_id=? AND EXISTS
                                (SELECT 1 FROM leave_application l WHERE l.student_id=? AND l.status='APPROVED' AND ? BETWEEN l.from_date AND l.to_date)""",
                                         (st, sid, st, info[0]["session_date"]))
            flash("Attendance saved.", "ok")
        except sqlite3.Error as e:
            flash("Rejected by database rule: " + str(e), "err")
        return redirect(url_for("mark", sid=sid))
    rows = q("""SELECT st.student_id,st.roll_no,st.name,a.status FROM enrollment e JOIN student st ON st.student_id=e.student_id
                LEFT JOIN attendance a ON a.student_id=st.student_id AND a.session_id=? WHERE e.section_id=? ORDER BY st.roll_no""",
             (sid, info[0]["section_id"]))
    return render_template("mark.html", info=info[0], rows=rows)

@app.route("/leaves")
def leaves():
    if need("faculty"): return need("faculty")
    rows = q("""SELECT l.*,st.roll_no,st.name,lt.type_name FROM leave_application l JOIN student st ON st.student_id=l.student_id
                JOIN leave_type lt ON lt.leave_type_id=l.leave_type_id
                WHERE l.status='PENDING' AND EXISTS (SELECT 1 FROM enrollment e JOIN section s ON s.section_id=e.section_id
                      WHERE e.student_id=l.student_id AND s.faculty_id=?) ORDER BY l.from_date""", (session["uid"],))
    return render_template("leaves.html", rows=rows)

@app.route("/leaves/<int:lid>/decide", methods=["POST"])
def decide(lid):
    if need("faculty"): return need("faculty")
    d = request.form["decision"]
    if d not in ("APPROVED", "REJECTED"): flash("Invalid decision.", "err")
    else: run("INSERT INTO approval(leave_id,faculty_id,decision,remarks) VALUES(?,?,?,?)",
              (lid, session["uid"], d, request.form.get("remarks", "")), f"Leave {d.lower()}.")
    return redirect(url_for("leaves"))

@app.route("/makeup", methods=["GET", "POST"])
def makeup():
    if need("faculty"): return need("faculty")
    if request.method == "POST":
        f = request.form
        sec = q("SELECT section_id FROM class_session WHERE session_id=?", (f["original_session_id"],))
        run("INSERT INTO makeup_session(section_id,original_session_id,makeup_date,start_time,end_time) VALUES(?,?,?,?,?)",
            (sec[0]["section_id"] if sec else 0, f["original_session_id"], f["makeup_date"], f["start_time"], f["end_time"]), "Makeup session scheduled.")
        return redirect(url_for("makeup"))
    orig = q("""SELECT cs.session_id,cs.session_date,c.course_code,s.section_name FROM class_session cs JOIN section s ON s.section_id=cs.section_id
                JOIN course c ON c.course_id=s.course_id WHERE s.faculty_id=? ORDER BY cs.session_date DESC""", (session["uid"],))
    rows = q("""SELECT m.*,c.course_code,s.section_name,o.session_date orig FROM makeup_session m JOIN section s ON s.section_id=m.section_id
                JOIN course c ON c.course_id=s.course_id JOIN class_session o ON o.session_id=m.original_session_id
                WHERE s.faculty_id=? ORDER BY m.makeup_date DESC""", (session["uid"],))
    return render_template("makeup.html", orig=orig, rows=rows)

@app.route("/makeup/<int:mid>/mark", methods=["GET", "POST"])
def makeup_mark(mid):
    if need("faculty"): return need("faculty")
    m = q("""SELECT m.*,c.course_code,s.section_name FROM makeup_session m JOIN section s ON s.section_id=m.section_id
             JOIN course c ON c.course_id=s.course_id WHERE m.makeup_id=? AND s.faculty_id=?""", (mid, session["uid"]))
    if not m: return redirect(url_for("makeup"))
    if request.method == "POST":
        try:
            with db():
                for k, v in request.form.items():
                    if k.startswith("s_"):
                        db().execute("""INSERT INTO makeup_attendance(makeup_id,student_id,status) VALUES(?,?,?)
                                        ON CONFLICT(makeup_id,student_id) DO UPDATE SET status=excluded.status""", (mid, int(k[2:]), v))
            flash("Makeup attendance saved.", "ok")
        except sqlite3.Error as e: flash("Rejected by database rule: " + str(e), "err")
        return redirect(url_for("makeup_mark", mid=mid))
    rows = q("""SELECT st.student_id,st.roll_no,st.name,ma.status FROM enrollment e JOIN student st ON st.student_id=e.student_id
                LEFT JOIN makeup_attendance ma ON ma.student_id=st.student_id AND ma.makeup_id=? WHERE e.section_id=? ORDER BY st.roll_no""", (mid, m[0]["section_id"]))
    return render_template("makeup_mark.html", m=m[0], rows=rows)

# -------------------------------- student --------------------------------
@app.route("/student")
def student():
    if need("student"): return need("student")
    me = q("SELECT * FROM student WHERE student_id=?", (session["uid"],))[0]
    summ = q("SELECT * FROM v_attendance_summary WHERE student_id=? ORDER BY course_code", (session["uid"],))
    alerts = q("SELECT * FROM alert WHERE student_id=? ORDER BY created_at DESC,alert_id DESC LIMIT 6", (session["uid"],))
    return render_template("student.html", me=me, summ=summ, alerts=alerts)

@app.route("/apply", methods=["GET", "POST"])
def apply():
    if need("student"): return need("student")
    if request.method == "POST":
        f = request.form
        if not f["reason"].strip(): flash("Reason is required.", "err")
        elif f["from_date"] > f["to_date"]: flash("From-date must not be after to-date.", "err")
        else:
            run("INSERT INTO leave_application(student_id,leave_type_id,from_date,to_date,reason) VALUES(?,?,?,?,?)",
                (session["uid"], f["leave_type_id"], f["from_date"], f["to_date"], f["reason"].strip()), "Leave application submitted.")
            return redirect(url_for("myleaves"))
    return render_template("apply.html", types=q("SELECT * FROM leave_type"), today=date.today().isoformat())

@app.route("/myleaves")
def myleaves():
    if need("student"): return need("student")
    rows = q("SELECT * FROM v_leave_history WHERE roll_no=(SELECT roll_no FROM student WHERE student_id=?) ORDER BY from_date DESC", (session["uid"],))
    return render_template("myleaves.html", rows=rows)

@app.route("/leaves/<int:lid>/cancel", methods=["POST"])
def cancel(lid):
    if need("student"): return need("student")
    run("DELETE FROM leave_application WHERE leave_id=? AND student_id=? AND status='PENDING'", (lid, session["uid"]), "Pending application withdrawn.")
    return redirect(url_for("myleaves"))

# -------------------------------- templates -------------------------------
CSS = """body{font-family:Arial,sans-serif;background:#faf6ec;color:#3b2a20;margin:0}
.top{background:#5a2d1c;color:#fff;padding:12px 24px;font-size:18px}.top a{color:#ffd9b8;margin-left:18px;font-size:14px;text-decoration:none}
.wrap{padding:20px 24px;max-width:1080px}h2{color:#5a2d1c;margin-top:4px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}th{background:#f3dfc9;text-align:left}
td,th{border:1px solid #e3cdb5;padding:6px 8px}.card{background:#fff;border:1px solid #e3cdb5;border-left:5px solid #f08a3c;padding:10px 14px;margin:0 10px 10px 0;display:inline-block;min-width:130px}
.card b{font-size:22px;display:block}.ok{background:#e4f5e1;border:1px solid #9bd08f;padding:8px 12px;margin-bottom:8px}.err{background:#fde4e1;border:1px solid #e59a90;padding:8px 12px;margin-bottom:8px}
input,select,button,textarea{padding:5px 7px;font-size:13px;border:1px solid #c9ae92;border-radius:3px}button{background:#f08a3c;color:#fff;border-color:#d97626;cursor:pointer}
.low{color:#b3261e;font-weight:bold}.good{color:#2e7d32;font-weight:bold}.tab{display:inline-block;padding:5px 10px;background:#f3dfc9;margin:0 4px 8px 0;text-decoration:none;color:#5a2d1c;font-size:13px}.tab.on{background:#5a2d1c;color:#fff}"""
T = {}
T["base.html"] = """<!doctype html><html><head><meta charset="utf-8"><title>Attendance &amp; Leave System</title><style>""" + CSS + """</style></head><body>
<div class="top"><b>Student Attendance &amp; Leave Approval System</b>
{% if session.role=='admin' %}<a href="/admin">Dashboard</a><a href="/students">Students</a><a href="/reports">Reports</a>{% endif %}
{% if session.role=='faculty' %}<a href="/faculty">My Sections</a><a href="/leaves">Leave Requests</a><a href="/makeup">Makeup</a>{% endif %}
{% if session.role=='student' %}<a href="/student">My Attendance</a><a href="/apply">Apply Leave</a><a href="/myleaves">My Leaves</a>{% endif %}
{% if session.role %}<a href="/logout">Logout ({{ session.role }})</a>{% endif %}</div>
<div class="wrap">{% for cat,m in get_flashed_messages(with_categories=true) %}<div class="{{cat}}">{{ m }}</div>{% endfor %}{% block body %}{% endblock %}</div></body></html>"""
T["login.html"] = """{% extends 'base.html' %}{% block body %}<h2>Sign in</h2><p>Select a role and user (demo login without passwords).</p>
<form method="post"><p>Role: <select name="role" id="r"><option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Administrator</option></select></p>
<p>Student: <select name="uid">{% for s in students %}<option value="{{s.student_id}}">{{s.roll_no}} - {{s.name}}</option>{% endfor %}</select></p>
<button>Login as student</button></form><hr><form method="post"><input type="hidden" name="role" value="faculty"><p>Faculty:
<select name="uid">{% for f in faculty %}<option value="{{f.faculty_id}}">{{f.name}}</option>{% endfor %}</select> <button>Login as faculty</button></p></form>
<form method="post"><input type="hidden" name="role" value="admin"><button>Login as administrator</button></form>{% endblock %}"""
T["admin.html"] = """{% extends 'base.html' %}{% block body %}<h2>Administrator Dashboard</h2>
{% for k,v in c.items() %}<div class="card">{{k|replace('_',' ')|title}}<b>{{v}}</b></div>{% endfor %}
<form method="post" action="/alerts/generate"><button>Generate shortage alerts</button></form>{% endblock %}"""
T["students.html"] = """{% extends 'base.html' %}{% block body %}<h2>Student Management</h2>
<form method="get">Search: <input name="q" value="{{s}}" placeholder="name / roll no / e-mail"> <button>Search</button></form><br>
<form method="post" action="/students/save"><input type="hidden" name="student_id" value="{{edit.student_id if edit else ''}}">
<input name="roll_no" placeholder="Roll no" value="{{edit.roll_no if edit else ''}}" required> <input name="name" placeholder="Name" value="{{edit.name if edit else ''}}" required>
<input name="email" placeholder="E-mail" value="{{edit.email if edit else ''}}" required> <input name="department" size="6" value="{{edit.department if edit else 'CSE'}}">
Year <input name="year" size="2" value="{{edit.year if edit else 2}}"> Sem <input name="semester" size="2" value="{{edit.semester if edit else 3}}">
<button>{{ 'Update' if edit else 'Add' }} student</button></form><br>
<table><tr><th>Roll No</th><th>Name</th><th>E-mail</th><th>Dept</th><th>Year</th><th>Sem</th><th>Actions</th></tr>
{% for r in rows %}<tr><td>{{r.roll_no}}</td><td>{{r.name}}</td><td>{{r.email}}</td><td>{{r.department}}</td><td>{{r.year}}</td><td>{{r.semester}}</td>
<td><a href="/students?edit={{r.student_id}}">Edit</a> <form method="post" action="/students/{{r.student_id}}/delete" style="display:inline" onsubmit="return confirm('Delete this student?')"><button>Delete</button></form></td></tr>{% endfor %}</table>{% endblock %}"""
T["reports.html"] = """{% extends 'base.html' %}{% block body %}<h2>Reports</h2>
{% for k,v in views.items() %}<a class="tab {{ 'on' if k==key }}" href="/reports?r={{k}}">{{v[0]}}</a>{% endfor %}
<h3>{{title}} ({{rows|length}} rows)</h3><table><tr>{% for c in cols %}<th>{{c|replace('_',' ')}}</th>{% endfor %}</tr>
{% for r in rows %}<tr>{% for c in cols %}<td>{{ r[c] if r[c] is not none else '-' }}</td>{% endfor %}</tr>{% endfor %}</table>{% endblock %}"""
T["faculty.html"] = """{% extends 'base.html' %}{% block body %}<h2>Welcome, {{me.name}}</h2><h3>My sections</h3>
<table><tr><th>Course</th><th>Section</th><th>Sessions created</th></tr>{% for s in secs %}<tr><td>{{s.course_code}} - {{s.course_name}}</td><td>{{s.section_name}}</td><td>{{s.sessions}}</td></tr>{% endfor %}</table>
<h3>Create class session</h3><form method="post" action="/sessions/new"><select name="section_id">{% for s in secs %}<option value="{{s.section_id}}">{{s.course_code}}-{{s.section_name}}</option>{% endfor %}</select>
<input type="date" name="session_date" value="{{today}}" required> <input type="time" name="start_time" value="09:00"> <input type="time" name="end_time" value="10:00">
<select name="session_type"><option>LECTURE</option><option>LAB</option><option>TUTORIAL</option></select> <button>Create session</button></form>
<h3>Recent sessions</h3><table><tr><th>Date</th><th>Course</th><th>Time</th><th>Type</th><th>Marked</th><th></th></tr>
{% for s in sessions %}<tr><td>{{s.session_date}}</td><td>{{s.course_code}}-{{s.section_name}}</td><td>{{s.start_time}}-{{s.end_time}}</td><td>{{s.session_type}}</td><td>{{s.marked}}</td><td><a href="/sessions/{{s.session_id}}/mark">Mark attendance</a></td></tr>{% endfor %}</table>{% endblock %}"""
T["mark.html"] = """{% extends 'base.html' %}{% block body %}<h2>Mark attendance</h2><p>{{info.course_code}} {{info.course_name}} - Section {{info.section_name}} | {{info.session_date}} {{info.start_time}}-{{info.end_time}} ({{info.session_type}})</p>
<form method="post"><table><tr><th>Roll No</th><th>Name</th><th>Status</th></tr>{% for r in rows %}<tr><td>{{r.roll_no}}</td><td>{{r.name}}</td><td>
<select name="s_{{r.student_id}}">{% for o in ['PRESENT','ABSENT','LATE'] %}<option {{ 'selected' if r.status==o }}>{{o}}</option>{% endfor %}{% if r.status=='EXCUSED' %}<option selected>EXCUSED</option>{% endif %}</select></td></tr>{% endfor %}</table><br><button>Save attendance</button></form>{% endblock %}"""
T["leaves.html"] = """{% extends 'base.html' %}{% block body %}<h2>Pending leave requests</h2>{% if not rows %}<p>No pending requests.</p>{% endif %}
<table><tr><th>Student</th><th>Type</th><th>From</th><th>To</th><th>Reason</th><th>Decision</th></tr>{% for r in rows %}<tr><td>{{r.roll_no}} {{r.name}}</td><td>{{r.type_name}}</td><td>{{r.from_date}}</td><td>{{r.to_date}}</td><td>{{r.reason}}</td>
<td><form method="post" action="/leaves/{{r.leave_id}}/decide"><input name="remarks" placeholder="Remarks"> <button name="decision" value="APPROVED">Approve</button> <button name="decision" value="REJECTED">Reject</button></form></td></tr>{% endfor %}</table>{% endblock %}"""
T["makeup.html"] = """{% extends 'base.html' %}{% block body %}<h2>Makeup sessions</h2><form method="post"><select name="original_session_id">{% for o in orig %}<option value="{{o.session_id}}">{{o.session_date}} {{o.course_code}}-{{o.section_name}}</option>{% endfor %}</select>
<input type="date" name="makeup_date" required> <input type="time" name="start_time" value="16:30"> <input type="time" name="end_time" value="17:30"> <button>Schedule makeup</button></form><br>
<table><tr><th>Course</th><th>Original</th><th>Makeup date</th><th>Time</th><th></th></tr>{% for m in rows %}<tr><td>{{m.course_code}}-{{m.section_name}}</td><td>{{m.orig}}</td><td>{{m.makeup_date}}</td><td>{{m.start_time}}-{{m.end_time}}</td><td><a href="/makeup/{{m.makeup_id}}/mark">Mark attendance</a></td></tr>{% endfor %}</table>{% endblock %}"""
T["makeup_mark.html"] = """{% extends 'base.html' %}{% block body %}<h2>Makeup attendance - {{m.course_code}}-{{m.section_name}} on {{m.makeup_date}}</h2>
<form method="post"><table><tr><th>Roll No</th><th>Name</th><th>Status</th></tr>{% for r in rows %}<tr><td>{{r.roll_no}}</td><td>{{r.name}}</td><td><select name="s_{{r.student_id}}">{% for o in ['PRESENT','ABSENT'] %}<option {{ 'selected' if r.status==o }}>{{o}}</option>{% endfor %}</select></td></tr>{% endfor %}</table><br><button>Save</button></form>{% endblock %}"""
T["student.html"] = """{% extends 'base.html' %}{% block body %}<h2>{{me.name}} ({{me.roll_no}})</h2><h3>Attendance by course</h3>
<table><tr><th>Course</th><th>Section</th><th>Sessions counted</th><th>Attended</th><th>Excused</th><th>Attendance %</th><th>Minimum</th></tr>
{% for s in summ %}<tr><td>{{s.course_code}} - {{s.course_name}}</td><td>{{s.section_name}}</td><td>{{s.counted_sessions}}</td><td>{{s.attended}}</td><td>{{s.excused}}</td>
<td class="{{ 'low' if s.attendance_pct < s.min_attendance_pct else 'good' }}">{{s.attendance_pct}}%</td><td>{{s.min_attendance_pct}}%</td></tr>{% endfor %}</table>
<h3>Alerts</h3>{% for a in alerts %}<div class="{{ 'err' if a.alert_type=='SHORTAGE' else 'ok' }}">{{a.created_at}} - {{a.message}}</div>{% else %}<p>No alerts.</p>{% endfor %}{% endblock %}"""
T["apply.html"] = """{% extends 'base.html' %}{% block body %}<h2>Apply for leave</h2><form method="post"><p>Type: <select name="leave_type_id">{% for t in types %}<option value="{{t.leave_type_id}}">{{t.type_name}} (max {{t.max_days}} days)</option>{% endfor %}</select></p>
<p>From: <input type="date" name="from_date" value="{{today}}" required> To: <input type="date" name="to_date" value="{{today}}" required></p>
<p><textarea name="reason" rows="3" cols="60" placeholder="Reason"></textarea></p><button>Submit application</button></form>{% endblock %}"""
T["myleaves.html"] = """{% extends 'base.html' %}{% block body %}<h2>My leave applications</h2><table><tr><th>#</th><th>Type</th><th>From</th><th>To</th><th>Days</th><th>Status</th><th>Decided by</th><th>Remarks</th><th></th></tr>
{% for r in rows %}<tr><td>{{r.leave_id}}</td><td>{{r.type_name}}</td><td>{{r.from_date}}</td><td>{{r.to_date}}</td><td>{{r.days}}</td><td>{{r.status}}</td><td>{{r.decided_by or '-'}}</td><td>{{r.remarks or ''}}</td>
<td>{% if r.status=='PENDING' %}<form method="post" action="/leaves/{{r.leave_id}}/cancel"><button>Withdraw</button></form>{% endif %}</td></tr>{% endfor %}</table>{% endblock %}"""
app.jinja_loader = DictLoader(T)

if __name__ == "__main__":
    if not os.path.exists(DB): raise SystemExit("Run `python init_db.py` first.")
    app.run(debug=True)
