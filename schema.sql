-- =====================================================================
-- Student Attendance & Leave Approval System  (DBMS PBL - Project 26)
-- DBMS: SQLite 3 (portable to MySQL / PostgreSQL with minor syntax changes)
-- Author: Faisal Mohammed | Roll No: 25WU0101161
-- =====================================================================
PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS v_makeup_report;  DROP VIEW IF EXISTS v_monthly_trend;
DROP VIEW IF EXISTS v_course_summary; DROP VIEW IF EXISTS v_leave_history;
DROP VIEW IF EXISTS v_shortage;       DROP VIEW IF EXISTS v_attendance_summary;
DROP TABLE IF EXISTS alert;           DROP TABLE IF EXISTS makeup_attendance;
DROP TABLE IF EXISTS makeup_session;  DROP TABLE IF EXISTS approval;
DROP TABLE IF EXISTS leave_application; DROP TABLE IF EXISTS leave_type;
DROP TABLE IF EXISTS attendance;      DROP TABLE IF EXISTS class_session;
DROP TABLE IF EXISTS enrollment;      DROP TABLE IF EXISTS section;
DROP TABLE IF EXISTS course;          DROP TABLE IF EXISTS faculty;
DROP TABLE IF EXISTS student;

-- ---------------------------- Core entities ---------------------------
CREATE TABLE student (
    student_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no     TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    department  TEXT    NOT NULL,
    year        INTEGER NOT NULL CHECK (year BETWEEN 1 AND 4),
    semester    INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8)
);

CREATE TABLE faculty (
    faculty_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    department  TEXT NOT NULL
);

CREATE TABLE course (
    course_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code        TEXT    NOT NULL UNIQUE,
    course_name        TEXT    NOT NULL,
    credits            INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 6),
    min_attendance_pct REAL    NOT NULL DEFAULT 75
                       CHECK (min_attendance_pct BETWEEN 0 AND 100)
);

CREATE TABLE section (
    section_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES course(course_id)   ON UPDATE CASCADE ON DELETE RESTRICT,
    faculty_id    INTEGER NOT NULL REFERENCES faculty(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    section_name  TEXT    NOT NULL,
    semester      INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    academic_year TEXT    NOT NULL DEFAULT '2026-27',
    UNIQUE (course_id, section_name, semester, academic_year)
);

CREATE TABLE enrollment (
    student_id  INTEGER NOT NULL REFERENCES student(student_id) ON UPDATE CASCADE ON DELETE CASCADE,
    section_id  INTEGER NOT NULL REFERENCES section(section_id) ON UPDATE CASCADE ON DELETE CASCADE,
    enrolled_on TEXT    NOT NULL DEFAULT (date('now')),
    PRIMARY KEY (student_id, section_id)
);

-- ------------------------ Sessions and attendance ---------------------
CREATE TABLE class_session (
    session_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id   INTEGER NOT NULL REFERENCES section(section_id) ON UPDATE CASCADE ON DELETE CASCADE,
    session_date TEXT    NOT NULL CHECK (date(session_date) IS NOT NULL),
    start_time   TEXT    NOT NULL,
    end_time     TEXT    NOT NULL,
    session_type TEXT    NOT NULL DEFAULT 'LECTURE'
                 CHECK (session_type IN ('LECTURE','LAB','TUTORIAL')),
    CHECK (end_time > start_time),
    UNIQUE (section_id, session_date, start_time)
);

CREATE TABLE attendance (
    student_id INTEGER NOT NULL REFERENCES student(student_id)       ON UPDATE CASCADE ON DELETE RESTRICT,
    session_id INTEGER NOT NULL REFERENCES class_session(session_id) ON UPDATE CASCADE ON DELETE CASCADE,
    status     TEXT    NOT NULL CHECK (status IN ('PRESENT','ABSENT','LATE','EXCUSED')),
    marked_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (student_id, session_id)            -- one record per student per session
);

-- --------------------------- Leave workflow ---------------------------
CREATE TABLE leave_type (
    leave_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name     TEXT    NOT NULL UNIQUE,
    max_days      INTEGER NOT NULL CHECK (max_days > 0)
);

CREATE TABLE leave_application (
    leave_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES student(student_id)         ON UPDATE CASCADE ON DELETE CASCADE,
    leave_type_id INTEGER NOT NULL REFERENCES leave_type(leave_type_id)   ON UPDATE CASCADE ON DELETE RESTRICT,
    from_date     TEXT    NOT NULL CHECK (date(from_date) IS NOT NULL),
    to_date       TEXT    NOT NULL CHECK (date(to_date)   IS NOT NULL),
    reason        TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    applied_on    TEXT    NOT NULL DEFAULT (date('now')),
    CHECK (from_date <= to_date)
);

CREATE TABLE approval (
    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    leave_id    INTEGER NOT NULL UNIQUE REFERENCES leave_application(leave_id) ON UPDATE CASCADE ON DELETE CASCADE,
    faculty_id  INTEGER NOT NULL REFERENCES faculty(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    decision    TEXT    NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
    remarks     TEXT,
    approved_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------ Makeup sessions & alerts --------------------
CREATE TABLE makeup_session (
    makeup_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id          INTEGER NOT NULL REFERENCES section(section_id)           ON UPDATE CASCADE ON DELETE CASCADE,
    original_session_id INTEGER NOT NULL REFERENCES class_session(session_id)     ON UPDATE CASCADE ON DELETE CASCADE,
    makeup_date         TEXT    NOT NULL CHECK (date(makeup_date) IS NOT NULL),
    start_time          TEXT    NOT NULL,
    end_time            TEXT    NOT NULL,
    CHECK (end_time > start_time),
    UNIQUE (original_session_id, makeup_date)
);

CREATE TABLE makeup_attendance (
    makeup_id  INTEGER NOT NULL REFERENCES makeup_session(makeup_id) ON UPDATE CASCADE ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student(student_id)       ON UPDATE CASCADE ON DELETE CASCADE,
    status     TEXT    NOT NULL CHECK (status IN ('PRESENT','ABSENT')),
    PRIMARY KEY (makeup_id, student_id)
);

CREATE TABLE alert (
    alert_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES student(student_id) ON UPDATE CASCADE ON DELETE CASCADE,
    section_id INTEGER REFERENCES section(section_id)          ON UPDATE CASCADE ON DELETE SET NULL,
    alert_type TEXT    NOT NULL CHECK (alert_type IN ('SHORTAGE','LEAVE_STATUS','MAKEUP')),
    message    TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    is_read    INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0,1))
);

-- ------------------------------- Indexes ------------------------------
CREATE INDEX idx_session_section_date ON class_session(section_id, session_date);
CREATE INDEX idx_attendance_session   ON attendance(session_id);
CREATE INDEX idx_enrollment_section   ON enrollment(section_id);
CREATE INDEX idx_leave_student_status ON leave_application(student_id, status);
CREATE INDEX idx_alert_student_unread ON alert(student_id, is_read);
CREATE INDEX idx_section_faculty      ON section(faculty_id);

-- ------------------------------- Triggers -----------------------------
-- R1: only enrolled students can be marked in a session
CREATE TRIGGER trg_attendance_enrolled BEFORE INSERT ON attendance
BEGIN
  SELECT RAISE(ABORT, 'Student is not enrolled in the section of this session')
  WHERE NOT EXISTS (SELECT 1 FROM class_session cs
                    JOIN enrollment e ON e.section_id = cs.section_id
                    WHERE cs.session_id = NEW.session_id AND e.student_id = NEW.student_id);
END;

-- R2: an ABSENT mark that falls inside an approved leave becomes EXCUSED
CREATE TRIGGER trg_attendance_excuse AFTER INSERT ON attendance
WHEN NEW.status = 'ABSENT'
BEGIN
  UPDATE attendance SET status = 'EXCUSED'
  WHERE student_id = NEW.student_id AND session_id = NEW.session_id
    AND EXISTS (SELECT 1 FROM leave_application l
                JOIN class_session cs ON cs.session_id = NEW.session_id
                WHERE l.student_id = NEW.student_id AND l.status = 'APPROVED'
                  AND cs.session_date BETWEEN l.from_date AND l.to_date);
END;

-- R3: leave must not exceed the maximum days of its leave type
CREATE TRIGGER trg_leave_duration BEFORE INSERT ON leave_application
BEGIN
  SELECT RAISE(ABORT, 'Leave duration exceeds the maximum days allowed for this leave type')
  WHERE (julianday(NEW.to_date) - julianday(NEW.from_date) + 1) >
        (SELECT max_days FROM leave_type WHERE leave_type_id = NEW.leave_type_id);
END;

-- R4: a student cannot hold two overlapping pending/approved leaves
CREATE TRIGGER trg_leave_overlap BEFORE INSERT ON leave_application
BEGIN
  SELECT RAISE(ABORT, 'Leave dates overlap with another pending/approved application')
  WHERE EXISTS (SELECT 1 FROM leave_application l
                WHERE l.student_id = NEW.student_id AND l.status IN ('PENDING','APPROVED')
                  AND l.from_date <= NEW.to_date AND l.to_date >= NEW.from_date);
END;

-- R5: only a faculty member who teaches the student may decide the leave
CREATE TRIGGER trg_approval_authorized BEFORE INSERT ON approval
BEGIN
  SELECT RAISE(ABORT, 'Faculty is not assigned to any section of this student')
  WHERE NOT EXISTS (SELECT 1 FROM leave_application l
                    JOIN enrollment e ON e.student_id = l.student_id
                    JOIN section s    ON s.section_id = e.section_id
                    WHERE l.leave_id = NEW.leave_id AND s.faculty_id = NEW.faculty_id);
END;

-- R6: one transaction: update status, excuse absences, notify the student
CREATE TRIGGER trg_approval_apply AFTER INSERT ON approval
BEGIN
  UPDATE leave_application SET status = NEW.decision WHERE leave_id = NEW.leave_id;
  UPDATE attendance SET status = 'EXCUSED'
  WHERE NEW.decision = 'APPROVED' AND status = 'ABSENT'
    AND student_id = (SELECT student_id FROM leave_application WHERE leave_id = NEW.leave_id)
    AND session_id IN (SELECT cs.session_id FROM class_session cs
                       JOIN leave_application l ON l.leave_id = NEW.leave_id
                       WHERE cs.session_date BETWEEN l.from_date AND l.to_date);
  INSERT INTO alert(student_id, alert_type, message)
  SELECT student_id, 'LEAVE_STATUS',
         'Your leave application #' || leave_id || ' was ' || lower(NEW.decision) || '.'
  FROM leave_application WHERE leave_id = NEW.leave_id;
END;

-- R7: makeup session must belong to the same section and not precede the original
CREATE TRIGGER trg_makeup_valid BEFORE INSERT ON makeup_session
BEGIN
  SELECT RAISE(ABORT, 'Original session does not belong to this section')
  WHERE NOT EXISTS (SELECT 1 FROM class_session
                    WHERE session_id = NEW.original_session_id AND section_id = NEW.section_id);
  SELECT RAISE(ABORT, 'Makeup date cannot be earlier than the original session date')
  WHERE NEW.makeup_date < (SELECT session_date FROM class_session
                           WHERE session_id = NEW.original_session_id);
END;

-- R8: only enrolled students can attend a makeup session
CREATE TRIGGER trg_makeup_att_enrolled BEFORE INSERT ON makeup_attendance
BEGIN
  SELECT RAISE(ABORT, 'Student is not enrolled in the section of this makeup session')
  WHERE NOT EXISTS (SELECT 1 FROM makeup_session m
                    JOIN enrollment e ON e.section_id = m.section_id
                    WHERE m.makeup_id = NEW.makeup_id AND e.student_id = NEW.student_id);
END;

-- -------------------------------- Views -------------------------------
-- Attendance % = (PRESENT + LATE) / (all marked sessions except EXCUSED) x 100
CREATE VIEW v_attendance_summary AS
SELECT e.student_id, st.roll_no, st.name AS student_name,
       sec.section_id, c.course_code, c.course_name, sec.section_name,
       COUNT(CASE WHEN a.status <> 'EXCUSED' THEN 1 END)               AS counted_sessions,
       SUM(CASE WHEN a.status IN ('PRESENT','LATE') THEN 1 ELSE 0 END) AS attended,
       SUM(CASE WHEN a.status = 'EXCUSED' THEN 1 ELSE 0 END)           AS excused,
       CASE WHEN COUNT(CASE WHEN a.status <> 'EXCUSED' THEN 1 END) = 0 THEN NULL
            ELSE ROUND(100.0 * SUM(CASE WHEN a.status IN ('PRESENT','LATE') THEN 1 ELSE 0 END)
                       / COUNT(CASE WHEN a.status <> 'EXCUSED' THEN 1 END), 2) END AS attendance_pct,
       c.min_attendance_pct
FROM enrollment e
JOIN student st ON st.student_id = e.student_id
JOIN section sec ON sec.section_id = e.section_id
JOIN course c ON c.course_id = sec.course_id
JOIN class_session cs ON cs.section_id = sec.section_id
LEFT JOIN attendance a ON a.session_id = cs.session_id AND a.student_id = e.student_id
GROUP BY e.student_id, sec.section_id;

CREATE VIEW v_shortage AS
SELECT * FROM v_attendance_summary
WHERE attendance_pct IS NOT NULL AND attendance_pct < min_attendance_pct;

CREATE VIEW v_leave_history AS
SELECT l.leave_id, st.roll_no, st.name AS student_name, lt.type_name, l.from_date, l.to_date,
       CAST(julianday(l.to_date) - julianday(l.from_date) + 1 AS INTEGER) AS days,
       l.reason, l.status, f.name AS decided_by, ap.remarks, ap.approved_at
FROM leave_application l
JOIN student st ON st.student_id = l.student_id
JOIN leave_type lt ON lt.leave_type_id = l.leave_type_id
LEFT JOIN approval ap ON ap.leave_id = l.leave_id
LEFT JOIN faculty f ON f.faculty_id = ap.faculty_id;

CREATE VIEW v_course_summary AS
SELECT sec.section_id, c.course_code, c.course_name, sec.section_name, f.name AS faculty_name,
       (SELECT COUNT(*) FROM class_session x WHERE x.section_id = sec.section_id) AS sessions_held,
       COUNT(*)                          AS students,
       ROUND(AVG(v.attendance_pct), 2)   AS avg_attendance_pct,
       SUM(CASE WHEN v.attendance_pct < v.min_attendance_pct THEN 1 ELSE 0 END) AS students_in_shortage
FROM v_attendance_summary v
JOIN section sec ON sec.section_id = v.section_id
JOIN course c ON c.course_id = sec.course_id
JOIN faculty f ON f.faculty_id = sec.faculty_id
GROUP BY sec.section_id;

CREATE VIEW v_monthly_trend AS
SELECT c.course_code, strftime('%Y-%m', cs.session_date) AS month,
       COUNT(CASE WHEN a.status <> 'EXCUSED' THEN 1 END) AS marked,
       SUM(CASE WHEN a.status IN ('PRESENT','LATE') THEN 1 ELSE 0 END) AS attended,
       ROUND(100.0 * SUM(CASE WHEN a.status IN ('PRESENT','LATE') THEN 1 ELSE 0 END)
             / NULLIF(COUNT(CASE WHEN a.status <> 'EXCUSED' THEN 1 END), 0), 2) AS attendance_pct
FROM attendance a
JOIN class_session cs ON cs.session_id = a.session_id
JOIN section sec ON sec.section_id = cs.section_id
JOIN course c ON c.course_id = sec.course_id
GROUP BY c.course_code, strftime('%Y-%m', cs.session_date);

CREATE VIEW v_makeup_report AS
SELECT m.makeup_id, c.course_code, sec.section_name, o.session_date AS original_date,
       m.makeup_date, m.start_time,
       (SELECT COUNT(*) FROM makeup_attendance x WHERE x.makeup_id = m.makeup_id AND x.status = 'PRESENT') AS present_count,
       (SELECT COUNT(*) FROM makeup_attendance x WHERE x.makeup_id = m.makeup_id) AS marked_count
FROM makeup_session m
JOIN class_session o ON o.session_id = m.original_session_id
JOIN section sec ON sec.section_id = m.section_id
JOIN course c ON c.course_id = sec.course_id;
