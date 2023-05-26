import os
import json
import openai
import time
import csv
import re
import xml.etree.ElementTree as ET

from utils.gpt_util import if_exceed_token_limit
from project import Project
from path_config import DATA_DIR,API_KEY_FILEPATH,CONFIG_DIR, PRO_DIR
from utils.file_util import read_file
from utils.git_util import get_parent_commit
from utils.file_util import extract_content_within_line_range, read_file
from utils.markdown_util import extract_assertion
from utils.prompt_generator_util import get_vulnerable_function_attributes

from py4j.java_gateway import JavaGateway

# Organization IDs
orgs = ['org-0wLi1kKIt9USgXMYklRCeTFQ', 'org-9WS8eYC3IjH69yYgQNrk0X4w', 'org-yclg2hcASx6eAd3nEyoFKrlf']
org_counter = [0, 0, 0]
current_org = 0

# Setup                                                                                                                                                                                                       
openai.api_key = read_file(API_KEY_FILEPATH)  # OpenAPI key                                                                                                                                                   
MAX_INTERACTION = 10  # Maximum number of interactions
FEEDBACK_BUDGET = 5 # Maximum number of retries based on compilation and execution feedback                                                                                                                                                         
MODEL_NAME = "gpt-3.5-turbo"

global messages
def prompt_generator(interact_index=None, setup="", test="", focal=""):
    if interact_index == 0:
        return "Given the setup code <SETUP>, test prefix <TEST>, and focal method <FOCAL>, generate only one org.junit.Assert statement that is different from the previous one for the same <SETUP>, <TEST>, and <FOCAL>, where <SETUP>: {}\n<TEST>: {}\n<FOCAL>: {}\nDo not include any error message or precision value in the assert statement.".format(setup, test, focal)
    elif interact_index > 0:
        return "Can you generate another type of assertion?"

def shuffle_organization():
    global openai, orgs, org_counter, current_org

    # Shuffle organizations to avoid Rate Limit Error
    if org_counter[current_org] == 2:
        org_counter[current_org] = 0
        current_org = (current_org + 1) % len(org_counter)

def interact_with_openai():
    global openai, orgs, org_counter, current_org

    # Increase current organization's interaction counter for shuffle tracking
    openai.organization = orgs[current_org]
    org_counter[current_org] += 1

    # Get the model's response  
    while(True):
        try:
            # Function for interacting with the API                                                                                                                                                                   
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=messages
            )

            result = ""
            for choice in response.choices:
                result += choice.message.content
            break
        except Exception as e: 
            sum = 0
            for message in messages:
                sum += len(message['content'])

            print("\n\nMessage length: {}\n!!! Interaction Exception (Rate Limit Exceeded? Print Exception Message) - Sleeping for 20s !!!\n".format(sum))
            time.sleep(20)

    shuffle_organization()

    return result

def get_gpt_oracle():
    model_response = interact_with_openai()
    gpt_oracle = extract_assertion(model_response)
    print("Gen: {}".format(gpt_oracle))

    if gpt_oracle is not None:
        # add response to conversation history
        insert_message(role="assistant", content=gpt_oracle)

    return gpt_oracle

def ask(oracle_id, before_code, test_code, focal_code):
    global messages
    
    # Add user input to the conversation history                                                                                                                                                          
    prompt = prompt_generator(oracle_id, before_code, test_code, focal_code)
    insert_message(role="user", content=prompt)

    if if_exceed_token_limit(prompt, MODEL_NAME):
        #TODO: text-splitter
        pass

    gpt_oracle = get_gpt_oracle()

    return gpt_oracle

def follow_up(feedback_anchor, gpt_oracle):
    res, feedback = collect_feedback(gateway, project, filePath, className, test_name, test_code, gpt_oracle)

    for feedback_id in range(FEEDBACK_BUDGET):
        print('\n\nMESSAGES:')
        print(messages)
        print('\n\n')
        if feedback is not None:
            if len(feedback) > 0 and (feedback_id != FEEDBACK_BUDGET): 
                gpt_oracle = get_gpt_oracle()
            elif len(feedback) == 0 or (feedback_id == FEEDBACK_BUDGET-1):
                # Cleanup feedback chain
                for msg_id in range(len(messages)-1, feedback_anchor-1, -1): messages.pop(msg_id)
                # Add the most recent gpt_oracle that resolved compilation/test errors or if FEEDBACK_BUDGET is over select the last gpt_oracle in the feedback chain
                insert_message(role="assistant", content=gpt_oracle)
                # Either no error has occurred or the compilation/test error was not resolved within the FEEDBACK_BUDGET
                print('\n\nAFTER CLEANUP:')
                print(messages)
                print('\n\n')
                break

        res, feedback = collect_feedback(gateway, project, filePath, className, test_name, test_code, gpt_oracle)                       
    
    return res, feedback, gpt_oracle

def insert_message(role, content):
    global messages
    messages.append({"role": role, "content": content})

def collect_feedback(javaGateway, project, file_path, class_name, test_name, test_code, gpt_oracle):
    # Check if the oracle is plausible (using py4j and Java Method Injector)
    try:
        testInjector = javaGateway.entry_point
        testInjector.setFile(file_path)
        testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>", gpt_oracle))

        res, output = project.run_test(class_name, test_name)
        output = output.lower()

        feedback = ""
        output_lines = output.split('\n')
        
        for i in range(len(output_lines)):
            # Compilation error
            if "compilation failure" in output_lines[i]:
                if i+1 < len(output_lines):
                    feedback = "I am getting the following compilation error: \n{}\nCan you please fix the generated assert statement?".format(output_lines[i+1])
                else:
                    print('\n\n!!! Could not retrieve compilation error message !!!\n\n')
                break

            # Test failure
            if "test failures" in output_lines[i]:
                report_dir = os.path.join(project.repo_dir, 'target/surefire-reports/')
                report_path = None
                for r_path in os.listdir(report_dir):
                    if (class_name + '.xml') in r_path:
                        report_path = os.path.join(report_dir, r_path)
                        break
                
                if report_path is None:
                    print('\n\n!!! Could not retrieve test error message (report path not found) !!!\n\n')
                else:
                    report = ET.parse(report_path)
                    root = report.getroot()
                    message_found = False
                    for item in root.findall('./testcase'):
                        for child in item:
                            if child.tag == 'failure':
                                err_msg = child.attrib['message'] if 'message' in child.attrib else child.text.split('\n')[0]
                                feedback = "I am getting the following test failure: \n{}\nCan you please fix the generated assert statement?".format(err_msg)
                                message_found = True
                                break
                        # If there are multiple test cases reported then consider the failure message of only the first test case
                        if message_found:
                            break
                    if not message_found:
                        print('\n\n!!! Could not retrieve test error message (report not found in xml) !!!\n\n')
                break

        if len(feedback) > 0:
            print('\nFEEDBACK: {}\n'.format(feedback))
            insert_message(role='user', content=feedback)
    
        return res, feedback

    except Exception as e:
        print('Exception: {}'.format(e))

    return None, None

if __name__ == "__main__":
    global messages
    messages = [
        {"role": "system", "content": "You are a chatbot for oracle generation."},
    ]

    gateway = JavaGateway()
    assertionTypes = ['assertEquals', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull', 'assertArrayEquals', 'assertThat']

    with open(os.path.join(PRO_DIR, "prelim_res.csv"), "w+") as resCSV:
        csvWriter = csv.writer(resCSV, delimiter='\t')
        csvWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Corr", "Incorr", "BuildErr", "RunErr", "TestFailure"])

        corr, incorr, build_err, run_err, test_failure = 0, 0, 0, 0, 0

        configuration_file = os.path.join(PRO_DIR, "new_data.json")
        with open(configuration_file) as f:
            data = json.load(f)
            testId = 0
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
                    filePath = os.path.join(project.repo_dir, classPath)
                    classTests = testClass["classTests"]

                    before_name = ""
                    before_code = ""
                    after_code = ""

                    if "before" in testClass:
                        # before_code = "".join(read_file(filePath, int(testClass["before"]["startLn"]), int(testClass["before"]["endLn"])))
                        before_name = testClass["before"]["setupName"]
                        before_code = testClass["before"]["setupMethod"]
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
                        testId += 1
                        test_name = test["testName"]
                        test_lines = read_file(filePath, int(test["startLn"]), int(test["endLn"]))
                        # test_lines[test["oracleLn"]-test["startLn"]] = "<AssertPlaceHolder>"
                                
                        # test_code = "".join(test_lines)
                        test_code = test["testMethod"]

                        focal_name = test["focalName"]
                        focal_path = os.path.join(project.repo_dir, test["focalFile"])
                        # focal_code = "".join(read_file(os.path.join(project.repo_dir, test["focalFile"]), test["focalStartLn"], test["focalEndLn"])) if "focalFile" in test else ""
                        focal_code = test["focalMethod"]

                        # RQ1. Exp1. Rewrite the original source code to comply with Teco's formatting (e.g. no comments, string literals are replaced by STR)
                        testInjector = gateway.entry_point
                        testInjector.setFile(filePath)
                        testInjector.inject(test_name, test_code)
                        if before_name != "":
                            testInjector.inject(before_name, before_code)

                        focalInjector = gateway.entry_point
                        focalInjector.setFile(focal_path)
                        focalInjector.inject(focal_name, focal_code)

                        # oracle_code = "".join(read_file(filePath, int(test["oracleLn"]), int(test["oracleLn"])))
                        oracle_code = test['oracle']
                        test_code = test_code.replace(oracle_code, "<AssertPlaceHolder>")

                        # print('\n\nTEST CODE: {}\nORACLE CODE: {}\nTEST CODE: {}\n\n'.format(''.join(test_lines), oracle_code, test_code))

                        messages = [
                            {"role": "system", "content": "You are a chatbot for oracle generation."},
                        ]
                        feedback_anchor = None
                        # for variantId, assertion_type in enumerate(assertionTypes):                            
                        for oracle_id in range(MAX_INTERACTION):
                            print('\n\n')
                            gpt_oracle = ask(oracle_id, before_code, test_code, focal_code)
                            if gpt_oracle == None: continue
                            res, feedback, gpt_oracle = follow_up(feedback_anchor=len(messages)-1, gpt_oracle=gpt_oracle)

                            if res is not None:
                                csv_corr, csv_incorr, csv_buildErr, csv_runErr, csv_testFailure = "0", "0", "0", "0", "0"
                                
                                # if res["tests"] == 0:
                                #     raise Exception("unexpected: could not find tests in this project")

                                if res["build_failure"]:
                                    print("Build failure has occurred")
                                    build_err += 1
                                    csv_buildErr = "1"
                                elif res["failures"]+res["errors"] == 0:
                                    print("Plausible oracle detected")
                                    
                                    if gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").replace(" ", "").strip() == oracle_code.replace("org.junit.Assert.", "").replace("Assert.", "").replace(" ", "").strip():
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

                                csvWriter.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId, oracle_id, userName, repoName, className, test_name, oracle_code.strip(), gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip(), csv_corr, csv_incorr, csv_buildErr, csv_runErr, csv_testFailure).split('\t'))

                                # input('\n\nENTER A KEY')
                    #         break
                    #     break
                    # break

            print('\n---------------------\nCorrect: {}\nIncorrect: {}\nBuild Error: {}\nTest Error: {}\nTest Failure: {}\n---------------------\n'.format(str(corr), str(incorr), str(build_err), str(run_err), str(test_failure)))
