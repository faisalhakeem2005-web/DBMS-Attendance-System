-- =====================================================================
-- Representative reports (joins, aggregation, subqueries, views)
-- =====================================================================

-- Q1. Attendance percentage per student per course (view + join)
SELECT roll_no, student_name, course_code, counted_sessions, attended, excused, attendance_pct
FROM v_attendance_summary
ORDER BY roll_no, course_code;

-- Q2. Attendance shortage list (students below the course minimum)
SELECT roll_no, student_name, course_code, attendance_pct, min_attendance_pct,
       ROUND(min_attendance_pct - attendance_pct, 2) AS shortfall
FROM v_shortage
ORDER BY shortfall DESC;

-- Q3. Leave history with decision details (3-table join, outer joins)
SELECT * FROM v_leave_history ORDER BY from_date;

-- Q4. Course summary (aggregate per section)
SELECT course_code, section_name, faculty_name, sessions_held, students,
       avg_attendance_pct, students_in_shortage
FROM v_course_summary;

-- Q5. Monthly attendance trend per course
SELECT course_code, month, marked, attended, attendance_pct FROM v_monthly_trend ORDER BY course_code, month;

-- Q6. Makeup attendance report
SELECT * FROM v_makeup_report;

-- Q7. Nested query: students whose overall attendance is below the institute average
SELECT st.roll_no, st.name, ROUND(AVG(v.attendance_pct), 2) AS overall_pct
FROM v_attendance_summary v JOIN student st ON st.student_id = v.student_id
GROUP BY st.student_id
HAVING AVG(v.attendance_pct) < (SELECT AVG(attendance_pct) FROM v_attendance_summary)
ORDER BY overall_pct;

-- Q8. Nested query: pending leave applications of students already in shortage
SELECT l.leave_id, l.student_name, l.from_date, l.to_date
FROM v_leave_history l
WHERE l.status = 'PENDING'
  AND l.roll_no IN (SELECT roll_no FROM v_shortage);

-- Q9. Faculty workload: sections, sessions held and pending leave decisions
SELECT f.name,
       COUNT(DISTINCT s.section_id) AS sections,
       (SELECT COUNT(*) FROM class_session cs JOIN section x ON x.section_id = cs.section_id
        WHERE x.faculty_id = f.faculty_id) AS sessions_held
FROM faculty f LEFT JOIN section s ON s.faculty_id = f.faculty_id
GROUP BY f.faculty_id;

-- Q10. Sections where more than 40% of the students are in shortage
SELECT course_code, section_name, students_in_shortage, students
FROM v_course_summary
WHERE 100.0 * students_in_shortage / students > 40;
