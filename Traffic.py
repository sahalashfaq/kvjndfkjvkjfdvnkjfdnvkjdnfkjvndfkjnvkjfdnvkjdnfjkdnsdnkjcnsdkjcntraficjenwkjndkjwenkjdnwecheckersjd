import streamlit as st
import pandas as pd
import time
import re
from io import BytesIO
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import timedelta
import os

# --------------------------------------------------------------------
# Streamlit Config
# --------------------------------------------------------------------
st.set_page_config(page_title="Ahrefs Batch Extractor", layout="centered")

# --------------------------------------------------------------------
# Ensure SeleniumBase auto-manages Chromium (no system install)
# --------------------------------------------------------------------
os.environ["WDM_LOG_LEVEL"] = "0"
os.environ["WDM_LOCAL"] = "1"

# --------------------------------------------------------------------
# Load CSS (optional)
# --------------------------------------------------------------------
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except:
        st.warning("No CSS file found. You can add one for custom styling.")

load_css()

# --------------------------------------------------------------------
# 1️⃣ File Upload Section
# --------------------------------------------------------------------
st.title("🔍 Ahrefs Batch Traffic Extractor")
uploaded_file = st.file_uploader("Upload CSV/XLSX file containing URLs", type=["csv", "xlsx"])

max_wait_time = st.number_input(
    "Set maximum wait time per URL (seconds, min 30)",
    min_value=30, max_value=50000, value=30, step=5
)

# --------------------------------------------------------------------
# 2️⃣ Process Uploaded File
# --------------------------------------------------------------------
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    total_urls = len(df)
    estimated_total_time = total_urls * max_wait_time

    st.info(f"✅ File loaded successfully! Total URLs: {total_urls}")
    st.dataframe(df.head())

    url_column = st.selectbox("Select the column containing URLs", df.columns)
    start_btn = st.button("🚀 Start Processing")

    # ----------------------------------------------------------------
    # 3️⃣ Processing Logic
    # ----------------------------------------------------------------
    if start_btn:
        st.warning("Please don’t close this tab until all URLs are processed.")
        processing_text = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()

        results = []
        success_count = 0
        fail_count = 0
        batch_start_time = time.time()

        driver = Driver(uc=True, headless=True)

        for idx, user_url in enumerate(df[url_column], start=1):
            status = "Success"
            with st.spinner(f"Processing ({idx}/{total_urls}): {user_url}"):
                try:
                    ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={user_url}&mode=subdomains"
                    driver.uc_open_with_reconnect(ahrefs_url, reconnect_time=10)

                    # Wait for modal
                    modal_elements = WebDriverWait(driver, max_wait_time).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                    )
                    elem = modal_elements[0]

                    def safe_extract_css(selector):
                        try:
                            return WebDriverWait(elem, max_wait_time).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            ).text.strip()
                        except:
                            return "Error"

                    # Extract information
                    website_name = safe_extract_css("h2")
                    website_traffic = safe_extract_css(
                        "span.css-vemh4e.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1x5n6ob"
                    )
                    traffic_value = safe_extract_css(
                        "span.css-6s0ffe.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1jyb9g4"
                    )
                    top_country_raw = safe_extract_css("table:nth-of-type(1) tbody tr:first-child")
                    top_keyword_raw = safe_extract_css("table:nth-of-type(2) tbody tr:first-child")

                    # Parse country
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    if country_match:
                        top_country = country_match.group(1)
                        top_country_share = country_match.group(2)
                    else:
                        top_country = top_country_raw
                        top_country_share = "Error"

                    # Parse keyword
                    keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw)
                    if keyword_match:
                        top_keyword = keyword_match.group(1)
                        keyword_position = keyword_match.group(2)
                        top_keyword_traffic = keyword_match.group(3)
                    else:
                        top_keyword = top_keyword_raw
                        keyword_position = "Error"
                        top_keyword_traffic = "Error"

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

                # Update progress
                progress = int((idx / total_urls) * 100)
                progress_bar.progress(progress)
                table_area.dataframe(pd.DataFrame(results))

                stats_area.markdown(
                    f"""
                    <p class="states_p">Total URLs: <b>{total_urls}</b></p>
                    <p class="states_p">Processed: <b>{idx}</b></p>
                    <p class="states_p">Success: <b>{success_count}</b></p>
                    <p class="states_p">Failed: <b>{fail_count}</b></p>
                    """,
                    unsafe_allow_html=True,
                )

                # Small delay for stability
                time.sleep(3)

        driver.quit()
        processing_text.markdown("✅ **Batch processing completed successfully!**")

        # ----------------------------------------------------------------
        # 4️⃣ Export Results
        # ----------------------------------------------------------------
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

        st.success("All URLs processed! If some failed, try increasing wait time.")
