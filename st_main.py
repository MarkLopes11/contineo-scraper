# app.py

import streamlit as st
import os
from dotenv import load_dotenv
from streamlit_local_storage import LocalStorage
from datetime import datetime
import pytz
import math 
import re 


# --- Local Storage Setup ---
try:
    _localS = LocalStorage()
except Exception:
    class MockLocalStorage:
        def getItem(self, key): return None
        def setItem(self, key, value): pass
    _localS = MockLocalStorage()

def get_item(key): return _localS.getItem(key)
def set_item(key, value): _localS.setItem(key, value)

load_dotenv()
import config
import db_utils
import web_scraper

# --- Email Function ---
import resend

def send_email_notification(user, user_email, message, rating): # <--- Added user_email param
    api_key = os.getenv("RESEND_API_KEY")
    receiver_email = os.getenv("EMAIL_RECEIVER") # Your personal email

    if not api_key:
        return

    resend.api_key = api_key

    # If user didn't provide email, reply-to defaults to your own email (so you don't lose the thread)
    reply_to_address = user_email if user_email else receiver_email

    html_content = f"""
    <h3>🔔 New User Feedback</h3>
    <p><strong>User:</strong> {user}</p>
    <p><strong>Email:</strong> {user_email if user_email else "Not provided"}</p>
    <p><strong>Rating:</strong> {rating}/5 ⭐</p>
    <p><strong>Message:</strong><br>{message}</p>
    <hr>
    <p><em>To reply to the student, simply click "Reply" in your email client.</em></p>
    """

    try:
        resend.Emails.send({
            "from": "Student App <onboarding@resend.dev>",
            "to": receiver_email,
            "reply_to": reply_to_address,  # <--- THIS IS THE MAGIC LINE
            "subject": f"New Feedback from {user} ({rating} Stars)",
            "html": html_content
        })
        print("Email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")

# --- Helper Functions ---

def identify_semester(subject_code):
    """Extracts semester from subject code (CSC701 -> 7)."""
    match = re.search(r'\d', subject_code)
    return int(match.group()) if match else 0

def scrape_fresh_data(user_details):
    """
    Scrapes data and organizes it.
    - Default: Uses the Semester found on the Welcome Page (e.g., 7).
    - Exception: Moves 'CSC8...', 'CSDC8...', 'CSDL8...' subjects to Semester 8.
    """
    
    # 1. Login and get the Dashboard HTML
    session, html = web_scraper.login_and_get_welcome_page(
        user_details["prn"], user_details["dob_day"], 
        user_details["dob_month"], user_details["dob_year"], 
        user_details["full_name"]
    )
    if not html: return None

    # 2. Extract the Default Semester from the Dashboard
    dashboard_sem = web_scraper.extract_student_semester(html)
    if not dashboard_sem: 
        dashboard_sem = 0 

    # 3. Scrape Raw Data
    raw_marks = web_scraper.extract_cie_marks(session, html)
    raw_att = web_scraper.extract_detailed_attendance_info(session, html)
    
    # 4. Organize Data (Hybrid Logic)
    organized_data = {}

    def get_sem_for_subject(sub_code, default_sem):
        """Checks if subject is explicitly Sem 8, otherwise returns default."""
        code = sub_code.strip().upper()
        
        # RULE: If code starts with CSC8, CSDC8, or CSDL8 -> Force Sem 8
        if re.search(r"^(CSC|CSDC|CSDL)8", code):
            return 8
        
        # Otherwise, stick to what the dashboard says (e.g., Sem 7)
        return default_sem

    # --- Process Marks ---
    for sub, exams in raw_marks.items():
        sem = get_sem_for_subject(sub, dashboard_sem)
        
        if sem == 0: continue # Skip if invalid

        if sem not in organized_data: 
            organized_data[sem] = {'cie': {}, 'att': {}}
        organized_data[sem]['cie'][sub] = exams

    # --- Process Attendance ---
    for sub, details in raw_att.items():
        sem = get_sem_for_subject(sub, dashboard_sem)
        
        if sem == 0: continue

        if sem not in organized_data: 
            organized_data[sem] = {'cie': {}, 'att': {}}
        organized_data[sem]['att'][sub] = details

    return {
        "semesters_data": organized_data,
        "scraped_at": datetime.now(pytz.utc)
    }

def calculate_grade_point(percentage):
    if percentage >= 85.00: return 10
    if 80.00 <= percentage <= 84.99: return 9
    if 70.00 <= percentage <= 79.99: return 8
    if 60.00 <= percentage <= 69.99: return 7
    if 55.00 <= percentage <= 59.99: return 6
    if 50.00 <= percentage <= 54.99: return 5
    if 45.00 <= percentage <= 49.99: return 4
    return 0

# --- Init ---
if 'db_initialized' not in st.session_state:
    db_utils.create_db_and_table_pg()
    db_utils.create_feedback_table_pg()
    st.session_state.db_initialized = True

st.set_page_config(page_title="Student Portal Viewer", layout="wide")
st.header("🎓 Student Portal Data Viewer")

# --- PWA Customization ---
st.markdown(
    """
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#0e1117">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3135/3135810.png">
    <style>
        /* This hides the "made with streamlit" footer to make it feel more like a native app */
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)

# --- Sidebar ---
if 'first_name' not in st.session_state:
    st.session_state.first_name = get_item(key="last_username") or ""
if 'show_add_user_form' not in st.session_state:
    st.session_state.show_add_user_form = False
if 'student_data_result' not in st.session_state:
    st.session_state.student_data_result = None

def on_user_change():
    st.session_state.student_data_result = None

st.sidebar.header("Student Lookup")
st.sidebar.text_input("Enter your username:", key="first_name", on_change=on_user_change)
first_name_input = st.session_state.first_name.strip()

if first_name_input:
    st.sidebar.write(f"Welcome back, **{first_name_input}**!")

col1, col2 = st.sidebar.columns(2)
with col1:
    fetch_button = st.button("🔍 Fetch Data", type="primary", width='stretch')
    st.caption("📂 **From DB**\n(Cached Data)")
with col2:
    force_refresh_button = st.button("🔄 Get Live Data", width='stretch')
    st.caption("🌐 **From Portal**\n(Current Data)")
st.sidebar.markdown("---")

# --- Add User Form (WITH VALIDATION) ---
if st.sidebar.button("➕ Register New Student"):
    st.session_state.show_add_user_form = not st.session_state.show_add_user_form

if st.session_state.show_add_user_form:
    with st.sidebar.expander("Add New Student Form", expanded=True):
        with st.form("new_user_form"):
            st.markdown("##### Enter New Student Details:")
            st.info("⚠️ Details must match the University Portal exactly.")
            
            new_first_name = st.text_input("App Username (e.g. 'gamer709'):").strip()
            new_full_name = st.text_input("Full Name (as on Portal):").strip()
            new_prn = st.text_input("PRN:").strip()
            
            
            new_dob_day = st.text_input("Date (DD)", max_chars=2).strip()
            new_dob_month = st.text_input("Month (MM)", max_chars=2).strip()
            new_dob_year = st.text_input("Year (YYYY)", max_chars=4).strip()
            
            submitted_add_user = st.form_submit_button("Validate & Save Student")

            if submitted_add_user:
                # 1. Local Validation: Check for empty fields
                if not all([new_first_name, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year]):
                    st.error("❌ All fields are required.")
                else:
                    # 2. Remote Validation: Attempt to Log in to the Portal
                    with st.spinner("🔐 Attempting login to University Portal..."):
                        try:
                            # Attempt login using the web_scraper module
                            session, validation_html = web_scraper.login_and_get_welcome_page(
                                new_prn, 
                                new_dob_day, 
                                new_dob_month, 
                                new_dob_year, 
                                new_full_name
                            )
                        except Exception as e:
                            session, validation_html = None, None
                            st.error(f"Connection Error: {e}")

                    # 3. Verify Result
                    if validation_html:
                        st.success("✅ Credentials Validated Successfully!")
                        
                        # 4. Save to Database (Only happens if validation passed)
                        save_success = db_utils.add_user_to_db_pg(
                            new_first_name, 
                            new_full_name, 
                            new_prn, 
                            new_dob_day, 
                            new_dob_month, 
                            new_dob_year
                        )
                        
                        if save_success:
                            st.balloons()
                            st.success(f"👤 User '{new_first_name}' saved to database.")
                            st.session_state.show_add_user_form = False
                            st.rerun()
                        else:
                            st.warning("⚠️ Validation passed, but Username or PRN already exists in the database.")
                    else:
                        # 5. Validation Failed - Do NOT Save
                        st.error("❌ Validation Failed.")
                        st.markdown("""
                        **Possible causes:**
                        1. Incorrect PRN or Date of Birth.
                        2. **Full Name** does not match the portal exactly (check spelling/spacing).
                        3. Portal is currently down.
                        """)
# --- Fetch Logic ---
should_fetch = (fetch_button or force_refresh_button or (first_name_input and not st.session_state.student_data_result))

if should_fetch and first_name_input:
    set_item("last_username", first_name_input)
    user_details = db_utils.get_user_from_db_pg(first_name_input)
    
    if user_details:
        result = None
        source = "Database"

        # 1. Try DB Cache
        if not force_refresh_button:
            with st.spinner("Checking cache..."):
                result = db_utils.get_student_data_from_db(user_details["id"])
        
        # 2. Scrape if needed
        if not result or force_refresh_button:
            source = "Live Portal"
            with st.spinner("Fetching from portal..."):
                scrape_res = scrape_fresh_data(user_details)
                if scrape_res:
                    result = scrape_res
                    # Save to DB (Marks & Attendance linked to Current Semester)
                    for sem, data in result["semesters_data"].items():
                        db_utils.update_student_marks_in_db_pg(
                            user_details["id"], sem, data['cie'], result["scraped_at"]
                        )
                        db_utils.update_attendance_in_db_pg(
                            user_details["id"], sem, data['att']
                        )
                    
                    # Add latest_sem logic for display
                    latest = max(result["semesters_data"].keys()) if result["semesters_data"] else None
                    result["latest_sem"] = latest

        if result:
            st.session_state.student_data_result = {"user_details": user_details, "data_pkg": result, "source": source}
        else:
            st.error("Login Failed or No Data.")
            st.session_state.student_data_result = None
    else:
        st.error("User not found.")

# --- Display Logic ---
if st.session_state.student_data_result:
    pkg = st.session_state.student_data_result
    user = pkg["user_details"]
    data = pkg["data_pkg"]
    source = pkg["source"]
    
    st.subheader(f"Student: {user['full_name']}")
    
    if data and data.get("scraped_at"):
        ts = data["scraped_at"].astimezone(pytz.timezone('Asia/Kolkata')).strftime('%d-%b %I:%M %p')
        if source == "Database": st.info(f"⚡ Cached: {ts}")
        else: st.success(f"🔄 Live: {ts}")

    all_sem_data = data.get("semesters_data", {})
    latest_sem = data.get("latest_sem")

    if all_sem_data:
        # Semester Selector
        sem_options = sorted(all_sem_data.keys(), reverse=True)
        selected_sem = st.selectbox("Select Semester", sem_options, index=0)
        
        # Get data for selected semester
        current_data = all_sem_data[selected_sem]
        marks_data = current_data.get('cie', {})
        att_data = current_data.get('att', {})

        # --- SGPI Calculation ---
        st.markdown(f"### 📈 Semester {selected_sem} Performance")
        
        total_credits = 0
        weighted_gp = 0
        breakdown = []
        db_details = [] # For saving

        if marks_data:
            for sub_code, exams in marks_data.items():
                sub_name = config.SUBJECT_CODE_TO_NAME_MAP.get(sub_code, sub_code)
                
                if "lab" in sub_name.lower(): cred = 1
                elif "project" in sub_name.lower(): cred = 3
                else: cred = 3

                obt_sum = 0.0
                max_sum = 0.0
                
                for ex, val in exams.items():
                    o = val.get('obtained', 0)
                    m = val.get('max', 0)
                    if isinstance(o, (int, float)):
                        obt_sum += o
                        max_sum += m if m > 0 else config.get_max_marks(sub_code, ex)

                if max_sum > 0:
                    perc = (obt_sum / max_sum) * 100
                    rnd_perc = math.floor(perc + 0.5)
                    gp = calculate_grade_point(rnd_perc)
                    
                    weighted_gp += (cred * gp)
                    total_credits += cred
                    
                    grade = "F"
                    if gp == 10: grade = "O"
                    elif gp == 9: grade = "A"
                    elif gp == 8: grade = "B"
                    elif gp == 7: grade = "C"
                    elif gp == 6: grade = "D"
                    elif gp == 5: grade = "E"
                    elif gp == 4: grade = "P"

                    breakdown.append(f"**{sub_name}**: {perc:.1f}% → {grade} ({gp})")
                    db_details.append({
                        "subject_code": sub_code, "subject_name": sub_name,
                        "percentage": float(f"{perc:.2f}"), "grade_point": gp, "grade_letter": grade, "credits": cred
                    })

            if total_credits > 0:
                sgpi = weighted_gp / total_credits
                
                # Save SGPI if from Live Source
                if source == "Live Portal":
                    db_utils.save_student_sgpi_pg(user["id"], selected_sem, sgpi, db_details)

                c1, c2, c3 = st.columns([2, 3, 2])
                c1.metric("SGPI", f"{sgpi:.2f}")
                with c2:
                    with st.expander("Subject Breakdown"):
                        for b in breakdown: st.markdown(f"- {b}")
                with c3:
                    if st.button(f"🏆 Sem {selected_sem} Leaderboard"):
                        lb = db_utils.get_semester_leaderboard_pg(selected_sem)
                        if lb:
                            st.write(f"**Top Students (Sem {selected_sem}):**")
                            for i, (n, s) in enumerate(lb):
                                icon = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
                                bold = "**" if n == user['full_name'] else ""
                                st.write(f"{icon} {bold}{n}: {s:.2f}{bold}")
                        else:
                            st.caption("No leaderboard data.")
        else:
            st.info("No marks available for this semester.")
        
        st.divider()

        # --- Attendance & Marks Columns ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Attendance")
            if att_data:
                att_display = []
                for sub, det in att_data.items():
                    # --- Formatting: Name (Code) ---
                    subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(sub, sub)
                    display_name = f"{subject_name} ({sub})"
                    
                    att = det.get('attended', 0)
                    cond = det.get('conducted', 0)
                    
                    if cond > 0:
                        p = (att/cond)*100
                        status = "N/A"
                        if p >= 75:
                            miss = math.floor((att/0.75) - cond)
                            status = f"✅ Safe. Miss {int(miss)}"
                        else:
                            need = math.ceil(((0.75*cond) - att)/0.25)
                            status = f"⚠️ Low. Attend {int(need)}"
                        
                        att_display.append({"Subject": display_name, "Attendance": f"{p:.1f}%", "Status(For 75%)": status})
                st.dataframe(att_display, width='stretch', hide_index=True)
            else:
                st.info("No attendance records.")

        with col2:
            st.subheader("📝 Marks")
            if marks_data:
                for sub, exams in marks_data.items():
                    # --- Formatting: Name (Code) ---
                    subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(sub, sub)
                    display_name = f"{subject_name} ({sub})"
                    
                    # Initialize totals for this subject
                    sub_total_obt = 0
                    sub_total_max = 0

                    with st.expander(f"{display_name}"):
                        for ex, val in exams.items():
                            if isinstance(val, dict):
                                o = val.get('obtained', 0)
                                m = val.get('max', 0)
                                
                                # Display the individual exam line
                                st.write(f"**{ex}:** {o} / {m}")
                                
                                # Add to running total
                                sub_total_obt += float(o)
                                sub_total_max += float(m)
                            else:
                                # Fallback for old data formats
                                st.write(f"**{ex}:** {val}")
                        
                        # Display the Total at the very end
                        st.markdown("---") 
                        st.markdown(f"**Total:** {sub_total_obt} / {sub_total_max}")

            else:
                st.info("No marks records.")
    else:
        st.warning("No data found for any semester.")

elif (fetch_button or force_refresh_button) and not first_name_input:
    st.sidebar.warning("Please enter a username to fetch data.")


# --- Append this to the very end of app.py ---
st.divider()
st.subheader("💬 Feedback & Support")

with st.expander("📝 Report a bug or leave a suggestion"):
    with st.form("feedback_form_main"):
        current_user = st.session_state.first_name.strip() if st.session_state.first_name else "Anonymous"
        
        c1, c2 = st.columns([1, 4])
        
        with c1:
            st.write("**Rate your experience:**")
            selected_sentiment = st.feedback("stars")
            
        with c2:
            # New Email Input
            fb_email = st.text_input("Your Email:")
            fb_msg = st.text_area("Message", placeholder="Tell us what you think...")

        submitted_fb = st.form_submit_button("Submit Feedback")

        if submitted_fb:
            final_rating = (selected_sentiment + 1) if selected_sentiment is not None else 0
            
            if final_rating == 0:
                st.warning("⚠️ Please select a Star Rating.")
            elif not fb_msg.strip():
                st.warning("⚠️ Please write a message.")
            else:
                # 1. Save to Database (Pass email now)
                if db_utils.save_feedback_pg(current_user, fb_email, fb_msg, final_rating):
                    
                    # 2. Send Email Notification (Pass email now)
                    send_email_notification(current_user, fb_email, fb_msg, final_rating)
                    
                    st.success("Thank you! Your feedback has been recorded. ❤️")
                    st.balloons()
                else:
                    st.error("Internal Error: Could not save feedback.")