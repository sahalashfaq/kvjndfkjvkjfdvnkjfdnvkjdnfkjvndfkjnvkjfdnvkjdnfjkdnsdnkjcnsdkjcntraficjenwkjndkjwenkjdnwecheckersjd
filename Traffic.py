import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure Chrome options for Streamlit Cloud (headless, no sandbox, etc.)
@st.cache_resource
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background (no GUI)
    chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource issues
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--window-size=1920x1080")  # Set window size for consistency
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

st.title("Selenium App on Streamlit Cloud")

if st.button("Scrape Example (e.g., Wikipedia)"):
    with st.spinner("Scraping..."):
        driver = get_driver()
        try:
            driver.get("https://en.wikipedia.org/wiki/Python_(programming_language)")
            wait = WebDriverWait(driver, 10)
            title = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            st.success(f"Page title: {title.text}")
            # Add your scraping logic here (e.g., find elements, extract data)
        except Exception as e:
            st.error(f"Error: {str(e)}")
        finally:
            driver.quit()  # Always close the driver

st.info("This app uses Selenium to scrape Wikipedia. Customize the scraping logic as needed.")
