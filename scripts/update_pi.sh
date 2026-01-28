
#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "Pulling updates..."
git pull

echo "Installing deps..."
source .venv/bin/activate
pip install -r requirements.txt

echo "Restarting POS..."
sudo systemctl restart barbacoa-pos

echo "Update complete."
#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "Pulling updates..."
git pull

echo "Installing deps..."
source .venv/bin/activate
pip install -r requirements.txt

echo "Restarting POS..."
sudo systemctl restart barbacoa-pos

echo "Update complete."
