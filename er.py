import subprocess
ents = {
 "student":[("PK","student_id"),("","roll_no (U)"),("","name"),("","email (U)"),("","department"),("","year"),("","semester")],
 "faculty":[("PK","faculty_id"),("","name"),("","email (U)"),("","department")],
 "course":[("PK","course_id"),("","course_code (U)"),("","course_name"),("","credits"),("","min_attendance_pct")],
 "section":[("PK","section_id"),("FK","course_id"),("FK","faculty_id"),("","section_name"),("","semester"),("","academic_year")],
 "enrollment":[("PK","student_id (FK)"),("PK","section_id (FK)"),("","enrolled_on")],
 "class_session":[("PK","session_id"),("FK","section_id"),("","session_date"),("","start_time"),("","end_time"),("","session_type")],
 "attendance":[("PK","student_id (FK)"),("PK","session_id (FK)"),("","status"),("","marked_at")],
 "leave_type":[("PK","leave_type_id"),("","type_name (U)"),("","max_days")],
 "leave_application":[("PK","leave_id"),("FK","student_id"),("FK","leave_type_id"),("","from_date"),("","to_date"),("","reason"),("","status"),("","applied_on")],
 "approval":[("PK","approval_id"),("FK","leave_id (U)"),("FK","faculty_id"),("","decision"),("","remarks"),("","approved_at")],
 "makeup_session":[("PK","makeup_id"),("FK","section_id"),("FK","original_session_id"),("","makeup_date"),("","start_time"),("","end_time")],
 "makeup_attendance":[("PK","makeup_id (FK)"),("PK","student_id (FK)"),("","status")],
 "alert":[("PK","alert_id"),("FK","student_id"),("FK","section_id"),("","alert_type"),("","message"),("","created_at"),("","is_read")],
}
def node(n, rows):
    h = f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2" BGCOLOR="white"><TR><TD COLSPAN="2" BGCOLOR="#5a2d1c"><FONT COLOR="white" POINT-SIZE="13"><B>{n.upper()}</B></FONT></TD></TR>'
    for k, a in rows:
        col = "#b3261e" if k == "PK" else ("#1a5fb4" if k == "FK" else "black")
        h += f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="{col}"><B>{k or "&#160;"}</B></FONT></TD><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{"<U>"+a+"</U>" if k=="PK" else a}</FONT></TD></TR>'
    return f'{n} [shape=plain label={h}</TABLE>>];'
# (parent, child, label, parent_end, child_end)  tee=exactly one, teeodot=zero/one, crowodot=zero or many
edges = [("faculty","section","teaches","tee","crowodot"),("course","section","offered as","tee","crowodot"),
 ("section","enrollment","has","tee","crowodot"),("student","enrollment","enrols in","tee","crowodot"),
 ("section","class_session","schedules","tee","crowodot"),("class_session","attendance","records","tee","crowodot"),
 ("student","attendance","has","tee","crowodot"),("student","leave_application","submits","tee","crowodot"),
 ("leave_type","leave_application","classifies","tee","crowodot"),("leave_application","approval","decided by","tee","teeodot"),
 ("faculty","approval","gives","tee","crowodot"),("class_session","makeup_session","rescheduled by","tee","crowodot"),
 ("section","makeup_session","holds","tee","crowodot"),("makeup_session","makeup_attendance","records","tee","crowodot"),
 ("student","makeup_attendance","attends","tee","crowodot"),("student","alert","receives","tee","crowodot"),
 ("section","alert","about","teeodot","crowodot")]
g = 'digraph ER { graph [splines=true, nodesep=0.45, ranksep=1.1, dpi=200, pad=0.2, rankdir=LR]; edge [dir=both, fontsize=9, color="#7a5a45", fontcolor="#3b2a20"]; node [fontname="Helvetica"]; fontname="Helvetica";\n'
g += "\n".join(node(n, r) for n, r in ents.items()) + "\n"
for p, c, l, pe, ce in edges: g += f'{p} -> {c} [arrowtail={pe}, arrowhead={ce}, label="{l}"];\n'
open("er.dot", "w").write(g + "}")
subprocess.run(["dot", "-Tpng", "er.dot", "-o", "er_diagram.png"], check=True)
