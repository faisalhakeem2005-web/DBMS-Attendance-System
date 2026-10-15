# Student Attendance & Leave Approval System (DBMS PBL - Project 26)
Faisal Mohammed | 25WU0101161

## Run
    pip install flask
    python init_db.py      # builds attendance.db from schema.sql + sample_data.sql
    python app.py          # open http://127.0.0.1:5000
    python test_app.py     # 19 positive / negative test cases

## Files
schema.sql (tables, indexes, triggers, views) | sample_data.sql | queries.sql | build_sample.py | app.py | init_db.py | test_app.py | er_diagram.png
Login is a demo role selector (Student / Faculty / Administrator) without passwords.
