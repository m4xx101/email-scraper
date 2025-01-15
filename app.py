from flask import Flask, request, render_template, send_file, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyhunter import PyHunter
import threading
import time
import os
import re
import ssl
import random
import requests
import argparse
import csv
from datetime import datetime
from RecaptchaSolver import RecaptchaSolver

# Flask App Initialization
app = Flask(__name__)

# Ensure SSL module is loaded
if not hasattr(ssl, 'CERT_NONE'):
    raise ImportError("The 'ssl' module is required but not available in this environment.")

# Load User Agents
def load_user_agents(useragent_file):
    try:
        with open(useragent_file, 'r') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        return ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"]

def is_recaptcha_present(driver):
    """Detect if Google reCAPTCHA is present."""
    try:
        # Check for reCAPTCHA iframe
        driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha')]")
        return True
    except NoSuchElementException:
        return False

# random delays 
def random_delay(min_delay=3, max_delay=6):
    time.sleep(random.uniform(min_delay, max_delay))

def simulate_scrolling(driver):
    scroll_pause_time = random.uniform(1, 3)
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

# Google Scraping with reCAPTCHA Handling
def gather_contacts(company, domain, chrome_driver_path, user_agents):
    print(f"🟢 Starting scraping for {company}...")

    # Configure Chrome options
    chrome_options = Options()
    user_agent = random.choice(user_agents)
    chrome_options.add_argument(f'user-agent={user_agent}')
    chrome_options.add_argument("--headless=new")  # Switch to headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # Start Chrome driver
    service = Service(executable_path=chrome_driver_path)
    browser = webdriver.Chrome(service=service, options=chrome_options)

    # Anti-detection script
    browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """
    })

    all_results = []

    try:
        search_query = f'site:linkedin.com/in/ "{company}"'
        browser.get('https://www.google.com')
        random_delay()

        # Check and solve reCAPTCHA if detected
        if is_recaptcha_present(browser):
            print("🔍 reCAPTCHA detected. Attempting to solve...")
            recaptcha_solver = RecaptchaSolver(browser)
            try:
                recaptcha_solver.solveCaptcha()
                print("✅ reCAPTCHA solved.")
            except Exception as e:
                print(f"❌ Failed to solve reCAPTCHA: {e}")
                browser.quit()
                return []

        # Enter search query
        search_box = browser.find_element(By.NAME, 'q')
        search_box.send_keys(search_query)
        search_box.submit()
        random_delay()

        page_num = 1
        while True:
            print(f"🔎 Scraping Google page {page_num}...")
            simulate_scrolling(browser)
            results = browser.find_elements(By.CSS_SELECTOR, "h3")

            # Extract search result titles
            for result in results:
                text = result.text.strip()
                if text and text not in all_results:
                    all_results.append(text)

            # Check for "Next" button
            try:
                next_button = WebDriverWait(browser, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@id='pnnext']"))
                )
                next_button.click()
                random_delay()
                page_num += 1
            except (NoSuchElementException, TimeoutException):
                print("❗ No more pages or Next button not found.")
                break

    except (TimeoutException, WebDriverException) as e:
        print(f"❌ Error during scraping: {e}")

    finally:
        browser.quit()

    print(f"✅ Scraping completed. Total results: {len(all_results)}")
    return all_results
    

# Generate Emails
def create_emails(names, domain_name, format_option):
    print("🟢 Generating Emails...")
    emails = []
    format_options = {
        1: lambda first, last: f"{first[0]}{last}@{domain_name}",
        2: lambda first, last: f"{first}.{last}@{domain_name}",
        3: lambda first, last: f"{last}{first[0]}@{domain_name}",
        4: lambda first, last: f"{first}{last[0]}@{domain_name}",
    }
    for name in names:
        parts = name.split()
        if len(parts) >= 2:
            first, last = parts[0].lower(), parts[1].lower()
            emails.append(format_options[format_option](first, last))
    print(f"✅ Generated {len(emails)} emails.")
    return emails

# Fetch Emails from Dehashed
def fetch_dehashed_emails(api_key, username, domain):
    print("🟢 Fetching from Dehashed...")

    if not api_key or not username:
        print("⚠️ Dehashed API Key or Username not provided. Skipping...")
        return []

    url = f"https://api.dehashed.com/search?query=domain:{domain}&size=10000"
    headers = {'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, auth=(username, api_key))
        response.raise_for_status()

        data = response.json()
        emails = [entry['email'] for entry in data.get('entries', []) if 'email' in entry]

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
            print("❌ Unauthorized: Invalid Dehashed API Key or Username.")
        elif http_err.response.status_code == 403:
            print("❌ Forbidden: Access denied. Check your account permissions.")
        elif http_err.response.status_code == 429:
            print("❌ Rate Limit: Too many requests. Please wait and try again.")
        else:
            print(f"❌ HTTP error occurred: {http_err}")
        return []
    except requests.exceptions.RequestException as req_err:
        print(f"❌ Network error occurred: {req_err}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error occurred: {e}")
        return []

    print(f"✅ Fetched {len(emails)} emails from Dehashed.")
    return emails


# Fetch Emails from Hunter.io
def fetch_hunter_emails(api_key, domain):
    print("🟢 Fetching from Hunter.io...")
    
    if not api_key:
        print("⚠️ Hunter.io API Key not provided. Skipping...")
        return []

    hunter = PyHunter(api_key)
    emails, page = [], 0

    try:
        while True:
            data = hunter.domain_search(domain, limit=100, offset=page * 100)
            
            if 'errors' in data:
                print(f"❌ Hunter.io Error: {data['errors']}")
                break

            if not data or not data.get('emails'):
                break

            emails.extend(email['value'] for email in data['emails'])
            page += 1

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
            print("❌ Unauthorized: Invalid Hunter.io API Key.")
        elif http_err.response.status_code == 403:
            print("❌ Forbidden: Access denied. Check your account permissions.")
        elif http_err.response.status_code == 429:
            print("❌ Rate Limit: Too many requests. Please wait and try again.")
        else:
            print(f"❌ HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"❌ Network error occurred: {req_err}")
    except Exception as e:
        print(f"❌ Unexpected error occurred: {e}")

    print(f"✅ Fetched {len(emails)} emails from Hunter.io.")
    return emails

# Save Results
def save_results(output_dir, names, gen_emails, dehashed_emails, hunter_emails):
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'names.txt'), 'w') as f:
        f.write("\n".join(names))
    with open(os.path.join(output_dir, 'emails_generated.txt'), 'w') as f:
        f.write("\n".join(gen_emails))
    with open(os.path.join(output_dir, 'emails_dehashed.txt'), 'w') as f:
        f.write("\n".join(dehashed_emails))
    with open(os.path.join(output_dir, 'emails_hunterio.txt'), 'w') as f:
        f.write("\n".join(hunter_emails))

# Flask Web UI
@app.route('/', methods=['GET', 'POST'])
def home():
    result = None
    if request.method == 'POST':
        company = request.form['company']
        domain = request.form['domain']
        email_format = int(request.form['email_format'])
        dehashed_api = request.form.get('dehashed_api')
        dehashed_username = request.form.get('dehashed_username')
        hunter_api = request.form.get('hunter_api')
        user_agents = load_user_agents('uploaded_user_agents.txt')
        names = gather_contacts(company, domain, '/app/chromedriver', user_agents)
        gen_emails = create_emails(names, domain, email_format)
        dehashed_emails = fetch_dehashed_emails(dehashed_api, dehashed_username, domain)
        hunter_emails = fetch_hunter_emails(hunter_api, domain)

        result = {'emails': list(set(gen_emails + dehashed_emails + hunter_emails))}
    return render_template('index.html', result=result)

# CLI Support
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    parser = argparse.ArgumentParser(description="Advanced Email Scraper Tool")
    parser.add_argument('-i', '--interactive', action='store_true')
    parser.add_argument('-c', '--company')
    parser.add_argument('-d', '--domain')
    parser.add_argument('--output', help='Output directory')
    args = parser.parse_args()

    if args.interactive:
        app.run(debug=True)
