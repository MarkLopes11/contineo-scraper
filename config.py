# config.py
import os

NEON_DB_PASSWORD = os.environ.get("NEON_DB_PASSWORD")

# Critical check: Ensure password was actually loaded
if NEON_DB_PASSWORD is None:
    import sys
    sys.exit("Database password not configured. Exiting.")

# Construct the connection string using the (hopefully) loaded password
PG_HOST = os.environ.get("NEON_DB_URI", "ep-spring-voice-a1yre8if-pooler.ap-southeast-1.aws.neon.tech")
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
    "CSDL06013": "QA (Quantitative Analysis)",
    "CSC702" : "BDA",
    "CSC701" : "ML",
    "CSDC7013" : "NLP",
    "CSDC7023" : "IR",
    "CSL701" : "ML LAB",
    "CSL702" : "BDA LAB",
    "CSDL7013" : "NLP LAB",
    "CSDL7023" : "IR LAB",
    "CSDC7022" : "Blockchain",
    "CSDL7022" : "Blockchain Lab",
    "MEC702" : "Logistics & Supply Chain Management",
    "MEC701" : "Design of Mechanical system",
    "MEL701" : "Design of Mechanical system lab",
    "MEL702" : "Maintainence Engineering",
    "MEL703" : "Industrial Skills",
    "MEDLO7032" : "Renewable Energy System",
    "MEDLO7041" : "Machinery Diagnostics",
    "ILO7017" : "Disaster Management and Mitigation Measures",
    "CSP701" : "Major Project",
    "25PCC13CE11" : "Computer Network",
    "25PCC13CE12" : "TCS",
    "25PCC13CE13" : "OS",
    "25PCC13CE14" : "DWM",
    "25PEC13CE16" : "HMI",
    "25MDM42" : "Emotional And Spiritual Intelligence",
    "25PECL13CE14" : "Innovative Product Development Lab Phase 1",
    "25OE13CE43" : "SUpply Chain Management",
    "25BSC12CE05" : "DSGT",
    "25PCC12CE05" : "COA",
    "25PCC12CE06" : "Data Structures",
    "25PCC12CE07" : "Object Oriented Programming",
    "25VEC12CE01" : "Human Values And Professional Ethics",
    "25AEC12CE021" : "Sanskrit",
    "25MDMBM1" : "Financial Accounting",
    "25OE13CE12" : "Financial Planning Taxation And Investment",
    "25MDMBM2" : "Economics For Businees",
    "CSDC8013" : "ADS",
    "CSDC8023" : "SMA",
    "CSC801" : "DC",
    "CSDL8013" : "ADS Lab"
}

MAX_MARKS_CONFIG = {
    # A. DEFAULTS (Applied if no specific subject rule exists)
    "DEFAULT": {
        "MSE": 30,
        "TH-ISE1": 20,
        "TH-ISE2": 20,
        "ESE": 30,
        "PR-ISE1": 25,  # Labs usually out of 25
        "PR-ISE2": 25,
    },

    # B. SUBJECT SPECIFIC OVERRIDES
    # Format: "SUBJECT_CODE": { "EXAM_NAME": MAX_MARKS }
    
    # "CSL701": {         # Example: Machine Learning Lab
    #     "PR-ISE1": 10,  # <--- HERE: You specify this is out of 10
    #     "PR-ISE2": 10   # <--- HERE: You specify this is out of 10
    # },
    
    "CSDL7013": {       # Example: NLP Lab
        "PR-ISE1": 10,
        "PR-ISE2": 15
    },

    "CSDL7023": {       # Example: IR Lab
        "PR-ISE1": 10,
        "PR-ISE2": 15
    }
}

def get_max_marks(subject_code, exam_type):
    """
    Returns the max marks for a specific subject and exam.
    Prioritizes specific subject rules, falls back to defaults.
    """
    # 1. Check if there are special rules for this Subject Code
    if subject_code in MAX_MARKS_CONFIG:
        if exam_type in MAX_MARKS_CONFIG[subject_code]:
            return MAX_MARKS_CONFIG[subject_code][exam_type]

    # 2. Fallback to Default values
    return MAX_MARKS_CONFIG["DEFAULT"].get(exam_type, 20) # Default to 20 if unknown