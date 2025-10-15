import os
import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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
# Fixed Scraping Function
# -------------------------------------------------------
def scrape_ahrefs_data(driver, url, max_wait_time):
    try:
        ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={url}&mode=subdomains"
        driver.get(ahrefs_url)
        
        # Wait for the main modal to appear (using your XPath)
        WebDriverWait(driver, max_wait_time).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[6]/div/div/div/div/div[2]/div[1]/div/div/div[1]/div[2]/div/div/div/span"))
        )

        # Extract website name using your exact XPath
        website_name = driver.find_element(By.XPATH, "/html/body/div[6]/div/div/div/div/div[2]/div[1]/div/div/div[1]/div[2]/div/div/div/span").text.strip()
        
        # Extract traffic value using your exact XPath
        website_traffic = driver.find_element(By.XPATH, "/html/body/div[6]/div/div/div/div/div[2]/div[1]/div/div/div[2]/div[2]/div/div/div/span").text.strip()

        # Extract top country data from first table
        top_country_element = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(1) tbody tr:first-child")
        top_country_raw = top_country_element.text.strip() if top_country_element else "N/A"

        # Extract top keyword data from second table  
        top_keyword_element = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(2) tbody tr:first-child")
        top_keyword_raw = top_keyword_element.text.strip() if top_keyword_element else "N/A"

        # Parse country data
        country_match = re.match(r"(.+?)\s+([\d.%]+)", top_country_raw)
        if country_match:
            top_country = country_match.group(1)
            top_country_share = country_match.group(2)
        else:
            top_country, top_country_share = top_country_raw, "N/A"

        # Parse keyword data
        keyword_match = re.match(r"(.+?)\s+(\d+)\s+([\d,K,M]+)", top_keyword_raw)
        if keyword_match:
            top_keyword = keyword_match.group(1)
            keyword_position = keyword_match.group(2)
            top_keyword_traffic = keyword_match.group(3)
        else:
            top_keyword, keyword_position, top_keyword_traffic = top_keyword_raw, "N/A", "N/A"

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
            "Status": f"Failed: {str(e)}"
        }

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
        # Use Standard Selenium like Facebook Scraper (MORE RELIABLE)
        # -------------------------------------------------------
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.binary_location = "/usr/bin/chromium-browser"

        service = Service(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        results, success_count, fail_count = [], 0, 0
        batch_start_time = time.time()

        # -------------------------------------------------------
        # Main scraping loop - FIXED
        # -------------------------------------------------------
        for idx, raw_url in enumerate(df[url_column], start=1):
            url = str(raw_url).strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # Use the fixed scraping function
            result = scrape_ahrefs_data(driver, url, max_wait_time)
            results.append(result)
            
            if result["Status"] == "Success":
                success_count += 1
            else:
                fail_count += 1

            # Progress updates
            progress = int(idx / total_urls * 100)
            progress_bar.progress(progress)
            
            # Update results table
            table_area.dataframe(pd.DataFrame(results))
            
            # Time estimation
            elapsed = time.time() - batch_start_time
            avg_per_url = elapsed / idx
            remaining_time = avg_per_url * (total_urls - idx)
            time_placeholder.markdown(
                f"<p>⏳ Estimated time remaining: <b>{timedelta(seconds=int(remaining_time))}</b></p>",
                unsafe_allow_html=True
            )
            
            # Stats update
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

        # Download results
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
        
        st.success(f"🎉 Processing complete! Success: {success_count}, Failed: {fail_count}")
