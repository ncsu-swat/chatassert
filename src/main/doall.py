import os
import sys
import json
import time
import csv
import re
import shutil
import xml.etree.ElementTree as ET

from project import Project
from path_config import DATA_DIR, CONFIG_DIR, PRO_DIR

from utils.gpt_util import oracle_prompt_generator, interact_with_openai, if_exceed_token_limit
from utils.context_util import Prompts, Context
from utils.file_util import read_file
from utils.git_util import get_parent_commit
from utils.file_util import extract_content_within_line_range, read_file
from utils.markdown_util import extract_assertion, clean_args, check_commutative_equal, get_assert_type
from utils.repair_util import adhoc_repair, check_and_fix_lhs2rhs
from utils.summarization_util import summarize
from utils.one_shot_util import find_similar

from py4j.java_gateway import JavaGateway

# Constants to determine various generation/repair loop termination
TARGET_NUMBER = 10 # Number of oracles to be generated (NO in the paper)
GLOBAL_TRIALS = 30  # Maximum number of interactions (GT in the paper)
LOCAL_TRIALS = 3 # Maximum number of retries based on compilation and execution feedback (LT in the paper)

# Switches for ablation study
FEEDBACK_REPAIR = True  # Ablation Study No. 1
FUZZ_REPAIR = True      # Ablation Study No. 2
SUMMARIZATION = True    # Ablation Study No. 3
ONE_SHOT = True         # Ablation Study No. 4

# Switches
EXECUTE_GENERATION = True # Only cache summaries or execute oracle generation conversation too?

status_count = {
    'total': 0,
    'comp_err': 0,
    'test_err': 0,
    'test_fail': 0
}

global first_case_done, first_pass_case_done

def get_gpt_oracle(test_name="", temperature=1, context=None):
    if context is None: raise Exception("In get_gpt_oracle: context cannot be None")
    
    gpt_oracle = None
    
    model_response = interact_with_openai(temperature, context)
    print("\nRESPONSE:\n{}".format(model_response))
    gpt_oracle = extract_assertion(model_response)
    print("GEN: {}\n".format(gpt_oracle))

    if (gpt_oracle is None) or (gpt_oracle.strip() == "org.junit.Assert."):
        return None

    return gpt_oracle

def ask(oracle_id, context, summaries, example_method, test_name, before_code, test_code, focal_code):
    global conversation_history
    
    # Add user input to the conversation history                                                                                                                                                          
    oracle_prompt_generator(oracle_id, context, summaries, example_method, before_code, test_code, focal_code)

    # if if_exceed_token_limit(prompt, MODEL_NAME):
    #     #TODO: text-splitter
    #     pass

    gpt_oracle = get_gpt_oracle(test_name=test_name, context=context)
    status_count['total'] += 1

    return gpt_oracle

def follow_up(gateway, project, oracle_id, file_path, subRepo, className, test_name, test_code, gpt_oracle, focal_code):
    # Instantiating feedback context (per example)
    feedback_context = Context(_name=Context.FEEDBACK_CONTEXT_NAME)

    # Insert the original oracle generation prompt in the feedback-driven repair context
    feedback_context.insert(role="user", content=Prompts.FEEDBACK_SEED)
    # Insert the faulty oracle and ask ChatGPT to fix the oracle so that it compiles and executes
    feedback_context.insert(role="user", content=(Prompts.FEEDBACK_SEED_EXT).format(gpt_oracle))

    res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, gpt_oracle)
    for feedback_id in range(LOCAL_TRIALS):
        # print('\nFEEDBACK ID: {}\n'.format(str(feedback_id)))
        print('FOLLOW-UP ORACLE: {}'.format(gpt_oracle))
        if feedback is not None:
            if len(feedback) > 0:
                if FUZZ_REPAIR:        # (Ablation Study No. 2)
                    # Carry out adhoc-repairs before asking ChatGPT to repair (to reduce interaction time)
                    fuzzed_mutants = adhoc_repair(gateway, project, gpt_oracle, feedback, file_path, test_name, test_code, focal_code)

                    for mutant in fuzzed_mutants:
                        print('FOLLOW-UP MUTANT: {}'.format(mutant))
                        res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, mutant)
                        if feedback is not None and len(feedback)==0:
                            # Mutant causes successful build without any feedback. So, select this mutant as gpt_oracle.
                            gpt_oracle = mutant
                            break

                if FEEDBACK_REPAIR:    # (Ablation Study No. 1)
                    if feedback is None or len(feedback) > 0:
                        feedback_context.insert(role="user", content=feedback)

                        fixed_gpt_oracle = get_gpt_oracle(test_name=test_name, temperature=1.5, context=feedback_context)
                        if fixed_gpt_oracle is None: continue
                        else:
                            gpt_oracle = fixed_gpt_oracle
                            # Insert the fixed oracle inside the feedback-driven repair context
                            feedback_context.insert(role="assistant", content=(Prompts.FEEDBACK_FIXED).format(gpt_oracle))
            elif len(feedback) == 0:
                break

        res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, gpt_oracle)                       

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
    v1_flag, v2_flag = False, False
    arg = " ".join(sys.argv)
    if 'v1' in arg: 
        GLOBAL_TRIALS = 1 # L-One (Zero)
        v1_flag = True
    if 'v2' in arg: 
        # Default GLOBAL_TRIALS = 30
        v2_flag = True

    # Add condition for only generating and caching summaries (which can be used later)
    # Add conditions for ablation study

    # Input data sample id (e.g. sample_1.json)
    sample_id = sys.argv[-1]
    print('SAMPLE: sample_{}.json'.format(sample_id))

    testId = 0

    # Initialize a PY4J client to communicate with the Java gateway server
    gateway = JavaGateway()

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
                        # Instantiate oracle generation conversation context
                        context = Context(_name=Context.GENERATION_CONTEXT_NAME)

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

                        # Get Summarization (Ablation Study No. 3)
                        summaries = None
                        if SUMMARIZATION:
                            print('Running Summarization Queries. Please wait for ChatGPT to build a knowledge base.\n')
                            summaries = summarize(filePath, className, os.path.join(project.repo_dir, subRepo, 'src'), depPaths, test_name, test_code.replace("<AssertPlaceHolder>;", ""))

                        if not EXECUTE_GENERATION: continue

                        # Get one Example from the same test file (Ablation Study No. 4)
                        example_method = None
                        if ONE_SHOT:
                            print('Finding an Example that is a best match with the Test Method')
                            example_method = find_similar(className, test_name, test_code)

                        # Get Oracle Code
                        oracle_code = test['oracle']

                        global first_case_done, first_pass_case_done
                        first_pass_case_done, first_case_done = False, False
                        target_number = TARGET_NUMBER
                        already_gen_oras = set()

                        for oracle_id in range(GLOBAL_TRIALS):
                            print('\nORACLE ID: {}\n'.format(oracle_id))

                            start_time = time.time()

                            if target_number == 0: break # Already produced TARGET_NUMBER of plausible oracles for this test

                            res, feedback = None, None
                            # print('\nTEST CODE: {}\n'.format(test_code))

                            if v1_flag: # No feedback (L-One)
                                gpt_oracle = ask(oracle_id, context, summaries, example_method, test_name, before_code, test_code, focal_code)
                                if gpt_oracle is None: continue

                                if gpt_oracle not in already_gen_oras:
                                    already_gen_oras.add(gpt_oracle)
                                    res, feedback = collect_feedback(gateway, oracle_id, project, filePath, subRepo, className, test_name, test_code, gpt_oracle)

                            elif v2_flag: # Feedback loop
                                gpt_oracle = ask(oracle_id, context, summaries, example_method, test_name, before_code, test_code, focal_code)

                                # gpt_oracle = 'org.junit.Assert.assertTrue(((ODirtyManager) doc.getReal()).newRecords.isEmpty());'

                                # print("\nGPT ORACLE: {}\n".format(gpt_oracle))
                                if gpt_oracle is None: continue

                                if gpt_oracle not in already_gen_oras:
                                    already_gen_oras.add(gpt_oracle)
                                
                                    # Follow-up with feedback loop
                                    res, feedback, gpt_oracle = follow_up(gateway, project, oracle_id, filePath, subRepo, className, test_name, test_code, gpt_oracle, focal_code)
                                    # print('\nFEEDBACK:\n' + str(feedback))

                                    if gpt_oracle is None: continue

                                    if feedback is None or len(feedback) > 0:
                                        # Explicitly tell ChatGPT to avoid gpt_oracle
                                        context.insert(role="user", content="AVOID generating the assertion `" + gpt_oracle + "`, because it results in a build failure.")

                                    # # Check if the returned oracle compiles and runs and if yes, add it to main conversation history (the main conversation history should not contain any invalid assertion that does not compile or run)
                                    elif len(gpt_oracle) > 0 and feedback is not None and len(feedback) == 0:
                                        # Oracle compiles and runs - add it to main conversation history
                                        context.insert(role="user", content="GOOD. `" + gpt_oracle + "` is a plausible assertion. So, AVOID generating the assertion `" + gpt_oracle + "` again because you have already generated it.")
                                        # SUCCESS
                                        target_number -= 1

                            # Write results to csv file
                            write_res(gateway, resPassWriter, resAllWriter, testId, oracle_id, userName, repoName, className, test_name, gpt_oracle, oracle_code, start_time, time.time(), feedback)

                        # Restore test file from backup
                        restore_test_file(filePath)

                        # Increment test counter
                        testId += 1

                        # exit(0)
