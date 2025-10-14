import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
from io import BytesIO
from datetime import timedelta
import os

st.set_page_config(page_title="Ahrefs Batch Extractor", layout="centered")

# Load CSS
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except:
        pass

load_css()

# ---------------------------- 
# 1️⃣ User inputs
# ---------------------------- 
uploaded_file = st.file_uploader("Upload CSV/XLSX file containing URLs To check website's Traffic", type=["csv", "xlsx"])
max_wait_time = st.number_input(
    "Set maximum wait time per URL (seconds, min 30)",
    min_value=30, max_value=50000, value=30, step=5
)

# ---------------------------- 
# 2️⃣ File handling
# ---------------------------- 
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    total_urls = len(df)
    estimated_total_time = total_urls * max_wait_time
    st.markdown("<p style='color:#4B0082;'>∵ More Time ∝ More Perfect Results</p>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:large;margin-bottom:0px;'>Preview of uploaded file:</p>", unsafe_allow_html=True)
    st.dataframe(df.head())

    url_column = st.selectbox("Select the column containing URLs", df.columns)
    start_btn = st.button("Start Processing")

    # ---------------------------- 
    # 3️⃣ Start processing
    # ---------------------------- 
    if start_btn:
        # Placeholders for dynamic updates
        processing_text = st.empty()
        time_placeholder = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()

        processing_text.markdown("**Processing... Please wait!**")

        # Initialize Chrome driver with enhanced options
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless=new')  # Use new headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36')

        # Try common Chromium binary paths
        possible_binary_paths = [
            "/usr/bin/chromium-browser",
            "/usr/lib/chromium-browser/chromium-browser",
            "/usr/bin/chromium"
        ]
        binary_found = False
        for binary_path in possible_binary_paths:
            if os.path.exists(binary_path):
                chrome_options.binary_location = binary_path
                binary_found = True
                break

        if not binary_found:
            st.error("Chromium binary not found at common paths. Ensure 'chromium-browser' is installed via packages.txt.")
            st.stop()

        try:
            # Use webdriver_manager to handle chromedriver, matching Chromium 141
            service = Service(ChromeDriverManager(driver_version="141.0.7390.65").install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            # Log browser version for debugging
            st.write(f"Chromium version: {driver.capabilities['browserVersion']}")
        except Exception as e:
            st.error(f"Failed to initialize WebDriver: {str(e)}. Ensure ChromeDriver matches Chromium version 141.0.7390.65 and chromium-browser is installed.")
            st.stop()

        # Results and counters
        results = []
        success_count = 0
        fail_count = 0
        batch_start_time = time.time()

        for idx, user_url in enumerate(df[url_column], start=1):
            status = "Success"
            with st.spinner(f"Processing URL {idx}/{total_urls}: {user_url}"):
                try:
                    ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={user_url}&mode=subdomains"
                    driver.get(ahrefs_url)

                    # Log browser console for debugging
                    browser_logs = driver.get_log('browser')
                    if browser_logs:
                        st.write(f"Browser logs for {user_url}: {browser_logs}")

                    # ---------------------------- 
                    # Cloudflare handling
                    # ---------------------------- 
                    start_time = time.time()
                    cf_cleared = False
                    while True:
                        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                        if "cf_clearance" in cookies:
                            cf_cleared = True
                            break
                        if time.time() - start_time > max_wait_time:
                            break
                        time.sleep(2)

                    if not cf_cleared:
                        status = "Failed: Cloudflare"
                        raise Exception("Cloudflare not cleared")

                    # ---------------------------- 
                    # Extract modal
                    # ---------------------------- 
                    try:
                        modal_elements = WebDriverWait(driver, max_wait_time).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                        )
                    except:
                        status = "Failed: No modal"
                        raise Exception("No modal found")

                    elem = modal_elements[0]

                    def safe_extract_css(selector):
                        try:
                            return WebDriverWait(elem, max_wait_time).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            ).text.strip()
                        except:
                            return "Error"

                    # Extract data
                    website_name = safe_extract_css("h2")
                    website_traffic = safe_extract_css(
                        "span.css-vemh4e.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1x5n6ob"
                    )
                    traffic_value = safe_extract_css(
                        "span.css-6s0ffe.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1jyb9g4"
                    )
                    top_country_raw = safe_extract_css("table:nth-of-type(1) tbody tr:first-child")
                    top_keyword_raw = safe_extract_css("table:nth-of-type(2) tbody tr:first-child")

                    # Process country
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    if country_match:
                        top_country = country_match.group(1)
                        top_country_share = country_match.group(2)
                    else:
                        top_country = top_country_raw
                        top_country_share = "Error"

                    # Process keyword
                    keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw)
                    if keyword_match:
                        top_keyword = keyword_match.group(1)
                        keyword_position = keyword_match.group(2)
                        top_keyword_traffic = keyword_match.group(3)
                    else:
                        top_keyword = top_keyword_raw
                        keyword_position = "Error"
                        top_keyword_traffic = "Error"

                    # Append results
                    results.append({
                        "URL": user_url,
                        "Website": website_name,
                        "Website Traffic": website_traffic,
                        "Top Country": top_country,
                        "Top Country Share": top_country_share
                    })
                    success_count += 1

                except Exception as e:
                    results.append({
                        "URL": user_url,
                        "Website": "Error",
                        "Website Traffic": "Error",
                        "Top Country": "Error",
                        "Top Country Share": "Error",
                    })
                    fail_count += 1

                # ---------------------------- 
                # Live updates
                # ---------------------------- 
                progress_bar.progress(min(int(idx / total_urls * 100), 100))
                table_area.dataframe(pd.DataFrame(results))
                stats_area.markdown(
                    f"""
                    <p class="states_p">Total URLs: <b>{total_urls}</b></p>
                    <p class="states_p">Processed: <b>{idx}</b></p>
                    <p class="states_p">Success: <b>{success_count}</b></p>
                    <p class="states_p">Failed: <b>{fail_count}</b></p>
                    """, unsafe_allow_html=True
                )

                # Estimated remaining time
                elapsed = time.time() - batch_start_time
                avg_per_url = elapsed / idx
                remaining_time = avg_per_url * (total_urls - idx)
                
        driver.quit()
        processing_text.markdown("**Batch processing completed!**")

        # ---------------------------- 
        # Download CSV
        # ---------------------------- 
        st.markdown("<p style='font-weight:400;margin:20px 0px;'>If there are any errors, recheck the website with increased time...</p>", unsafe_allow_html=True)
        if results:
            result_df = pd.DataFrame(results)
            csv_buffer = BytesIO()
            result_df.to_csv(csv_buffer, index=False)
            st.download_button(
                "Download Results as CSV",
                csv_buffer.getvalue(),
                file_name="ahrefs_batch_results.csv",
                mime="text/csv"
            )
        st.success("All URLs processed successfully!")

