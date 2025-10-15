import os
import streamlit as st
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from io import BytesIO
from datetime import timedelta

# -------------------------------------------------------
# Environment paths for Streamlit Cloud
# -------------------------------------------------------
os.environ["CHROME_BIN"] = "/usr/bin/chromium-browser"
os.environ["CHROMEDRIVER_PATH"] = "/usr/bin/chromedriver"

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
    min_value=30, max_value=300, value=60, step=5
)

# -------------------------------------------------------
# Process file
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

        # -------------------------------------------------------
        # Configure undetected_chromedriver
        # -------------------------------------------------------
        options = uc.ChromeOptions()
        options.headless = True
        options.binary_location = "/usr/bin/chromium-browser"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-software-rasterizer")

        driver = uc.Chrome(options=options, driver_executable_path="/usr/bin/chromedriver")

        results, success_count, fail_count = [], 0, 0
        batch_start_time = time.time()

        # -------------------------------------------------------
        # Main scraping loop
        # -------------------------------------------------------
        for idx, raw_url in enumerate(df[url_column], start=1):
            try:
                url = str(raw_url).strip()
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={url}&mode=subdomains"
                with st.spinner(f"Processing {idx}/{total_urls}: {url}"):
                    driver.get(ahrefs_url)

                    # --- Cloudflare handling ---
                    start_time = time.time()
                    while "cf_clearance" not in {c["name"]: c["value"] for c in driver.get_cookies()}:
                        if time.time() - start_time > max_wait_time:
                            raise Exception("Cloudflare not cleared in time.")
                        time.sleep(3)

                    # --- Wait for modal ---
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
                    website_traffic = safe_extract(
                        "span.css-vemh4e.css-rr08kv-textFontWeight.css-oi9nct-textDisplay.css-1x5n6ob"
                    )
                    top_country_raw = safe_extract("table:nth-of-type(1) tbody tr:first-child")
                    top_keyword_raw = safe_extract("table:nth-of-type(2) tbody tr:first-child")

                    # --- Parse ---
                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    top_country, top_country_share = (
                        (country_match.group(1), country_match.group(2))
                        if country_match else (top_country_raw, "N/A")
                    )

                    keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw)
                    if keyword_match:
                        top_keyword = keyword_match.group(1)
                        keyword_position = keyword_match.group(2)
                        top_keyword_traffic = keyword_match.group(3)
                    else:
                        top_keyword, keyword_position, top_keyword_traffic = top_keyword_raw, "N/A", "N/A"

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

            # --- Progress updates ---
            progress_bar.progress(int(idx / total_urls * 100))
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
                <p>❌ Failed: <b>{fail_count}</b></p>
                """,
                unsafe_allow_html=True
            )

        driver.quit()
        processing_text.markdown("✅ **Batch processing completed successfully!**")

        # --- Download results ---
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
        st.success("🎉 All URLs processed successfully!")
