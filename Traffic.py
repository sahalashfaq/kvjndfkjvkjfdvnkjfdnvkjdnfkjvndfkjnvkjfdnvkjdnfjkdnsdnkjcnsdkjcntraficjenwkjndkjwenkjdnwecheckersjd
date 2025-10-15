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
# Chromium Paths for Streamlit Cloud
# -------------------------------------------------------
CHROME_BIN = "/usr/bin/chromium-browser"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"

# -------------------------------------------------------
# Streamlit Page Setup
# -------------------------------------------------------
st.set_page_config(page_title="Ahrefs Batch Traffic Extractor", layout="centered")

def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css()

uploaded_file = st.file_uploader("📁 Upload CSV/XLSX file containing URLs:", type=["csv", "xlsx"])
max_wait_time = st.number_input("⏱️ Wait time per URL (seconds)", 30, 300, 60, 5)

# -------------------------------------------------------
# Handle File Upload
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
        progress_bar = st.progress(0)
        table_area = st.empty()
        stats_area = st.empty()
        time_placeholder = st.empty()

        processing_text.markdown("**Processing... Please wait!**")

        # -------------------------------------------------------
        # Initialize Undetected ChromeDriver
        # -------------------------------------------------------
        options = uc.ChromeOptions()
        options.binary_location = CHROME_BIN
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1920,1080")

        driver = uc.Chrome(options=options, driver_executable_path=CHROMEDRIVER_PATH)

        results = []
        success_count = 0
        fail_count = 0
        batch_start_time = time.time()

        # -------------------------------------------------------
        # Process Each URL
        # -------------------------------------------------------
        for idx, raw_url in enumerate(df[url_column], start=1):
            url = str(raw_url).strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={url}&mode=subdomains"

            try:
                with st.spinner(f"Processing {idx}/{total_urls}: {url}"):
                    driver.get(ahrefs_url)
                    WebDriverWait(driver, max_wait_time).until(
                        lambda d: "traffic" in d.page_source.lower()
                    )

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

                    country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
                    top_country, top_country_share = (
                        (country_match.group(1), country_match.group(2))
                        if country_match
                        else (top_country_raw, "N/A")
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
                    "URL": url,
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

            # -------------------------------------------------------
            # Live Progress Update
            # -------------------------------------------------------
            progress_bar.progress(int(idx / total_urls * 100))
            table_area.dataframe(pd.DataFrame(results))
            elapsed = time.time() - batch_start_time
            avg_time = elapsed / idx
            remaining = avg_time * (total_urls - idx)
            time_placeholder.markdown(
                f"<p>⏳ Estimated time remaining: <b>{timedelta(seconds=int(remaining))}</b></p>",
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
        processing_text.markdown("✅ **Batch processing completed!**")

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
