# update_all_students.py

import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
import math
import re

# Load environment variables
load_dotenv()

import db_utils
import web_scraper
import config

# --- Configuration ---
DELAY_BETWEEN_REQUESTS = 5  # Seconds to wait between students

# --- Helper Functions ---

def identify_target_semester(sub_code, default_sem):
    """
    Logic: Use dashboard sem as default. 
    Force to 8 if code starts with CSC8, CSDC8, or CSDL8.
    """
    code = sub_code.strip().upper()
    if re.search(r"^(CSC|CSDC|CSDL)8", code):
        return 8
    return default_sem

def calculate_grade_point(percentage):
    """Maps percentage to Grade Point (GP)."""
    if percentage >= 85.00: return 10
    if 80.00 <= percentage <= 84.99: return 9
    if 70.00 <= percentage <= 79.99: return 8
    if 60.00 <= percentage <= 69.99: return 7
    if 55.00 <= percentage <= 59.99: return 6
    if 50.00 <= percentage <= 54.99: return 5
    if 45.00 <= percentage <= 49.99: return 4
    return 0

def run_update():
    print("="*60)
    print("🚀 Starting BATCH UPDATE: Hybrid Sem 7/8 Logic")
    print("="*60)

    all_users = db_utils.get_all_users_from_db_pg()

    if not all_users:
        print("❌ No users found in the database. Exiting.")
        return

    total_users = len(all_users)
    print(f"✅ Found {total_users} users to process.\n")
    
    success_count = 0
    fail_count = 0

    for i, user in enumerate(all_users):
        user_id = user['id']
        full_name = user['full_name']
        prn = user['prn']
        
        print("-" * 50)
        print(f"[{i+1}/{total_users}] Processing: {full_name} (PRN: {prn})")

        try:
            # 1. Login
            session, html = web_scraper.login_and_get_welcome_page(
                prn, user['dob_day'], user['dob_month'], user['dob_year'], full_name
            )

            if not html:
                print(f"   ❌ Login FAILED. Skipping.")
                fail_count += 1
                continue

            # 2. Scrape Mixed Raw Data
            raw_marks = web_scraper.extract_cie_marks(session, html)
            raw_att = web_scraper.extract_detailed_attendance_info(session, html)
            dashboard_sem = web_scraper.extract_student_semester(html) or 0
            
            # 3. Organize into Buckets (Hybrid Logic)
            # Structure: { 7: {'cie': {}, 'att': {}}, 8: {...} }
            organized_data = {}

            # Sort Marks
            for sub, exams in raw_marks.items():
                sem = identify_target_semester(sub, dashboard_sem)
                if sem not in organized_data: organized_data[sem] = {'cie': {}, 'att': {}}
                organized_data[sem]['cie'][sub] = exams

            # Sort Attendance
            for sub, details in raw_att.items():
                sem = identify_target_semester(sub, dashboard_sem)
                if sem not in organized_data: organized_data[sem] = {'cie': {}, 'att': {}}
                organized_data[sem]['att'][sub] = details

            timestamp = datetime.now(pytz.utc)

            # 4. Process each semester found
            for sem, data in organized_data.items():
                print(f"   💾 Updating Semester {sem}...")
                
                # Save Marks & Attendance to DB
                if data['cie']:
                    db_utils.update_student_marks_in_db_pg(user_id, sem, data['cie'], timestamp)
                if data['att']:
                    db_utils.update_attendance_in_db_pg(user_id, sem, data['att'])

                # 5. Calculate SGPI for this specific semester bucket
                if data['cie']:
                    total_credits = 0
                    weighted_gp = 0
                    db_grade_details = []

                    for sub_code, exams in data['cie'].items():
                        sub_name = config.SUBJECT_CODE_TO_NAME_MAP.get(sub_code, sub_code)
                        
                        # Credits: Lab=1, Project=3, Theory=3
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
                            
                            # Letter Grades
                            grade = "F"
                            if gp == 10: grade = "O"
                            elif gp == 9: grade = "A"
                            elif gp == 8: grade = "B"
                            elif gp == 7: grade = "C"
                            elif gp == 6: grade = "D"
                            elif gp == 5: grade = "E"
                            elif gp == 4: grade = "P"

                            db_grade_details.append({
                                "subject_code": sub_code, "subject_name": sub_name,
                                "percentage": float(f"{perc:.2f}"), "grade_point": gp, 
                                "grade_letter": grade, "credits": cred
                            })

                    if total_credits > 0:
                        sgpi = weighted_gp / total_credits
                        db_utils.save_student_sgpi_pg(user_id, sem, sgpi, db_grade_details)
                        print(f"      ✅ Saved SGPI: {sgpi:.2f}")

            print(f"   ✅ {full_name} updated successfully.")
            success_count += 1

        except Exception as e:
            print(f"   🚨 Error processing {full_name}: {e}")
            fail_count += 1
        
        # Rate Limiting
        if i + 1 < total_users:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print("\n" + "="*60)
    print("🎉 BATCH UPDATE COMPLETE")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Failed:  {fail_count}")
    print("="*60)

if __name__ == "__main__":
    run_update()