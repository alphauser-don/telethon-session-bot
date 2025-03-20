#!/bin/bash
sudo apt update
sudo apt install -y python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p sessions
touch .env
echo "Please edit the .env file with your credentials"
