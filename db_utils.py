# db_utils.py
import psycopg2
import config # Import your config file to get NEON_CONNECTION_STRING

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
    """Creates the users table in PostgreSQL if it doesn't exist."""
    conn = get_db_connection()
    if not conn:
        print("Skipping table creation due to connection failure.")
        return

    cursor = conn.cursor()
    try:
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
        conn.commit()
        print(f"Table 'users' checked/created successfully in {DB_NAME_FOR_MESSAGES}.")
    except psycopg2.Error as e:
        print(f"Error creating table in {DB_NAME_FOR_MESSAGES}: {e}")
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
        print(f"Error adding user '{full_name}': PRN '{prn}' or First Name '{first_name}' might already exist.")
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
    """Retrieves user details from the PostgreSQL database by first name (case-insensitive)."""
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    sql = '''
        SELECT full_name, prn, dob_day, dob_month, dob_year
        FROM users
        WHERE first_name = %s
    '''
    try:
        cursor.execute(sql, (first_name_query.lower().strip(),))
        user_data = cursor.fetchone()
        if user_data:
            return {
                "full_name": user_data[0],
                "prn": user_data[1],
                "dob_day": user_data[2],
                "dob_month": user_data[3],
                "dob_year": user_data[4]
            }
        return None
    except psycopg2.Error as e:
        print(f"Error fetching user from {DB_NAME_FOR_MESSAGES}: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()