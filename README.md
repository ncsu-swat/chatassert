# genoracle

# Setup 

  - Create a Python 3.11.2 virtual environment with all
    dependencies. Run the command: \
    `$> bash create_env.sh`
  - From the root directory:
    - Create file `openai_api.key` and add a key to access the openai API (Optional if you wish to use the mock version)
    - Run the following command \
      `$> export PYTHONPATH="$PWD/src"`


Obs. The script `src/test/s.sh` sets up the environment to run the
script doall.py. 

# Execution

 - System requirements: Java 1.8 and Maven 3.8
 - In one terminal CD into the `astvisitors` directory
 - Run `bash s` and keep the terminal open
 - Open a separate terminal CD into the `src/main` directory
 - Run `python3 doall.py` (Append option `v1` for running without feedback loop, option `v2` for running with feedback loop, option `mock` to use the mock version instead of the actual ChatGPT API (mock currently supports the tests `testToMillibar` and `testReadExcel`)
