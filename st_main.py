#st_main.py

import streamlit as st
import os
from dotenv import load_dotenv

# Load .env file (important to do this first)
load_dotenv()

import config  # Your configurations (URLs, subject map, etc.)
import db_utils  # Your database utility functions
import web_scraper # Your web scraping functions

# --- Initialize DB Table (runs once per app session if needed) ---
# Using a flag in session_state to ensure it runs only once per session effectively
if 'db_initialized' not in st.session_state:
    db_utils.create_db_and_table_pg()
    st.session_state.db_initialized = True

# --- Page Configuration (Optional, but good for a cleaner look) ---
st.set_page_config(page_title="Student Portal Viewer", layout="wide")

# --- App Title ---
st.title("🎓 Student Portal Data Viewer")
st.markdown("Enter a student's first name to fetch their attendance and CIE marks.")

# --- Session State Initialization for inputs and user data ---
if 'first_name' not in st.session_state:
    st.session_state.first_name = ""
if 'user_details_to_add' not in st.session_state: # To store details for adding a new user
    st.session_state.user_details_to_add = None
if 'show_add_user_form' not in st.session_state:
    st.session_state.show_add_user_form = False

# --- User Input Section ---
st.sidebar.header("Student Lookup")
first_name_input = st.sidebar.text_input(
    "Enter your username:", 
    value=st.session_state.first_name,
    key="first_name_key" # Using a key helps Streamlit manage the widget
).strip()
st.session_state.first_name = first_name_input # Keep session state updated

fetch_button = st.sidebar.button("🔍 Fetch Data", type="primary")
st.sidebar.markdown("---") # Separator

# --- Add New User Section (in sidebar) ---
if st.sidebar.button("➕ Register New Student"):
    st.session_state.show_add_user_form = not st.session_state.show_add_user_form # Toggle form visibility

if st.session_state.show_add_user_form:
    with st.sidebar.expander("Add New Student Form", expanded=True):
        with st.form("new_user_form"):
            st.markdown("##### Enter New Student Details:")
            new_first_name = st.text_input("username (for lookup, e.g., gamer709):", key="add_first_name").strip()
            new_full_name = st.text_input("Full Name (LAST_NAME FIRST_NAME MIDDLE_NAME):", key="add_full_name").strip()
            new_prn = st.text_input("PRN:", key="add_prn").strip()
            new_dob_day = st.text_input("DOB - Day (01-31):", key="add_dob_day").strip()
            new_dob_month = st.text_input("DOB - Month (01-12):", key="add_dob_month").strip()
            new_dob_year = st.text_input("DOB - Year (e.g., 2005):", key="add_dob_year").strip()
            
            submitted_add_user = st.form_submit_button("💾 Save Student")

            if submitted_add_user:
                if not all([new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year]):
                    st.error("All fields are required to add a new student.")
                else:
                    if db_utils.add_user_to_db_pg(new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year):
                        st.success(f"Student '{new_full_name}' added successfully!")
                        st.session_state.show_add_user_form = False # Hide form after success
                        st.rerun() # Rerun to clear form and potentially update display
                    else:
                        st.error("Failed to add student. They might already exist or there was a DB error.")

# --- Main Data Display Area ---
if fetch_button and first_name_input:
    st.session_state.show_add_user_form = False # Hide add user form if fetching data
    
    with st.spinner(f"Accessing data for {first_name_input}..."):
        user_details = db_utils.get_user_from_db_pg(first_name_input)

        if not user_details:
            st.error(f"No user found in the database with first name '{first_name_input}'. Please add them using the sidebar form.")
        else:
            current_prn = user_details["prn"]
            current_dob_day = user_details["dob_day"]
            current_dob_month = user_details["dob_month"]
            current_dob_year = user_details["dob_year"]
            current_full_name = user_details["full_name"]

            st.header(f"Displaying Data for: {current_full_name} (PRN: {current_prn})")
            
            session, welcome_page_html = web_scraper.login_and_get_welcome_page(
                current_prn, 
                current_dob_day, 
                current_dob_month,
                current_dob_year,
                current_full_name 
            )

            if session and welcome_page_html:
                st.success("Login to portal successful!")

                # --- Display in Columns ---
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("📊 Attendance Data")
                    attendance_records = web_scraper.extract_attendance_from_welcome_page(welcome_page_html)
                    if attendance_records:
                        attendance_display_data = []
                        for record in attendance_records:
                            subject_code = record['subject']
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
                            st.info("No attendance data to display (after filtering CSM601).")
                    else:
                        st.warning("Could not extract attendance data from the portal.")

                with col2:
                    st.subheader("📝 CIE Marks & Totals")
                    cie_marks_records = web_scraper.extract_cie_marks(welcome_page_html)
                    if cie_marks_records:
                        for subject_code, marks_dict in cie_marks_records.items():
                            subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                            with st.expander(f"{subject_name} ({subject_code})", expanded=False):
                                exam_types_to_show = []
                                if subject_code.startswith("CSC") or subject_code.startswith("CSD"): 
                                    exam_types_to_show = ["MSE", "TH-ISE1", "TH-ISE2", "ESE"]
                                elif subject_code.startswith("CSL"): 
                                    exam_types_to_show = ["PR-ISE1", "PR-ISE2"]
                                elif subject_code == "CSM601": 
                                    pass 
                                
                                subject_total = 0.0
                                has_valid_marks_for_total = False
                                defined_order = ["MSE", "TH-ISE1", "TH-ISE2", "ESE", "PR-ISE1", "PR-ISE2"]
                                temp_marks_to_print = {}

                                for exam_type in defined_order:
                                    if exam_type in marks_dict and (not exam_types_to_show or exam_type in exam_types_to_show) : 
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
                                        st.markdown(f"  **Total (Filtered): {subject_total:.2f}**")
                                elif not exam_types_to_show and marks_dict: 
                                    st.markdown("_(No specific filter rules, showing all available marks)_")
                                    unfiltered_total = 0.0
                                    has_unfiltered_marks = False
                                    for exam_type, mark_value in marks_dict.items(): 
                                         st.markdown(f" **{exam_type}:** {mark_value if mark_value is not None else 'N/A'}")
                                         if isinstance(mark_value, (int, float)):
                                             unfiltered_total += mark_value
                                             has_unfiltered_marks = True
                                    if has_unfiltered_marks:
                                        st.markdown(f"  ---")
                                        st.markdown(f"  **Total (All Available): {unfiltered_total:.2f}")
                                elif exam_types_to_show : 
                                     st.markdown(f"(No marks available for the filtered exam types: {', '.join(exam_types_to_show)})_")
                                else: 
                                    st.markdown("(No applicable marks to display for this subject based on current filters.)_")
                    else:
                        st.warning("Could not extract CIE marks data from the portal.")
            else:
                st.error("Login to portal FAILED or welcome page not retrieved correctly.")
elif fetch_button and not first_name_input:
    st.sidebar.warning("Please enter a first name to fetch data.")