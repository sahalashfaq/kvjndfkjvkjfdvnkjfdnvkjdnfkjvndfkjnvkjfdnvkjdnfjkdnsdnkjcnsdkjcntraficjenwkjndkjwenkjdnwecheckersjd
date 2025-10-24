import asyncio
import re
import pandas as pd
import streamlit as st
from io import BytesIO
from pyppeteer import launch
import time

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

st.title("🌐 Ahrefs Batch Traffic Checker (Headless Chromium via Pyppeteer)")
st.markdown(
    "Upload a CSV/XLSX file of website URLs to fetch visible traffic data from Ahrefs automatically."
)

# --------------------------------------------
# File Upload + Settings
# --------------------------------------------
uploaded_file = st.file_uploader("📂 Upload CSV/XLSX file", type=["csv", "xlsx"])
max_wait_time = st.number_input(
    "⏱ Set maximum wait time per URL (seconds)", min_value=10, max_value=120, value=30
)

# --------------------------------------------
# Core Async Scraper
# --------------------------------------------
async def fetch_traffic(urls, wait_time):
    browser = await launch(
        headless=True,
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1920,1080",
        ],
    )
    page = await browser.newPage()
    results = []

    for i, user_url in enumerate(urls, start=1):
        ahrefs_url = f"https://ahrefs.com/traffic-checker/?input={user_url}&mode=subdomains"
        st.write(f"🔍 Processing ({i}/{len(urls)}): {user_url}")
        try:
            await page.goto(ahrefs_url, {"timeout": wait_time * 1000})
            await page.waitForSelector("body", {"timeout": wait_time * 1000})
            await asyncio.sleep(5)

            content = await page.content()
            title_match = re.search(r"<title>(.*?)</title>", content)
            traffic_match = re.search(r"([\d,\.]+)\s+visits", content, re.I)

            results.append({
                "URL": user_url,
                "Page Title": title_match.group(1) if title_match else "N/A",
                "Estimated Traffic": traffic_match.group(1) if traffic_match else "N/A",
                "Status": "Success",
            })
        except Exception as e:
            results.append({
                "URL": user_url,
                "Page Title": "Error",
                "Estimated Traffic": "N/A",
                "Status": f"Failed: {str(e)[:80]}"
            })
    await browser.close()
    return results

# --------------------------------------------
# Main Execution
# --------------------------------------------
if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    url_col = st.selectbox("Select the column containing URLs", df.columns)
    st.dataframe(df.head())

    if st.button("🚀 Start Checking"):
        urls = df[url_col].dropna().tolist()
        st.info("Starting headless Chromium browser...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(fetch_traffic(urls, max_wait_time))

        result_df = pd.DataFrame(results)
        st.success("✅ Completed!")
        st.dataframe(result_df)

        # Download button
        buffer = BytesIO()
        result_df.to_csv(buffer, index=False)
        st.download_button(
            "📥 Download Results as CSV",
            data=buffer.getvalue(),
            file_name="ahrefs_traffic_results.csv",
            mime="text/csv"
        )
