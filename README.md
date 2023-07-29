# ChatAssert

# Requirements

 - System requirements: Java 1.8 and Maven 3.8

# Setup 

  - Create a Python 3.11.2 virtual environment with all
    dependencies. Run the command: \
    `$> bash create_env.sh`
  - Create openai key file. **This file is personal; it is listed on .gitignore** 
      - Create file `src/openai_api.key` and add a key to access the openai API. (This step is optional if you use the option "mock" to run our tool.)
  - For every new terminal: from the root directory, run the following commands:
      - `export PYTHONPATH="$PWD/src"`
      - `source env/bin/activate`

# Execution

 - **Step 1**: Spawn the java transformation server:
    - Open a terminal and CD into the `astvisitors` directory
    - Run `bash s` and keep the terminal open
 - **Step 2:** From a separate terminal
    - CD into the `src/main` directory
    - Examples:
        - Run `python3 doall.py v1` # for running L-One
        - Run `python3 doall.py v2` # for running ChatAssert
