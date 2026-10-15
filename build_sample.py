"""Generates sample_data.sql (deterministic). Run: python build_sample.py"""
import random, datetime as dt
random.seed(26)
q = lambda s: "'" + str(s).replace("'", "''") + "'"
out = ["PRAGMA foreign_keys = ON;", "BEGIN TRANSACTION;"]

names = ["Faisal Mohammed","Aarav Reddy","Ayesha Khan","Rohan Sharma","Sneha Iyer","Mohammed Irfan",
 "Priya Nair","Karthik Varma","Fatima Zahra","Vikram Singh","Ananya Das","Sai Teja","Neha Gupta",
 "Imran Ali","Divya Menon","Arjun Patel","Zoya Siddiqui","Harsha Vardhan","Meera Joshi","Tarun Kumar"]
rolls = ["25WU0101161"] + ["25WU0101%03d" % n for n in
        [102,118,125,131,140,147,153,158,166,172,179,184,190,196,203,209,215,221,228]]
for i, (n, r) in enumerate(zip(names, rolls), 1):
    email = n.lower().replace(" ", ".") + "@student.woxsen.edu.in"
    out.append(f"INSERT INTO student(roll_no,name,email,department,year,semester) VALUES({q(r)},{q(n)},{q(email)},'CSE',2,3);")

fac = ["Dr. Ramesh Babu","Dr. Lakshmi Prasad","Prof. Anjali Deshmukh","Dr. Suresh Kulkarni","Prof. Nisha Verma"]
for n in fac:
    e = n.lower().replace("dr. ","").replace("prof. ","").replace(" ",".") + "@woxsen.edu.in"
    out.append(f"INSERT INTO faculty(name,email,department) VALUES({q(n)},{q(e)},'CSE');")

courses = [("CS201","Database Management Systems",4),("CS202","Operating Systems",4),
           ("CS203","Data Structures",4),("MA201","Discrete Mathematics",3),("CS204","Computer Networks",3)]
for c in courses:
    out.append(f"INSERT INTO course(course_code,course_name,credits) VALUES({q(c[0])},{q(c[1])},{c[2]});")

# (course_id, faculty_id, name, student ids)
S = list(range(1, 21))
sections = [(1,1,"A",S[:10]),(1,2,"B",S[10:]),(2,3,"A",S),(3,4,"A",S),(4,5,"A",S),(5,2,"A",S)]
for cid, fid, nm, studs in sections:
    out.append(f"INSERT INTO section(course_id,faculty_id,section_name,semester,academic_year) VALUES({cid},{fid},{q(nm)},3,'2026-27');")
for sid, (_, _, _, studs) in enumerate(sections, 1):
    for st in studs:
        out.append(f"INSERT INTO enrollment(student_id,section_id,enrolled_on) VALUES({st},{sid},'2026-08-03');")

# sessions: 2 per week for 8 weeks (15 kept), starting Mon 10 Aug 2026
slots = [("09:00","10:00"),("10:15","11:15"),("11:30","12:30"),("14:00","15:00"),("15:15","16:15"),("09:00","10:00")]
days = [(0,2),(1,3),(2,4),(0,3),(1,4),(0,4)]
sessions = {}   # session_id -> (section_id, date)
sid_counter = 0
start = dt.date(2026, 8, 10)
for sec_id, (cid, fid, nm, studs) in enumerate(sections, 1):
    n = 0
    for w in range(8):
        for k, d in enumerate(days[sec_id-1]):
            if n == 15: break
            date = start + dt.timedelta(weeks=w, days=d)
            lab = cid == 1 and k == 1
            st, en = slots[sec_id-1]
            if lab: en = "%02d:%s" % (int(st[:2])+2, st[3:]); 
            stype = "LAB" if lab else "LECTURE"
            sid_counter += 1; n += 1
            sessions[sid_counter] = (sec_id, date.isoformat(), en)
            out.append(f"INSERT INTO class_session(section_id,session_date,start_time,end_time,session_type) VALUES({sec_id},{q(date)},{q(st)},{q(en)},{q(stype)});")

# attendance
prop = {1: 0.90}
for s in range(2, 21):
    prop[s] = random.choice([0.66,0.72,0.80,0.86,0.88,0.90,0.92,0.94,0.96,0.98])
att = {}
for sid, (sec_id, date, en) in sessions.items():
    for st in sections[sec_id-1][3]:
        r = random.random()
        status = "ABSENT" if r > prop[st] else ("LATE" if random.random() < 0.06 else "PRESENT")
        att[(st, sid)] = status
        out.append(f"INSERT INTO attendance(student_id,session_id,status,marked_at) VALUES({st},{sid},{q(status)},{q(date+' '+en+':00')});")

# leave types
for n, d in [("Medical",15),("Casual",3),("Sports / Event Participation",7),("Family Emergency",5)]:
    out.append(f"INSERT INTO leave_type(type_name,max_days) VALUES({q(n)},{d});")

# leave applications: (student, type, from, to, reason, decision or None, remarks)
D = lambda s: dt.date.fromisoformat(s)
leaves = [
 (2,1,"2026-08-19","2026-08-21","Viral fever, doctor's certificate attached","APPROVED","Get well soon. Submit certificate to department office."),
 (3,4,"2026-09-02","2026-09-04","Family function out of town","APPROVED","Approved. Collect notes from classmates."),
 (5,3,"2026-09-09","2026-09-11","Inter-university quiz competition","APPROVED","Approved with event letter."),
 (7,1,"2026-08-24","2026-08-28","Dengue treatment","APPROVED","Approved on medical grounds."),
 (9,2,"2026-09-16","2026-09-16","Passport appointment","REJECTED","Casual leave not allowed during internal test week."),
 (11,1,"2026-09-21","2026-09-23","Dental surgery","APPROVED","Approved."),
 (13,4,"2026-09-14","2026-09-17","Sibling's wedding","REJECTED","Insufficient attendance in my course; resubmit with invitation."),
 (15,3,"2026-09-28","2026-10-01","Hackathon at IIT Hyderabad","APPROVED","Approved. Share the certificate afterwards."),
 (18,1,"2026-09-07","2026-09-09","Food poisoning","APPROVED","Approved."),
 (1,3,"2026-10-19","2026-10-21","Paper presentation at a student symposium",None,None),
 (4,2,"2026-10-20","2026-10-20","Visa document submission",None,None),
 (12,1,"2026-10-19","2026-10-23","Minor surgery, recovery period",None,None),
]
for i, (st, lt, f, t, why, dec, rem) in enumerate(leaves, 1):
    applied = (D(f) - dt.timedelta(days=2 if dec else 6)).isoformat()
    out.append(f"INSERT INTO leave_application(student_id,leave_type_id,from_date,to_date,reason,applied_on) VALUES({st},{lt},{q(f)},{q(t)},{q(why)},{q(applied)});")
    if dec:
        teachers = [sections[s-1][1] for s in range(1,7) if st in sections[s-1][3]]
        fid = random.choice(teachers)
        out.append(f"INSERT INTO approval(leave_id,faculty_id,decision,remarks,approved_at) VALUES({i},{fid},{q(dec)},{q(rem)},{q(applied+' 16:30:00')});")

# makeup sessions for sessions with at least 3 absences
cands = []
for sid, (sec_id, date, en) in sessions.items():
    ab = [st for st in sections[sec_id-1][3] if att[(st, sid)] == "ABSENT"]
    if len(ab) >= 3 and D(date) < dt.date(2026, 10, 1): cands.append((sid, sec_id, date, ab))
random.shuffle(cands)
used = set(); mk = 0
for sid, sec_id, date, ab in cands:
    if sec_id in used or mk == 5: continue
    used.add(sec_id); mk += 1
    md = (D(date) + dt.timedelta(days=8)).isoformat()
    out.append(f"INSERT INTO makeup_session(section_id,original_session_id,makeup_date,start_time,end_time) VALUES({sec_id},{sid},{q(md)},'16:30','17:30');")
    for st in ab:
        status = "PRESENT" if random.random() < 0.7 else "ABSENT"
        out.append(f"INSERT INTO makeup_attendance(makeup_id,student_id,status) VALUES({mk},{st},{q(status)});")

# shortage alerts generated from the view (same statement the application runs)
out.append("""INSERT INTO alert(student_id, section_id, alert_type, message)
SELECT v.student_id, v.section_id, 'SHORTAGE',
       'Attendance in ' || v.course_code || ' is ' || v.attendance_pct || '% (minimum ' || v.min_attendance_pct || '%).'
FROM v_shortage v
WHERE NOT EXISTS (SELECT 1 FROM alert a WHERE a.student_id = v.student_id AND a.section_id = v.section_id
                  AND a.alert_type = 'SHORTAGE' AND a.is_read = 0);""")
out.append("UPDATE alert SET is_read = 1 WHERE alert_type = 'LEAVE_STATUS' AND alert_id % 2 = 0;")
out.append("COMMIT;")
open("sample_data.sql", "w").write("\n".join(out) + "\n")
print(len(out), "statements")
