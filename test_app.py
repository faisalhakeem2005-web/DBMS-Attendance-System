"""Functional tests (positive + negative). Run: python test_app.py   (uses a temporary copy of the database)"""
import shutil, sqlite3, tempfile, os, json
import app as A
src = os.path.join(A.BASE, "attendance.db")
tmp = os.path.join(tempfile.mkdtemp(), "test.db"); shutil.copy(src, tmp); A.DB = tmp
c = A.app.test_client()
def login(role, uid=None): c.post("/login", data={"role": role, **({"uid": uid} if uid else {})})
def post(u, **d): return c.post(u, data=d, follow_redirects=True).data.decode()
def sql(s, a=()):
    con = sqlite3.connect(tmp); con.execute("PRAGMA foreign_keys=ON")
    try: return con.execute(s, a).fetchall()
    finally: con.close()
def msg(html):
    import re
    m = re.search(r'<div class="(ok|err)">(.*?)</div>', html, re.S)
    return (m.group(2).replace("&#39;", "'").strip() if m else "no message")
R = []
def case(feat, action, expected, actual, ok): R.append(dict(id="TC-%02d" % (len(R)+1), feature=feat, action=action, expected=expected, actual=actual, status="Pass" if ok else "Fail"))

login("admin")
m = msg(post("/students/save", roll_no="25WU0101301", name="Test Student", email="test.student@student.woxsen.edu.in", department="CSE", year="2", semester="3"))
case("Add student", "Submit valid student form", "Student added", m, m == "Student added.")
m = msg(post("/students/save", roll_no="25WU0101301", name="Dup", email="dup@x.in", department="CSE", year="2", semester="3"))
case("Unique roll number", "Add a second student with an existing roll number", "Rejected (UNIQUE)", m, "UNIQUE" in m)
m = msg(post("/students/save", roll_no="25WU0101302", name="Bad Year", email="b@x.in", department="CSE", year="9", semester="3"))
case("Year range check", "Add student with year = 9", "Rejected (CHECK)", m, "CHECK" in m)
m = msg(post("/students/1/delete"))
case("Controlled delete", "Delete a student who has attendance records", "Rejected (FOREIGN KEY)", m, "FOREIGN KEY" in m)
login("faculty", "1")
m = msg(post("/sessions/new", section_id="1", session_date="2026-10-16", start_time="09:00", end_time="10:00", session_type="LECTURE"))
case("Create session", "Faculty creates a lecture for CS201-A", "Class session created", m, m == "Class session created.")
m = msg(post("/sessions/new", section_id="1", session_date="2026-10-16", start_time="09:00", end_time="10:00", session_type="LECTURE"))
case("Duplicate session", "Create the same session again", "Rejected (UNIQUE)", m, "UNIQUE" in m)
m = msg(post("/sessions/new", section_id="1", session_date="2026-10-17", start_time="11:00", end_time="10:00", session_type="LECTURE"))
case("Time validation", "Create a session ending before it starts", "Rejected (CHECK)", m, "CHECK" in m)
sid = sql("SELECT MAX(session_id) FROM class_session")[0][0] - 0
sid = sql("SELECT session_id FROM class_session WHERE session_date='2026-10-16' AND section_id=1")[0][0]
form = {f"s_{r[0]}": ("ABSENT" if r[0] == 2 else "PRESENT") for r in sql("SELECT student_id FROM enrollment WHERE section_id=1")}
m = msg(post(f"/sessions/{sid}/mark", **form)); n = sql("SELECT COUNT(*) FROM attendance WHERE session_id=?", (sid,))[0][0]
case("Mark attendance", "Mark 10 students of CS201-A (1 absent)", "Attendance saved; 10 rows", f"{m} {n} rows", m == "Attendance saved." and n == 10)
try:
    sql("INSERT INTO attendance(student_id,session_id,status) VALUES(15,?, 'PRESENT')", (sid,)); a = "accepted"
except sqlite3.Error as e: a = str(e)
case("Enrolment check", "Mark student 15 (not in CS201-A) present", "Rejected (trigger)", a, "not enrolled" in a)
login("student", "1")
m = msg(post("/apply", leave_type_id="2", from_date="2026-11-04", to_date="2026-11-04", reason="Personal work"))
case("Submit leave", "Student 1 applies 1 day casual leave", "Leave application submitted", m, m == "Leave application submitted.")
m = msg(post("/apply", leave_type_id="2", from_date="2026-11-10", to_date="2026-11-17", reason="Trip"))
case("Leave duration limit", "Apply 8 days casual leave (max 3)", "Rejected (max days)", m, "maximum days" in m)
m = msg(post("/apply", leave_type_id="2", from_date="2026-11-04", to_date="2026-11-05", reason="Overlap"))
case("Overlapping leave", "Apply leave overlapping a pending one", "Rejected (overlap)", m, "overlap" in m)
m = msg(post("/apply", leave_type_id="1", from_date="2026-11-09", to_date="2026-11-06", reason="Bad dates"))
case("Date validation", "From-date later than to-date", "Rejected (validation)", m, "From-date" in m)
lid = sql("SELECT MAX(leave_id) FROM leave_application")[0][0]
sql_leave = sql("SELECT leave_id FROM leave_application WHERE student_id=1 AND from_date='2026-11-04'")[0][0]
login("faculty", "3")   # teaches OS to all students
m = msg(post(f"/leaves/{sql_leave}/decide", decision="APPROVED", remarks="Approved")); st = sql("SELECT status FROM leave_application WHERE leave_id=?", (sql_leave,))[0][0]
al = sql("SELECT COUNT(*) FROM alert WHERE student_id=1 AND message LIKE ?", (f"%#{sql_leave} was approved%",))[0][0]
case("Authorized approval", "Faculty 3 approves the pending leave", "Status APPROVED + student alert", f"{m} status={st}, alerts={al}", st == "APPROVED" and al == 1)
login("faculty", "1")
m = msg(post("/leaves/12/decide", decision="APPROVED", remarks="x"))
case("Unauthorized approval", "Faculty 1 decides leave of student 12 (not his student)", "Rejected (trigger)", m, "not assigned" in m)
ex = sql("""SELECT COUNT(*) FROM attendance a JOIN class_session cs ON cs.session_id=a.session_id JOIN leave_application l ON l.student_id=a.student_id
            WHERE l.status='APPROVED' AND cs.session_date BETWEEN l.from_date AND l.to_date AND a.status='ABSENT'""")[0][0]
case("Excused absence", "Count ABSENT marks that fall inside approved leaves", "0 (all converted to EXCUSED)", str(ex), ex == 0)
v = sql("SELECT attendance_pct FROM v_attendance_summary WHERE student_id=1 AND section_id=1")[0][0]
man = sql("SELECT ROUND(100.0*SUM(a.status IN ('PRESENT','LATE'))/COUNT(*),2) FROM attendance a JOIN class_session cs ON cs.session_id=a.session_id WHERE a.student_id=1 AND cs.section_id=1 AND a.status<>'EXCUSED'")[0][0]
case("Attendance percentage", "Compare view result with manual calculation (student 1, CS201-A)", "Both values equal", f"view={v}, manual={man}", v == man)
login("admin"); post("/alerts/generate"); n1 = sql("SELECT COUNT(*) FROM alert")[0][0]; post("/alerts/generate"); n2 = sql("SELECT COUNT(*) FROM alert")[0][0]
case("Shortage alerts", "Run alert generation twice", "No duplicate alerts on second run", f"count {n1} -> {n2}", n1 == n2)
login("faculty", "1")
try:
    sql("INSERT INTO makeup_session(section_id,original_session_id,makeup_date,start_time,end_time) VALUES(1,5,'2026-01-01','16:00','17:00')"); a = "accepted"
except sqlite3.Error as e: a = str(e)
case("Makeup date rule", "Schedule a makeup before the original session date", "Rejected (trigger)", a, "earlier" in a)
for r in R: print(r["id"], r["status"], "|", r["feature"], "|", r["actual"][:70])
json.dump(R, open(os.path.join(A.BASE, "test_results.json"), "w"), indent=1)
print(sum(r["status"] == "Pass" for r in R), "/", len(R), "passed")
