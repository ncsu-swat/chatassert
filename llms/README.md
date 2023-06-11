create_venv.sh: script to create virtual environment
requirements.txt: list of dependencies
env: automatically-created virtual environment (see create_venv.sh)
...rest are LLM models


source env/bin/activate
# Need to set python path from (this) root directory
export PYTHONPATH=`pwd`