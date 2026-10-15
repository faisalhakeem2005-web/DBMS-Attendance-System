"""Creates attendance.db from schema.sql + sample_data.sql.  Usage: python init_db.py"""
import sqlite3, os
here = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(here, "attendance.db")
if os.path.exists(path): os.remove(path)
con = sqlite3.connect(path)
for f in ("schema.sql", "sample_data.sql"):
    con.executescript(open(os.path.join(here, f), encoding="utf-8").read())
con.commit()
for t in ["student","faculty","course","section","enrollment","class_session","attendance","leave_type",
          "leave_application","approval","makeup_session","makeup_attendance","alert"]:
    print(f"{t:18}", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
con.close()
