# main_app.py
import os
from dotenv import load_dotenv
load_dotenv()
import db_utils
import web_scraper
import config 

def run_application():
    # --- Ensure DB table exists ---
    db_utils.create_db_and_table_pg() 

    first_name_input = input("Enter your username: ").strip()
    if not first_name_input:
        print("No first name entered. Exiting.")
        return

    user_details = db_utils.get_user_from_db_pg(first_name_input) 

    if not user_details:
        print(f"No user found in the database with first name '{first_name_input}'.")
        add_new = input("Would you like to add this user? (yes/no): ").strip().lower()
        if add_new == 'yes':
            print("\nPlease provide details for the new user:")
            new_full_name = input(f"Full Name (e.g., {first_name_input.capitalize()} Lastname): ").strip()
            new_prn = input("PRN: ").strip()
            new_dob_day = input("Date of Birth - Day (01-31): ").strip()
            new_dob_month = input("Date of Birth - Month (01-12): ").strip()
            new_dob_year = input("Date of Birth - Year: ").strip()
            
            if db_utils.add_user_to_db_pg(first_name_input, new_full_name, new_prn, new_dob_day, new_dob_month, new_dob_year): 
                user_details = db_utils.get_user_from_db_pg(first_name_input) 
            else:
                print("Failed to add user. Exiting.")
                return
        else:
            print("Exiting.")
            return
            
    if not user_details: 
        print("Could not retrieve user details. Exiting.")
        return

    current_prn = user_details["prn"]
    current_dob_day = user_details["dob_day"]
    current_dob_month = user_details["dob_month"]
    current_dob_year = user_details["dob_year"]
    current_full_name = user_details["full_name"]

    print(f"\n--- Attempting Login for: {current_full_name} (PRN: {current_prn}) ---")
    
    session, welcome_page_html = web_scraper.login_and_get_welcome_page(
        current_prn, 
        current_dob_day, 
        current_dob_month,
        current_dob_year,
        current_full_name 
    )

    if session and welcome_page_html:
        # You might want to save the debug page only if a specific debug flag is set
        # with open("debug_welcome_page_from_script.html", "w", encoding="utf-8") as f:
        #     f.write(welcome_page_html)

        attendance_records = web_scraper.extract_attendance_from_welcome_page(welcome_page_html)
        if attendance_records:
            print("\n--- Extracted Attendance Data ---")
            for record in attendance_records:
                subject_code = record['subject']
                if subject_code == "CSM601": 
                    continue 
                subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code) 
                print(f"Subject: {subject_name} ({subject_code}), Percentage: {record['percentage']}%")
        else:
            print("\nCould not extract attendance data.")

        cie_marks_records = web_scraper.extract_cie_marks(welcome_page_html)
        if cie_marks_records:
            print("\n--- Extracted and Filtered CIE Marks Data (with Totals) ---")
            for subject_code, marks_dict in cie_marks_records.items():
                subject_name = config.SUBJECT_CODE_TO_NAME_MAP.get(subject_code, subject_code)
                print(f"Subject: {subject_name} ({subject_code})")
                
                exam_types_to_show = []
                if subject_code.startswith("CSC") or subject_code.startswith("CSDC"): 
                    exam_types_to_show = ["MSE", "TH-ISE1", "TH-ISE2", "ESE"]
                elif subject_code.startswith("CSL") or subject_code.startswith("CSDL"): 
                    exam_types_to_show = ["PR-ISE1", "PR-ISE2"]
                elif subject_code == "CSM601": 
                    pass # No specific filter for Mini Project, shows all if exam_types_to_show remains empty
                
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
                         print(f"  {exam_type}: {mark_value if mark_value is not None else 'N/A'}")
                    if has_valid_marks_for_total:
                        print(f"  --------------------")
                        print(f"  Total (Filtered): {subject_total:.2f}") 
                elif not exam_types_to_show and marks_dict: 
                    print("  (No specific filter rules for this subject type, showing all available marks)")
                    unfiltered_total = 0.0
                    has_unfiltered_marks = False
                    for exam_type, mark_value in marks_dict.items(): 
                         print(f"  {exam_type}: {mark_value if mark_value is not None else 'N/A'}")
                         if isinstance(mark_value, (int, float)):
                             unfiltered_total += mark_value
                             has_unfiltered_marks = True
                    if has_unfiltered_marks:
                        print(f"  --------------------")
                        print(f"  Total (All Available): {unfiltered_total:.2f}")
                elif exam_types_to_show : 
                     print(f"  (No marks available for the filtered exam types: {', '.join(exam_types_to_show)})")
                else: 
                    print("  (No applicable marks to display for this subject based on current filters.)")
                print("-" * 20) 
        else:
            print("\nCould not extract CIE marks data.")
    else:
        print("\nLogin FAILED or welcome page not retrieved correctly.")

if __name__ == "__main__":
    run_application()
    print(f"\n--- Script Finished ---")