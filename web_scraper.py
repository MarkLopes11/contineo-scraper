import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import config  # Import your config file

def login_and_get_welcome_page(prn, dob_day, dob_month_val, dob_year, user_full_name_for_check):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
        "Referer": config.LOGIN_URL
    })
    try:
        # 1. Get Login Page
        response_get = session.get(config.LOGIN_URL, timeout=20)
        response_get.raise_for_status()
        soup_login = BeautifulSoup(response_get.content, "html.parser")
        login_form = soup_login.find("form", {"id": "login-form"})
        
        if not login_form:
            print("Could not find login form.")
            return None, None

        # 2. Prepare Payload
        password_string_for_payload = f"{dob_year}-{str(dob_month_val).zfill(2)}-{str(dob_day).zfill(2)}"
        payload = {
            config.PRN_FIELD_NAME: prn,
            config.DAY_FIELD_NAME: dob_day,
            config.MONTH_FIELD_NAME: dob_month_val,
            config.YEAR_FIELD_NAME: dob_year,
            config.PASSWORD_FIELD_NAME: password_string_for_payload,
        }

        # Handle hidden fields
        hidden_inputs = login_form.find_all("input", {"type": "hidden"})
        for hidden_input in hidden_inputs:
            name = hidden_input.get("name")
            value = hidden_input.get("value")
            if name and name not in payload:
                payload[name] = value if value is not None else ""

        # 3. Post Login
        form_action = login_form.get("action")
        actual_post_url = urljoin(config.LOGIN_URL, form_action) if form_action else config.FORM_ACTION_URL
        
        response_post = session.post(actual_post_url, data=payload, timeout=20)
        response_post.raise_for_status()
        welcome_page_html = response_post.text

        # 4. Verify Login
        if user_full_name_for_check.lower() in welcome_page_html.lower() or "logout" in welcome_page_html.lower():
            print(f"Login successful for {user_full_name_for_check}.")
            return session, welcome_page_html
        else:
            print("Login failed or dashboard not reached.")
            return None, None

    except Exception as e:
        print(f"Error during login: {e}")
        return None, None

def extract_attendance_from_welcome_page(welcome_page_html):
    """
    Extracts attendance from the dashboard Gauge Chart logic.
    """
    if not welcome_page_html: return []
    soup = BeautifulSoup(welcome_page_html, "html.parser")
    attendance_data = []
    
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and "gaugeTypeMulti" in script.string:
            # Regex to find the data array: [['Subject', 85], ['Subject2', 90]]
            columns_match = re.search(r"columns\s*:\s*(\[[\s\S]*?\])\s*,\s*type\s*:\s*\"gauge\"", script.string)
            if columns_match:
                columns_str = columns_match.group(1)
                # Extract pairs: ['Subject Name', Value]
                pairs = re.findall(r"\[\s*['\"](.*?)['\"]\s*,\s*(\d+)\s*\]", columns_str)
                for subject, value in pairs:
                    attendance_data.append({
                        "subject": subject.strip(),
                        "percentage": int(value)
                    })
                return attendance_data
    return []

def get_cie_detail_urls(dashboard_html):
    """
    Parses the dashboard to find the URL for each subject's "CIE" detail page.
    Returns a dict: { "Subject Name": "URL" }
    """
    soup = BeautifulSoup(dashboard_html, "html.parser")
    subject_urls = {}

    # The HTML you showed uses <ul uk-tab> with onclick="window.location.href='...'"
    # It might also use standard <a href> in the table list.
    
    # Strategy 1: Look for the "Course registration" table (First screenshot)
    # The "CIE" button usually has a link containing 'task=ciedetails'
    links = soup.find_all("a", href=True)
    for link in links:
        href = link['href']
        if "task=ciedetails" in href:
            # Try to find the course code in the same row
            row = link.find_parent("tr")
            if row:
                cols = row.find_all("td")
                if cols:
                    subject_code = cols[0].get_text(strip=True)
                    subject_urls[subject_code] = href
                    continue

    # Strategy 2: Look for Tab-based layout (onclick events)
    # <a href="#" onclick="window.location.href='index.php?option=...task=ciedetails...'">CSC702</a>
    tabs = soup.find_all("a", onclick=True)
    for tab in tabs:
        onclick_text = tab['onclick']
        if "task=ciedetails" in onclick_text:
            # Extract URL from: window.location.href='URL'
            match = re.search(r"href=['\"](.*?)['\"]", onclick_text)
            if match:
                url = match.group(1)
                # Use text inside <a> as subject code (e.g., "CSC702")
                subject_code = tab.get_text(strip=True)
                if subject_code:
                    subject_urls[subject_code] = url

    print(f"Found {len(subject_urls)} subject detail links.")
    return subject_urls

def scrape_subject_detail_page(session, url):
    """
    Visits a subject's detail page and scrapes the 'uk-table' for marks.
    Returns: { "ExamName": { "obtained": 16.0, "max": 20.0 } }
    """
    full_url = urljoin(config.LOGIN_URL, url)
    try:
        response = session.get(full_url, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        
        marks_data = {}
        
        # Find the table with class 'uk-table cn-cie-table'
        table = soup.find("table", class_="cn-cie-table")
        if not table:
            return {}

        # 1. Extract Headers (Exam Names)
        # The headers are in the <thead>. Note: There are empty <th> for spacing in your HTML.
        headers = []
        header_row = table.find("thead").find("tr")
        for th in header_row.find_all("th"):
            text = th.get_text(strip=True)
            # Only keep headers that look like exams (ignore 'Attendance', 'Eligibility', empty)
            if text and text not in ["Attendance", "Eligibility", "Final IA"]:
                headers.append(text)
        
        # 2. Extract Values (Row 1)
        # Your HTML shows the marks are in the first <tr> of <tbody>
        body_row = table.find("tbody").find("tr")
        if not body_row:
            return {}
            
        cells = body_row.find_all("td")
        
        # Map headers to cells. 
        # Note: Your table has empty <td> cells between marks. We need to filter them or count carefully.
        # Strategy: Get all non-empty text cells that contain a slash '/'
        
        valid_cells = [td.get_text(strip=True) for td in cells if "/" in td.get_text(strip=True)]
        
        # Safety check: Do we have the same number of headers and value cells?
        # If headers are [TH-ISE1, TH-ISE2, MSE, ESE] and cells are [16/20, 15/20, ...], we match them.
        
        for i, exam_name in enumerate(headers):
            if i < len(valid_cells):
                raw_text = valid_cells[i] # e.g., "16.00/20"
                try:
                    parts = raw_text.split('/')
                    if len(parts) == 2:
                        obt = float(parts[0])
                        max_m = float(parts[1])
                        
                        marks_data[exam_name] = {
                            "obtained": obt,
                            "max": max_m
                        }
                except ValueError:
                    continue

        return marks_data

    except Exception as e:
        print(f"Error scraping detail page {url}: {e}")
        return {}

def extract_cie_marks(session_or_html, html_content=None):
    """
    MAIN FUNCTION called by app.py.
    Now accepts 'session' as the first argument (tuple unpacking handled inside if needed)
    to allow deep scraping.
    """
    # Handle legacy calls where only HTML was passed
    session = None
    dashboard_html = ""

    if isinstance(session_or_html, requests.Session):
        session = session_or_html
        dashboard_html = html_content
    else:
        # If app.py passed only HTML (old version), we can't deep scrape. 
        # Return None or try regex on dashboard (Old logic).
        # Ideally, app.py should be updated to pass (session, html).
        print("Warning: Session not provided to extract_cie_marks. Cannot fetch max marks.")
        return {}

    all_subjects_data = {}
    
    # 1. Get Links
    subject_links = get_cie_detail_urls(dashboard_html)
    
    # 2. Iterate and Scrape
    print("Starting deep scrape of subject pages...")
    for subject, url in subject_links.items():
        # Clean subject name (e.g., remove newlines)
        subject = subject.strip()
        
        # Scrape
        marks = scrape_subject_detail_page(session, url)
        
        if marks:
            all_subjects_data[subject] = marks
            
    return all_subjects_data

def extract_detailed_attendance_info(session, welcome_page_html):
    """
    Extracts detailed attendance (Conducted vs Attended).
    """
    if not welcome_page_html or not session: return {}

    soup = BeautifulSoup(welcome_page_html, "html.parser")
    detailed_data = {}
    
    # Look for the "Attendance" buttons (usually link to task=attendencelist)
    links = soup.find_all("a", href=True)
    for link in links:
        if "task=attendencelist" in link['href']:
            # Attempt to find Subject Name
            # It might be in the same row
            row = link.find_parent("tr")
            if row:
                cols = row.find_all("td")
                if cols:
                    subject = cols[0].get_text(strip=True)
                    
                    # Go to page
                    try:
                        full_url = urljoin(config.LOGIN_URL, link['href'])
                        resp = session.get(full_url, timeout=10)
                        det_soup = BeautifulSoup(resp.content, "html.parser")
                        
                        # Parse Green (Present) and Red (Absent) spans
                        # Example: <span class="cn-color-green">[12]</span>
                        green_span = det_soup.find("span", class_="cn-color-green")
                        red_span = det_soup.find("span", class_="cn-color-red")
                        
                        present = 0
                        absent = 0
                        
                        if green_span:
                            m = re.search(r"\[(\d+)\]", green_span.get_text())
                            if m: present = int(m.group(1))
                        
                        if red_span:
                            m = re.search(r"\[(\d+)\]", red_span.get_text())
                            if m: absent = int(m.group(1))

                        detailed_data[subject] = {
                            "attended": present,
                            "conducted": present + absent
                        }
                    except:
                        pass
    return detailed_data