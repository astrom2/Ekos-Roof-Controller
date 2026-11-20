#!/bin/bash
# Jarnan Observatory roof automation - installer for StellarMate
# Run from inside this folder:   bash install.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"

echo ">> Installing python3-opencv and ffmpeg"
sudo apt-get update -qq
sudo apt-get install -y python3-opencv python3-numpy ffmpeg

echo ">> Preparing $DIR"
mkdir -p "$DIR/data"
chmod +x "$DIR"/scripts/*.py "$DIR"/*.py

echo ">> Creating camera monitor service"
sudo tee /etc/systemd/system/roof-monitor.service >/dev/null <<EOF
[Unit]
Description=Jarnan Observatory roof camera monitor
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 $DIR/roof_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable roof-monitor

echo
echo "Done. Next:"
echo "  1) edit $DIR/roof_config.py   (ESP_HOST, ESP_USER, ESP_PASS, STATUS_SOURCE)"
echo "  2) python3 $DIR/roof_calibrate.py esp-state"
echo "  3) In Ekos set Dome Scripting Gateway scripts folder to: $DIR/scripts"
echo "  (camera, optional: grab -> closed -> sudo systemctl start roof-monitor)"
