import os
import json
import openai
import time
import csv

from utils.gpt_util import if_exceed_token_limit
from project import Project
from path_config import DATA_DIR,API_KEY_FILEPATH,CONFIG_DIR, PRO_DIR
from utils.file_util import read_file
from utils.git_util import get_parent_commit
from utils.file_util import extract_content_within_line_range, read_file
from utils.markdown_util import extract_code_block_from_markdown_text
from utils.prompt_generator_util import get_vulnerable_function_attributes

# Setup                                                                                                                                                                                                       
openai.api_key = read_file(API_KEY_FILEPATH)  # OpenAPI key                                                                                                                                                   
MAX_INTERACTION = 3  # Maximum number of interactions                                                                                                                                                         
MODEL_NAME = "gpt-3.5-turbo"

def interact_with_openai(prompt):
    # Function for interacting with the API                                                                                                                                                                   

    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a chatbot for oracle generation."},
            {"role": "user", "content": prompt},
        ]
    )

    result = ""
    for choice in response.choices:
        result += choice.message.content

    return result


def prompt_generator(interact_index, setup="", test="", focal=""):
    return "Given the setup code <SETUP>, test prefix <TEST>, and focal method <FOCAL>, generate only one org.junit.Assert statement, where <SETUP>: {}\n<TEST>: {}\n<FOCAL>: {}\nDo not include any error message or precision value in the assert statement.".format(setup, test, focal)


if __name__ == "__main__":
    with open(os.path.join(PRO_DIR, "prelim_res.csv"), "w+") as resCSV:
        csvWriter = csv.writer(resCSV, delimiter='\t')
        csvWriter.writerow(["Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Corr", "Incorr", "BuildErr", "RunErr", "TestFailure"])

        corr, incorr, build_err, run_err, test_failure = 0, 0, 0, 0, 0

        configuration_file = os.path.join(PRO_DIR, "data.json")
        with open(configuration_file) as f:
            data = json.load(f)
            for project_data in data["projects"]:
                print('\n-----------------------\nPROJECT NAME: {}\{}\n-----------------------\n'.format(project_data["userName"], project_data["repoName"]))

                userName = project_data["userName"]
                repoName = project_data["repoName"]
                subDir = project_data["subRepo"] if "subRepo" in project_data else ""
                gitURL = "git@github.com:{}/{}.git".format(userName, repoName)
                commit = project_data["commitSHA"]
                allTests = project_data["allTests"]
                # create project object
                project = Project(repoName, subDir, gitURL, commit)
                # clone the project
                project.init_env()

                for testClass in allTests:
                    className = testClass["className"]
                    classPath = testClass["classPath"]
                    filePath = os.path.join(project.repo_dir, classPath+"/"+className+".java")
                    classTests = testClass["classTests"]

                    before_code = ""
                    after_code = ""

                    if "before" in testClass:
                        before_code = "".join(read_file(filePath, int(testClass["before"]["startLn"]), int(testClass["before"]["endLn"])))
                    if "after" in testClass:
                        after_code = "".join(read_file(filePath, int(testClass["after"]["startLn"]), int(testClass["after"]["endLn"])))

                    # run the tests before anlyzing to make sure that there are tests and that the tests pass
                    # res = project.run_tests()
                    # if res["tests"] == 0:
                    #     raise Exception("unexpected: could not find tests in this project")
                    # if res["failures"]+res["errors"] > 0:
                    #     raise Exception("expecting all tests to pass")
                            
                    print("\n-----------------------------------------\nAnalyzing Oracles for Test Class: {}\n-----------------------------------------\n".format(className))
                    for test in classTests:
                        testName = test["testName"]
                        test_lines = read_file(filePath, int(test["startLn"]), int(test["endLn"]))
                        test_lines[test["oracleLn"]-test["startLn"]] = "<AssertPlaceHolder>"
                        test_code = "".join(test_lines)
                        focal_code = "".join(read_file(os.path.join(project.repo_dir, test["focalFile"]), test["focalStartLn"], test["focalEndLn"])) if "focalFile" in test else ""

                        oracle_code = "".join(read_file(filePath, int(test["oracleLn"]), int(test["oracleLn"])))

                        #TODO: ask gpt to generate oracles
                        '''
                        1. replace oracle with whatever gpt gives
                        2. compile and run tests
                        3. stop if finds a solution
                        4. repeat for a number of times
                        '''

                        # Initialize the conversation history                                                                                                                                                                     
                        conversation_history = ""

                        for i in range(1, MAX_INTERACTION + 1):
                            # Add user input to the conversation history                                                                                                                                                          
                            prompt = prompt_generator(i, before_code, test_code, focal_code)
                            # prompt = f"{conversation_history}\n{prompt}"
                            if if_exceed_token_limit(prompt, MODEL_NAME):
                                #TODO: text-splitter
                                break

                            # Get the model's response  
                            while(True):
                                try:
                                    model_response = interact_with_openai(prompt)
                                    print('\nRESPONSE:\n'+model_response+'\n')
                                    break
                                except Exception as e:                                                                                                                                                                          
                                    print("\n\n!!! Interaction Exception (Rate Limit Exceeded? Print Exception Message) - Sleeping for 20s !!!\n")
                                    time.sleep(20)

                            # print('\n---------------------\nChatGPT Response:\n---------------------')
                            # print(model_response)
                            # print('\n----------------------------------------------\n')

                            gpt_oracle = extract_code_block_from_markdown_text(model_response)
                            print("Gen: {}".format(gpt_oracle))

                            if gpt_oracle == None:
                                continue ## could not find anything apparently

                            # use fully-qualified name for Assertion type
                            # TODO (low prio): Better solution is to use a type solver https://www.javadoc.io/doc/com.github.javaparser/javaparser-symbol-solver-core/3.6.10/com/github/javaparser/symbolsolver/JavaSymbolSolver.html
                            gpt_oracle = gpt_oracle.lstrip()
                            if "Assert." in gpt_oracle:
                                gpt_oracle = gpt_oracle.replace("Assert.", "org.junit.Assert.")

                            # Check if the oracle is plausible
                            project.replace_oracle_atln(filepath=filePath, neworacle=gpt_oracle, ln=int(test["oracleLn"]))

                            res = project.run_test(className, testName)

                            csv_corr, csv_incorr, csv_buildErr, csv_runErr, csv_testFailure = "0", "0", "0", "0", "0"
                            
                            # if res["tests"] == 0:
                            #     raise Exception("unexpected: could not find tests in this project")

                            if res["failures"]+res["errors"] == 0:
                                print("Plausible oracle detected")
                                
                                ##TODO: check if oracle is identical
                                print('\n\n\nGPT Oracle: {}'.format(gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip()))
                                print('True Oracle: {}\n\n\n'.format(oracle_code.strip()))
                                if gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip() == oracle_code.strip():
                                    corr += 1
                                    csv_corr = "1"
                                else:
                                    incorr += 1
                                    csv_incorr = "1"

                                # break # DONE with this oracle
                            elif res["errors"] > 0:
                                print('Test error has occurred')
                                run_err += 1
                                csv_runErr = "1"
                            elif res["failures"] > 0:
                                print('Test failure has occurred')
                                test_failure += 1
                                csv_testFailure = "1"
                            elif res["build_failure"]:
                                build_err += 1
                                csv_buildErr = "1"
                                # continue # build failure

                            csvWriter.writerow("{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(userName, repoName, className, testName, oracle_code.strip(), gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip(), csv_corr, csv_incorr, csv_buildErr, csv_runErr, csv_testFailure).split('\t'))
                #             break
                #         break
                #     break
                # break

            print('\n---------------------\nCorrect: {}\nIncorrect: {}\nBuild Error: {}\nTest Error: {}\nTest Failure: {}\n---------------------\n'.format(str(corr), str(incorr), str(build_err), str(run_err), str(test_failure)))