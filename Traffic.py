import os
import time
import re
import pandas as pd
import streamlit as st
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller

# --------------------------------------------
# Streamlit Page Setup
# --------------------------------------------
st.set_page_config(page_title="Ahrefs Traffic Checker", layout="centered")

def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass

load_css()

st.title("🌐 Ahrefs Batch Traffic Checker")
st.markdown(
    "Upload a CSV/XLSX file containing website URLs, and this tool will fetch basic traffic info from Ahrefs."
)

# --------------------------------------------
# File Upload + User Options
# --------------------------------------------
uploaded_file = st.file_uploader("📂 Upload CSV/XLSX file", type=["csv", "xlsx"])
max_wait_time = st.number_input(
    "⏱ Set maximum wait time per URL (seconds, min 20)", min_value=20, max_value=300, value=30
)

# --------------------------------------------
# Handle Uploaded File
# --------------------------------------------
if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    url_column = st.selectbox("Select column containing URLs", df.columns)
    st.dataframe(df.head())

    if st.button("🚀 Start Checking"):
        st.info("Initializing headless browser... Please wait.")
        chromedriver_autoinstaller.install()  # installs matching driver

        # Chrome Options
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920x1080")

        driver = webdriver.Chrome(service=Service(), options=options)

        results = []
        progress = st.progress(0)
        status_text = st.empty()

        for i, url in enumerate(df[url_column], start=1):
            clean_url = str(url).strip()
            ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={clean_url}&mode=subdomains"
            status_text.text(f"Processing ({i}/{len(df)}): {clean_url}")

            try:
                driver.get(ahrefs_url)
                WebDriverWait(driver, max_wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
                time.sleep(5)  # allow data to load

                # Try to extract key data (simplified version)
                title = driver.title
                text = driver.page_source

                traffic = re.search(r'(?i)([\d,\.]+)\s+visits', text)
                traffic_val = traffic.group(1) if traffic else "N/A"

                results.append({
                    "URL": clean_url,
                    "Page Title": title,
                    "Estimated Traffic": traffic_val,
                    "Status": "Success"
                })
            except Exception as e:
                results.append({
                    "URL": clean_url,
                    "Page Title": "Error",
                    "Estimated Traffic": "N/A",
                    "Status": f"Failed: {str(e)[:60]}"
                })

            progress.progress(int(i / len(df) * 100))

        driver.quit()

        result_df = pd.DataFrame(results)
        st.success("✅ Processing complete!")
        st.dataframe(result_df)

        # Download Button
        buffer = BytesIO()
        result_df.to_csv(buffer, index=False)
        st.download_button(
            label="📥 Download Results as CSV",
            data=buffer.getvalue(),
            file_name="ahrefs_traffic_results.csv",
            mime="text/csv"
        )
