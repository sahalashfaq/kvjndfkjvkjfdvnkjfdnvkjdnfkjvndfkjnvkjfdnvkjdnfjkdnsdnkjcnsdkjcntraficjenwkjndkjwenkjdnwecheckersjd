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
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Ahrefs Batch Extractor", layout="centered")

# Embed minimal CSS directly
st.markdown("""
<style>
    .states_p { font-size: 16px; margin: 5px 0; }
    p { font-size: 14px; color: #333; }
    .debug-log { font-size: 12px; color: #666; }
</style>
""", unsafe_allow_html=True)

# Debug mode toggle
debug_mode = st.checkbox("Enable Debug Mode", value=False)

# ---------------------------- 
# 1️⃣ User inputs
# ---------------------------- 
uploaded_file = st.file_uploader("Upload CSV/XLSX file containing URLs To check website's Traffic", type=["csv", "xlsx"])
max_wait_time = st.number_input(
    "Set maximum wait time per URL (seconds, min 30)",
    min_value=30, max_value=50000, value=60, step=5
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
        debug_area = st.empty() if debug_mode else None

        def log_debug(message):
            if debug_mode:
                logger.info(message)
                debug_area.markdown(f"<p class='debug-log'>{message}</p>", unsafe_allow_html=True)

        processing_text.markdown("**Processing... Please wait!**")

        # Initialize Chrome driver with optimized options
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless=new')  # Use new headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--window-size=1920,1080')  # Set window size to mimic real browser
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-client-side-phishing-detection')
        chrome_options.add_argument('--disable-hang-monitor')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36')

        # Try common Chromium binary paths
        possible_binary_paths = [
            "/usr/bin/chromium-browser",
            "/usr/lib/chromium-browser/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium"
        ]
        binary_found = False
        for binary_path in possible_binary_paths:
            if os.path.exists(binary_path):
                chrome_options.binary_location = binary_path
                binary_found = True
                log_debug(f"Chromium binary found at: {binary_path}")
                break

        if not binary_found:
            st.error("Chromium binary not found at common paths. Ensure 'chromium-browser' is installed via packages.txt.")
            st.stop()

        def initialize_driver():
            try:
                service = Service(ChromeDriverManager(driver_version="141.0.7390.65").install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.set_page_load_timeout(max_wait_time)
                log_debug(f"Chromium version: {driver.capabilities['browserVersion']}")
                return driver
            except Exception as e:
                st.error(f"Failed to initialize WebDriver: {str(e)}. Ensure ChromeDriver matches Chromium version 141.0.7390.65 and chromium-browser is installed.")
                st.stop()

        driver = initialize_driver()

        # Results and counters
        results = []
        success_count = 0
        fail_count = 0
        batch_start_time = time.time()

        for idx, user_url in enumerate(df[url_column], start=1):
            status = "Success"
            with st.spinner(f"Processing URL {idx}/{total_urls}: {user_url}"):
                try:
                    # Clean URL
                    user_url = user_url.strip()
                    if not user_url.startswith(('http://', 'https://')):
                        user_url = 'https://' + user_url
                    ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={user_url}&mode=subdomains"
                    log_debug(f"Navigating to: {ahrefs_url}")

                    # Retry navigation up to 3 times
                    max_nav_attempts = 3
                    for attempt in range(1, max_nav_attempts + 1):
                        try:
                            driver.get(ahrefs_url)
                            log_debug(f"Navigation successful for {user_url} on attempt {attempt}")
                            break
                        except Exception as e:
                            log_debug(f"Navigation failed for {user_url} on attempt {attempt}: {str(e)}")
                            if attempt == max_nav_attempts:
                                raise Exception(f"Navigation failed after {max_nav_attempts} attempts: {str(e)}")
                            # Restart driver if session is invalid
                            try:
                                driver.quit()
                            except:
                                pass
                            driver = initialize_driver()
                            time.sleep(2)

                    # Log page source for debugging
                    try:
                        page_source = driver.page_source[:500]  # Truncate for brevity
                        log_debug(f"Page source preview for {user_url}: {page_source}")
                    except Exception as e:
                        log_debug(f"Failed to get page source for {user_url}: {str(e)}")

                    # ---------------------------- 
                    # Cloudflare handling
                    # ---------------------------- 
                    start_time = time.time()
                    cf_cleared = False
                    max_cf_attempts = 3
                    for attempt in range(1, max_cf_attempts + 1):
                        log_debug(f"Cloudflare check attempt {attempt} for {user_url}")
                        try:
                            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                            if "cf_clearance" in cookies:
                                cf_cleared = True
                                log_debug(f"Cloudflare cleared for {user_url}")
                                break
                        except Exception as e:
                            log_debug(f"Error checking cookies for {user_url}: {str(e)}")
                        if time.time() - start_time > max_wait_time:
                            log_debug(f"Cloudflare timeout after {max_wait_time} seconds for {user_url}")
                            break
                        time.sleep(5)  # Increased interval for Cloudflare
                        # Refresh page to trigger Cloudflare check
                        if attempt < max_cf_attempts:
                            try:
                                driver.refresh()
                                log_debug(f"Page refreshed for Cloudflare check on attempt {attempt}")
                            except Exception as e:
                                log_debug(f"Refresh failed for {user_url}: {str(e)}")
                                # Restart driver if session is invalid
                                try:
                                    driver.quit()
                                except:
                                    pass
                                driver = initialize_driver()

                    if not cf_cleared:
                        status = "Failed: Cloudflare"
                        log_debug(f"Cloudflare not cleared for {user_url}")
                        raise Exception("Cloudflare not cleared")

                    # ---------------------------- 
                    # Extract modal
                    # ---------------------------- 
                    try:
                        modal_elements = WebDriverWait(driver, max_wait_time).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                        )
                        log_debug(f"Modal found for {user_url}")
                    except:
                        status = "Failed: No modal"
                        log_debug(f"No modal found for {user_url}")
                        raise Exception("No modal found")

                    elem = modal_elements[0]

                    def safe_extract_css(selector, fallback_selector=None):
                        try:
                            element = WebDriverWait(elem, max_wait_time).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            text = element.text.strip()
                            log_debug(f"Extracted {selector}: {text}")
                            return text
                        except:
                            if fallback_selector:
                                try:
                                    element = WebDriverWait(elem, max_wait_time).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, fallback_selector))
                                    )
                                    text = element.text.strip()
                                    log_debug(f"Extracted fallback {fallback_selector}: {text}")
                                    return text
                                except:
                                    log_debug(f"Failed to extract {selector} or {fallback_selector}")
                                    return "Error"
                            log_debug(f"Failed to extract {selector}")
                            return "Error"

                    # Extract data with fallback selectors
                    website_name = safe_extract_css("h2", "h1")
                    website_traffic = safe_extract_css(
                        "span.css-vemh4e.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1x5n6ob",
                        "span[data-testid='traffic-value']"
                    )
                    traffic_value = safe_extract_css(
                        "span.css-6s0ffe.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1jyb9g4",
                        "span[data-testid='traffic-value-metric']"
                    )
                    top_country_raw = safe_extract_css(
                        "table:nth-of-type(1) tbody tr:first-child",
                        "table[data-testid='top-countries'] tbody tr:first-child"
                    )
                    top_keyword_raw = safe_extract_css(
                        "table:nth-of-type(2) tbody tr:first-child",
                        "table[data-testid='top-keywords'] tbody tr:first-child"
                    )

                    # Process country
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    if country_match:
                        top_country = country_match.group(1)
                        top_country_share = country_match.group(2)
                    else:
                        top_country = top_country_raw
                        top_country_share = "Error"
                    log_debug(f"Top country: {top_country}, Share: {top_country_share}")

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
                    log_debug(f"Top keyword: {top_keyword}, Position: {keyword_position}, Traffic: {top_keyword_traffic}")

                    # Append results
                    results.append({
                        "URL": user_url,
                        "Website": website_name,
                        "Website Traffic": website_traffic,
                        "Top Country": top_country,
                        "Top Country Share": top_country_share
                    })
                    success_count += 1
                    log_debug(f"Successfully processed {user_url}")

                except Exception as e:
                    results.append({
                        "URL": user_url,
                        "Website": "Error",
                        "Website Traffic": "Error",
                        "Top Country": "Error",
                        "Top Country Share": "Error",
                    })
                    fail_count += 1
                    log_debug(f"Error processing {user_url}: {str(e)}")
                    # Restart driver if session is invalid
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = initialize_driver()

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
                avg_per_url = elapsed / idx if idx > 0 else 0
                remaining_time = avg_per_url * (total_urls - idx)
                time_placeholder.markdown(
                    f"<p class='states_p'>Estimated time remaining: {timedelta(seconds=int(remaining_time))}</p>",
                    unsafe_allow_html=True
                )

        try:
            driver.quit()
        except:
            pass
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
