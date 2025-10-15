import os
import streamlit as st
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
from io import BytesIO
from datetime import timedelta
import random
import undetected_chromedriver as uc

# -------------------------------------------------------
# Streamlit setup
# -------------------------------------------------------
st.set_page_config(page_title="Ahrefs Batch Traffic Extractor", layout="centered")

def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css()

uploaded_file = st.file_uploader(
    "Upload CSV/XLSX file containing URLs to check traffic:",
    type=["csv", "xlsx"]
)
max_wait_time = st.number_input(
    "Maximum wait time per URL (seconds)",
    min_value=30, max_value=300, value=120, step=5
)

# -------------------------------------------------------
# ADVANCED Cloudflare Bypass with Clicking Method
# -------------------------------------------------------
def bypass_cloudflare(driver, max_wait_time):
    try:
        # Check for Cloudflare challenge
        cloudflare_indicators = [
            "//*[contains(text(), 'Checking if the site connection is secure')]",
            "//*[contains(text(), 'Checking your browser')]",
            "//*[contains(@id, 'challenge-form')]",
            "//*[contains(@class, 'cf-browser-verification')]",
            "//input[@type='checkbox']",
            "//*[contains(@id, 'cf-content')]",
            "//*[contains(@id, 'cf-captcha')]",  # Added for CAPTCHA detection
            "//iframe[@title='Widget containing a Cloudflare security challenge']",
        ]
        
        cloudflare_detected = False
        for indicator in cloudflare_indicators:
            try:
                if driver.find_elements(By.XPATH, indicator):
                    cloudflare_detected = True
                    break
            except:
                continue
        
        if not cloudflare_detected:
            st.info("No Cloudflare challenge detected.")
            return True

        st.warning("Cloudflare protection detected - Attempting bypass...")
        
        # Simulate human-like scrolling
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(random.uniform(0.5, 1.5))
        driver.execute_script("window.scrollTo(0, 0);")
        
        # Method 1: Handle checkbox CAPTCHA
        challenge_selectors = [
            "input[type='checkbox']",
            ".cf-btn-wrap .mark",
            "#challenge-form input[type='submit']",
            "button[type='submit']",
            ".hcaptcha-box",
            ".cf-cta-refresh",
            "input#checkbox",  # Common hCaptcha/reCAPTCHA checkbox
        ]
        
        for selector in challenge_selectors:
            try:
                challenge_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                actions = ActionChains(driver)
                # Simulate human-like mouse movement
                actions.move_to_element_with_offset(challenge_element, random.randint(-5, 5), random.randint(-5, 5))
                actions.pause(random.uniform(0.3, 0.7)).click().perform()
                st.info("Clicked Cloudflare challenge button")
                time.sleep(random.uniform(3, 5))  # Wait for processing
                break
            except:
                continue

        # Method 2: Handle text-based challenges
        challenge_texts = [
            "Verify you are human",
            "I am human",
            "Verify",
            "Continue",
            "Submit",
            "Click to verify",
        ]
        
        for text in challenge_texts:
            try:
                xpath = f"//*[contains(text(), '{text}') or contains(@value, '{text}')]"
                challenge_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                actions = ActionChains(driver)
                actions.move_to_element_with_offset(challenge_element, random.randint(-5, 5), random.randint(-5, 5))
                actions.pause(random.uniform(0.3, 0.7)).click().perform()
                st.info(f"Clicked '{text}' button")
                time.sleep(random.uniform(3, 5))
                break
            except:
                continue

        # Method 3: Handle iframe-based CAPTCHAs (e.g., hCaptcha, reCAPTCHA)
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                if "captcha" in iframe.get_attribute("title").lower():
                    driver.switch_to.frame(iframe)
                    try:
                        checkbox = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='checkbox']"))
                        )
                        actions = ActionChains(driver)
                        actions.move_to_element_with_offset(checkbox, random.randint(-5, 5), random.randint(-5, 5))
                        actions.pause(random.uniform(0.3, 0.7)).click().perform()
                        st.info("Clicked CAPTCHA checkbox in iframe")
                        time.sleep(random.uniform(3, 5))
                    except:
                        pass
                    driver.switch_to.default_content()
                    break
        except:
            pass

        # Wait for Cloudflare to clear with retries
        start_time = time.time()
        retry_count = 0
        max_retries = 3
        
        while time.time() - start_time < max_wait_time - 30 and retry_count < max_retries:
            page_source = driver.page_source.lower()
            cloudflare_still_present = any([
                "checking your browser" in page_source,
                "checking if the site connection is secure" in page_source,
                "ddos protection" in page_source,
                "cf-browser-verification" in page_source,
                "captcha" in page_source,
            ])
            
            if not cloudflare_still_present:
                st.success("Cloudflare bypass successful!")
                return True
                
            # Try interacting with any new challenge elements
            try:
                interactive_elements = driver.find_elements(By.CSS_SELECTOR,
                    "button, input[type='submit'], input[type='button'], [role='button'], input[type='checkbox']"
                )
                for element in interactive_elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            text = element.text.lower()
                            if any(keyword in text for keyword in ['verify', 'continue', 'submit', 'human', 'captcha']):
                                actions = ActionChains(driver)
                                actions.move_to_element_with_offset(element, random.randint(-5, 5), random.randint(-5, 5))
                                actions.pause(random.uniform(0.3, 0.7)).click().perform()
                                st.info("Clicked additional challenge element")
                                time.sleep(random.uniform(2, 4))
                                break
                    except:
                        continue
            except:
                pass
                
            time.sleep(random.uniform(2, 4))
            retry_count += 1

        # Final check
        page_source = driver.page_source.lower()
        if "cloudflare" not in page_source and "checking your browser" not in page_source and "captcha" not in page_source:
            st.success("Cloudflare bypass successful!")
            return True
        else:
            st.error("Cloudflare bypass failed after retries")
            return False

    except Exception as e:
        st.error(f"Error during Cloudflare bypass: {str(e)}")
        return False

# -------------------------------------------------------
# IMPROVED Scraping Function with Your Cloudflare Method
# -------------------------------------------------------
def scrape_ahrefs_data(driver, url, max_wait_time):
    try:
        ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={url}&mode=subdomains"
        driver.get(ahrefs_url)
        
        # Wait for initial load
        time.sleep(3)
        
        # USE YOUR PROVEN CLOUDFLARE BYPASS METHOD
        cloudflare_bypassed = bypass_cloudflare(driver, max_wait_time)
        
        if not cloudflare_bypassed:
            return {
                "URL": url,
                "Website": "Blocked",
                "Website Traffic": "Blocked",
                "Top Country": "Blocked",
                "Top Country Share": "Blocked",
                "Top Keyword": "Blocked",
                "Keyword Position": "Blocked",
                "Keyword Traffic": "Blocked",
                "Status": "Cloudflare Blocked"
            }

        # Now try to extract data with multiple attempts
        def safe_find_element(selector_type, selector, timeout=15):
            try:
                if selector_type == "xpath":
                    element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    return element.text.strip() if element.text else "N/A"
                else:  # css
                    element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    return element.text.strip() if element.text else "N/A"
            except:
                return "N/A"

        # Extract data using your perfect XPaths
        website_name = safe_find_element("xpath", "/html/body/div[6]/div/div/div/div/div[2]/div[1]/div/div/div[1]/div[2]/div/div/div/span")
        website_traffic = safe_find_element("xpath", "/html/body/div[6]/div/div/div/div/div[2]/div[1]/div/div/div[2]/div[2]/div/div/div/span")
        
        # Extract table data
        top_country_raw = safe_find_element("css", "table:nth-of-type(1) tbody tr:first-child")
        top_keyword_raw = safe_find_element("css", "table:nth-of-type(2) tbody tr:first-child")

        # Parse the data
        country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw) if top_country_raw != "N/A" else None
        if country_match:
            top_country = country_match.group(1)
            top_country_share = country_match.group(2)
        else:
            top_country, top_country_share = top_country_raw, "N/A"

        keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw) if top_keyword_raw != "N/A" else None
        if keyword_match:
            top_keyword = keyword_match.group(1)
            keyword_position = keyword_match.group(2)
            top_keyword_traffic = keyword_match.group(3)
        else:
            top_keyword, keyword_position, top_keyword_traffic = top_keyword_raw, "N/A", "N/A"

        # Check if we actually got data or if we're still blocked
        if website_name == "N/A" and website_traffic == "N/A":
            return {
                "URL": url,
                "Website": "Still Blocked",
                "Website Traffic": "Still Blocked", 
                "Top Country": "Still Blocked",
                "Top Country Share": "Still Blocked",
                "Top Keyword": "Still Blocked",
                "Keyword Position": "Still Blocked",
                "Keyword Traffic": "Still Blocked",
                "Status": "Still Blocked After Bypass"
            }

        return {
            "URL": url,
            "Website": website_name,
            "Website Traffic": website_traffic,
            "Top Country": top_country,
            "Top Country Share": top_country_share,
            "Top Keyword": top_keyword,
            "Keyword Position": keyword_position,
            "Keyword Traffic": top_keyword_traffic,
            "Status": "Success"
        }

    except Exception as e:
        return {
            "URL": url,
            "Website": "Error",
            "Website Traffic": "Error",
            "Top Country": "Error",
            "Top Country Share": "Error",
            "Top Keyword": "Error",
            "Keyword Position": "Error",
            "Keyword Traffic": "Error",
            "Status": f"Error: {str(e)[:100]}"
        }

# -------------------------------------------------------
# Driver Setup Function
# -------------------------------------------------------
def setup_driver():
    options = uc.ChromeOptions()
    # Optionally disable headless for better success (comment out if running locally)
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Add a realistic user-agent
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")
    
    # Set window size to mimic a real browser
    options.add_argument("--window-size=1920,1080")
    
    # Optional: Add proxy for residential IPs (replace with your proxy details)
    # options.add_argument("--proxy-server=http://your_proxy:port")
    
    driver = uc.Chrome(options=options)
    
    # Remove webdriver property (undetected_chromedriver handles much of this internally)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# -------------------------------------------------------
# Process file
# -------------------------------------------------------
if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    total_urls = len(df)
    st.markdown("<p style='color:#6a0dad;'>More Time = More Perfect Results</p>", unsafe_allow_html=True)
    st.dataframe(df.head())

    url_column = st.selectbox("Select the column containing URLs", df.columns)
    start_btn = st.button("Start Processing")

    if start_btn:
        processing_text = st.empty()
        time_placeholder = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()
        processing_text.markdown("**Processing... Please wait!**")

        try:
            driver = setup_driver()
        except Exception as e:
            st.error(f"Failed to start Chrome driver: {e}")
            st.stop()

        results, success_count, fail_count, blocked_count = [], 0, 0, 0
        batch_start_time = time.time()

        # Main scraping loop
        for idx, raw_url in enumerate(df[url_column], start=1):
            url = str(raw_url).strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            result = scrape_ahrefs_data(driver, url, max_wait_time)
            results.append(result)
            
            if result["Status"] == "Success":
                success_count += 1
            elif "Blocked" in result["Status"]:
                blocked_count += 1
            else:
                fail_count += 1

            # Progress updates
            progress = int(idx / total_urls * 100)
            progress_bar.progress(progress)
            table_area.dataframe(pd.DataFrame(results))
            
            elapsed = time.time() - batch_start_time
            avg_per_url = elapsed / idx
            remaining_time = avg_per_url * (total_urls - idx)
            time_placeholder.markdown(
                f"<p>Estimated time remaining: <b>{timedelta(seconds=int(remaining_time))}</b></p>",
                unsafe_allow_html=True
            )
            
            stats_area.markdown(
                f"""
                <p>Total URLs: <b>{total_urls}</b></p>
                <p>Processed: <b>{idx}</b></p>
                <p>Success: <b>{success_count}</b></p>
                <p>Blocked: <b>{blocked_count}</b></p>
                <p>Failed: <b>{fail_count}</b></p>
                """,
                unsafe_allow_html=True
            )

        driver.quit()
        processing_text.markdown("**Batch processing completed successfully!**")

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
        
        st.success(f"Processing complete! Success: {success_count}, Blocked: {blocked_count}, Failed: {fail_count}")
