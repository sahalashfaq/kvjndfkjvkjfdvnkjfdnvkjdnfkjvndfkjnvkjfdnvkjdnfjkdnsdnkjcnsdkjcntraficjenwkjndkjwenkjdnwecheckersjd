import streamlit as st
import pandas as pd
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from io import BytesIO
from datetime import timedelta

# ----------------------------
# Streamlit Page Config
# ----------------------------
st.set_page_config(page_title="Ahrefs Batch Traffic Extractor", layout="centered")

# ----------------------------
# CSS Loader
# ----------------------------
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("⚠️ No custom CSS found. Using default Streamlit style.")

load_css()

# ----------------------------
# User Inputs
# ----------------------------
uploaded_file = st.file_uploader(
    "📁 Upload CSV/XLSX file containing URLs to check traffic:",
    type=["csv", "xlsx"]
)

max_wait_time = st.number_input(
    "⏱️ Set maximum wait time per URL (seconds)",
    min_value=30,
    max_value=300,
    value=60,
    step=5
)

# ----------------------------
# Handle File Upload
# ----------------------------
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    total_urls = len(df)
    st.markdown("<p style='color:#6a0dad;'>∵ More Time ∝ More Perfect Results</p>", unsafe_allow_html=True)
    st.markdown("<h4>Preview of Uploaded File:</h4>", unsafe_allow_html=True)
    st.dataframe(df.head())

    url_column = st.selectbox("Select the column containing URLs", df.columns)
    start_btn = st.button("🚀 Start Processing")

    # ----------------------------
    # Begin Extraction
    # ----------------------------
    if start_btn:
        processing_text = st.empty()
        time_placeholder = st.empty()
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()

        processing_text.markdown("**Processing... Please wait!**")

        # Initialize SeleniumBase Driver (auto undetected mode)
        driver = Driver(uc=True, headless=True)
        results = []
        success_count = 0
        fail_count = 0
        batch_start_time = time.time()

        for idx, raw_url in enumerate(df[url_column], start=1):
            try:
                url = str(raw_url).strip()
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={url}&mode=subdomains"
                with st.spinner(f"Processing {idx}/{total_urls}: {url}"):
                    driver.uc_open_with_reconnect(ahrefs_url, reconnect_time=10)

                    # ----------------------------
                    # Cloudflare Handling
                    # ----------------------------
                    start_time = time.time()
                    cf_cleared = False
                    while True:
                        try:
                            driver.uc_gui_click_captcha()
                        except Exception:
                            pass

                        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                        if "cf_clearance" in cookies:
                            cf_cleared = True
                            break
                        if time.time() - start_time > max_wait_time:
                            break
                        time.sleep(3)

                    if not cf_cleared:
                        raise Exception("Cloudflare verification failed.")

                    # ----------------------------
                    # Extract Modal Content
                    # ----------------------------
                    modal = WebDriverWait(driver, max_wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".ReactModalPortal"))
                    )

                    def safe_extract(selector):
                        try:
                            element = WebDriverWait(modal, max_wait_time).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            return element.text.strip()
                        except:
                            return "N/A"

                    website_name = safe_extract("h2")
                    website_traffic = safe_extract("span.css-vemh4e.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1x5n6ob")
                    top_country_raw = safe_extract("table:nth-of-type(1) tbody tr:first-child")
                    top_keyword_raw = safe_extract("table:nth-of-type(2) tbody tr:first-child")

                    # ----------------------------
                    # Data Parsing
                    # ----------------------------
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    if country_match:
                        top_country = country_match.group(1)
                        top_country_share = country_match.group(2)
                    else:
                        top_country, top_country_share = top_country_raw, "N/A"

                    keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw)
                    if keyword_match:
                        top_keyword = keyword_match.group(1)
                        keyword_position = keyword_match.group(2)
                        top_keyword_traffic = keyword_match.group(3)
                    else:
                        top_keyword, keyword_position, top_keyword_traffic = top_keyword_raw, "N/A", "N/A"

                    # ----------------------------
                    # Append Results
                    # ----------------------------
                    results.append({
                        "URL": url,
                        "Website": website_name,
                        "Website Traffic": website_traffic,
                        "Top Country": top_country,
                        "Top Country Share": top_country_share,
                        "Top Keyword": top_keyword,
                        "Keyword Position": keyword_position,
                        "Keyword Traffic": top_keyword_traffic,
                        "Status": "Success"
                    })
                    success_count += 1

            except Exception as e:
                results.append({
                    "URL": raw_url,
                    "Website": "Error",
                    "Website Traffic": "Error",
                    "Top Country": "Error",
                    "Top Country Share": "Error",
                    "Top Keyword": "Error",
                    "Keyword Position": "Error",
                    "Keyword Traffic": "Error",
                    "Status": f"Failed: {str(e)}"
                })
                fail_count += 1

            # ----------------------------
            # Progress Update
            # ----------------------------
            progress_bar.progress(int(idx / total_urls * 100))
            table_area.dataframe(pd.DataFrame(results))

            elapsed = time.time() - batch_start_time
            avg_per_url = elapsed / idx
            remaining_time = avg_per_url * (total_urls - idx)
            time_placeholder.markdown(
                f"<p style='font-size:14px;'>⏳ Estimated time remaining: <b>{timedelta(seconds=int(remaining_time))}</b></p>",
                unsafe_allow_html=True
            )

            stats_area.markdown(
                f"""
                <p>Total URLs: <b>{total_urls}</b></p>
                <p>Processed: <b>{idx}</b></p>
                <p>✅ Success: <b>{success_count}</b></p>
                <p>❌ Failed: <b>{fail_count}</b></p>
                """,
                unsafe_allow_html=True
            )

        driver.quit()
        processing_text.markdown("✅ **Batch processing completed successfully!**")

        # ----------------------------
        # CSV Export
        # ----------------------------
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
        st.success("🎉 All URLs processed!")

