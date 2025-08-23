# update_all_students.py

import time
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load environment variables from .env file FIRST
load_dotenv()

import db_utils
import web_scraper
import config

# --- Configuration ---
# Be a good internet citizen. Wait this many seconds between scraping each student.
# A value between 5 and 15 is recommended to avoid getting blocked.
DELAY_BETWEEN_REQUESTS = 7 


def run_update():
    """
    Main function to fetch data for all registered users and update the database.
    """
    print("="*50)
    print("🚀 Starting the batch leaderboard update process...")
    print("="*50)

    all_users = db_utils.get_all_users_from_db_pg()

    if not all_users:
        print("❌ No users found in the database. Exiting.")
        return

    total_users = len(all_users)
    print(f"✅ Found {total_users} users to process.")
    
    success_count = 0
    fail_count = 0

    for i, user in enumerate(all_users):
        user_id = user['id']
        full_name = user['full_name']
        prn = user['prn']
        dob_day = user['dob_day']
        dob_month = user['dob_month']
        dob_year = user['dob_year']

        print("\n" + "-"*50)
        print(f"⚙️ Processing user {i+1}/{total_users}: {full_name} (ID: {user_id})")

        try:
            # Step 1: Login and get the welcome page HTML
            print(f"  - Logging in for {full_name}...")
            session, html = web_scraper.login_and_get_welcome_page(
                prn, dob_day, dob_month, dob_year, full_name
            )

            if not html:
                print(f"  - ❌ Login FAILED or page not retrieved for {full_name}.")
                fail_count += 1
                # Wait before processing the next user
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue

            # Step 2: Extract the CIE marks from the HTML
            print("  - Parsing CIE marks...")
            cie_marks_records = web_scraper.extract_cie_marks(html)

            if not cie_marks_records:
                print(f"  - ⚠️ Could not parse CIE marks for {full_name}. They may not be available yet.")
                # We'll still count this as a success since login worked, but you could change this
                success_count += 1
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue
            
            # Step 3: Update the database with the new marks
            print(f"  - Found marks for {len(cie_marks_records)} subjects. Updating database...")
            scraped_timestamp = datetime.now(pytz.utc)
            
            if db_utils.update_student_marks_in_db_pg(user_id, cie_marks_records, scraped_timestamp):
                print(f"  - ✅ Successfully updated marks for {full_name}.")
                success_count += 1
            else:
                print(f"  - ❌ Database update FAILED for {full_name}.")
                fail_count += 1

        except Exception as e:
            print(f"  - 🚨 An unexpected error occurred while processing {full_name}: {e}")
            fail_count += 1
        
        # Step 4: Wait before processing the next user
        if i + 1 < total_users:
            print(f"  - 😴 Waiting for {DELAY_BETWEEN_REQUESTS} seconds before next user...")
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print("\n" + "="*50)
    print("🎉 Batch update process finished!")
    print(f"  - Successful updates: {success_count}")
    print(f"  - Failed updates: {fail_count}")
    print("="*50)


if __name__ == "__main__":
    run_update()