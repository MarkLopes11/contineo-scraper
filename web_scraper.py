# web_scraper.py
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin # Moved import here
import config # Import your config file

def login_and_get_welcome_page(prn, dob_day, dob_month_val, dob_year, user_full_name_for_check):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
        "Referer": config.LOGIN_URL
    })
    try:
        # print(f"Navigating to login page: {config.LOGIN_URL}")
        response_get = session.get(config.LOGIN_URL, timeout=20)
        response_get.raise_for_status()
        # print("Successfully fetched login page.")
        soup_login = BeautifulSoup(response_get.content, "html.parser")
        login_form = soup_login.find("form", {"id": "login-form"})
        if not login_form:
            print("Could not find the login form with id='login-form'. This is critical.")
            return None, None
        # print("Successfully found login form with id='login-form'.")
        password_string_for_payload = f"{dob_year}-{str(dob_month_val).zfill(2)}-{str(dob_day).zfill(2)}"
        # print(f"Constructed password string for '{config.PASSWORD_FIELD_NAME}': {password_string_for_payload}")
        payload = {
            config.PRN_FIELD_NAME: prn,
            config.DAY_FIELD_NAME: dob_day,
            config.MONTH_FIELD_NAME: dob_month_val,
            config.YEAR_FIELD_NAME: dob_year,
            config.PASSWORD_FIELD_NAME: password_string_for_payload,
        }
        hidden_inputs = login_form.find_all("input", {"type": "hidden"})
        if hidden_inputs:
            # print("Found hidden fields in the targeted login form (id='login-form'):")
            for hidden_input in hidden_inputs:
                name = hidden_input.get("name")
                value = hidden_input.get("value")
                if name:
                    if name not in [config.PRN_FIELD_NAME, config.DAY_FIELD_NAME, config.MONTH_FIELD_NAME, config.YEAR_FIELD_NAME, config.PASSWORD_FIELD_NAME]:
                        payload[name] = value if value is not None else ""
                        # print(f"  Added hidden field: {name}={payload[name]}")
        # else:
            # print("No hidden input fields found in the login form (id='login-form').")
        # print(f"Payload to be sent: {payload}")
        form_action = login_form.get("action")
        actual_post_url = config.FORM_ACTION_URL
        if form_action:
            actual_post_url = urljoin(config.LOGIN_URL, form_action)
        # print(f"Attempting to POST login data to: {actual_post_url}")
        response_post = session.post(actual_post_url, data=payload, timeout=20)
        response_post.raise_for_status()
        # print(f"POST request completed. Status: {response_post.status_code}")
        # print(f"Current URL after POST: {response_post.url}")
        welcome_page_html = response_post.text
        login_successful = False
        if user_full_name_for_check.lower() in welcome_page_html.lower():
            print(f"Login successful! Welcome {user_full_name_for_check}.")
            login_successful = True
        elif "id=\"gaugeTypeMulti\"" in welcome_page_html: 
            print(f"Login successful (found attendance chart)! Welcome {user_full_name_for_check}.")
            login_successful = True
        elif "id=\"stackedBarChart_1\"" in welcome_page_html: 
            print(f"Login successful (found CIE chart)! Welcome {user_full_name_for_check}.")
            login_successful = True
        else:
            temp_soup_post = BeautifulSoup(welcome_page_html, "html.parser")
            if temp_soup_post.find("form", {"id": "login-form"}):
                print("Login FAILED. The page after POST still contains the login form.")
                if "invalid username or password" in welcome_page_html.lower():
                     print("Reason: Invalid username or password detected on page.")
            else:
                print("Login status uncertain. User identifier not found, dashboard elements not found, but it's not clearly the login page either.")
        if not login_successful:
            return None, None
        return session, welcome_page_html
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred during login: {e}")
        if e.response is not None: print(f"Response content (first 500 chars): {e.response.text[:500]}...")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"A request error occurred during login: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during login: {e}")
        return None, None

def extract_attendance_from_welcome_page(welcome_page_html):
    if not welcome_page_html: return None
    soup = BeautifulSoup(welcome_page_html, "html.parser")
    attendance_data = []
    found_data_script = False
    scripts = soup.find_all("script")
    for i, script in enumerate(scripts):
        if script.string: 
            script_content = script.string.strip()
            if "gaugeTypeMulti" in script_content and "type: \"gauge\"" in script_content and "columns:" in script_content:
                data_block_regex = r"data\s*:\s*(\{[\s\S]*?type\s*:\s*\"gauge\"[\s\S]*?\})"
                data_block_match = re.search(data_block_regex, script_content, re.DOTALL)
                if data_block_match:
                    data_object_str = data_block_match.group(1) 
                    columns_array_capture_regex = r"columns\s*:\s*(\[[\s\S]*?\])\s*,\s*type\s*:\s*\"gauge\""
                    columns_match = re.search(columns_array_capture_regex, data_object_str, re.DOTALL)
                    if columns_match:
                        columns_the_actual_array_str = columns_match.group(1).strip() 
                        pair_regex = r"\[\s*['\"]([^'\"]+)['\"]\s*,\s*(\d+)\s*\]"
                        subject_value_pairs = re.findall(pair_regex, columns_the_actual_array_str)
                        if subject_value_pairs:
                            for subject, value in subject_value_pairs:
                                attendance_data.append({"subject": subject.strip(), "percentage": int(value)})
                            found_data_script = True 
                            print("  Successfully parsed attendance data.")
                            break 
    if not found_data_script: 
        print("\nCould not find or parse the specific attendance chart data.")
        return None
    return attendance_data

def extract_cie_marks(welcome_page_html):
    if not welcome_page_html: return None
    soup = BeautifulSoup(welcome_page_html, "html.parser")
    cie_data = {} 
    scripts = soup.find_all("script")
    found_cie_script = False
    for i, script in enumerate(scripts):
        if script.string:
            script_content = script.string.strip()
            if "stackedBarChart_1" in script_content and "type: \"bar\"" in script_content and "categories:" in script_content:
                chart_config_regex = r"bb\.generate\s*\(\s*(\{[\s\S]*?bindto\s*:\s*[\"']#stackedBarChart_1[\"'][\s\S]*?\}\s*)\s*\)\s*;"
                bb_generate_match = re.search(chart_config_regex, script_content, re.DOTALL)
                if bb_generate_match:
                    chart_config_str = bb_generate_match.group(1)
                    categories_match = re.search(r"categories\s*:\s*(\[[\s\S]*?\])", chart_config_str, re.DOTALL)
                    subjects = []
                    if categories_match:
                        categories_str = categories_match.group(1)
                        subjects = re.findall(r"['\"]([^'\"]+)['\"]", categories_str)
                    else: continue 
                    if not subjects: continue
                    columns_data_match = re.search(r"columns\s*:\s*(\[[\s\S]*?\])\s*,\s*type\s*:\s*\"bar\"", chart_config_str, re.DOTALL)
                    if columns_data_match:
                        columns_str = columns_data_match.group(1)
                        series_regex = r"\[\s*['\"]([^'\"]+)['\"]\s*([^\]]*)?\s*\]"
                        all_series_matches = re.findall(series_regex, columns_str)
                        for exam_type, marks_values_str in all_series_matches:
                            parsed_marks = []
                            if marks_values_str: 
                                individual_mark_items = marks_values_str.strip(',').split(',')
                                for mark_val_raw in individual_mark_items:
                                    mark_val = mark_val_raw.strip()
                                    if mark_val.lower() == 'null': parsed_marks.append(None)
                                    elif mark_val.startswith('"') and mark_val.endswith('"'):
                                        val_inside_quotes = mark_val[1:-1]
                                        if val_inside_quotes.lower() == 'null': parsed_marks.append(None)
                                        elif not val_inside_quotes: parsed_marks.append(None)
                                        else:
                                            try: parsed_marks.append(float(val_inside_quotes))
                                            except ValueError: parsed_marks.append(val_inside_quotes) 
                                    elif not mark_val: parsed_marks.append(None)
                                    else: 
                                        try: parsed_marks.append(float(mark_val))
                                        except ValueError: parsed_marks.append(mark_val)
                            for idx, subject_code in enumerate(subjects):
                                if subject_code not in cie_data: cie_data[subject_code] = {}
                                if idx < len(parsed_marks): cie_data[subject_code][exam_type] = parsed_marks[idx]
                                else: cie_data[subject_code][exam_type] = None 
                        found_cie_script = True 
                        print(f"  Successfully parsed CIE marks for {len(subjects)} subjects and {len(all_series_matches)} exam types.")
                        break 
    if not found_cie_script:
        print("\nCould not find or parse the CIE marks data from any script tag.")
        return None
    return cie_data