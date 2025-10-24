#!/bin/bash
set -e

echo "🔧 Installing Chromium and Chromedriver..."
sudo apt-get update -y
sudo apt-get install -y chromium chromium-driver

echo "✅ Setting environment variables..."
export CHROME_BIN=/usr/bin/chromium
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
export SB_CHROME_BINARY_PATH=/usr/bin/chromium

echo "🌐 Chromium version:"
chromium --version
echo "🚗 Chromedriver version:"
chromedriver --version
