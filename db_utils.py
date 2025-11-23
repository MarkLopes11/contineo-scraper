# db_utils.py
import psycopg2
import config 
from datetime import datetime
import json

DB_NAME_FOR_MESSAGES = "PostgreSQL (Neon.tech)"

def get_db_connection():
    try:
        conn = psycopg2.connect(config.NEON_CONNECTION_STRING)
        return conn
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

def create_db_and_table_pg():
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        # 1. Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                first_name TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                prn TEXT NOT NULL UNIQUE,
                dob_day TEXT NOT NULL,
                dob_month TEXT NOT NULL,
                dob_year TEXT NOT NULL
            )
        ''')

        # 2. CIE Marks Table (Added SEMESTER)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cie_marks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                semester INTEGER NOT NULL, -- NEW
                subject_code TEXT NOT NULL,
                exam_type TEXT NOT NULL,
                marks NUMERIC(5, 2),
                max_marks NUMERIC(5, 2),
                scraped_at TIMESTAMP WITH TIME ZONE NOT NULL,
                UNIQUE (user_id, subject_code, exam_type) 
            )
        ''')

        # 3. Attendance Table (New Dedicated Table)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_records (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                semester INTEGER NOT NULL,
                subject_code TEXT NOT NULL,
                attended INTEGER,
                conducted INTEGER,
                percentage NUMERIC(5, 2),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                UNIQUE (user_id, semester, subject_code)
            )
        ''')

        # 4. Student Performance (SGPI)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_performance (
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                semester INTEGER NOT NULL,
                sgpi FLOAT,
                grade_details JSONB,
                updated_at TIMESTAMPTZ,
                PRIMARY KEY (user_id, semester)
            );
        """)
        conn.commit()
        print("Tables checked/created successfully.")
    except psycopg2.Error as e:
        print(f"Error creating tables: {e}")
    finally:
        cursor.close()
        conn.close()

def add_user_to_db_pg(first_name, full_name, prn, dob_day, dob_month, dob_year):
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (first_name, full_name, prn, dob_day, dob_month, dob_year)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (first_name.lower().strip(), full_name.strip(), prn.strip(), dob_day, dob_month, dob_year))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_from_db_pg(first_name_query):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, full_name, prn, dob_day, dob_month, dob_year
            FROM users WHERE first_name = %s
        ''', (first_name_query.lower().strip(),))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0], "full_name": row[1], "prn": row[2],
                "dob_day": row[3], "dob_month": row[4], "dob_year": row[5]
            }
        return None
    finally:
        cursor.close()
        conn.close()

def update_student_marks_in_db_pg(user_id, semester, cie_marks_data, scraped_timestamp):
    """Saves Marks into the DB linked to a Semester."""
    if not cie_marks_data or not semester: return False
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        records = []
        for sub, exams in cie_marks_data.items():
            for exam, val in exams.items():
                obt = val.get('obtained') if isinstance(val, dict) else val
                mx = val.get('max', 0) if isinstance(val, dict) else 0
                if isinstance(obt, (int, float)):
                    records.append((user_id, semester, sub, exam, obt, mx, scraped_timestamp))
        
        if records:
            cursor.executemany("""
                INSERT INTO cie_marks (user_id, semester, subject_code, exam_type, marks, max_marks, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, subject_code, exam_type) 
                DO UPDATE SET marks = EXCLUDED.marks, max_marks = EXCLUDED.max_marks, scraped_at = EXCLUDED.scraped_at, semester = EXCLUDED.semester;
            """, records)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating marks: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def update_attendance_in_db_pg(user_id, semester, attendance_data):
    """Saves Attendance to the DB linked to a Semester."""
    if not attendance_data or not semester: return False
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        records = []
        # Input format: {'CSC701': {'attended': 10, 'conducted': 12}}
        for sub, details in attendance_data.items():
            att = details.get('attended', 0)
            cond = details.get('conducted', 0)
            perc = (att / cond * 100) if cond > 0 else 0
            records.append((user_id, semester, sub, att, cond, perc, datetime.now()))

        if records:
            cursor.executemany("""
                INSERT INTO attendance_records (user_id, semester, subject_code, attended, conducted, percentage, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, semester, subject_code)
                DO UPDATE SET attended = EXCLUDED.attended, conducted = EXCLUDED.conducted, percentage = EXCLUDED.percentage, updated_at = NOW();
            """, records)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating attendance: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def save_student_sgpi_pg(user_id, semester, sgpi, grade_details):
    """Saves SGPI."""
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        json_grades = json.dumps(grade_details)
        cursor.execute("""
            INSERT INTO student_performance (user_id, semester, sgpi, grade_details, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, semester) 
            DO UPDATE SET 
                sgpi = EXCLUDED.sgpi,
                grade_details = EXCLUDED.grade_details,
                updated_at = NOW();
        """, (user_id, semester, sgpi, json_grades))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving SGPI: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_student_data_from_db(user_id):
    """
    Retrieves ALL data for a user, organized by semester.
    Returns: { 7: { 'cie': ..., 'att': ..., 'sgpi': ... }, 8: { ... } }
    """
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    
    full_data = {} # Key = Semester
    
    try:
        # 1. Fetch Marks
        cursor.execute("SELECT semester, subject_code, exam_type, marks, max_marks, scraped_at FROM cie_marks WHERE user_id = %s", (user_id,))
        mark_rows = cursor.fetchall()
        
        last_scraped = None

        for r in mark_rows:
            sem, sub, exam, obt, mx, ts = r
            last_scraped = ts # Just take the last one
            
            if sem not in full_data: full_data[sem] = {'cie': {}, 'att': {}, 'sgpi': None}
            if sub not in full_data[sem]['cie']: full_data[sem]['cie'][sub] = {}
            
            full_data[sem]['cie'][sub][exam] = {'obtained': float(obt), 'max': float(mx)}

        # 2. Fetch Attendance
        cursor.execute("SELECT semester, subject_code, attended, conducted FROM attendance_records WHERE user_id = %s", (user_id,))
        att_rows = cursor.fetchall()
        for r in att_rows:
            sem, sub, att, cond = r
            if sem not in full_data: full_data[sem] = {'cie': {}, 'att': {}, 'sgpi': None}
            full_data[sem]['att'][sub] = {'attended': att, 'conducted': cond}

        # 3. Fetch SGPI
        cursor.execute("SELECT semester, sgpi FROM student_performance WHERE user_id = %s", (user_id,))
        sgpi_rows = cursor.fetchall()
        for r in sgpi_rows:
            sem, val = r
            if sem in full_data:
                full_data[sem]['sgpi'] = val

        if not full_data: return None

        # Find the latest semester to show by default
        latest_sem = max(full_data.keys()) if full_data else None

        return {
            "semesters_data": full_data,
            "latest_sem": latest_sem,
            "scraped_at": last_scraped
        }

    except Exception as e:
        print(f"Error fetching DB: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_semester_leaderboard_pg(semester, limit=5):
    """Gets top students for a specific semester."""
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT u.full_name, sp.sgpi
            FROM student_performance sp
            JOIN users u ON sp.user_id = u.id
            WHERE sp.semester = %s
            ORDER BY sp.sgpi DESC
            LIMIT %s
        """, (semester, limit))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        return []
    finally:
        cursor.close()
        conn.close()