import json
import subprocess
import os
import sys

INPUT_FILENAME = "generation-output.json"
TMP_FILENAME = "out.txt"

llm_generators = ["incoder", "xyz"]

root_dir = os.getcwd()
if not root_dir.endswith("pipeline"):
    raise "please, check! the root directory should be the pipeline directory"

# builds the visitor maven project
def clean_compile():
    os.chdir(os.path.join(root_dir, "../../astvisitors"))
    # Run the script
    subprocess.run(["mvn", "clean", "compile"])

# returns a line with variation of str_assertion with different holes injected
def dig_holes(str_assertion):
    os.chdir(os.path.join(root_dir, "../../astvisitors"))
    curdir = os.getcwd()
    # Run the script
    subprocess.run(["bash", "find_holes.sh", str_assertion])
    tmp_filename = os.path.join(curdir, TMP_FILENAME)
    with open(tmp_filename, 'r') as f:
        tmp = f.read()    
    os.remove(tmp_filename)
    return tmp

dict = {}
  
# Opening JSON file
with open(INPUT_FILENAME) as f:
    json_data = json.load(f)

    # clean compile the astvisitor directory
    clean_compile()

    # DEBUGGING
    # dig_holes("Assert.assertEquals(otp, OTP.generateOTP(OTP.generateOTP(otp)));")
    # sys.exit(0)

    # Iterating through the json list
    for key in list(json_data.keys()):
        # processing one oracle
        elem = json_data[key]
        oracles = set()
        # join oracles generated with different generators
        for llm in llm_generators:
            if elem.get(llm) is not None:
                oracles = oracles.union(elem[llm])
        print(f"processing {len(oracles)} oracles")
        for oracle in oracles:
            holes = set()
            # digging holes in oracle candidates
            ora_variations = dig_holes(oracle).split("\n")
            # iterate through each oracle with holes
            for ora_variation in ora_variations:
                holed_oracle = ora_variation.strip()
                if "<insert>" in holed_oracle:
                    holes.add(holed_oracle)
            # associated the set of holed oracles with 
            # corresponding parent oracle
            dict[oracle] = list(holes)

    # print dictionary        
    print(json.dumps(dict, indent=4))
