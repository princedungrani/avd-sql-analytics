
import os, mysql.connector as mysql

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "avd_user"),
    "password": os.getenv("DB_PASS", "change_me"),
    "database": os.getenv("DB_NAME", "avd_ops"),
}

def get_conn():
    return mysql.connect(**DB)

def rollup_peak_concurrency():
    q = """
    SELECT DATE(logon_time) as d, HOUR(logon_time) as h, COUNT(*) as concurrent
    FROM sessions
    GROUP BY d, h
    ORDER BY d DESC, h DESC;
    """
    with get_conn() as cx, cx.cursor(dictionary=True) as cur:
        cur.execute(q)
        return cur.fetchall()

if __name__ == "__main__":
    rows = rollup_peak_concurrency()
    for r in rows[:10]:
        print(r)
