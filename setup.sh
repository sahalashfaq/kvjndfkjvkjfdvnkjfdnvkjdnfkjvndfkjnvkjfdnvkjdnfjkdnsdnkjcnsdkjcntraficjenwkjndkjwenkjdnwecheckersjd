#!/bin/bash
set -e

echo "📦 Updating system packages..."
sudo apt-get update -y

echo "🌐 Installing Chromium and Chromedriver..."
sudo apt-get install -y chromium chromium-driver

echo "✅ Setting environment variables..."
export CHROME_BIN=/usr/bin/chromium
export CHROMEDRIVER_PATH=/usr/bin/chromedriver

echo "🔍 Verifying installations..."
chromium --version
chromedriver --version

echo "✅ Chromium setup complete!"
