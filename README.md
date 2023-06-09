# genoracle

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


<!--
## Ishrak, I don't understand what this is doing here:
Obs. The script `src/test/s.sh` sets up the environment to run the
script doall.py. 
-->

# Execution

 - **Step 1**: Spawn the java transformation server:
    - Open a terminal and CD into the `astvisitors` directory
    - Run `bash s` and keep the terminal open
 - **Step 2:** From a separate terminal
    - CD into the `src/main` directory
    <!-- why doall.py instead of tname? why it does not take a (json?) file with all tests to generate assertions as input? -->
    - Examples:
        - Run `python3 doall.py` 
        - Run `python3 doall.py v1` # for running without feedback loop
        - Run `python3 doall.py v2` # for running with feedback loop 
        - Run `python3 doall.py mock` # to use the mock version instead of the actual ChatGPT API; mock currently supports the tests "testToMillibar" and "testReadExcel" only.
