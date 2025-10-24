import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
from io import BytesIO

st.set_page_config(page_title="Ahrefs Batch Extractor", layout="centered")

# Load CSS
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        pass  # No CSS = no problem

load_css()

# ----------------------------
# 1. User inputs
# ----------------------------
uploaded_file = st.file_uploader("Upload CSV/XLSX file containing URLs", type=["csv", "xlsx"])
max_wait_time = st.number_input(
    "Max wait time per URL (seconds, min 30)",
    min_value=30, max_value=300, value=60, step=5
)

# ----------------------------
# 2. File handling
# ----------------------------
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    total_urls = len(df)
    st.markdown("<p style='color:#aaa;'>∵ More Time = Better Results (Cloudflare bypass)</p>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:large;margin-bottom:0px;'>Preview:</p>", unsafe_allow_html=True)
    st.dataframe(df.head())

    url_column = st.selectbox("Select URL column", df.columns)
    start_btn = st.button("Start Processing")

    # ----------------------------
    # 3. Start processing
    # ----------------------------
    if start_btn:
        processing_text = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()

        processing_text.markdown("**Initializing Chrome driver...**")

        # === ROBUST DRIVER SETUP ===
        def init_driver():
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

            try:
                service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
                driver = webdriver.Chrome(service=service, options=options)
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                })
                return driver
            except Exception as e:
                st.error(f"Driver failed: {e}")
                st.stop()

        driver = init_driver()
        processing_text.markdown("**Processing URLs...**")

        results = []
        success_count = fail_count = 0
        batch_start_time = time.time()

        for idx, user_url in enumerate(df[url_column], start=1):
            with st.spinner(f"Processing {idx}/{total_urls}: {user_url}"):
                try:
                    ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={user_url}&mode=subdomains"
                    driver.get(ahrefs_url)

                    # === Cloudflare Bypass ===
                    start_time = time.time()
                    cf_cleared = False
                    while time.time() - start_time < max_wait_time and not cf_cleared:
                        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                        if "cf_clearance" in cookies:
                            cf_cleared = True
                            break

                        for selector in ["input[type='checkbox']", ".g-recaptcha", "[data-sitekey]"]:
                            try:
                                el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                                ActionChains(driver).move_to_element(el).click().perform()
                                time.sleep(3)
                                break
                            except:
                                continue
                        time.sleep(2)

                    if not cf_cleared:
                        raise Exception("Cloudflare blocked")

                    # === Extract Modal ===
                    modal = WebDriverWait(driver, max_wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                    )

                    def get_text(sel):
                        try:
                            return modal.find_element(By.CSS_SELECTOR, sel).text.strip()
                        except:
                            return "Error"

                    website = get_text("h2")
                    traffic = get_text("span.css-vemh4e")
                    country_raw = get_text("table:nth-of-type(1) tbody tr:first-child")
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", country_raw)
                    top_country = country_match.group(1) if country_match else country_raw
                    top_share = country_match.group(2) if country_match else "Error"

                    results.append({
                        "URL": user_url,
                        "Website": website,
                        "Website Traffic": traffic,
                        "Top Country": top_country,
                        "Top Country Share": top_share
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
                    st.warning(f"{user_url} → {str(e)[:100]}")

                # === Live Updates ===
                progress_bar.progress(int(idx / total_urls * 100))
                table_area.dataframe(pd.DataFrame(results))
                stats_area.markdown(f"""
                    **Stats:** Total: `{total_urls}` | Done: `{idx}` | Success: `{success_count}` | Failed: `{fail_count}`
                """)

        driver.quit()
        processing_text.markdown("**Done! Download below.**")

        # === Download ===
        if results:
            result_df = pd.DataFrame(results)
            csv = result_df.to_csv(index=False).encode()
            st.download_button(
                "Download Results CSV",
                csv,
                "ahrefs_results.csv",
                "text/csv"
            )
        st.success("Batch complete!")
