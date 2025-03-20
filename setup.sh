#!/bin/bash
set -e

# System dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv sqlite3

# Project setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Directories
mkdir -p sessions logs
touch users.db .env

# Permissions
sudo chown -R ubuntu:ubuntu /home/ubuntu/telethon-session-bot
chmod 750 venv sessions logs
chmod 640 .env users.db

echo "Setup complete! Edit .env file before starting."
