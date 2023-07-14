import os
import sys
import json
import openai
import time
import csv
import re
import shutil
import xml.etree.ElementTree as ET

from utils.gpt_util import if_exceed_token_limit
from project import Project
from path_config import DATA_DIR,API_KEY_FILEPATH,CONFIG_DIR, PRO_DIR
from utils.file_util import read_file
from utils.git_util import get_parent_commit
from utils.file_util import extract_content_within_line_range, read_file
from utils.markdown_util import extract_assertion, clean_args, check_commutative_equal, get_assert_type
from utils.prompt_generator_util import get_vulnerable_function_attributes
from utils.repair_util import adhoc_repair, check_and_fix_lhs2rhs
from utils.abstraction_util import fetch_abstraction_targets, generate_abstraction_prompts

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
FEEDBACK_BUDGET = 3 # Maximum number of retries based on compilation and execution feedback                                                                                                                                                         
MODEL_NAME = "gpt-3.5-turbo-16k"
SYSTEM_ROLE = "You are a programmer who is proficient in Java programming languge"
ABSTRACTION = True

common_assertion_kinds = ['assertEquals', 'assertNotEquals', 'assertSame', 'assertNotSame', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull', 'assertArrayEquals']
status_count = {
    'total': 0,
    'comp_err': 0,
    'test_err': 0,
    'test_fail': 0
}

global conversation_history, feedback_history, abstraction_history
global first_case_done, first_pass_case_done

def prompt_generator(interact_index=None, setup="", test="", focal=""):
    if interact_index == 0:
        #  Try next: Follow the rules <RULES>, where <RULES>:\n\nRule 1. DO NOT MODIFY TEST PREFIX.\nRule 2. DO NOT ASSUME ANYTHING IF IT IS NOT GIVEN.\nRule 3. DO NOT USE THE STRING LITERAL \"<FOCAL>\" IN THE GENERATED ASSERTION.\nRule 4. PAY ATTENTION TO VARIABLES IN THE TEST PREFIX.\n
        return "Given the setup code <SETUP>, test prefix <TEST>, and focal method <FOCAL>, generate only one org.junit.Assert statement, where,\n\n<SETUP>: ```{}```\n\n<TEST>: ```{}```\n\n<FOCAL>: ```{}```\n".format(setup, test, focal)
    else:
        return "Can you generate another type of assertion?"

def shuffle_organization():
    global openai, orgs, org_counter, current_org

    # Shuffle organizations to avoid Rate Limit Error
    if org_counter[current_org] == 2:
        org_counter[current_org] = 0
        current_org = (current_org + 1) % len(org_counter)

def interact_with_openai(temperature=1, which_history="conversation"):
    global history, conversation_history, feedback_history, abstraction_history
    global openai, orgs, org_counter, current_org

    if which_history == "conversation": history = conversation_history
    elif which_history == "feedback": history = feedback_history
    elif which_history == "abstraction": history = abstraction_history

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
            print(e)
            
            all_messages = [message['content'] for message in history]
            all_messages_string = ' '.join(all_messages)

            print("\n!!! Interaction Exception !!!")
            # Interaction exception can be either due to "exceeding token limit" or "exceeding rate limit"
            # print("Message length: {}".format(sum))
            if if_exceed_token_limit(all_messages_string, 'gpt-3.5-turbo-16k'):
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
                elif which_history == "abstraction":
                    abstraction_history = [
                        {"role": "system", "content": SYSTEM_ROLE}
                    ]
                    history = abstraction_history

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
    status_count['total'] += 1

    return gpt_oracle

def follow_up(mock_flag, gateway, project, oracle_id, file_path, subRepo, className, test_name, test_code, gpt_oracle, focal_code):
    # Adding the original assertion generation prompt in the feedback chain to give ChatGPT more content
    insert_message(role="user", content=conversation_history[1]["content"], which_history="feedback")

    res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, gpt_oracle)

    for feedback_id in range(FEEDBACK_BUDGET):
        # print('\nFEEDBACK ID: {}\n'.format(str(feedback_id)))
        print('FOLLOW-UP ORACLE: {}'.format(gpt_oracle))
        if feedback is not None:
            if len(feedback) > 0:
                # Carry out adhoc-repairs before asking ChatGPT to repair (to reduce interaction time)
                fuzzed_mutants = adhoc_repair(gateway, project, gpt_oracle, feedback, file_path, test_name, test_code, focal_code)

                for mutant in fuzzed_mutants:
                    print('FOLLOW-UP MUTANT: {}'.format(mutant))
                    res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, mutant)
                    if feedback is not None and len(feedback)==0:
                        # Mutant causes successful build without any feedback. So, select this mutant as gpt_oracle
                        gpt_oracle = mutant
                        break

                insert_message(role="assistant", content=gpt_oracle, which_history="feedback")
                insert_message(role="user", content=feedback, which_history="feedback")

                fixed_gpt_oracle = get_gpt_oracle(mock_flag=mock_flag, test_name=test_name, temperature=1.5, which_history="feedback")
                if fixed_gpt_oracle is None: continue
                else: gpt_oracle = fixed_gpt_oracle
            elif len(feedback) == 0:
                break

        res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, gpt_oracle)                       
    
    if feedback is None or len(feedback) > 0:
        # Even after exhausting the feedback budget, no plausible oracle was found
        return res, feedback, gpt_oracle

    return res, feedback, gpt_oracle

def collect_feedback(javaGateway, oracle_id, project, file_path, subRepo, class_name, test_name, test_code, gpt_oracle):
    res, feedback = None, None
    # Check if the oracle is plausible (using py4j and Java Method Injector)
    try:
        testInjector = javaGateway.entry_point
        testInjector.setFile(file_path)
        testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))

        res, output = project.run_test(subRepo, class_name, test_name)

        with open('execution_log/{}_{}.txt'.format(test_name, oracle_id), 'w+') as logFile:
            logFile.write(output)

        feedback = ""
        output_lines = output.split('\n')
        
        for i in range(len(output_lines)):
            # Compilation error
            if "COMPILATION ERROR" in output_lines[i]:
                status_count['comp_err'] += 1

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
                report_dir = os.path.join(project.repo_dir, subRepo, 'target/surefire-reports/')
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
                                if child.tag == "failure": status_count['test_fail'] += 1
                                elif child.tag == "error": status_count['test_err'] += 1

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
    except Exception as e:
        print('Exception: {}'.format(e))
        return None, None

    return res, feedback

def insert_message(role, content, which_history):
    global conversation_history, feedback_history, abstraction_history
    if which_history == "conversation": conversation_history.append({"role": role, "content": content})
    elif which_history == "feedback": feedback_history.append({"role": role, "content": content})
    elif which_history == "abstraction": abstraction_history.append({"role": role, "content": content})

def backup_test_file(file_path):
    backup_file_path = file_path.replace(".java", "") + "_backup.txt"
    shutil.copyfile(file_path, backup_file_path)

def restore_test_file(file_path):
    backup_file_path = file_path.replace(".java", "") + "_backup.txt"
    shutil.copyfile(backup_file_path, file_path)

def tecofy_testlines(lines):
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
            
            tecofied_lines.append(line)

    return tecofied_lines

def place_placeholder(tecofied_lines, startLn, oracleLn):
    offset = 2
    
    # `@Test \n public void testFoo(...) {` VS. `@Test \n public void testFoo(...) \n { ...` VS. `@Test \n public void testFoo(...) \n { \n ...`
    if '{' in tecofied_lines[2]:
        if len(tecofied_lines[2].strip()) == 1:
            offset = 3

    placeheld_lines = []

    for line in tecofied_lines:
        if len(placeheld_lines) == (oracleLn+offset):
            # Trigger stop
            placeheld_lines.append("<AssertPlaceHolder>;")
            placeheld_lines.append("}")
            break
        else:
            placeheld_lines.append(line)
    
    return placeheld_lines

def write_res(gateway, res_pass, res_all, test_id, oracle_id, user_name, repo_name, class_name, test_name, gpt_oracle, oracle_code, start_time, end_time, feedback):
    global first_case_done, first_pass_case_done

    # Convert the string literals in the generated assertion, to abstract STR tag
    gpt_oracle = gateway.entry_point.abstractStringLiterals(gpt_oracle)
    # Apply assignment heuristics (lhs = rhs -> replace rhs with lhs in the assertion)
    gpt_oracle = check_and_fix_lhs2rhs(gateway, gpt_oracle, test_code)

    # Removing org.junit.Assert. substring, Assert. substring and empty spaces in both gpt_oracle, and in the original assertion
    gpt_oracle = gpt_oracle.replace("org.junit.Assert.", "")
    gpt_oracle = gpt_oracle.replace("Assert.", "")
    gpt_oracle = gpt_oracle.replace(" ", "")
    gpt_oracle = gpt_oracle.strip()
    gpt_oracle = check_commutative_equal(gpt_oracle, oracle_code)

    oracle_code = clean_args(oracle_code) # Checking wihout optional assertion message
    oracle_code = oracle_code.replace("org.junit.Assert.", "")
    oracle_code = oracle_code.replace("Assert.", "")
    oracle_code = oracle_code.replace(" ", "")
    oracle_code = oracle_code.strip()

    if feedback is not None and len(feedback.strip()) > 0:
        # Build failure since len(feedback) > 0
        if gpt_oracle == oracle_code and oracle_id < 10:
            res_pass.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId if not first_pass_case_done else "/", oracle_id, userName if oracle_id==0 else "/", repoName if oracle_id==0 else "", className, test_name, oracle_code, gpt_oracle, str(end_time-start_time), '1', '0').split('\t'))
            first_pass_case_done = True
        else:
            res_all.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId if not first_case_done else "/", oracle_id, userName if oracle_id==0 else "/", repoName if oracle_id==0 else "", className, test_name, oracle_code, gpt_oracle, str(end_time-start_time), '0', '0').split('\t'))
            first_case_done = True

    elif len(gpt_oracle) > 0 and feedback is not None and len(feedback.strip()) == 0:
        # Successful build since len(feedback) == 0
        if gpt_oracle == oracle_code:
            res_pass.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId if not first_pass_case_done else "/", oracle_id, userName if oracle_id==0 else "/", repoName if oracle_id==0 else "", className, test_name, oracle_code, gpt_oracle, str(end_time-start_time), '1', '0').split('\t'))
            first_pass_case_done = True
        else:
            res_pass.writerow("{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(testId if not first_case_done else "/", oracle_id, userName if oracle_id==0 else "/", repoName if oracle_id==0 else "", className, test_name, oracle_code, gpt_oracle, str(end_time-start_time), '0', '0').split('\t'))
            first_case_done = True
    

if __name__ == "__main__":
    v1_flag, v2_flag, mock_flag = False, False, False
    arg = " ".join(sys.argv)
    if 'v1' in arg: 
        v1_flag = True
        MAX_INTERACTION = 1
    if 'v2' in arg: 
        v2_flag = True
        # Default MAX_INTERACTION
    if 'mock' in arg: 
        mock_flag = True
        MAX_INTERACTION = 3

    # Input data sample id (e.g. sample_1.json)
    sample_id = sys.argv[-1]
    print('SAMPLE: sample_{}.json'.format(sample_id))

    testId = 0
    global conversation_history, feedback_history, abstraction_history
    conversation_history = [
        {"role": "system", "content": SYSTEM_ROLE},
    ]

    gateway = JavaGateway()
    assertionTypes = ['assertEquals', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull', 'assertArrayEquals', 'assertThat']

    with open(os.path.join(PRO_DIR, "res/res_all/res_all_{}.csv".format(sample_id)), "w+") as resAll, open(os.path.join(PRO_DIR, "res/res_pass/res_pass_{}.csv".format(sample_id)), "w+") as resPass:
        resAllWriter = csv.writer(resAll, delimiter='\t')
        resPassWriter = csv.writer(resPass, delimiter='\t')

        resAllWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Time", "Corr", "BuildErr"])
        resPassWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Time", "Corr", "BuildErr"])

        corr, incorr, build_err, run_err, test_failure = 0, 0, 0, 0, 0

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
                project = Project(repoName, "", gitURL, commit, gateway)

                for testClass in allTests:
                    className = testClass["className"]
                    classPath = testClass["classPath"]
                    filePath = os.path.join(project.repo_dir, classPath)
                    classTests = testClass["classTests"]
                    subRepo = testClass["subRepo"]

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

                    # Make sure that all dependencies are added to pom.xml
                    project.ensure_dependencies(subRepo)

                    # Fetch dependency jar paths to pass to the JarTypeSolver
                    depPaths = list(project.list_dependencies(subRepo))
                            
                    print("\n-----------------------------------------\nAnalyzing Oracles for Test Class: {}\n-----------------------------------------\n".format(className))
                    for test in classTests:
                        # Restore test file from backup
                        restore_test_file(filePath)

                        # Get Test Code
                        test_name = test["testName"]
                        test_lines = read_file(filePath, int(test["startLn"]), int(test["endLn"]))
                        test_lines = tecofy_testlines(test_lines)
                        test_lines = place_placeholder(test_lines, int(test["startLn"]), int(test["oracleLn"]))
                        if len(test_lines) == 0: continue
                        test_code = " ".join(test_lines)

                        # Get Focal Code
                        focal_name = test["focalName"]
                        focal_path = os.path.join(project.repo_dir, test["focalFile"])
                        focal_code = "".join(read_file(os.path.join(project.repo_dir, test["focalFile"]), test["focalStartLn"], test["focalEndLn"])) if "focalFile" in test else ""

                        # Get Abstraction
                        if ABSTRACTION:
                            print('Running Abstraction Queries. Please wait for ChatGPT to build a knowledge base.\n')
                            abstraction_history = [
                                {'role': 'system', 'content': SYSTEM_ROLE}
                            ]
                            abstraction_length = 0

                            # fetch methods and classes
                            meta = fetch_abstraction_targets(filePath, os.path.join(project.repo_dir, subRepo, 'src'), depPaths, test_code.replace("<AssertPlaceHolder>;", ""))

                            if meta is not None:
                                # get a list of abstraction prompts for each line (one line can have multiple abstraction prompts):
                                abstraction_prompts = generate_abstraction_prompts(meta)
                                print(abstraction_prompts)

                                # Introducing the task to ChatGPT and mimicking its response from the WebUI
                                insert_message(role='user', content='I will ask you to explain a few methods and classes. I will also walk you through the steps of a Java test method prefix. Then, given a setup method, test prefix and a focal method, I will ask you to generate a JUnit assertion. Alright?', which_history='conversation')
                                insert_message(role='assistant', content='Yes. I will explain the methods and classes that you give me. I will pay close attention to the steps you describe. If you give me the test prefix and a focal method, I will generate a JUnit assertion.', which_history='conversation')

                                insert_message(role='user', content='I will ask you to explain a few methods and classes. I will also walk you through the steps of a Java test method prefix. Then, given a setup method, test prefix and a focal method, I will ask you to generate a JUnit assertion. Alright?', which_history='abstraction')
                                insert_message(role='assistant', content='Yes. I will explain the methods and classes that you give me. I will pay close attention to the steps you describe. If you give me the test prefix and a focal method, I will generate a JUnit assertion.', which_history='abstraction')
                                for prompt in abstraction_prompts:
                                    print('LENGTH OF ABSTRACTION HISTORY: {}\n'.format(len(abstraction_history)))
                                    print('ABSTRACTION HISTORY: {}\n'.format(abstraction_history))

                                    # insert prompt into abstraction_history
                                    insert_message('user', prompt, 'abstraction')

                                    # interact with open ai about abstraction
                                    abstraction_response = interact_with_openai(which_history='abstraction')
                                    print('ABSTRACTION RESPONSE: {}\n'.format(abstraction_response))

                                    # check if adding the current response to the abstraction message history will overflow our token limits allocated for abstraction. # if cummulative response token length exceeds 12288 (3/4 of token limit 16384), stop and leave the remaining 4096 tokens for the assertion query and feedback cycle
                                    if (abstraction_length + len(abstraction_response))/4 > 12288:
                                        break

                                    # remove last message from abstraction_history
                                    abstraction_history.pop()

                                    # insert response into abstraction_history and conversation_history
                                    insert_message(role='assistant', content=abstraction_response, which_history='abstraction')
                                    insert_message(role='assistant', content=abstraction_response, which_history='conversation')

                                    # keep track of cummulative response token length
                                    abstraction_length += len(abstraction_response)

                        # Get Oracle Code
                        oracle_code = test['oracle']

                        # Will not run for assertThat and helper assertions
                        if get_assert_type(oracle_code) not in common_assertion_kinds: continue

                        conversation_history = [
                            {"role": "system", "content": SYSTEM_ROLE},
                        ]

                        global first_case_done, first_pass_case_done
                        first_pass_case_done, first_case_done = False, False
                        target_number = TARGET_NUMBER
                        already_gen_oras = set()
                        # for variantId, assertion_type in enumerate(assertionTypes):                            
                        for oracle_id in range(MAX_INTERACTION):
                            print('\nORACLE ID: {}\n'.format(oracle_id))

                            start_time = time.time()

                            feedback_history = [
                                {"role": "system", "content": SYSTEM_ROLE},
                            ]

                            if target_number == 0: break # Already produced TARGET_NUMBER of plausible oracles for this test

                            res, feedback = None, None
                            print('\nTEST CODE: {}\n'.format(test_code))
                            if v1_flag: # Single feedback
                                gpt_oracle = ask(mock_flag, oracle_id, test_name, before_code, test_code, focal_code)
                                if gpt_oracle is None: continue

                                if gpt_oracle not in already_gen_oras:
                                    already_gen_oras.add(gpt_oracle)
                                    res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, gpt_oracle)

                            elif v2_flag: # Feedback loop
                                gpt_oracle = ask(mock_flag, oracle_id, test_name, before_code, test_code, focal_code)

                                # gpt_oracle = 'org.junit.Assert.assertTrue(((ODirtyManager) doc.getReal()).newRecords.isEmpty());'

                                # print("\nGPT ORACLE: {}\n".format(gpt_oracle))
                                if gpt_oracle is None: continue

                                if gpt_oracle not in already_gen_oras:
                                    already_gen_oras.add(gpt_oracle)
                                
                                    # Follow-up with feedback loop
                                    res, feedback, gpt_oracle = follow_up(mock_flag, gateway, project, oracle_id, filePath, subRepo, className, test_name, test_code, gpt_oracle, focal_code)
                                    print('\n\nFEEDBACK:\n' + str(feedback))

                                    if gpt_oracle is None: continue

                                    if feedback is not None and len(feedback) > 0:
                                        # Explicitly tell ChatGPT to avoid gpt_oracle
                                        insert_message(role="user", content="AVOID generating the assertion `"+gpt_oracle+"` because it results in a build failure.", which_history="conversation")

                                    # # Check if the returned oracle compiles and runs and if yes, add it to main conversation history (the main conversation history should not contain any invalid assertion that does not compile or run)
                                    elif len(gpt_oracle) > 0 and feedback is not None and len(feedback) == 0:
                                        # Oracle compiles and runs - add it to main conversation history
                                        insert_message(role="user", content="GOOD. `"+gpt_oracle+"` is a plausible assertion. So, AVOID generating the assertion `"+gpt_oracle+"` again because you have already generated it.", which_history="conversation")
                                        target_number -= 1

                            # Write results to csv file
                            write_res(gateway, resPassWriter, resAllWriter, testId, oracle_id, userName, repoName, className, test_name, gpt_oracle, oracle_code, start_time, time.time(), feedback)

                        # Restore test file from backup
                        restore_test_file(filePath)

                        # Increment test counter
                        testId += 1

                        # exit(0)
