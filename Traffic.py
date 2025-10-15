import os
import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
from io import BytesIO
from datetime import timedelta

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
    "📁 Upload CSV/XLSX file containing URLs to check traffic:",
    type=["csv", "xlsx"]
)
max_wait_time = st.number_input(
    "⏱️ Maximum wait time per URL (seconds)",
    min_value=30, max_value=300, value=120, step=5
)

# -------------------------------------------------------
# ADVANCED Cloudflare Bypass with Clicking Method
# -------------------------------------------------------
def bypass_cloudflare(driver, max_wait_time):
    """Your proven Cloudflare bypass method with clicking"""
    try:
        # Check if Cloudflare challenge is present
        cloudflare_indicators = [
            "//*[contains(text(), 'Checking if the site connection is secure')]",
            "//*[contains(text(), 'Checking your browser')]",
            "//*[contains(@id, 'challenge-form')]",
            "//*[contains(@class, 'cf-browser-verification')]",
            "//input[@type='checkbox']",
            "//*[contains(@id, 'cf-content')]"
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
            return True  # No Cloudflare detected

        st.warning("🛡️ Cloudflare protection detected - Attempting bypass...")
        
        # Method 1: Try to find and click the challenge button
        challenge_selectors = [
            "input[type='checkbox']",
            ".cf-btn-wrap .mark",
            "#challenge-form input[type='submit']",
            "button[type='submit']",
            ".hcaptcha-box",
            ".cf-cta-refresh"
        ]
        
        for selector in challenge_selectors:
            try:
                challenge_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                # Use ActionChains for more human-like click
                actions = ActionChains(driver)
                actions.move_to_element(challenge_element).pause(1).click().perform()
                st.info("✅ Clicked Cloudflare challenge button")
                time.sleep(5)  # Wait for challenge to process
                break
            except:
                continue

        # Method 2: Try to find and click by text
        challenge_texts = [
            "Verify you are human",
            "I am human",
            "Verify",
            "Continue",
            "Submit"
        ]
        
        for text in challenge_texts:
            try:
                xpath = f"//*[contains(text(), '{text}')]"
                challenge_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                actions = ActionChains(driver)
                actions.move_to_element(challenge_element).pause(0.5).click().perform()
                st.info(f"✅ Clicked '{text}' button")
                time.sleep(5)
                break
            except:
                continue

        # Wait for Cloudflare to clear
        start_time = time.time()
        while time.time() - start_time < max_wait_time - 30:
            # Check if we're still on Cloudflare
            current_url = driver.current_url
            page_source = driver.page_source.lower()
            
            cloudflare_still_present = any([
                "checking your browser" in page_source,
                "checking if the site connection is secure" in page_source,
                "ddos protection" in page_source,
                "cf-browser-verification" in page_source
            ])
            
            if not cloudflare_still_present:
                st.success("🎉 Cloudflare bypass successful!")
                return True
                
            # Try to find and interact with any new challenge elements
            try:
                # Look for any interactive elements that might be challenges
                interactive_elements = driver.find_elements(By.CSS_SELECTOR, 
                    "button, input[type='submit'], input[type='button'], [role='button']"
                )
                for element in interactive_elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            text = element.text.lower()
                            if any(keyword in text for keyword in ['verify', 'continue', 'submit', 'human']):
                                actions = ActionChains(driver)
                                actions.move_to_element(element).pause(0.3).click().perform()
                                st.info("🔄 Clicked additional challenge element")
                                time.sleep(3)
                                break
                    except:
                        continue
            except:
                pass
                
            time.sleep(3)

        # Final check
        page_source = driver.page_source.lower()
        if "cloudflare" not in page_source and "checking your browser" not in page_source:
            return True
        else:
            st.error("❌ Cloudflare bypass failed")
            return False

    except Exception as e:
        st.error(f"❌ Error during Cloudflare bypass: {str(e)}")
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
# Process file (Rest of the code remains the same)
# -------------------------------------------------------
if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    total_urls = len(df)
    st.markdown("<p style='color:#6a0dad;'>∵ More Time ∝ More Perfect Results</p>", unsafe_allow_html=True)
    st.dataframe(df.head())

    url_column = st.selectbox("Select the column containing URLs", df.columns)
    start_btn = st.button("🚀 Start Processing")

    if start_btn:
        processing_text = st.empty()
        time_placeholder = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()
        processing_text.markdown("**Processing... Please wait!**")

        # Driver setup with stealth options
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver_path = "/usr/bin/chromedriver"
        service = Service(executable_path=driver_path)
        
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
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
                f"<p>⏳ Estimated time remaining: <b>{timedelta(seconds=int(remaining_time))}</b></p>",
                unsafe_allow_html=True
            )
            
            stats_area.markdown(
                f"""
                <p>Total URLs: <b>{total_urls}</b></p>
                <p>Processed: <b>{idx}</b></p>
                <p>✅ Success: <b>{success_count}</b></p>
                <p>🚫 Blocked: <b>{blocked_count}</b></p>
                <p>❌ Failed: <b>{fail_count}</b></p>
                """,
                unsafe_allow_html=True
            )

        driver.quit()
        processing_text.markdown("✅ **Batch processing completed successfully!**")

        if results:
            result_df = pd.DataFrame(results)
            csv_buffer = BytesIO()
            result_df.to_csv(csv_buffer, index=False)
            st.download_button(
                "📥 Download Results as CSV",
                csv_buffer.getvalue(),
                file_name="ahrefs_batch_results.csv",
                mime="text/csv"
            )
        
        st.success(f"🎉 Processing complete! Success: {success_count}, Blocked: {blocked_count}, Failed: {fail_count}")
