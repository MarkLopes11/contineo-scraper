import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import config

def login_and_get_welcome_page(prn, dob_day, dob_month_val, dob_year, user_full_name_for_check):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
        "Referer": config.LOGIN_URL
    })
    try:
        response_get = session.get(config.LOGIN_URL, timeout=20)
        response_get.raise_for_status()
        soup_login = BeautifulSoup(response_get.content, "html.parser")
        login_form = soup_login.find("form", {"id": "login-form"})
        
        if not login_form: return None, None

        password_string_for_payload = f"{dob_year}-{str(dob_month_val).zfill(2)}-{str(dob_day).zfill(2)}"
        payload = {
            config.PRN_FIELD_NAME: prn,
            config.DAY_FIELD_NAME: dob_day,
            config.MONTH_FIELD_NAME: dob_month_val,
            config.YEAR_FIELD_NAME: dob_year,
            config.PASSWORD_FIELD_NAME: password_string_for_payload,
        }

        hidden_inputs = login_form.find_all("input", {"type": "hidden"})
        for hidden_input in hidden_inputs:
            name = hidden_input.get("name")
            value = hidden_input.get("value")
            if name and name not in payload:
                payload[name] = value if value is not None else ""

        form_action = login_form.get("action")
        actual_post_url = urljoin(config.LOGIN_URL, form_action) if form_action else config.FORM_ACTION_URL
        
        response_post = session.post(actual_post_url, data=payload, timeout=20)
        response_post.raise_for_status()
        welcome_page_html = response_post.text

        if user_full_name_for_check.lower() in welcome_page_html.lower() or "logout" in welcome_page_html.lower():
            return session, welcome_page_html
        else:
            return None, None
    except Exception:
        return None, None

def extract_attendance_from_welcome_page(welcome_page_html):
    if not welcome_page_html: return []
    soup = BeautifulSoup(welcome_page_html, "html.parser")
    attendance_data = []
    
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and "gaugeTypeMulti" in script.string:
            columns_match = re.search(r"columns\s*:\s*(\[[\s\S]*?\])\s*,\s*type\s*:\s*\"gauge\"", script.string)
            if columns_match:
                columns_str = columns_match.group(1)
                pairs = re.findall(r"\[\s*['\"](.*?)['\"]\s*,\s*(\d+)\s*\]", columns_str)
                for subject, value in pairs:
                    attendance_data.append({
                        "subject": subject.strip(),
                        "percentage": int(value)
                    })
                return attendance_data
    return []

def get_cie_detail_urls(dashboard_html):
    soup = BeautifulSoup(dashboard_html, "html.parser")
    subject_urls = {}

    links = soup.find_all("a", href=True)
    for link in links:
        if "task=ciedetails" in link['href']:
            row = link.find_parent("tr")
            if row:
                cols = row.find_all("td")
                if cols:
                    subject_code = cols[0].get_text(strip=True)
                    subject_urls[subject_code] = link['href']

    if not subject_urls:
        tabs = soup.find_all("a", onclick=True)
        for tab in tabs:
            onclick_text = tab['onclick']
            if "task=ciedetails" in onclick_text:
                match = re.search(r"href=['\"](.*?)['\"]", onclick_text)
                if match:
                    url = match.group(1)
                    subject_code = tab.get_text(strip=True)
                    if subject_code:
                        subject_urls[subject_code] = url
    return subject_urls

def _parse_table_marks_safely(soup):
    """
    Helper: Extracts marks from the HTML Table using strict index alignment.
    Returns a dict: {'ExamName': {'obtained': X, 'max': Y}}
    """
    table_marks = {}
    table = soup.find("table", class_="cn-cie-table")
    if table:
        thead = table.find("thead")
        tbody = table.find("tbody")
        if thead and tbody:
            header_cells = thead.find_all("th")
            # Find the first data row
            body_row = tbody.find("tr")
            if body_row:
                body_cells = body_row.find_all("td")
                
                # Iterate by index to keep alignment correct
                limit = min(len(header_cells), len(body_cells))
                for i in range(limit):
                    header_text = header_cells[i].get_text(strip=True)
                    cell_text = body_cells[i].get_text(strip=True)
                    
                    if not header_text or header_text in ["Attendance", "Eligibility", "Final IA"]: continue
                    
                    # Only accept if format is "Obtained/Max" (e.g., "18/20" or "0/20")
                    if "/" in cell_text:
                        try:
                            parts = cell_text.split('/')
                            table_marks[header_text] = {
                                "obtained": float(parts[0]),
                                "max": float(parts[1])
                            }
                        except: pass
    return table_marks

def scrape_subject_detail_page(session, url):
    full_url = urljoin(config.LOGIN_URL, url)
    try:
        response = session.get(full_url, timeout=15)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        
        final_marks_data = {}
        
        # 1. Parse Table Data (Source of Truth for "Is exam taken?")
        table_data = _parse_table_marks_safely(soup)

        # 2. Parse Chart Data (Source of Truth for "Correct Column Mapping")
        chart_match = re.search(r'var\s+chartData\s*=\s*(\[\{.*?\}\]);', html, re.DOTALL)
        
        if chart_match:
            json_str = chart_match.group(1)
            # Extract: { "xaxis": "ExamName", "maxmarks": 20, "optainmarks": 15.5 }
            objects = re.findall(r'\{[^{}]*?"xaxis"\s*:\s*"([^"]+)"[^{}]*?"maxmarks"\s*:\s*([\d\.]+)[^{}]*?"optainmarks"\s*:\s*([\d\.]+)[^{}]*?\}', json_str, re.DOTALL)
            
            for exam_name, max_val, obt_val in objects:
                try:
                    obt = float(obt_val)
                    max_m = float(max_val)
                    
                    # --- HYBRID VALIDATION ---
                    if obt == 0:
                        # If Chart says 0, verify with Table.
                        # If Table has an explicit entry for this exam and it is 0, accept it.
                        # If Table does NOT have this exam (cell was empty), reject the 0.
                        if exam_name in table_data and table_data[exam_name]['obtained'] == 0:
                            final_marks_data[exam_name] = {"obtained": 0.0, "max": max_m}
                        else:
                            # Placeholder 0 in chart, Empty in table -> Skip
                            continue
                    else:
                        # Non-zero marks are trusted from Chart
                        final_marks_data[exam_name] = {"obtained": obt, "max": max_m}
                except ValueError:
                    pass
            
            if final_marks_data:
                return final_marks_data

        # 3. Fallback: If Chart failed entirely, return Table Data
        return table_data

    except Exception as e:
        print(f"Error scraping detail page {url}: {e}")
        return {}

def extract_cie_marks(session, html_content=None):
    if not isinstance(session, requests.Session): return {}
    all_subjects_data = {}
    subject_links = get_cie_detail_urls(html_content)
    
    for subject, url in subject_links.items():
        subject = subject.strip()
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
    
    links = soup.find_all("a", href=True)
    for link in links:
        if "task=attendencelist" in link['href']:
            row = link.find_parent("tr")
            if row:
                cols = row.find_all("td")
                if cols:
                    subject = cols[0].get_text(strip=True)
                    try:
                        full_url = urljoin(config.LOGIN_URL, link['href'])
                        resp = session.get(full_url, timeout=10)
                        det_soup = BeautifulSoup(resp.content, "html.parser")
                        
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

def extract_student_semester(html_content):
    if not html_content: return None
    soup = BeautifulSoup(html_content, "html.parser")
    match = re.search(r"SEM\s+(\d+)", soup.get_text(), re.IGNORECASE)
    return int(match.group(1)) if match else None