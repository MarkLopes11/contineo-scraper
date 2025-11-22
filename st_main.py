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
    
    # UPDATED: Pass 'session' to allow deep scraping of marks
    cie_marks_records = web_scraper.extract_cie_marks(session, html)
    
    detailed_attendance_records = web_scraper.extract_detailed_attendance_info(session, html)

    return {
        "data": {
            "attendance": attendance_records,
            "cie_marks": cie_marks_records,
            "detailed_attendance": detailed_attendance_records,
        },
        "scraped_at": datetime.now(pytz.utc)
    }

def calculate_grade_point(percentage):
    """
    Maps percentage to Grade Point (GP) based on the PG Program table.
    """
    if percentage >= 85.00: return 10
    if 80.00 <= percentage <= 84.99: return 9
    if 70.00 <= percentage <= 79.99: return 8
    if 60.00 <= percentage <= 69.99: return 7
    if 55.00 <= percentage <= 59.99: return 6
    if 50.00 <= percentage <= 54.99: return 5
    if 45.00 <= percentage <= 49.99: return 4
    return 0 # Less than 45 or Fail

# --- DB and Page Initialization ---
if 'db_initialized' not in st.session_state:
    db_utils.create_db_and_table_pg()
    st.session_state.db_initialized = True

st.set_page_config(page_title="Student Portal Viewer", layout="wide")

st.header("🎓 Student Portal Data Viewer")
st.markdown("Enter your username to fetch attendance, CIE marks, and see subject leaderboards.")

# --- Session State and Input Section ---

# 1. Initialize 'first_name' from LocalStorage if it doesn't exist in session
if 'first_name' not in st.session_state:
    st.session_state.first_name = get_item(key="last_username") or ""

if 'show_add_user_form' not in st.session_state:
    st.session_state.show_add_user_form = False
if 'student_data_result' not in st.session_state:
    st.session_state.student_data_result = None

# 2. Callback function to clear data when username changes
def on_user_change():
    st.session_state.student_data_result = None

st.sidebar.header("Student Lookup")

# 3. Text Input bound DIRECTLY to session state key
# Removing 'value=' fixes the flickering/reverting issue.
st.sidebar.text_input(
    "Enter your username:",
    key="first_name",         # Binds to st.session_state.first_name
    on_change=on_user_change  # Triggers immediately on Enter
)

# Access the value from state
first_name_input = st.session_state.first_name.strip()

if first_name_input:
    st.sidebar.write(f"Welcome back, **{first_name_input}**!")

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

        # --- SGPI CALCULATION ---
        if cie_marks_records:
            st.markdown("### 📈 Academic Performance (Projected SGPI)")
            
            total_credits_registered = 0
            weighted_gp_sum = 0
            sgpi_details = []

            for subject_code_raw, marks_data in cie_marks_records.items():
                subject_code = subject_code_raw.strip()
                subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                
                # --- CREDIT LOGIC ---
                # Auto-detect credits based on subject name
                if "lab" in subject_name.lower():
                    credits = 1
                elif "project" in subject_name.lower():
                    credits = 3
                else:
                    credits = 3

                subject_obtained_marks = 0.0
                subject_max_marks = 0.0
                
                # Calculate Sums for this Subject
                # mark_data is likely: {'MSE': {'obtained': 15.0, 'max': 30.0}, ...}
                for exam_type, data_entry in marks_data.items():
                    
                    # Handle New Structure (Dict) from deep scraper
                    if isinstance(data_entry, dict):
                        obt = data_entry.get('obtained', 0.0)
                        mx = data_entry.get('max', 0.0)
                        
                        subject_obtained_marks += obt
                        
                        if mx > 0:
                            subject_max_marks += mx
                        else:
                            # Fallback to Config if scraper returned 0 for max
                            subject_max_marks += config.get_max_marks(subject_code, exam_type)
                    
                    # Handle Legacy/Simple Structure (Float) - just in case
                    elif isinstance(data_entry, (int, float)):
                        subject_obtained_marks += data_entry
                        subject_max_marks += config.get_max_marks(subject_code, exam_type)

                # Calculate Grade Point for this subject
                if subject_max_marks > 0:
                    percentage = (subject_obtained_marks / subject_max_marks) * 100
                    gp = calculate_grade_point(percentage)
                    
                    weighted_gp_sum += (credits * gp)
                    total_credits_registered += credits
                    
                    # Grade Letter for display
                    grade_letter = "F"
                    if gp == 10: grade_letter = "O"
                    elif gp == 9: grade_letter = "A"
                    elif gp == 8: grade_letter = "B"
                    elif gp == 7: grade_letter = "C"
                    elif gp == 6: grade_letter = "D"
                    elif gp == 5: grade_letter = "E"
                    elif gp == 4: grade_letter = "P"

                    sgpi_details.append(f"**{subject_name}** ({subject_code}): {percentage:.1f}% → Grade {grade_letter} ({gp}) × {credits} Credit(s)")

            if total_credits_registered > 0:
                calculated_sgpi = weighted_gp_sum / total_credits_registered
                
                sgpi_col1, sgpi_col2 = st.columns([1, 3])
                with sgpi_col1:
                    st.metric(label="Predicted SGPI", value=f"{calculated_sgpi:.2f}")
                with sgpi_col2:
                    st.info(f"**Calculation:** Σ(Credits × GP) / Σ(Credits) = {weighted_gp_sum} / {total_credits_registered}")
                    with st.expander("View Subject-wise Breakdown"):
                        for det in sgpi_details:
                            st.markdown(f"- {det}")
                        st.caption("*Note: SGPI is calculated based on the percentage of marks currently obtained in available exams vs. their max marks.*")
            else:
                st.caption("No valid credits found for calculations.")
            
            st.divider()

        # --- EXISTING COLUMNS ---
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Attendance Data")
            if attendance_records:
                attendance_display_data = []
                for record in attendance_records:
                    subject_code = record['subject'].strip() 
                    
                    if subject_code == "CSM601": continue
                    
                    subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                    current_percentage = record.get('percentage', 0)
                    
                    required_str = "N/A"
                    if detailed_attendance_records and subject_code in detailed_attendance_records:
                        details = detailed_attendance_records[subject_code]
                        attended = details.get('attended', 0)
                        conducted = details.get('conducted', 0)

                        if conducted > 0:
                            actual_percentage = (attended / conducted) * 100
                            if actual_percentage >= 75:
                                can_miss = math.floor((attended / 0.75) - conducted)
                                required_str = f"✅ Can miss {max(0, can_miss)} {'lecture' if max(0, can_miss) == 1 else 'lectures'}"
                            else:
                                needed = math.ceil(((0.75 * conducted) - attended) / 0.25)
                                required_str = f"Must attend {max(0, needed)} {'lecture' if max(0, needed) == 1 else 'lectures'}"
                        else:
                            required_str = "No classes held"

                    attendance_display_data.append({
                        "Subject": f"{subject_name} ({subject_code})",
                        "Percentage": f"{current_percentage}%",
                        "Attendance Goal": required_str
                    })
                
                if attendance_display_data:
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
                        if subject_code.startswith(("CSC", "CSDC", "MEC", "MEDLO", "ILO")):
                            exam_types_to_show = ["MSE", "TH-ISE1", "TH-ISE2", "ESE"]
                        elif subject_code.startswith(("CSL", "CSDL", "MEL", "MEP")):
                            exam_types_to_show = ["PR-ISE1", "PR-ISE2"]

                        subject_total, has_valid_marks = 0.0, False
                        defined_order = ["MSE", "TH-ISE1", "TH-ISE2", "ESE", "PR-ISE1", "PR-ISE2"]
                        
                        temp_marks_to_print = {}

                        for exam_type in defined_order:
                            if exam_type in marks_dict and (not exam_types_to_show or exam_type in exam_types_to_show):
                                mark_entry = marks_dict.get(exam_type)
                                temp_marks_to_print[exam_type] = mark_entry
                                
                                # Add to Total Calculation
                                if isinstance(mark_entry, dict):
                                    # New Structure
                                    obt = mark_entry.get('obtained', 0)
                                    subject_total += obt
                                    has_valid_marks = True
                                elif isinstance(mark_entry, (int, float)):
                                    # Old Structure
                                    subject_total += mark_entry
                                    has_valid_marks = True
                        
                        if temp_marks_to_print:
                            for exam_type, val in temp_marks_to_print.items():
                                # Display Logic: Handle Dict vs Float
                                if isinstance(val, dict):
                                    st.markdown(f"• **{exam_type}:** {val['obtained']} / {val['max']}")
                                else:
                                    st.markdown(f"• **{exam_type}:** {val if val is not None else 'N/A'}")

                            if has_valid_marks:
                                st.markdown(f"  ---\n  **Your Total (Obtained): {subject_total:.2f}**")
                        else:
                            st.markdown("_(No applicable marks to display)_")

                        st.markdown("---")
                        
                        # Leaderboard Button Logic
                        if st.button(f"🏆 Show Leaderboard for {subject_name}", key=f"lb_{subject_code}"):
                            with st.spinner("Fetching leaderboard..."):
                                # Collect available exams to show LB for
                                exam_types_for_lb = []
                                for e, m in marks_dict.items():
                                    # Check if we have a valid number for this exam
                                    if isinstance(m, dict) and isinstance(m.get('obtained'), (int, float)):
                                        exam_types_for_lb.append(e)
                                    elif isinstance(m, (int, float)):
                                        exam_types_for_lb.append(e)

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
                                            score_display = score
                                            
                                            entry = f"**{medal} {name}: {score_display} (You)**" if name == current_full_name else f"{medal} {name}: {score_display}"
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