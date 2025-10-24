import asyncio
import re
import pandas as pd
import streamlit as st
from io import BytesIO
from pyppeteer import launch
import os
import sys

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

uploaded_file = st.file_uploader("📂 Upload CSV/XLSX file", type=["csv", "xlsx"])
max_wait_time = st.number_input(
    "⏱ Set maximum wait time per URL (seconds)", min_value=10, max_value=120, value=30
)

# --------------------------------------------
# Locate Chromium executable for Pyppeteer
# --------------------------------------------
def get_chromium_path():
    """Return the pyppeteer-downloaded Chromium binary path."""
    home = os.path.expanduser("~")
    base = os.path.join(home, ".local", "share", "pyppeteer", "local-chromium")
    if not os.path.exists(base):
        return None
    for folder in os.listdir(base):
        exec_path = os.path.join(base, folder, "chrome-linux", "chrome")
        if os.path.exists(exec_path):
            return exec_path
    return None

# --------------------------------------------
# Core Async Scraper
# --------------------------------------------
async def fetch_traffic(urls, wait_time):
    chromium_path = get_chromium_path()
    if not chromium_path:
        st.error("Chromium not found — please rerun once the initial download finishes.")
        return []

    st.info("Launching Chromium headless browser...")

    browser = await launch(
        headless=True,
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False,
        executablePath=chromium_path,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-infobars",
            "--disable-extensions",
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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(fetch_traffic(urls, max_wait_time))

        if results:
            result_df = pd.DataFrame(results)
            st.success("✅ Completed!")
            st.dataframe(result_df)

            buffer = BytesIO()
            result_df.to_csv(buffer, index=False)
            st.download_button(
                "📥 Download Results as CSV",
                data=buffer.getvalue(),
                file_name="ahrefs_traffic_results.csv",
                mime="text/csv"
            )
