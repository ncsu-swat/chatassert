from main.utils.git_util import reset_repo, clone_repo
from main.utils.cmd_util import execute_cmd_with_output
from main.utils.file_util import delete_folder
import os
from path_config import TMP_DIR
import re

class Project():

    def __init__(self, project_name, project_url, cur_com):
        self.project_name = project_name
        self.project_url = project_url        
        self.cur_com = cur_com
        self.repo_dir = os.path.join(TMP_DIR, "repos", project_name)

    def init_env(self): 
        # delete folder if it exists
        delete_folder(self.repo_dir)

        # cloning the repo
        print("Cloning the repo to {}...".format(self.repo_dir))
        clone_repo(self.repo_dir, self.project_url)

        # reset
        print("Reseting the repo to {}...".format(self.cur_com))
        reset_repo(self.repo_dir, self.cur_com)
        print("Done.")

    def run_tests(self):
        res_dict = {"build_failure": False, "tests": 0, "failures": 0, "errors": 0}
        print("Running maven tests...")
        output = execute_cmd_with_output("cd {}; mvn clean test".format(self.repo_dir))
        print("Done.")
        # parse the result
        print("Parsing the result...")
        if "BUILD FAILURE" in output:
            res_dict["build_failure"] = True
            return res_dict
        for line in output.splitlines():
            if "Tests run:" in line and not "Time" in line:
                ar = re.findall(r'\d+', line)
                if len(ar) != 4:
                    raise Exception("Check! expecting 4 elements in the output.\n   For example: [INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0")
                res_dict["tests"] = int(ar[0])
                res_dict["failures"] = int(ar[1])
                res_dict["errors"] = int(ar[2])
                return res_dict


    def replace_oracle_atln(self, filepath, neworacle, ln):
        ## read file into array
        with open(filepath, 'r') as file:
            # read a list of lines into data
            data = file.readlines()
        # for x in range(len(data)):
        #     print('{}: {}'.format(x, data[x]))

        # defensive programming; check that we are replacing an assertion
        if not "ssert" in data[ln-1]:
            return Exception("unexpected: trying to replace a line without assertion")                            
        # update the array
        data[ln-1] = neworacle + '\n'
        # write array to file
        with open(filepath, 'w') as file:
            file.writelines(data)