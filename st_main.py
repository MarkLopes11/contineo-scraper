# st_main.py

import streamlit as st
import os
from dotenv import load_dotenv
from streamlit_local_storage import LocalStorage
from datetime import datetime
import pytz

# --- Local Storage Setup ---
# This needs to be at the top level of the script
try:
    _localS = LocalStorage()
except Exception:
    # Handle cases where LocalStorage might not be available (e.g., in some cloud environments)
    class MockLocalStorage:
        def getItem(self, key): return None
        def setItem(self, key, value): pass
    _localS = MockLocalStorage()
    st.warning("Could not initialize local storage. Username will not be remembered across sessions.")


def get_item(key):
    return _localS.getItem(key)

def set_item(key, value):
    _localS.setItem(key, value)

# Load .env file (important to do this first)
load_dotenv()

import config  # Your configurations (URLs, subject map, etc.)
import db_utils  # Your database utility functions
import web_scraper # Your web scraping functions

@st.cache_data(ttl=3600)
def get_processed_student_data(prn, dob_day, dob_month, dob_year, full_name):
    """
    Logs into the portal, scrapes data, and returns it along with a timestamp.
    The entire dictionary output is cached.
    """
    session, html = web_scraper.login_and_get_welcome_page(
        prn, dob_day, dob_month, dob_year, full_name
    )

    if not html:
        return None

    attendance_records = web_scraper.extract_attendance_from_welcome_page(html)
    cie_marks_records = web_scraper.extract_cie_marks(html)

    return {
        "data": {
            "attendance": attendance_records,
            "cie_marks": cie_marks_records
        },
        "scraped_at": datetime.now(pytz.utc)
    }

# --- Initialize DB Table (runs once per app session if needed) ---
if 'db_initialized' not in st.session_state:
    db_utils.create_db_and_table_pg()
    st.session_state.db_initialized = True

# --- Page Configuration ---
st.set_page_config(page_title="Student Portal Viewer", layout="wide")

# --- App Title ---
st.header("🎓 Student Portal Data Viewer")
st.markdown("Enter your username to fetch attendance, CIE marks, and see subject leaderboards.")

# --- Session State Initialization and Local Storage ---
if 'first_name' not in st.session_state:
    st.session_state.first_name = get_item(key="last_username") or ""
    st.session_state.auto_fetch_done = False

if 'user_details_to_add' not in st.session_state:
    st.session_state.user_details_to_add = None
if 'show_add_user_form' not in st.session_state:
    st.session_state.show_add_user_form = False

# --- User Input Section ---
st.sidebar.header("Student Lookup")
first_name_input = st.sidebar.text_input(
    "Enter your username:",
    value=st.session_state.first_name,
    key="first_name_key"
).strip()

if first_name_input != st.session_state.first_name:
    st.session_state.auto_fetch_done = False

st.session_state.first_name = first_name_input

if st.session_state.first_name:
    st.sidebar.write(f"Welcome back, **{st.session_state.first_name}**!")

# --- Action Buttons ---
col1, col2 = st.sidebar.columns(2)
with col1:
    fetch_button = st.button("🔍 Fetch Data", type="primary", use_container_width=True)
with col2:
    force_refresh_button = st.button("🔄 Get Live Data", use_container_width=True)

st.sidebar.markdown("---") # Separator

# --- Add New User Section (in sidebar) ---
if st.sidebar.button("➕ Register New Student"):
    st.session_state.show_add_user_form = not st.session_state.show_add_user_form

if st.session_state.show_add_user_form:
    with st.sidebar.expander("Add New Student Form", expanded=True):
        with st.form("new_user_form"):
            st.markdown("##### Enter New Student Details:")
            new_first_name = st.text_input("Username (for lookup, e.g., 'gamer709'):", key="add_first_name").strip()
            new_full_name = st.text_input("Full Name (exactly as on the portal):", key="add_full_name").strip()
            new_prn = st.text_input("PRN:", key="add_prn").strip()
            new_dob_day = st.text_input("DOB - Date (e.g., 01, 23):", key="add_dob_day").strip()
            new_dob_month = st.text_input("DOB - Month (e.g., 01, 12):", key="add_dob_month").strip()
            new_dob_year = st.text_input("DOB - Year (e.g., 2005):", key="add_dob_year").strip()

            submitted_add_user = st.form_submit_button("💾 Save Student")

            if submitted_add_user:
                if not all([new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year]):
                    st.error("All fields are required to add a new student.")
                else:
                    if db_utils.add_user_to_db_pg(new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year):
                        st.success(f"Student '{new_full_name}' added successfully! You can now look them up.")
                        st.session_state.show_add_user_form = False
                        st.rerun()
                    else:
                        st.error("Failed to add student. The username or PRN might already exist.")

# --- DATA FETCH TRIGGER LOGIC ---
should_fetch = False

# Priority 1: Force Refresh button is clicked
if force_refresh_button and first_name_input:
    st.cache_data.clear()
    st.toast("Cache cleared! Fetching fresh data...", icon="🔄")
    should_fetch = True
    st.session_state.auto_fetch_done = True # Mark as fetched

# Priority 2: Normal Fetch button is clicked
elif fetch_button and first_name_input:
    should_fetch = True
    st.session_state.auto_fetch_done = True

# Priority 3: Auto-fetch on initial load or after changing username
elif first_name_input and not st.session_state.get('auto_fetch_done', False):
    should_fetch = True
    st.session_state.auto_fetch_done = True

# --- Main Data Display Area ---
if should_fetch:
    set_item(key="last_username", value=first_name_input)
    st.session_state.show_add_user_form = False

    with st.spinner(f"Accessing data for {first_name_input}..."):
        user_details = db_utils.get_user_from_db_pg(first_name_input)

        if not user_details:
            st.error(f"No user found in the database with username '{first_name_input}'. Please register them using the sidebar form.")
        else:
            current_user_id = user_details["id"]
            current_prn = user_details["prn"]
            current_dob_day = user_details["dob_day"]
            current_dob_month = user_details["dob_month"]
            current_dob_year = user_details["dob_year"]
            current_full_name = user_details["full_name"]

            st.subheader(f"Displaying Data for: {current_full_name} (PRN: {current_prn})")

            result = get_processed_student_data(
                current_prn,
                current_dob_day,
                current_dob_month,
                current_dob_year,
                current_full_name
            )

            if result:
                scraped_time_utc = result["scraped_at"]
                local_tz = pytz.timezone('Asia/Kolkata')
                scraped_time_local = scraped_time_utc.astimezone(local_tz)

                st.success("Login and data processing successful!")
                st.caption(f"Data fetched from portal at: {scraped_time_local.strftime('%I:%M:%S %p, %d-%b-%Y')}")

                processed_data = result["data"]
                attendance_records = processed_data["attendance"]
                cie_marks_records = processed_data["cie_marks"]
                
                if cie_marks_records:
                    if db_utils.update_student_marks_in_db_pg(current_user_id, cie_marks_records, scraped_time_utc):
                        st.toast("Updated leaderboard data successfully!", icon="🏆")
                    else:
                        st.toast("Could not update leaderboard data.", icon="⚠️")

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("📊 Attendance Data")
                    if attendance_records:
                        attendance_display_data = []
                        for record in attendance_records:
                            subject_code = record['subject'].strip()
                            if subject_code == "CSM601":
                                continue
                            subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                            attendance_display_data.append({
                                "Subject": f"{subject_name} ({subject_code})",
                                "Percentage": f"{record['percentage']}%"
                            })
                        if attendance_display_data:
                            st.table(attendance_display_data)
                        else:
                            st.info("No attendance data to display (after filtering).")
                    else:
                        st.warning("Could not extract attendance data from the portal.")

                with col2:
                    st.subheader("📝 CIE Marks & Leaderboards")
                    if cie_marks_records:
                        for subject_code, marks_dict in cie_marks_records.items():
                            subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                            with st.expander(f"{subject_name} ({subject_code})", expanded=False):
                                # --- Display Current User's Marks ---
                                st.markdown("**Your Marks:**")
                                exam_types_to_show = []
                                if subject_code.startswith("CSC") or subject_code.startswith("CSDC"):
                                    exam_types_to_show = ["MSE", "TH-ISE1", "TH-ISE2", "ESE"]
                                elif subject_code.startswith("CSL") or subject_code.startswith("CSDL"):
                                    exam_types_to_show = ["PR-ISE1", "PR-ISE2"]
                                
                                subject_total = 0.0
                                has_valid_marks_for_total = False
                                defined_order = ["MSE", "TH-ISE1", "TH-ISE2", "ESE", "PR-ISE1", "PR-ISE2"]
                                temp_marks_to_print = {}

                                for exam_type in defined_order:
                                    if exam_type in marks_dict and (not exam_types_to_show or exam_type in exam_types_to_show):
                                        mark = marks_dict[exam_type]
                                        temp_marks_to_print[exam_type] = mark
                                        if isinstance(mark, (int, float)):
                                            subject_total += mark
                                            has_valid_marks_for_total = True
                                
                                if temp_marks_to_print:
                                    for exam_type, mark_value in temp_marks_to_print.items():
                                        st.markdown(f"• **{exam_type}:** {mark_value if mark_value is not None else 'N/A'}")
                                    if has_valid_marks_for_total:
                                        st.markdown(f"  ---")
                                        st.markdown(f"  **Your Total (Filtered): {subject_total:.2f}**")
                                else:
                                    st.markdown("_(No applicable marks to display for you in this subject)_")
                                
                                st.markdown(f"**🏆 Leaderboard for {subject_name}**")

                                exam_types_for_leaderboard = [
                                    exam for exam, mark in marks_dict.items() if isinstance(mark, (int, float))
                                ]

                                if not exam_types_for_leaderboard:
                                    st.caption("_No numeric marks available to generate a leaderboard._")
                                
                                for exam_type in exam_types_for_leaderboard:
                                    leaderboard = db_utils.get_subject_leaderboard_pg(subject_code, exam_type)
                                    if leaderboard:
                                        st.markdown(f"**Top Performers in {exam_type}:**")
                                        
                                        leaderboard_entries = []
                                        medals = ["🥇", "🥈", "🥉"]
                                        for i, (student_name, score) in enumerate(leaderboard):
                                            medal = medals[i] if i < len(medals) else "•"
                                            if student_name == current_full_name:
                                                entry = f"**{medal} {student_name}: {score:.2f} (You)**"
                                            else:
                                                entry = f"{medal} {student_name}: {score:.2f}"
                                            leaderboard_entries.append(entry)
                                        
                                        # ######################################
                                        # ##### START OF THE FIX #####
                                        # ######################################
                                        # Add two spaces before \n to force a hard line break in Markdown
                                        st.markdown("  \n".join(leaderboard_entries))
                                        # ######################################
                                        # ##### END OF THE FIX #####
                                        # ######################################

                                    else:
                                        st.caption(f"_No leaderboard data yet for {exam_type}._")
                    else:
                        st.warning("Could not extract CIE marks data from the portal.")

            else:
                st.error("Login to portal FAILED or welcome page not retrieved correctly.")
elif (fetch_button or force_refresh_button) and not first_name_input:
    st.sidebar.warning("Please enter a username to fetch data.")