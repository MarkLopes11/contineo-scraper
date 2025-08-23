# db_utils.py
import psycopg2
import config # Import your config file to get NEON_CONNECTION_STRING
from datetime import datetime
import pytz

DB_NAME_FOR_MESSAGES = "PostgreSQL (Neon.tech)" # For user-friendly messages

def get_db_connection():
    """Establishes a connection to the PostgreSQL database using a connection string."""
    try:
        conn = psycopg2.connect(config.NEON_CONNECTION_STRING)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to {DB_NAME_FOR_MESSAGES} database: {e}")
        print("Please check your internet connection and database credentials/status.")
        return None
    except Exception as e_gen:
        print(f"A general error occurred during database connection: {e_gen}")
        return None

def create_db_and_table_pg():
    """Creates the users and cie_marks tables in PostgreSQL if they don't exist."""
    conn = get_db_connection()
    if not conn:
        print("Skipping table creation due to connection failure.")
        return

    cursor = conn.cursor()
    try:
        # Create users table (no changes here)
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
        print("Table 'users' checked/created successfully.")

        # --- NEW: Create cie_marks table ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cie_marks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                subject_code TEXT NOT NULL,
                exam_type TEXT NOT NULL,
                marks NUMERIC(5, 2),
                scraped_at TIMESTAMP WITH TIME ZONE NOT NULL,
                UNIQUE (user_id, subject_code, exam_type)
            )
        ''')
        print("Table 'cie_marks' for leaderboards checked/created successfully.")

        conn.commit()
    except psycopg2.Error as e:
        print(f"Error creating tables in {DB_NAME_FOR_MESSAGES}: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def add_user_to_db_pg(first_name, full_name, prn, dob_day, dob_month, dob_year):
    """Adds a new user to the PostgreSQL database."""
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    sql = '''
        INSERT INTO users (first_name, full_name, prn, dob_day, dob_month, dob_year)
        VALUES (%s, %s, %s, %s, %s, %s)
    '''
    try:
        cursor.execute(sql, (first_name.lower().strip(), full_name.strip(), prn.strip(), 
                              dob_day.strip(), dob_month.strip(), dob_year.strip()))
        conn.commit()
        print(f"User '{full_name}' added to the {DB_NAME_FOR_MESSAGES} database.")
        return True
    except psycopg2.IntegrityError: 
        print(f"Error adding user '{full_name}': PRN '{prn}' or Username '{first_name}' might already exist.")
        conn.rollback() 
        return False
    except psycopg2.Error as e:
        print(f"General error adding user to {DB_NAME_FOR_MESSAGES}: {e}")
        conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_user_from_db_pg(first_name_query):
    """
    Retrieves user details from the PostgreSQL database by first name (case-insensitive).
    MODIFIED: Now also returns the user's primary key 'id'.
    """
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    sql = '''
        SELECT id, full_name, prn, dob_day, dob_month, dob_year
        FROM users
        WHERE first_name = %s
    '''
    try:
        cursor.execute(sql, (first_name_query.lower().strip(),))
        user_data = cursor.fetchone()
        if user_data:
            return {
                "id": user_data[0], # <-- ADDED
                "full_name": user_data[1],
                "prn": user_data[2],
                "dob_day": user_data[3],
                "dob_month": user_data[4],
                "dob_year": user_data[5]
            }
        return None
    except psycopg2.Error as e:
        print(f"Error fetching user from {DB_NAME_FOR_MESSAGES}: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- NEW FUNCTION ---
def update_student_marks_in_db_pg(user_id, cie_marks_data, scraped_timestamp):
    """
    Deletes old marks and inserts the latest scraped marks for a user.
    This is an 'upsert' (update/insert) operation.
    """
    if not cie_marks_data:
        print("No CIE marks data provided to update in DB.")
        return False

    conn = get_db_connection()
    if not conn: return False
    
    cursor = conn.cursor()
    try:
        # Start a transaction
        # Step 1: Delete all existing marks for this user to avoid stale data
        delete_sql = "DELETE FROM cie_marks WHERE user_id = %s"
        cursor.execute(delete_sql, (user_id,))
        
        # Step 2: Prepare and insert the new data
        insert_sql = """
            INSERT INTO cie_marks (user_id, subject_code, exam_type, marks, scraped_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        records_to_insert = []
        for subject_code, marks_dict in cie_marks_data.items():
            for exam_type, mark_value in marks_dict.items():
                # Only insert if mark is a valid number
                if isinstance(mark_value, (int, float)):
                    records_to_insert.append((user_id, subject_code, exam_type, mark_value, scraped_timestamp))

        if records_to_insert:
            cursor.executemany(insert_sql, records_to_insert)
            print(f"Successfully updated {len(records_to_insert)} mark entries for user_id {user_id}.")
        
        conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"Database error during marks update for user_id {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- NEW FUNCTION ---
def get_subject_leaderboard_pg(subject_code, exam_type, limit=3):
    """
    Retrieves the top students for a given subject and exam type.
    """
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor()
    
    sql = """
        SELECT u.full_name, m.marks
        FROM cie_marks m
        JOIN users u ON m.user_id = u.id
        WHERE m.subject_code = %s AND m.exam_type = %s AND m.marks IS NOT NULL
        ORDER BY m.marks DESC
        LIMIT %s
    """
    try:
        cursor.execute(sql, (subject_code, exam_type, limit))
        leaderboard_data = cursor.fetchall()
        return leaderboard_data # Returns a list of tuples, e.g., [('Student A', 28.50), ('Student B', 27.00)]
    except psycopg2.Error as e:
        print(f"Error fetching leaderboard for {subject_code} - {exam_type}: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_all_users_from_db_pg():
    """Retrieves all registered users from the database for the batch update script."""
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor()
    sql = '''
        SELECT id, full_name, prn, dob_day, dob_month, dob_year
        FROM users
        ORDER BY first_name
    '''
    try:
        cursor.execute(sql)
        all_users_data = cursor.fetchall()
        users_list = []
        for user_data in all_users_data:
            users_list.append({
                "id": user_data[0],
                "full_name": user_data[1],
                "prn": user_data[2],
                "dob_day": user_data[3],
                "dob_month": user_data[4],
                "dob_year": user_data[5]
            })
        return users_list
    except psycopg2.Error as e:
        print(f"Error fetching all users from {DB_NAME_FOR_MESSAGES}: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()