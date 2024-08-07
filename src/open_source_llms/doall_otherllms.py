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

from py4j.java_gateway import JavaGateway, GatewayParameters
import py4j

from multiprocessing import Process, Queue

import traceback

import psutil
import time
import concurrent.futures
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

# Constants to determine various generation/repair loop termination
TARGET_NUMBER = 10  # Number of oracles to be generated (NO in the paper)
GLOBAL_TRIALS = 30  # Maximum number of interactions (GT in the paper)
LOCAL_TRIALS = 3    # Maximum number of retries based on compilation and execution feedback (LT in the paper)

# Switches for ablation study
FUZZ_REPAIR = True      # Ablation Study No. 4
FEEDBACK_REPAIR = True   # Ablation Study No. 3
SUMMARIZATION = True    # Ablation Study No. 2
ONE_SHOT = True         # Ablation Study No. 1

# Switches
EXECUTE_GENERATION = True # Only cache summaries or execute oracle generation conversation too?

status_count = {
    'total': 0,
    'comp_err': 0,
    'test_err': 0,
    'test_fail': 0
}

global examples_count

global first_case_done, first_pass_case_done
# global proc_q
global project

from utils.model_client import get_model_response

import random
# from utils.llama_util import interact_with_codellama
# from utils.llama_util import LlamaModel
# from utils.codegen_util import interact_with_codegen
# from utils.mistral_util import interact_with_mistral
def mock_interact_with_openai(temperature=1, context=None):
    mock_responses = [
        "This is a mock response blah blah blah",
        "It did the thing. Don't worry about it",
        "Error encountered: Please check the inputs.",
        "Thank you so incredibly much for using this mock.",
        "You are going crazy!!!"
    ]
    return random.choice(mock_responses)


def get_gpt_oracle(test_name="", temperature=1, context=None):
    if context is None: raise Exception("In get_gpt_oracle: context cannot be None")
    
    gpt_oracle = None
    # llama_model = LlamaModel()
    model_response = get_model_response(temperature, context) #llama_model.interact_with_codellama(temperature, context)
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

    # print("I GENERATED THIS PROMPT: ", context.history)

    # if if_exceed_token_limit(prompt, MODEL_NAME):
    #     #TODO: text-splitter
    #     pass

    gpt_oracle = get_gpt_oracle(test_name=test_name, context=context)
    status_count['total'] += 1

    return gpt_oracle


def follow_up(proc_q, repo_dir, oracle_id, file_path, subRepo, className, test_name, test_code, gpt_oracle, focal_code):
    # global proc_q
    gateway = JavaGateway()

    # Instantiating feedback context (per example)
    feedback_context = Context(_name=Context.FEEDBACK_CONTEXT_NAME)

    # Insert the original oracle generation prompt in the feedback-driven repair context
    feedback_context.insert(role="user", content=Prompts.FEEDBACK_SEED)
    # Insert the faulty oracle and ask ChatGPT to fix the oracle so that it compiles and executes
    feedback_context.insert(role="user", content=(Prompts.FEEDBACK_SEED_EXT).format(gpt_oracle))

    res, feedback = collect_feedback(repo_dir, oracle_id, file_path, subRepo, className, test_name, test_code, gpt_oracle)
    if len(feedback) > 0:
        for feedback_id in range(LOCAL_TRIALS):
            # print('\nFEEDBACK ID: {}\n'.format(str(feedback_id)))
            print('FOLLOW-UP ORACLE: {}'.format(gpt_oracle))
            if feedback is not None:
                if len(feedback) > 0:
                    if FUZZ_REPAIR:        # (Ablation Study No. 4)
                        # Carry out adhoc-repairs before asking ChatGPT to repair (to reduce interaction time)
                        fuzzed_mutants = adhoc_repair(gpt_oracle, feedback, file_path, test_name, test_code, focal_code)

                        for mutant in fuzzed_mutants:
                            print('FOLLOW-UP MUTANT: {}'.format(mutant))
                            res, feedback = collect_feedback(repo_dir, oracle_id, file_path, subRepo, className, test_name, test_code, mutant)
                            if feedback is not None and len(feedback)==0:
                                # Mutant causes successful build without any feedback. So, select this mutant as gpt_oracle.
                                gpt_oracle = mutant
                                break

                    if FEEDBACK_REPAIR:    # (Ablation Study No. 3)
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

            res, feedback = collect_feedback(repo_dir, oracle_id, file_path, subRepo, className, test_name, test_code, gpt_oracle)                       

    proc_q.put(res)
    proc_q.put(feedback)
    proc_q.put(gpt_oracle)

    return res, feedback, gpt_oracle


def collect_feedback(repo_dir, oracle_id, file_path, subRepo, class_name, test_name, test_code, gpt_oracle):
    res, feedback = None, None
    # Check if the oracle is plausible (using py4j and Java Method Injector)
    try:
        testInjector = JavaGateway().entry_point
        # testInjector.setFile(file_path)
        for attempt in range(20): 
            try:
                testInjector.setFile(file_path)
                break
            except py4j.protocol.Py4JJavaError as e:
                if attempt < 19: 
                    time.sleep(2)
                else:
                    print('FILE PATH: ', file_path)
                    raise e
                
        # testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))
        for attempt in range(20): 
            try:
                # testInjector.setFile(file_path)
                testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))
                break
            except py4j.protocol.Py4JJavaError as e:
                if attempt < 19: 
                    time.sleep(2)
                else:
                    print('FILE PATH (INJECTION): ', file_path)
                    raise e
        res, output = Project.run_test(repo_dir, subRepo, class_name, test_name)

        with open(os.path.join(DATA_DIR, 'execution_log/{}_{}.txt'.format(test_name, oracle_id)), 'w+') as logFile:
            logFile.write(output)

        feedback = ""
        output_lines = output.split('\n')
        
        for i in range(len(output_lines)):
            # Compilation error
            if "COMPILATION ERROR" in output_lines[i]:
                print("\n\nCOMPILATION ERROR:\n\n{}\n".format(output_lines[i]))
                status_count['comp_err'] += 1

                err_msg = ""
                err_line = 2
                while(i+err_line < len(output_lines)): # Get the next 5 lines until we get a line with INFO or ERROR or WARNING
                    if (err_line == 2) and (i+err_line < len(output_lines)):
                        err_msg += output_lines[i+err_line]
                    elif (err_line > 2) and (i+err_line < len(output_lines)):
                        if ("[ERROR]" in output_lines[i+err_line]) or ("[INFO]" in output_lines[i+err_line]) or ("[WARNING]" in output_lines[i+err_line]) or ("SEVERE" in output_lines[i+err_line]):
                            feedback = "I am getting the following compilation error: \n{}\nCan you please fix the generated assert statement?".format(err_msg)
                            break
                        else:
                            err_msg += " " + output_lines[i+err_line]
                    else:
                        if len(feedback) == 0:
                            print('\n\n!!! Could not retrieve compilation error message !!!\n\n')
                    err_line += 1
                break
            
        # Feedback was not updated so far as we have not observed any compilation error
        if len(feedback) == 0:
            # Check for Test failure
            report_dir = os.path.join(repo_dir, subRepo, 'target/surefire-reports/')
            if os.path.exists(report_dir):
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

    except Exception as e:
        traceback.print_exc()
        print('Exception: {}'.format(e))
        return None, None

    print('\n\nFeedback:\n{}\n'.format(feedback))

    return res, feedback



def is_functional(repo_dir, oracle_id, file_path, subRepo, class_name, test_name, test_code, gpt_oracle):
    return True
    # start_time = time.time()
    
    # # Initialize Java Gateway
    # gateway_start = time.time()
    # testInjector = JavaGateway().entry_point
    # gateway_end = time.time()
    
    # # Set file
    # set_file_start = time.time()
    # # testInjector.setFile(file_path)
    # for attempt in range(20): 
    #     try:
    #         testInjector.setFile(file_path)
    #         break
    #     except py4j.protocol.Py4JJavaError as e:
    #         if attempt < 19: 
    #             time.sleep(2)
    #         else:
    #             print('FILE PATH: ', file_path)
    #             raise e
    # set_file_end = time.time()
    
    # # Inject test
    # inject_start = time.time()
    # # testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))
    # for attempt in range(20): 
    #     try:
    #         testInjector.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))
    #         break
    #     except py4j.protocol.Py4JJavaError as e:
    #         if attempt < 19: 
    #             time.sleep(2)
    #         else:
    #             print('FILE PATH: ', file_path)
    #             raise e
    # inject_end = time.time()
    
    # # Run test
    # run_test_start = time.time()
    # res, output = Project.run_test(repo_dir, subRepo, class_name, test_name)
    # run_test_end = time.time()
    
    # # Check results
    # check_results_start = time.time()
    # if "BUILD SUCCESS" in output:
    #     print('FUNCTIONAL! ', output)
    #     check_results_end = time.time()
    
    #     total_time = time.time() - start_time
        
    #     print(f"Total is_functional time: {total_time:.2f} seconds")
    #     print(f"Java Gateway initialization time: {gateway_end - gateway_start:.2f} seconds")
    #     print(f"Set file time: {set_file_end - set_file_start:.2f} seconds")
    #     print(f"Inject test time: {inject_end - inject_start:.2f} seconds")
    #     print(f"Run test time: {run_test_end - run_test_start:.2f} seconds")
    #     print(f"Check results time: {check_results_end - check_results_start:.2f} seconds")
    #     return True
    # if output is None or len(output) > 0:
    #     print('NOT FUNCTIONAL BECAUSE OUTPUT IS GREATER THAN 0')
    #     print('OUTPUT: ', output)
    #     check_results_end = time.time()
        
    #     total_time = time.time() - start_time
        
    #     print(f"Total is_functional time: {total_time:.2f} seconds")
    #     print(f"Java Gateway initialization time: {gateway_end - gateway_start:.2f} seconds")
    #     print(f"Set file time: {set_file_end - set_file_start:.2f} seconds")
    #     print(f"Inject test time: {inject_end - inject_start:.2f} seconds")
    #     print(f"Run test time: {run_test_end - run_test_start:.2f} seconds")
    #     print(f"Check results time: {check_results_end - check_results_start:.2f} seconds")
    #     return False
    # check_results_end = time.time()
    
    # total_time = time.time() - start_time
    
    # print(f"Total is_functional time: {total_time:.2f} seconds")
    # print(f"Java Gateway initialization time: {gateway_end - gateway_start:.2f} seconds")
    # print(f"Set file time: {set_file_end - set_file_start:.2f} seconds")
    # print(f"Inject test time: {inject_end - inject_start:.2f} seconds")
    # print(f"Run test time: {run_test_end - run_test_start:.2f} seconds")
    # print(f"Check results time: {check_results_end - check_results_start:.2f} seconds")
    
    # return True

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

def write_res(gateway, test_id, oracle_id, user_name, repo_name, class_name, test_name, test_code, gpt_oracle, oracle_code, start_time, end_time, feedback, is_functional):
    global first_case_done, first_pass_case_done

    # Convert the string literals in the generated assertion, to abstract STR tag
    gpt_oracle = gateway.entry_point.abstractStringLiterals(gpt_oracle)
    # Apply assignment heuristics (lhs = rhs -> replace rhs with lhs in the assertion)
    gpt_oracle = check_and_fix_lhs2rhs(gpt_oracle, test_code)

    # Removing org.junit.Assert. substring, Assert. substring and empty spaces in both gpt_oracle, and in the original assertion
    gpt_oracle = gpt_oracle.replace("org.junit.Assert.", "")
    gpt_oracle = gpt_oracle.replace("Assert.", "")
    gpt_oracle = gpt_oracle.replace(" ", "")
    gpt_oracle = gpt_oracle.strip()
    gpt_oracle = check_commutative_equal(gpt_oracle, oracle_code)

    oracle_code = clean_args(oracle_code)  # Checking without optional assertion message
    oracle_code = oracle_code.replace("org.junit.Assert.", "")
    oracle_code = oracle_code.replace("Assert.", "")
    oracle_code = oracle_code.replace(" ", "")
    oracle_code = oracle_code.strip()

    print('FEEDBACK CHECK...')
    print('FEEDBACK: |', feedback, '|')
    print('GPT ORACLE: |', gpt_oracle, '|')

    result_pass = None
    result_all = None

    if feedback is not None and len(feedback.strip()) > 0:
        if gpt_oracle == oracle_code and oracle_id < 10:
            result_pass = "{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                test_id if not first_pass_case_done else "/", oracle_id, user_name if oracle_id == 0 else "/",
                repo_name if oracle_id == 0 else "", class_name, test_name, oracle_code, gpt_oracle,
                str(end_time - start_time), '1', '0').split('\t')
            first_pass_case_done = True
        else:
            result_all = "{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                test_id if not first_case_done else "/", oracle_id, user_name if oracle_id == 0 else "/",
                repo_name if oracle_id == 0 else "", class_name, test_name, oracle_code, gpt_oracle,
                str(end_time - start_time), '0', '0').split('\t')
            first_case_done = True

    elif len(gpt_oracle) > 0 and feedback is not None and len(feedback.strip()) == 0:
        if gpt_oracle == oracle_code:
            result_pass = "{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                test_id if not first_pass_case_done else "/", oracle_id, user_name if oracle_id == 0 else "/",
                repo_name if oracle_id == 0 else "", class_name, test_name, oracle_code, gpt_oracle,
                str(end_time - start_time), '1', '0').split('\t')
            first_pass_case_done = True
        else:
            result_pass = "{}\t{}\t{}/{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                test_id if not first_case_done else "/", oracle_id, user_name if oracle_id == 0 else "/",
                repo_name if oracle_id == 0 else "", class_name, test_name, oracle_code, gpt_oracle,
                str(end_time - start_time), '0', '0').split('\t')
            first_case_done = True

    return result_pass, result_all

from concurrent.futures import ProcessPoolExecutor, as_completed

# Define a function to process each project
def process_project(project_data, sample_id, global_vars):
    total_test_time = 0
    total_writeandflush_time = 0
    total_writeres_time = 0
    total_isfunctional_time = 0
    total_ask_time = 0
    total_oneshot_time = 0
    total_summarization_time = 0
    total_followup_time = 0
    v1_flag, v2_flag = False, True
    results_pass = []
    results_all = []
    testId = 0
    project = None
    gateway = JavaGateway()

    try:
        userName = project_data["userName"]
        repoName = project_data["repoName"]
        gitURL = "git@github.com:{}/{}.git".format(userName, repoName)
        commit = project_data["commitSHA"]
        allTests = project_data["allTests"]

        print('\n-----------------------\nPROJECT NAME: {}\{}\n-----------------------\n'.format(project_data["userName"], project_data["repoName"]))


        # removing existing repo
        if repoName in os.listdir('../tmp/repos'):
            os.system('rm -rf ../tmp/repos/{}'.format(repoName))

        # create project object
        project = Project(repoName, "", gitURL, commit)

        for testClass in allTests:
            className = testClass["className"]
            classPath = testClass["classPath"]
            filePath = os.path.join(project.repo_dir, classPath)
            classTests = testClass["classTests"]
            subRepo = testClass["subRepo"]

            before_name = ""
            before_code = ""
            after_code = ""

            if "before" in testClass:
                before_name = testClass["before"]["setupName"]
                before_code = testClass["before"]["setupMethod"]
            if "after" in testClass:
                after_code = "".join(read_file(filePath, int(testClass["after"]["startLn"]), int(testClass["after"]["endLn"])))

            # Make sure to copy repo from the cache directory to the working directory
            project.copy_cache()

            # Make sure that all dependencies are added to pom.xml
            project.ensure_dependencies(subRepo)

            # Fetch dependency jar paths to pass to the JarTypeSolver
            depPaths = list(project.list_dependencies(subRepo))
            
            backup_test_file(filePath)

            print("\n-----------------------------------------\nAnalyzing Oracles for Test Class: {}\n-----------------------------------------\n".format(className))

            for test in classTests:
                total_st_time = time.time()
                context = Context(_name=Context.GENERATION_CONTEXT_NAME)
                restore_test_file(filePath)

                test_name = test["testName"]
                test_lines = read_file(filePath, int(test["startLn"]), int(test["endLn"]))
                test_lines = tecofy_testlines(test_lines)
                test_lines = place_placeholder(test_lines, int(test["startLn"]), int(test["oracleLn"]))
                if len(test_lines) == 0: continue
                test_code = " ".join(test_lines)

                focal_name = test["focalName"]
                focal_path = os.path.join(project.repo_dir, test["focalFile"])
                focal_code = "".join(read_file(os.path.join(project.repo_dir, test["focalFile"]), test["focalStartLn"], test["focalEndLn"])) if "focalFile" in test else ""

                summaries = None
                if SUMMARIZATION:
                    print('Running Summarization Queries. Please wait for ChatGPT to build a knowledge base.\n')
                    st_time = time.time()
                    summaries = summarize(filePath, className, os.path.join(project.repo_dir, subRepo, 'src'), depPaths, test_name, test_code.replace("<AssertPlaceHolder>;", ""), focal_code, enforce_regeneration=True)
                    ed_time = time.time()
                    elapsed_time = ed_time - st_time
                    total_summarization_time += elapsed_time
                    print(f"Time taken to generate summaries: {elapsed_time:.2f} seconds")
                example_method = None
                if ONE_SHOT:
                    print('Finding Examples that are best matches with the Test Method')
                    st_time = time.time()
                    example_method = find_similar(className, test_name, test_code)
                    print('\nFEW-SHOT EXAMPLES:\n{}\n'.format(example_method))
                    ed_time = time.time()
                    elapsed_time = ed_time - st_time
                    total_oneshot_time += elapsed_time
                    print(f"Time taken to do one-shot: {elapsed_time:.2f} seconds")
                    if example_method is not None: global_vars["examples_count"] += 1

                if not EXECUTE_GENERATION: continue

                oracle_code = test['oracle']
                global first_case_done, first_pass_case_done
                first_pass_case_done, first_case_done = False, False
                target_number = TARGET_NUMBER
                already_gen_oras = set()

                for oracle_id in range(GLOBAL_TRIALS):
                    print('\nORACLE ID: {}\n'.format(oracle_id))
                    start_time = time.time()
                    if target_number == 0: break

                    res, feedback = None, None
                    if v1_flag:
                        gpt_oracle = ask(oracle_id, context, summaries, example_method, test_name, before_code, test_code, focal_code)
                        if gpt_oracle is None: continue

                        if gpt_oracle not in already_gen_oras:
                            already_gen_oras.add(gpt_oracle)
                            res, feedback = collect_feedback(project.repo_dir, oracle_id, filePath, subRepo, className, test_name, test_code, gpt_oracle)

                    elif v2_flag:
                        st_time = time.time()
                        gpt_oracle = ask(oracle_id, context, summaries, example_method, test_name, before_code, test_code, focal_code)
                        ed_time = time.time()
                        elapsed_time = ed_time - st_time
                        total_ask_time += elapsed_time
                        print(f"Time taken to ask: {elapsed_time:.2f} seconds")
                        if gpt_oracle is None: continue

                        if gpt_oracle not in already_gen_oras:
                            st_time = time.time()
                            already_gen_oras.add(gpt_oracle)
                            proc_q = Queue()
                            p = Process(target=follow_up, args=(proc_q, project.repo_dir, oracle_id, filePath, subRepo, className, test_name, test_code, gpt_oracle, focal_code))
                            p.start()
                            p.join(timeout=100)
                            if p.is_alive():
                                p.terminate()
                                gpt_oracle = None
                            else:
                                res = proc_q.get()
                                feedback = proc_q.get()
                                gpt_oracle = proc_q.get()

                            if gpt_oracle is None: continue

                            if feedback is None or len(feedback) > 0:
                                context.insert(role="user", content="AVOID generating the assertion `" + gpt_oracle + "`, because it results in a build failure.")

                            elif len(gpt_oracle) > 0 and feedback is not None and len(feedback) == 0:
                                context.insert(role="user", content="GOOD. `" + gpt_oracle + "` is a plausible assertion. So, AVOID generating the assertion `" + gpt_oracle + "` again because you have already generated it.")
                                target_number -= 1
                            ed_time = time.time()
                            elapsed_time = ed_time - st_time
                            total_followup_time += elapsed_time
                            print(f"Time taken to do follow ups: {elapsed_time:.2f} seconds")

                    print(f'Checking functionality for oracle ID: {oracle_id}')
                    st_time = time.time()
                    st_funct_time = time.time()
                    functional = is_functional(project.repo_dir, oracle_id, filePath, subRepo, className, test_name, test_code, gpt_oracle)
                    ed_time = time.time()
                    elapsed_time = ed_time - st_funct_time
                    total_isfunctional_time += elapsed_time
                    print(f"Time taken for isfunctional: {elapsed_time:.2f} seconds")
                    print(f'Functionality check complete for oracle ID: {oracle_id}, functional: {functional}')
                    print(f'Writing results for test ID: {testId}, oracle ID: {oracle_id}')
                    result_pass, result_all = write_res(gateway, testId, oracle_id, userName, repoName, className, test_name, test_code, gpt_oracle, oracle_code, total_st_time, time.time(), feedback, functional)
                    if result_pass:
                        results_pass.append(result_pass)
                    if result_all:
                        results_all.append(result_all)
                    print(f'Results written for test ID: {testId}, oracle ID: {oracle_id}')
                    ed_time = time.time()
                    elapsed_time = ed_time - st_time
                    print(f"Time taken to write and flush: {elapsed_time:.2f} seconds")
                    total_writeandflush_time += elapsed_time
                    
                    

                print('Restoring test file:', filePath)
                restore_test_file(filePath)
                testId += 1
               
                ed_time = time.time()
                elapsed_time = ed_time - total_st_time
                total_test_time += elapsed_time
                print('Test file restored:', filePath)
                print(f"Time taken this test: {elapsed_time:.2f} seconds")
                print(f"Total Test Time: {total_test_time}")
                print(f"Total Write and Flush Time: {total_writeandflush_time}")
                print(f"Total Write Res Time: {total_writeres_time}")
                print(f"Total Is Functional Time: {total_isfunctional_time}")
                print(f"Total Ask Time: {total_ask_time}")
                print(f"Total One Shot Time: {total_oneshot_time}")
                print(f"Total Summarization Time: {total_summarization_time}")
                print(f"Total Follow-Up Time: {total_followup_time}")



        del project
        del allTests
        del depPaths
        del filePath
        del classTests

    except Exception as e:
        print('Exception in project processing: {}\n'.format(e))
        traceback.print_exc()
    print('FINISHED PROJECT!!!!')
    print('FINISHED PROJECT!!!!')
    print('FINISHED PROJECT!!!!')
    print('FINISHED PROJECT!!!!')

    return results_pass, results_all

def main():
    total_test_time = 0
    global examples_count
    examples_count = 0

    try:
        v1_flag, v2_flag = False, False
        arg = " ".join(sys.argv)
        if 'v1' in arg: 
            GLOBAL_TRIALS = 1
            v1_flag = True
        if 'v2' in arg: 
            v2_flag = True

        sample_id = sys.argv[-1]
        print('SAMPLE ID: ', sample_id)
        print('SAMPLE: sample_{}.json'.format(sample_id))

        gateway = JavaGateway()
        global_vars = {
            "examples_count": 0,
            "first_pass_case_done": False,
            "first_case_done": False
        }

        configuration_file = os.path.join(DATA_DIR, "input/sample_{}.json".format(sample_id))
        with open(configuration_file, 'r') as f:
            data = json.load(f)
            projects = data["projects"]
            multiprocessing.set_start_method('spawn')

            num_projects = len(projects)
            batch_size = max(1, num_projects)  # Divide projects into 4 batches

            all_results_pass = []
            all_results_all = []

            for i in range(0, num_projects, batch_size):
                batch_projects = projects[i:i + batch_size]
                # multiprocessing.set_start_method('spawn')

                with ProcessPoolExecutor() as executor:
                    futures = [executor.submit(process_project, project_data, sample_id, global_vars) for project_data in batch_projects]
                    for future in as_completed(futures):
                        results_pass, results_all = future.result()
                        all_results_pass.extend(results_pass)
                        all_results_all.extend(results_all)

        # Flatten all_results and write to CSV
        # all_results = [item for sublist in all_results for item in sublist]
        with open(os.path.join(PRO_DIR, "res/res_all/res_all_{}.csv".format(sample_id)), "w+") as resAll, open(os.path.join(PRO_DIR, "res/res_pass/res_pass_{}.csv".format(sample_id)), "w+") as resPass:
            resAllWriter = csv.writer(resAll, delimiter='\t')
            resPassWriter = csv.writer(resPass, delimiter='\t')

            resAllWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Time", "Corr", "BuildErr"])
            resPassWriter.writerow(["TestID", "VariantID", "Project", "TestClass", "TestName", "TrueOracle", "GenOracle", "Time", "Corr", "BuildErr"])

            for result in all_results_pass:
                if result is not None:
                    resPassWriter.writerow(result)
                    resPass.flush()

            for result in all_results_all:
                if result is not None:
                    resAllWriter.writerow(result)
                    resAll.flush()

        print('\nExamples Count: {}\n'.format(global_vars["examples_count"]))
    except Exception as e:
        print('Exception has occurred: {}\n'.format(e))
        traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except:
        pass