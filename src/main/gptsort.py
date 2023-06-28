import os
import sys
import json
import openai
import time
import csv
import re
import shutil
import xml.etree.ElementTree as ET
from random import randint

from utils.gpt_util import if_exceed_token_limit
from project import Project
from path_config import DATA_DIR,API_KEY_FILEPATH,CONFIG_DIR, PRO_DIR
from utils.file_util import read_file
from utils.git_util import get_parent_commit
from utils.file_util import extract_content_within_line_range, read_file
from utils.markdown_util import extract_assertions, abstract_string_literals, check_commutative_equal
from utils.prompt_generator_util import get_vulnerable_function_attributes
from utils.mock_gpt import mock_response

from py4j.java_gateway import JavaGateway
from subprocess import Popen
# print("-----------------------------------------------\nSTARTING JAVA GATEWAY SERVER\n-----------------------------------------------\n")
# jServer = Popen(["bash", "s"], cwd="../../astvisitors")
# print("\n>> WAITING FOR JAVA GATEWAY SERVER TO START <<\n")
# time.sleep(15) # Giving the java gateway server some time to initiate
# print("\n>> JAVA GATEWAY SERVER STARTED <<\n-----------------------------------------------\n")

# Organization IDs
orgs = ['org-0wLi1kKIt9USgXMYklRCeTFQ', 'org-9WS8eYC3IjH69yYgQNrk0X4w', 'org-yclg2hcASx6eAd3nEyoFKrlf']
org_counter = [0, 0, 0]
current_org = 0

# Setup                                                                                                                                                                                                       
openai.api_key = read_file(API_KEY_FILEPATH)  # OpenAPI key                                                                                                                                                   
MAX_INTERACTION = 30  # Maximum number of interactions
TARGET_NUMBER = 10 # Number of oracles to be generated
FEEDBACK_BUDGET = 2 # Maximum number of retries based on compilation and execution feedback                                                                                                                                                         
MODEL_NAME = "gpt-3.5-turbo"
SYSTEM_ROLE = "You are a programmer who is proficient in Java programming languge"

ASK, SORT = 0, 1
SORTED, UNSORTED = 1, 0

global conversation_history, feedback_history

def prompt_generator(interact_index=None, setup="", test="", focal="", sorting_candidates=None):
    if interact_index == 0:
        return "Given the setup code <SETUP>, test prefix <TEST>, and focal method <FOCAL>, generate 30 different org.junit.Assert statements, where,\n\n<SETUP>:\n```{}```\n\n<TEST>:\n```{}```\n\n<FOCAL>:\n```{}```\n".format(setup, test, focal)
    elif interact_index == 1 and sorting_candidates is not None:
        prompt = "Given the setup code <SETUP>, test prefix <TEST>, and focal method <FOCAL>, sort the 30 different org.junit.Assert statements <ASSERTS> based on how good they fit the test method, where,\n\n<SETUP>:\n```{}```\n\n<TEST>:\n```{}```\n\n<FOCAL>:\n```{}```\n<ASSERTS>:\n".format(setup, test, focal)
        for (i, assertion) in enumerate(sorting_candidates):
            prompt += "\t```{}```\n".format(assertion)
        return prompt
    return None

def shuffle_organization():
    global openai, orgs, org_counter, current_org

    # Shuffle organizations to avoid Rate Limit Error
    if org_counter[current_org] == 2:
        org_counter[current_org] = 0
        current_org = (current_org + 1) % len(org_counter)

def ask(test_name, before_code, test_code, focal_code, oracle_code):
    global conversation_history
    
    # Add user input to the conversation history                                                                                                                                                          
    prompt = prompt_generator(ASK, before_code, test_code, focal_code, None)
    insert_message(role="user", content=prompt, which_history="conversation")

    if if_exceed_token_limit(prompt, MODEL_NAME):
        #TODO: text-splitter
        pass

    gpt_oracles = get_gpt_oracles(test_name=test_name)
    if gpt_oracles is None or len(gpt_oracles) == 0: return None, None

    # Sort
    gpt_oracles[randint(0, len(gpt_oracles)-1)] = oracle_code # JUSTSORT (ground truth is always in the prediction)

    prompt = prompt_generator(SORT, before_code, test_code, focal_code, gpt_oracles)
    insert_message(role="user", content=prompt, which_history="conversation")

    sorted_gpt_oracles = get_gpt_oracles(test_name=test_name)[0:TARGET_NUMBER]
    if sorted_gpt_oracles is None or len(sorted_gpt_oracles) == 0:
        # Try one more time
        sorted_gpt_oracles = get_gpt_oracles(test_name=test_name)[0:TARGET_NUMBER]

    if sorted_gpt_oracles is None or len(sorted_gpt_oracles) == 0:
        return gpt_oracles[0:TARGET_NUMBER], UNSORTED

    return sorted_gpt_oracles, SORTED

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
                sum += len(message['content'])/4 # OpenAI considers one token to consist of ~4 characters (ref. OpenAI website)

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
                    history = conversation_history
                elif which_history == "feedback":
                    feedback_history = [
                        {"role": "system", "content": SYSTEM_ROLE}
                    ]
                    history = feedback_history

            else:
                print("Potentially rate limit exceeded - Sleeping for 20s\n")
                time.sleep(20)

    shuffle_organization()

    return result

def get_gpt_oracles(test_name="", temperature=1, which_history="conversation"):
    gpt_oracles = None
    
    model_response = interact_with_openai(temperature, which_history)
    gpt_oracles = extract_assertions(model_response)
    print("Gen: {}".format(gpt_oracles))

    if gpt_oracles is None:
        return None

    return gpt_oracles

def insert_message(role, content, which_history):
    global conversation_history, feedback_history
    if which_history == "conversation": conversation_history.append({"role": role, "content": content})
    elif which_history == "feedback": feedback_history.append({"role": role, "content": content})

def tecofy_testlines(lines, startLn, oracleLn):
    tecofied_lines = []

    if len(lines) == 0:
        return []

    tecofied_lines.append(lines[0])
    tecofied_lines.append(lines[1])

    lines = lines[2:]

    i = -1
    while i+1 < len(lines):
        i += 1
        line = lines[i].strip()

        if len(line) > 0:
            if line[0] == '/' and line[1] == '/':
                continue
            if line[0] == '/' and line[1] == '*':
                while True:
                    if len(line) > 0:
                        if '*/' in line:
                            if len(line[line.find('*/')+2:]) > 0:
                                if len(tecofied_lines) == (oracleLn-startLn):
                                    # Trigger stop
                                    tecofied_lines.append("<AssertPlaceHolder>;")
                                    tecofied_lines.append("}")
                                    i = len(lines)
                                else:
                                    tecofied_lines.append(line[line.find('*/')+2:])
                            break
                    i += 1
                    line = lines[i].strip()
                continue
            if line[-1] != ';':
                while i < len(lines):
                    if i+1 < len(lines): 
                        line += lines[i+1].strip()
                    i += 1
                    if i < len(lines):
                        if len(lines[i].strip()) > 0 and lines[i].strip()[-1] == ';':
                            break
            
            if len(tecofied_lines) == (oracleLn-startLn):
                # Trigger stop
                tecofied_lines.append("<AssertPlaceHolder>;")
                tecofied_lines.append("}")
                break
            else:
                tecofied_lines.append(line)
    return tecofied_lines

def backup_test_file(file_path):
    backup_file_path = file_path.replace(".java", "") + "_backup.txt"
    shutil.copyfile(file_path, backup_file_path)

def restore_test_file(file_path):
    backup_file_path = file_path.replace(".java", "") + "_backup.txt"
    shutil.copyfile(backup_file_path, file_path)

if __name__ == "__main__":
    # Input data sample id (e.g. sample_1.json)
    sample_id = sys.argv[-1]

    print('SAMPLE: sample_{}.json'.format(sample_id))

    global conversation_history, feedback_history
    conversation_history = [
        {"role": "system", "content": SYSTEM_ROLE},
    ]

    gateway = JavaGateway()

    with open(os.path.join(PRO_DIR, "res_sorted_{}.csv".format(sample_id)), "w+") as res:
        resWriter = csv.writer(res, delimiter='\t')
        resWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Correct", "Sorted", "Time"])

        testId = 0
        corr = 0

        configuration_file = os.path.join(PRO_DIR, "sample_{}.json".format(sample_id))
        with open(configuration_file, 'r') as f:
            data = json.load(f)
            for project_data in data["projects"]:
                print('\n-----------------------\nPROJECT NAME: {}\{}\n-----------------------\n'.format(project_data["userName"], project_data["repoName"]))

                userName = project_data["userName"]
                repoName = project_data["repoName"]
                gitURL = "git@github.com:{}/{}.git".format(userName, repoName)
                commit = project_data["commitSHA"]
                allTests = project_data["allTests"]
                
                # removing existing repo
                if repoName in os.listdir('../tmp/repos'):
                    os.system('rm -rf ../tmp/repos/{}'.format(repoName))
                
                # create project object
                project = Project(repoName, "", gitURL, commit)
                # clone the project
                project.init_env()

                for testClass in allTests:
                    className = testClass["className"]
                    classPath = testClass["classPath"]
                    filePath = os.path.join(project.repo_dir, classPath)
                    classTests = testClass["classTests"]

                    backup_test_file(filePath)

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
                        # Restore test file from backup
                        restore_test_file(filePath)

                        test_name = test["testName"]
                        test_lines = read_file(filePath, int(test["startLn"]), int(test["endLn"]))
                        test_lines = tecofy_testlines(test_lines, int(test["startLn"]), int(test["oracleLn"]))[0:test["oracleLn"]]

                        if len(test_lines) == 0: continue
                        test_code = " ".join(test_lines)

                        focal_name = test["focalName"]
                        focal_path = os.path.join(project.repo_dir, test["focalFile"])
                        focal_code = "".join(read_file(os.path.join(project.repo_dir, test["focalFile"]), test["focalStartLn"], test["focalEndLn"])) if "focalFile" in test else ""

                        oracle_code = test['oracle']

                        # print('\n\nTEST CODE: {}\nORACLE CODE: {}\nTEST CODE: {}\n\n'.format(''.join(test_lines), oracle_code, test_code))

                        conversation_history = [
                            {"role": "system", "content": SYSTEM_ROLE},
                        ]
                        
                        start_time = time.time()
                        feedback_history = [
                            {"role": "system", "content": SYSTEM_ROLE},
                        ]

                        res, feedback = None, None
                        
                        gpt_oracles, sort_status = ask(test_name, before_code, test_code, focal_code, oracle_code)
                        if gpt_oracles is None or len(gpt_oracles)==0: continue
                        
                        end_time = time.time()
                        first_case_done = False
                        for (oracle_id, gpt_oracle) in enumerate(gpt_oracles):
                            corr = 0
                            gpt_oracle = check_commutative_equal(gpt_oracle, oracle_code)
                            if gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").replace(" ", "").strip() == oracle_code.replace("org.junit.Assert.", "").replace("Assert.", "").replace(" ", "").strip():
                                corr = 1

                            resWriter.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId, oracle_id, userName if oracle_id==0 else "", repoName if oracle_id==0 else "", className, test_name, oracle_code.replace("org.junit.Assert.", "").replace("Assert.", "").strip(), gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").strip(), str(corr), str(sort_status), str(end_time-start_time)).split('\t'))
                            first_case_done = True

                        # res, feedback = collect_feedback(gateway, oracle_id, project, filePath, testClass['subRepo'], className, test_name, test_code, gpt_oracle)
                        testId += 1

                            # input('\n\nENTER A KEY')
                #         break
                #     break
                # break

        # print('\n---------------------\nCorrect: {}\nIncorrect: {}\nBuild Error: {}\nTest Error: {}\nTest Failure: {}\n---------------------\n'.format(str(corr), str(incorr), str(build_err), str(run_err), str(test_failure)))
