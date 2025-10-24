#!/bin/bash
# Install Chrome & Driver for Streamlit Cloud
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver

# Set environment variables for SeleniumBase
export CHROME_BIN=/usr/bin/chromium-browser
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
