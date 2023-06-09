#!/bin/bash
## run this to create the virtual environment env
## you need to run /env/bin/activate to access env
python3.11 -m venv env
source env/bin/activate
python3.11 -m pip install -r requirements.txt
#pip install --upgrade pip
pip3 install --upgrade --no-deps --force-reinstall --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu
