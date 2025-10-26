# app.py

import streamlit as st
import os
from dotenv import load_dotenv
from streamlit_local_storage import LocalStorage
from datetime import datetime
import pytz
import math # Import math for calculations

# --- Local Storage Setup ---
try:
    _localS = LocalStorage()
except Exception:
    class MockLocalStorage:
        def getItem(self, key): return None
        def setItem(self, key, value): pass
    _localS = MockLocalStorage()
    st.warning("Could not initialize local storage. Username will not be remembered.")

def get_item(key):
    return _localS.getItem(key)

def set_item(key, value):
    _localS.setItem(key, value)

load_dotenv()

import config
import db_utils
import web_scraper

@st.cache_data(ttl=3600)
def get_processed_student_data(prn, dob_day, dob_month, dob_year, full_name):
    """
    Logs into the portal, scrapes all data, and returns it along with a timestamp.
    """
    session, html = web_scraper.login_and_get_welcome_page(
        prn, dob_day, dob_month, dob_year, full_name
    )
    if not html:
        return None

    attendance_records = web_scraper.extract_attendance_from_welcome_page(html)
    cie_marks_records = web_scraper.extract_cie_marks(html)
    detailed_attendance_records = web_scraper.extract_detailed_attendance_info(session, html)

    return {
        "data": {
            "attendance": attendance_records,
            "cie_marks": cie_marks_records,
            "detailed_attendance": detailed_attendance_records,
        },
        "scraped_at": datetime.now(pytz.utc)
    }

# --- DB and Page Initialization ---
if 'db_initialized' not in st.session_state:
    db_utils.create_db_and_table_pg()
    st.session_state.db_initialized = True

st.set_page_config(page_title="Student Portal Viewer", layout="wide")

st.header("🎓 Student Portal Data Viewer")
st.markdown("Enter your username to fetch attendance, CIE marks, and see subject leaderboards.")

# --- Session State and Input Section ---
if 'first_name' not in st.session_state:
    st.session_state.first_name = get_item(key="last_username") or ""
if 'show_add_user_form' not in st.session_state:
    st.session_state.show_add_user_form = False
if 'student_data_result' not in st.session_state:
    st.session_state.student_data_result = None

st.sidebar.header("Student Lookup")
first_name_input = st.sidebar.text_input(
    "Enter your username:", value=st.session_state.first_name, key="first_name_key"
).strip()

if first_name_input != st.session_state.first_name:
    st.session_state.student_data_result = None
st.session_state.first_name = first_name_input

if st.session_state.first_name:
    st.sidebar.write(f"Welcome back, **{st.session_state.first_name}**!")

col1, col2 = st.sidebar.columns(2)
with col1:
    fetch_button = st.button("🔍 Fetch Data", type="primary", use_container_width=True)
with col2:
    force_refresh_button = st.button("🔄 Get Live Data", use_container_width=True)
st.sidebar.markdown("---")

if st.sidebar.button("➕ Register New Student"):
    st.session_state.show_add_user_form = not st.session_state.show_add_user_form

if st.session_state.show_add_user_form:
    with st.sidebar.expander("Add New Student Form", expanded=True):
        with st.form("new_user_form"):
            st.markdown("##### Enter New Student Details:")
            new_first_name = st.text_input("Username (e.g., 'gamer709'):").strip()
            new_full_name = st.text_input("Full Name (exactly as on portal):").strip()
            new_prn = st.text_input("PRN/Roll No:").strip()
            new_dob_day = st.text_input("DOB - Date (DD):").strip()
            new_dob_month = st.text_input("DOB - Month (MM):").strip()
            new_dob_year = st.text_input("DOB - Year (YYYY):").strip()
            submitted_add_user = st.form_submit_button("💾 Validate & Save Student")

            if submitted_add_user:
                if not all([new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year]):
                    st.error("All fields are required.")
                else:
                    with st.spinner("Validating credentials..."):
                        _, validation_html = web_scraper.login_and_get_welcome_page(
                            new_prn, new_dob_day, new_dob_month, new_dob_year, new_full_name
                        )
                    if validation_html:
                        if db_utils.add_user_to_db_pg(new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year):
                            st.success(f"Student '{new_full_name}' added successfully!")
                            st.session_state.show_add_user_form = False
                            st.rerun()
                        else:
                            st.error("Validation passed, but failed to save. Username or PRN may already exist.")
                    else:
                        st.error("Login validation failed. Please double-check your details.")

# --- Data Fetching Logic ---
should_fetch = (fetch_button or (first_name_input and not st.session_state.student_data_result))
if force_refresh_button:
    st.cache_data.clear()
    st.toast("Cache cleared! Fetching fresh data...", icon="🔄")
    st.session_state.student_data_result = None
    should_fetch = True

if should_fetch and first_name_input:
    set_item(key="last_username", value=first_name_input)
    with st.spinner(f"Accessing data for {first_name_input}..."):
        user_details = db_utils.get_user_from_db_pg(first_name_input)
        if user_details:
            result = get_processed_student_data(
                user_details["prn"], user_details["dob_day"], user_details["dob_month"],
                user_details["dob_year"], user_details["full_name"]
            )
            st.session_state.student_data_result = {"user_details": user_details, "scraped_data": result}
            st.session_state.db_updated_at = None
        else:
            st.error(f"No user found with username '{first_name_input}'.")
            st.session_state.student_data_result = None

# --- Main Data Display Area ---
if st.session_state.student_data_result:
    user_details = st.session_state.student_data_result["user_details"]
    result = st.session_state.student_data_result["scraped_data"]
    current_user_id, current_full_name, current_prn = user_details["id"], user_details["full_name"], user_details["prn"]

    st.subheader(f"Displaying Data for: {current_full_name} (PRN: {current_prn})")

    if result:
        scraped_time_utc = result["scraped_at"]
        if 'db_updated_at' not in st.session_state or st.session_state.db_updated_at != scraped_time_utc:
            st.success("Login and data processing successful!")
            if result["data"]["cie_marks"] and db_utils.update_student_marks_in_db_pg(current_user_id, result["data"]["cie_marks"], scraped_time_utc):
                st.toast("Leaderboard data updated!", icon="🏆")
                st.session_state.db_updated_at = scraped_time_utc

        local_tz = pytz.timezone('Asia/Kolkata')
        scraped_time_local = scraped_time_utc.astimezone(local_tz)
        st.caption(f"Data fetched from portal at: {scraped_time_local.strftime('%I:%M:%S %p, %d-%b-%Y')}")

        attendance_records = result["data"]["attendance"]
        cie_marks_records = result["data"]["cie_marks"]
        detailed_attendance_records = result["data"].get("detailed_attendance", {})

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Attendance Data")
            if attendance_records:
                attendance_display_data = []
                for record in attendance_records:
                    subject_code = record['subject'].strip()
                    if subject_code == "CSM601": continue
                    
                    subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                    
                    # Get the current percentage from the summary data first
                    current_percentage = 0
                    if record.get('percentage') is not None:
                        current_percentage = record['percentage']
                    
                    required_str = "N/A"
                    if detailed_attendance_records and subject_code in detailed_attendance_records:
                        details = detailed_attendance_records[subject_code]
                        attended = details.get('attended', 0)
                        conducted = details.get('conducted', 0)

                        if conducted > 0:
                            # Recalculate percentage based on detailed numbers for accuracy
                            actual_percentage = (attended / conducted) * 100
                            
                            # --- NEW CALCULATION LOGIC STARTS HERE ---
                            if actual_percentage >= 75:
                                # Calculate how many lectures can be missed
                                # Formula: x <= (attended / 0.75) - conducted
                                can_miss = math.floor((attended / 0.75) - conducted)
                                can_miss = max(0, can_miss) # Ensure it's not negative
                                required_str = f"✅ Can miss {can_miss} {'lecture' if can_miss == 1 else 'lectures'}"
                            else:
                                # Calculate how many lectures must be attended
                                # Formula: y >= (0.75 * conducted - attended) / 0.25
                                needed = math.ceil(((0.75 * conducted) - attended) / 0.25)
                                needed = max(0, needed) # Ensure it's not negative
                                required_str = f"Must attend {needed} {'lecture' if needed == 1 else 'lectures'}"
                            # --- NEW CALCULATION LOGIC ENDS HERE ---
                        else:
                            required_str = "No classes held"

                    attendance_display_data.append({
                        "Subject": f"{subject_name} ({subject_code})",
                        "Percentage": f"{current_percentage}%",
                        "Attendance Goal": required_str
                    })
                
                if attendance_display_data:
                    # Renamed column for clarity
                    st.dataframe(
                        attendance_display_data, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={"Attendance Goal": st.column_config.TextColumn("To Reach 75%")}
                    )
                else:
                    st.info("No attendance data to display.")
            else:
                st.warning("Could not extract attendance data.")

        with col2:
            st.subheader("📝 CIE Marks & Leaderboards")
            if cie_marks_records:
                for subject_code, marks_dict in cie_marks_records.items():
                    subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                    with st.expander(f"{subject_name} ({subject_code})", expanded=False):
                        st.markdown("**Your Marks:**")
                        exam_types_to_show = []
                        if subject_code.startswith(("CSC", "CSDC")):
                            exam_types_to_show = ["MSE", "TH-ISE1", "TH-ISE2", "ESE"]
                        elif subject_code.startswith(("CSL", "CSDL")):
                            exam_types_to_show = ["PR-ISE1", "PR-ISE2"]

                        subject_total, has_valid_marks = 0.0, False
                        defined_order = ["MSE", "TH-ISE1", "TH-ISE2", "ESE", "PR-ISE1", "PR-ISE2"]
                        temp_marks_to_print = {}

                        for exam_type in defined_order:
                            if exam_type in marks_dict and (not exam_types_to_show or exam_type in exam_types_to_show):
                                mark = marks_dict[exam_type]
                                temp_marks_to_print[exam_type] = mark
                                if isinstance(mark, (int, float)):
                                    subject_total += mark
                                    has_valid_marks = True
                        
                        if temp_marks_to_print:
                            for exam_type, mark_value in temp_marks_to_print.items():
                                st.markdown(f"• **{exam_type}:** {mark_value if mark_value is not None else 'N/A'}")
                            if has_valid_marks:
                                st.markdown(f"  ---\n  **Your Total (Filtered): {subject_total:.2f}**")
                        else:
                            st.markdown("_(No applicable marks to display)_")

                        st.markdown("---")
                        if st.button(f"🏆 Show Leaderboard for {subject_name}", key=f"lb_{subject_code}"):
                            with st.spinner("Fetching leaderboard..."):
                                exam_types_for_lb = [exam for exam, mark in marks_dict.items() if isinstance(mark, (int, float))]
                                if not exam_types_for_lb:
                                    st.caption("_No numeric marks to generate a leaderboard._")
                                for exam_type in exam_types_for_lb:
                                    leaderboard = db_utils.get_subject_leaderboard_pg(subject_code, exam_type)
                                    if leaderboard:
                                        st.markdown(f"**Top Performers in {exam_type}:**")
                                        entries = []
                                        medals = ["🥇", "🥈", "🥉"]
                                        for i, (name, score) in enumerate(leaderboard):
                                            medal = medals[i] if i < 3 else "•"
                                            entry = f"**{medal} {name}: {score:.2f} (You)**" if name == current_full_name else f"{medal} {name}: {score:.2f}"
                                            entries.append(entry)
                                        st.markdown("  \n".join(entries))
                                    else:
                                        st.caption(f"_No leaderboard data yet for {exam_type}._")
            else:
                st.warning("Could not extract CIE marks data.")

    else:
        st.error("Login to portal FAILED or welcome page not retrieved correctly.")
elif (fetch_button or force_refresh_button) and not first_name_input:
    st.sidebar.warning("Please enter a username to fetch data.")