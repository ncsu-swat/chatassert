import os
import sys
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
from utils.mock_gpt import mock_response

from py4j.java_gateway import JavaGateway

# Organization IDs
orgs = ['org-0wLi1kKIt9USgXMYklRCeTFQ', 'org-9WS8eYC3IjH69yYgQNrk0X4w', 'org-yclg2hcASx6eAd3nEyoFKrlf']
org_counter = [0, 0, 0]
current_org = 0

# Setup                                                                                                                                                                                                       
openai.api_key = read_file(API_KEY_FILEPATH)  # OpenAPI key                                                                                                                                                   
MAX_INTERACTION = 50  # Maximum number of interactions
TARGET_NUMBER = 10 # Number of oracles to be generated
FEEDBACK_BUDGET = 2 # Maximum number of retries based on compilation and execution feedback                                                                                                                                                         
MODEL_NAME = "gpt-3.5-turbo"
SYSTEM_ROLE = "You are a programmer who is proficient in Java programming languge"

global conversation_history, feedback_history
def prompt_generator(interact_index=None, setup="", test="", focal=""):
    if interact_index == 0:
        return "Given the setup code <SETUP>, test prefix <TEST>, and focal method <FOCAL>, generate only one org.junit.Assert statement where,\n\n<SETUP>: ```{}```\n\n<TEST>: ```{}```\n\n<FOCAL>: ```{}```\n".format(setup, test, focal)
    elif interact_index > 0:
        return "Can you generate another type of assertion?"

def shuffle_organization():
    global openai, orgs, org_counter, current_org

    # Shuffle organizations to avoid Rate Limit Error
    if org_counter[current_org] == 2:
        org_counter[current_org] = 0
        current_org = (current_org + 1) % len(org_counter)

def interact_with_openai(temperature=1, which_history="conversation"):
    global history, conversation_history, feedback_history
    global openai, orgs, org_counter, current_org

    if which_history == "conversation": history = conversation_history
    elif which_history == "feedback": history = feedback_history

    # Increase current organization's interaction counter for shuffle tracking
    openai.organization = orgs[current_org]
    org_counter[current_org] += 1

    # Get the model's response  
    while(True):
        try:
            # Function for interacting with the API                                                                                                                                                                   
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=history,
                temperature=temperature
            )

            result = ""
            for choice in response.choices:
                result += choice.message.content
            break
        except Exception as e: 
            sum = 0
            for message in history:
                sum += len(message['content'])

            print("\n!!! Interaction Exception !!!")
            # Interaction exception can be either due to "exceeding token limit" or "exceeding rate limit"
            print("Message length: {}".format(sum))
            if sum > 3096:
                # Preemptively resetting conversation history to avoid future interaction exception due to exceeding token limit
                if which_history == "conversation":
                    conversation_history = [
                        {"role": "system", "content": SYSTEM_ROLE},
                        {"role": conversation_history[1]["role"], "content": conversation_history[1]["content"]} # Restoring original prompt
                    ]
                elif which_history == "feedback":
                    feedback_history = [
                        {"role": "system", "content": SYSTEM_ROLE}
                    ]

            else:
                print("Potentially rate limit exceeded - Sleeping for 20s\n")
                time.sleep(20)

    shuffle_organization()

    return result

def get_gpt_oracle(mock_flag=False, test_name="", temperature=1, which_history="conversation"):
    gpt_oracle = None
    
    if mock_flag:
        print(test_name)
        gpt_oracle = extract_assertion(mock_response(test_name))
        print("Gen: {}".format(gpt_oracle))

        if gpt_oracle is None:
            return None
    else:
        model_response = interact_with_openai(temperature, which_history)
        gpt_oracle = extract_assertion(model_response)
        print("Gen: {}".format(gpt_oracle))

        if (gpt_oracle is None) or (gpt_oracle.strip() == "org.junit.Assert."):
            return None

    return gpt_oracle

def ask(mock_flag, oracle_id, test_name, before_code, test_code, focal_code):
    global conversation_history
    
    # Add user input to the conversation history                                                                                                                                                          
    prompt = prompt_generator(oracle_id, before_code, test_code, focal_code)
    insert_message(role="user", content=prompt, which_history="conversation")

    if if_exceed_token_limit(prompt, MODEL_NAME):
        #TODO: text-splitter
        pass

    gpt_oracle = get_gpt_oracle(mock_flag=mock_flag, test_name=test_name)

    return gpt_oracle

def follow_up(mock_flag, gateway, oracle_id, project, file_path, className, test_name, test_code, gpt_oracle):
    # Adding the original assertion generation prompt in the feedback chain to give ChatGPT more content
    insert_message(role="user", content=conversation_history[1]["content"], which_history="feedback")

    res, feedback = collect_feedback(gateway, oracle_id, project, filePath, className, test_name, test_code, gpt_oracle)

    for feedback_id in range(FEEDBACK_BUDGET):
        # print('\nFEEDBACK ID: {}\n'.format(str(feedback_id)))
        if feedback is not None:
            if len(feedback) > 0 and (feedback_id < FEEDBACK_BUDGET-1): 
                insert_message(role="assistant", content=gpt_oracle, which_history="feedback")

                fixed_gpt_oracle = get_gpt_oracle(mock_flag=mock_flag, test_name=test_name, temperature=1.5, which_history="feedback")
                if fixed_gpt_oracle is None: continue
                else: gpt_oracle = fixed_gpt_oracle
            elif len(feedback) == 0:
                break

        res, feedback = collect_feedback(gateway, oracle_id, project, filePath, className, test_name, test_code, gpt_oracle)                       
    
    if feedback is None or len(feedback) > 0:
        # Even after exhausting the feedback budget, no plausible oracle was found
        return None, None, None

    return res, feedback, gpt_oracle

def collect_feedback(javaGateway, oracle_id, project, file_path, class_name, test_name, test_code, gpt_oracle):
    # Check if the oracle is plausible (using py4j and Java Method Injector)
    try:
        testInjector = javaGateway.entry_point
        testInjector.setFile(file_path)
        testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>", gpt_oracle))

        res, output = project.run_test(class_name, test_name)

        with open('execution_log/{}_{}.txt'.format(test_name, oracle_id), 'w+') as logFile:
            logFile.write(output)

        feedback = ""
        output_lines = output.split('\n')
        
        for i in range(len(output_lines)):
            # Compilation error
            if "COMPILATION ERROR" in output_lines[i]:
                err_msg = ""
                err_line = 2
                while(i+err_line < len(output_lines)): # Get the next 5 lines until we get a line with INFO or ERROR or WARNING
                    if (err_line == 2) and (i+err_line < len(output_lines)):
                        err_msg += output_lines[i+err_line]
                    elif (err_line > 2) and (i+err_line < len(output_lines)):
                        if ("[ERROR]" in output_lines[i+err_line]) or ("[INFO]" in output_lines[i+err_line]) or ("[WARNING]" in output_lines[i+err_line]):
                            feedback = "I am getting the following compilation error: \n{}\nCan you please fix the generated assert statement?".format(err_msg.replace("[ERROR]", ""))
                            break
                        else:
                            err_msg += " " + output_lines[i+err_line]
                    else:
                        if len(feedback) == 0:
                            print('\n\n!!! Could not retrieve compilation error message !!!\n\n')
                    err_line += 1
                break

            # Test failure
            if "test failures" in output_lines[i].lower():
                report_dir = os.path.join(project.repo_dir, 'target/surefire-reports/')
                report_path = None
                for r_path in os.listdir(report_dir):
                    if (class_name + '.xml') in r_path:
                        report_path = os.path.join(report_dir, r_path)
                        break
                
                if report_path is None:
                    print("\n\n!!! Could not retrieve test error message (report path not found) !!!\n\n")
                else:
                    report = ET.parse(report_path)
                    root = report.getroot()
                    message_found = False
                    for item in root.findall("./testcase"):
                        for child in item:
                            if child.tag == "failure" or child.tag == "error":
                                err_msg = child.attrib['message'] if 'message' in child.attrib else child.text.split('\n')[0]
                                feedback = "I am getting the following test {}: \n{}\nCan you please fix the generated assert statement?".format(child.tag, err_msg)
                                message_found = True
                                break
                        # If there are multiple test cases reported then consider the failure message of only the first test case
                        if message_found:
                            break
                    if not message_found:
                        print('\n\n!!! Could not retrieve test error message (report not found in xml) !!!\n\n')
                break

        if len(feedback) > 0:
            # print('\nFEEDBACK: {}\n'.format(feedback))
            insert_message(role="user", content=feedback, which_history="feedback")
    
        return res, feedback

    except Exception as e:
        print('Exception: {}'.format(e))

    return None, None

def insert_message(role, content, which_history):
    global conversation_history, feedback_history
    if which_history == "conversation": conversation_history.append({"role": role, "content": content})
    elif which_history == "feedback": feedback_history.append({"role": role, "content": content})

if __name__ == "__main__":
    v1_flag, v2_flag, mock_flag = False, False, False
    arg = " ".join(sys.argv)
    if 'v1' in arg: v1_flag = True
    if 'v2' in arg: v2_flag = True
    if 'mock' in arg: mock_flag = True

    global conversation_history, feedback_history
    conversation_history = [
        {"role": "system", "content": SYSTEM_ROLE},
    ]

    gateway = JavaGateway()
    assertionTypes = ['assertEquals', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull', 'assertArrayEquals', 'assertThat']

    with open(os.path.join(PRO_DIR, "res_all.csv"), "w+") as resAll, open(os.path.join(PRO_DIR, "res_pass.csv"), "w+") as resPass:
        resAllWriter = csv.writer(resAll, delimiter='\t')
        resPassWriter = csv.writer(resPass, delimiter='\t')

        resAllWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Time", "Corr", "Incorr", "BuildErr", "RunErr", "TestFailure"])
        resPassWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Time", "Corr", "Incorr", "BuildErr", "RunErr", "TestFailure"])

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
                
                # removing existing repo
                if repoName in os.listdir('../tmp/repos'):
                    os.system('rm -rf ../tmp/repos/{}'.format(repoName))
                
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
                        test_lines = read_file(filePath, int(test["startLn"]), int(test["oracleLn"]))
                        if len(test_lines) == 0: continue
                        test_lines[test["oracleLn"]-test["startLn"]] = "\t<AssertPlaceHolder>\n}"
                                
                        test_code = "".join(test_lines)
                        # test_code = test["testMethod"]

                        focal_name = test["focalName"]
                        focal_path = os.path.join(project.repo_dir, test["focalFile"])
                        focal_code = "".join(read_file(os.path.join(project.repo_dir, test["focalFile"]), test["focalStartLn"], test["focalEndLn"])) if "focalFile" in test else ""
                        # focal_code = test["focalMethod"]

                        # RQ1. Exp1. Rewrite the original source code to comply with Teco's formatting (e.g. no comments, string literals are replaced by STR)
                        # testInjector = gateway.entry_point
                        # testInjector.setFile(filePath)
                        # testInjector.inject(test_name, test_code)
                        # if before_name != "":
                        #     testInjector.inject(before_name, before_code)

                        # focalInjector = gateway.entry_point
                        # focalInjector.setFile(focal_path)
                        # focalInjector.inject(focal_name, focal_code)

                        # oracle_code = "".join(read_file(filePath, int(test["oracleLn"]), int(test["oracleLn"])))
                        oracle_code = test['oracle']
                        # test_code = test_code.replace(oracle_code, "<AssertPlaceHolder>")

                        # print('\n\nTEST CODE: {}\nORACLE CODE: {}\nTEST CODE: {}\n\n'.format(''.join(test_lines), oracle_code, test_code))

                        conversation_history = [
                            {"role": "system", "content": SYSTEM_ROLE},
                        ]
                        target_number = TARGET_NUMBER
                        # for variantId, assertion_type in enumerate(assertionTypes):                            
                        for oracle_id in range(MAX_INTERACTION):
                            start_time = time.time()

                            feedback_history = [
                                {"role": "system", "content": SYSTEM_ROLE},
                            ]

                            if target_number == 0: break # Already produced TARGET_NUMBER of plausible oracles for this test

                            res, feedback = None, None
                            if v1_flag: # Single feedback
                                gpt_oracle = ask(mock_flag, oracle_id, test_name, before_code, test_code, focal_code)
                                if gpt_oracle is None: continue
                                res, feedback = collect_feedback(gateway, oracle_id, project, filePath, className, test_name, test_code, gpt_oracle)

                            elif v2_flag: # Feedback loop
                                gpt_oracle = ask(mock_flag, oracle_id, test_name, before_code, test_code, focal_code)
                                if gpt_oracle is None: continue
                                res, feedback, gpt_oracle = follow_up(mock_flag, gateway, oracle_id, project, filePath, className, test_name, test_code, gpt_oracle)
                                if gpt_oracle is None: continue

                                if len(feedback) > 0:
                                    # Explicitly tell ChatGPT to avoid gpt_oracle
                                    insert_message(role="assistant", content="AVOID generating the assertion `"+gpt_oracle+"`", which_history="conversation")

                                # # Check if the returned oracle compiles and runs and if yes, add it to main conversation history (the main conversation history should not contain any invalid assertion that does not compile or run)
                                if len(gpt_oracle) > 0 and len(feedback) == 0:
                                    # Oracle compiles and runs - add it to main conversation history
                                    insert_message(role="assistant", content=gpt_oracle, which_history="conversation")
                                    target_number -= 1

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

                                end_time = time.time()

                                if len(feedback) == 0:
                                    resPassWriter.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId, oracle_id, userName, repoName, className, test_name, oracle_code.strip(), gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip(), str(end_time-start_time), csv_corr, csv_incorr, csv_buildErr, csv_runErr, csv_testFailure).split('\t'))
                                
                                resAllWriter.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId, oracle_id, userName, repoName, className, test_name, oracle_code.strip(), gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip(), str(end_time-start_time), csv_corr, csv_incorr, csv_buildErr, csv_runErr, csv_testFailure).split('\t'))

                                # input('\n\nENTER A KEY')
                    #         break
                    #     break
                    # break

            print('\n---------------------\nCorrect: {}\nIncorrect: {}\nBuild Error: {}\nTest Error: {}\nTest Failure: {}\n---------------------\n'.format(str(corr), str(incorr), str(build_err), str(run_err), str(test_failure)))
