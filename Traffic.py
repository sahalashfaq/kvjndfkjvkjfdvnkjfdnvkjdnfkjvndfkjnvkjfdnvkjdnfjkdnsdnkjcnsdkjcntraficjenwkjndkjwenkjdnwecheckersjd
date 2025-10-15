import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
from io import BytesIO
from datetime import timedelta

st.set_page_config(page_title="Ahrefs Batch Extractor", layout="centered")

# Load CSS
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        st.warning("No CSS loaded.")

load_css()

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
    st.markdown("<p style='color:var(--indigo-color);'>∵ More Time ∝ More Perfect Results</p>",unsafe_allow_html=True)
    st.markdown("<p style='font-size:large;margin-bottom:0px;'>Preview of uploaded file:</p>",unsafe_allow_html=True)
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

        # Initialize driver with Streamlit Cloud compatible options
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            # Execute script to hide webdriver property
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception as e:
            st.error(f"Failed to initialize Chrome driver: {str(e)}")
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

                    # ----------------------------
                    # Cloudflare handling with CAPTCHA clicking
                    # ----------------------------
                    start_time = time.time()
                    cf_cleared = False
                    captcha_attempts = 0
                    max_captcha_attempts = 3
                    
                    while time.time() - start_time < max_wait_time and not cf_cleared:
                        # Check if Cloudflare challenge is present
                        try:
                            # Try multiple selectors for Cloudflare CAPTCHA
                            captcha_selectors = [
                                "input[type='checkbox']",  # Checkbox CAPTCHA
                                "#challenge-form input[type='submit']",  # Challenge form
                                ".cf-browser-verification input[type='checkbox']",  # Browser verification
                                "[data-sitekey]",  # reCAPTCHA
                                ".g-recaptcha",  # Google reCAPTCHA
                            ]
                            
                            captcha_found = False
                            for selector in captcha_selectors:
                                try:
                                    captcha_element = WebDriverWait(driver, 3).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                    )
                                    captcha_found = True
                                    
                                    # Scroll to element if needed
                                    driver.execute_script("arguments[0].scrollIntoView(true);", captcha_element)
                                    time.sleep(1)
                                    
                                    # Click the CAPTCHA element
                                    try:
                                        # Use ActionChains for more reliable clicking
                                        ActionChains(driver).move_to_element(captcha_element).click().perform()
                                        st.write(f"Clicked CAPTCHA element with selector: {selector}")
                                    except:
                                        captcha_element.click()
                                    
                                    captcha_attempts += 1
                                    time.sleep(3)  # Wait after clicking
                                    break
                                    
                                except:
                                    continue
                            
                            if not captcha_found:
                                time.sleep(2)
                                continue
                                
                        except:
                            # No CAPTCHA found, continue checking cookies
                            pass
                        
                        # Check for cf_clearance cookie
                        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                        if "cf_clearance" in cookies:
                            cf_cleared = True
                            st.write(f"Cloudflare cleared after {captcha_attempts} attempts")
                            break
                            
                        # Check if page loaded successfully (no more waiting)
                        try:
                            WebDriverWait(driver, 5).until(
                                lambda d: "ahrefs" in d.current_url or d.execute_script("return document.readyState") == "complete"
                            )
                            # If we reach here without cf_clearance, try one more time
                            if captcha_attempts < max_captcha_attempts:
                                continue
                            else:
                                break
                        except:
                            pass
                            
                        time.sleep(2)

                    if not cf_cleared:
                        status = "Failed: Cloudflare"
                        raise Exception("Cloudflare not cleared after maximum attempts")

                    # ----------------------------
                    # Extract modal
                    # ----------------------------
                    try:
                        modal_elements = WebDriverWait(driver, max_wait_time).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                        )
                    except:
                        # Try alternative selectors for the modal
                        try:
                            modal_elements = WebDriverWait(driver, 10).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[role='dialog'], .modal, .popup"))
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
                            try:
                                # Try alternative approach
                                element = elem.find_element(By.CSS_SELECTOR, selector)
                                return element.text.strip()
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
                    st.write(f"Error processing {user_url}: {str(e)}")

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
                    """,unsafe_allow_html=True
                )

                # Estimated remaining time
                elapsed = time.time() - batch_start_time
                avg_per_url = elapsed / idx if idx > 0 else 0
                remaining_time = avg_per_url * (total_urls - idx)
                
        driver.quit()
        processing_text.markdown("**Batch processing completed!**")

        # ----------------------------
        # Download CSV
        # ----------------------------
        st.markdown("<p style='font-weight:400;margin:20px 0px;'>If There are any Error website then recheck the website with More Increased Time...</p>",unsafe_allow_html=True)
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
