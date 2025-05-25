# config.py
import os

NEON_DB_PASSWORD = os.environ.get("NEON_DB_PASSWORD")

# Critical check: Ensure password was actually loaded
if NEON_DB_PASSWORD is None:
    import sys
    sys.exit("Database password not configured. Exiting.")

# Construct the connection string using the (hopefully) loaded password
PG_HOST = os.environ.get("PG_HOST", "ep-spring-voice-a1yre8if-pooler.ap-southeast-1.aws.neon.tech")
PG_DBNAME = os.environ.get("PG_DBNAME", "neondb")
PG_USER = os.environ.get("PG_USER", "neondb_owner")

NEON_CONNECTION_STRING = f"postgresql://{PG_USER}:{NEON_DB_PASSWORD}@{PG_HOST}/{PG_DBNAME}?sslmode=require"


# --- Portal Configuration ---
LOGIN_URL = "https://crce-students.contineo.in/parents/index.php?option=com_studentdashboard&controller=studentdashboard&task=dashboard"
FORM_ACTION_URL = LOGIN_URL

# --- Form Field Names ---
PRN_FIELD_NAME = "username"
DAY_FIELD_NAME = "dd"
MONTH_FIELD_NAME = "mm"
YEAR_FIELD_NAME = "yyyy"
PASSWORD_FIELD_NAME = "passwd"

# --- Subject Code Mapping ---
SUBJECT_CODE_TO_NAME_MAP = {
    "CSC601": "SPCC (System Programming & Compiler Construction)",
    "CSC602": "CSS (Cryptography and System Security)",
    "CSC603": "MC (Mobile Computing)",
    "CSC604": "AI (Artificial Intelligence)",
    "CSL601": "SPCC Lab",
    "CSL602": "CSS Lab",
    "CSL603": "MC Lab",
    "CSL604": "AI Lab",
    "CSL605": "Skill-Based Lab",
    "CSM601": "Mini Project 2B",
    "CSDL06013": "QA (Quantitative Analysis)"
}