import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
from io import BytesIO

st.set_page_config(page_title="Ahrefs Batch Extractor", layout="centered")

# Load CSS (unchanged)
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        st.warning("No CSS loaded.")
load_css()

# User inputs
uploaded_file = st.file_uploader("Upload CSV/XLSX file with URLs", type=["csv", "xlsx"])
max_wait_time = st.number_input("Max wait time per URL (seconds, min 30)", min_value=30, max_value=50000, value=30, step=5)

if uploaded_file:
    # File handling
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    total_urls = len(df)
    st.markdown("<p style='color:var(--indigo-color);'>∵ More Time ∝ More Perfect Results</p>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:large;margin-bottom:0px;'>Preview of uploaded file:</p>", unsafe_allow_html=True)
    st.dataframe(df.head())
    url_column = st.selectbox("Select URL column", df.columns)
    start_btn = st.button("Start Processing")

    if start_btn:
        # Initialize placeholders
        processing_text = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()
        processing_text.markdown("**Processing... Please wait!**")

        # Set up Chrome options for Streamlit Cloud
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")

        # Initialize driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

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

                    # Cloudflare handling (limited without external service)
                    start_time = time.time()
                    cf_cleared = False
                    while time.time() - start_time < max_wait_time:
                        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                        if "cf_clearance" in cookies:
                            cf_cleared = True
                            break
                        time.sleep(2)

                    if not cf_cleared:
                        status = "Failed: Cloudflare"
                        raise Exception("Cloudflare not cleared")

                    # Extract modal
                    try:
                        modal_elements = WebDriverWait(driver, max_wait_time).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                        )
                        elem = modal_elements[0]
                    except:
                        status = "Failed: No modal"
                        raise Exception("No modal found")

                    def safe_extract_css(selector):
                        try:
                            return WebDriverWait(elem, max_wait_time).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            ).text.strip()
                        except:
                            return "Error"

                    # Extract data
                    website_name = safe_extract_css("h2")
                    website_traffic = safe_extract_css("span.css-vemh4e.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1x5n6ob")
                    traffic_value = safe_extract_css("span.css-6s0ffe.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1jyb9g4")
                    top_country_raw = safe_extract_css("table:nth-of-type(1) tbody tr:first-child")
                    top_keyword_raw = safe_extract_css("table:nth-of-type(2) tbody tr:first-child")

                    # Process country
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    top_country = country_match.group(1) if country_match else top_country_raw
                    top_country_share = country_match.group(2) if country_match else "Error"

                    # Process keyword
                    keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw)
                    top_keyword = keyword_match.group(1) if keyword_match else top_keyword_raw
                    keyword_position = keyword_match.group(2) if keyword_match else "Error"
                    top_keyword_traffic = keyword_match.group(3) if keyword_match else "Error"

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
                        "Top Country Share": "Error"
                    })
                    fail_count += 1
                    st.write(f"Error on {user_url}: {str(e)}")  # Log error for debugging

                # Live updates
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

        driver.quit()
        processing_text.markdown("**Batch processing completed!**")

        # Download CSV
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
