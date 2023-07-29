import os
import sys
import json
import time
import csv
import re
import shutil
import xml.etree.ElementTree as ET
import pandas as pd

from project import Project
from path_config import DATA_DIR, CONFIG_DIR, PRO_DIR
from utils.file_util import read_file

from py4j.java_gateway import JavaGateway

import traceback
import pickle

import matplotlib.pyplot as plt
import seaborn as sns

global project

def is_functional(repo_dir, file_path, subRepo, class_name, test_name, test_code, gpt_oracle):
    res, feedback = None, None
    
    try:
        pitGateway = JavaGateway().entry_point
        
        # Removing other test methods from the test class except the test_name method
        pitGateway.setFile(file_path)
        testFileWithTestsRemoved = pitGateway.removeTestMethodsExcept(test_name)
        with open(file_path, 'w+') as testFile:
            testFile.write(testFileWithTestsRemoved)

        # Injecting generated oracle into the only available test method in the test class
        pitGateway.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))
        
        res, feedback = Project.run_test(repo_dir, subRepo, class_name, test_name)

        if 'BUILD FAILURE' in feedback:
            return False
        else:
            return True

    except Exception as e:
        traceback.print_exc()
        print('Exception: {}'.format(e))
        return False

    return False

def run_pitest(repo_dir, file_path, subRepo, class_name, test_name, test_code, gpt_oracle):
    res, feedback = None, None
    line_coverage, mutation_coverage, test_strength, tests_ran = 0, 0, 0, 0
    try:
        pitGateway = JavaGateway().entry_point
        
        # Removing other test methods from the test class except the test_name method
        pitGateway.setFile(file_path)
        testFileWithTestsRemoved = pitGateway.removeTestMethodsExcept(test_name)
        with open(file_path, 'w+') as testFile:
            testFile.write(testFileWithTestsRemoved)

        # Injecting generated oracle into the only available test method in the test class
        pitGateway.inject(test_name, test_code.replace("<AssertPlaceHolder>;", gpt_oracle))
        
        line_coverage, mutation_coverage, test_strength, tests_ran = Project.run_pitest(repo_dir, subRepo)

        print('\n\nOutput:\n========\nLine coverage: {}\nMutation coverage: {}\nTest strength: {}\nTests ran: {}\n'.format(line_coverage, mutation_coverage, test_strength, tests_ran))

        return line_coverage, mutation_coverage, test_strength, tests_ran
    except Exception as e:
        traceback.print_exc()
        print('Exception: {}'.format(e))
        return None, None, None, None

    return -1, -1, -1, -1

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

def draw_violin_plot():
    try:
        chatassert = pd.read_csv(os.path.join(DATA_DIR, 'mutation/chatassert-non-xm-mutationCoverage.tsv'), sep='\t')
        chatassert_dr = pd.read_csv(os.path.join(DATA_DIR, 'mutation/chatassert-non-xm-dr-mutationCoverage.tsv'), sep='\t')
        teco = pd.read_csv(os.path.join(DATA_DIR, 'mutation/teco-non-xm-mutationCoverage.tsv'), sep='\t')

        from scipy import stats
        normality_chatassert = stats.shapiro(chatassert['MutationStrength'])
        normality_chatassert_dr = stats.shapiro(chatassert_dr['MutationStrength'])
        normality_teco = stats.shapiro(teco['MutationStrength'])
        print('\nNormality (Shapiro Wilk\'s Statistic):\n\tChatAssert: {}\n\tChatAssert-DR: {}\n\tTeco: {}\n\n'.format(normality_chatassert, normality_chatassert_dr, normality_teco))

        from scipy.stats import mannwhitneyu
        U1, p1 = mannwhitneyu(chatassert['MutationStrength'], chatassert_dr['MutationStrength'])
        U2, p2 = mannwhitneyu(chatassert['MutationStrength'], teco['MutationStrength'])
        U3, p3 = mannwhitneyu(teco['MutationStrength'], chatassert_dr['MutationStrength'])
        print('\nStatistical Significance (Mann-Whitney U):\n\tChatAssert vs. ChatAssert-DR: {}\n\tChatAssert vs. Teco: {}\n\tChatAssert-DR vs. Teco: {}\n\n'.format(p1, p2, p3))

        def cliffs_delta(data1, data2):
            len1, len2, delta = len(data1), len(data2), 0
            for _data1 in data1:
                for _data2 in data2:
                    if _data1 > _data2:
                        delta += 1
                    elif _data1 < _data2:
                        delta -= 1
            c_delta = delta/(len1 * len2)
            if c_delta < 0:
                c_delta = c_delta * (-1)

            print('Cliffs Delta: ' + str(c_delta))
            if c_delta < 0.5:
                return 'small'
            elif c_delta < 0.8:
                return 'medium'
            else:
                return 'large'

        res1 = cliffs_delta(chatassert['MutationStrength'], chatassert_dr['MutationStrength'])
        res2 = cliffs_delta(chatassert['MutationStrength'], teco['MutationStrength'])
        res3 = cliffs_delta(teco['MutationStrength'], chatassert_dr['MutationStrength'])
        print('\nEffect Size (Cliff\'s Delta):\n\tChatAssert vs. ChatAssert-DR: {}\n\tChatAssert vs. Teco: {}\n\tChatAssert-DR vs. Teco: {}\n\n'.format(res1, res2, res3))

        # mutation_df = pd.DataFrame({'chatassert': chatassert['MutationStrength'], 'chatassert-dr': chatassert_dr['MutationStrength'], 'teco': teco['MutationStrength']})
        mutation_df = pd.DataFrame({'chatassert-dr': chatassert_dr['MutationStrength'], 'teco': teco['MutationStrength']})
        # mutation_df = pd.DataFrame({'chatassert': chatassert['MutationStrength'], 'teco': teco['MutationStrength']})

        sns.set(font_scale=2)
        plt.tick_params(labelleft=False)
        plt.xlabel('Mutation Test Strength (%)')
        ax = sns.violinplot(data=mutation_df, orient='h', cut=0, bw_method=0.2, legend='full')

        plt.legend(loc='lower right', fontsize='large')
        plt.show()
    except Exception as e:
        print('Exception: ' + e)

def main():
    global project

    START_FROM = 0
    GO_UNTIL = 351

    try:
        res_file = sys.argv[1]
        df_res = pd.read_csv(os.path.join(DATA_DIR, 'mutation/{}.tsv'.format(res_file)), sep='\t')

        # Input data sample id (e.g. sample_1.json)
        sample_id = sys.argv[-1]
        print('SAMPLE: sample_{}.json'.format(sample_id))

        testId = 0

        # Initialize a PY4J client to communicate with the Java gateway server
        gateway = JavaGateway()

        configuration_file = os.path.join(DATA_DIR, "input", "sample_{}.json".format(sample_id))
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

                # Make sure to copy the repo from the cache directory to the working directory
                project.copy_cache()

                for testClass in allTests:
                    className = testClass["className"]
                    classPath = testClass["classPath"]
                    filePath = os.path.join(project.repo_dir, classPath)
                    classTests = testClass["classTests"]
                    subRepo = testClass["subRepo"]

                    # Copy only the original pom.xml from cache
                    project.restore_pom(subRepo)

                    # Precompile project jar
                    # is_precompiled = project.precompile_jar(subRepo=subRepo)

                    # If project is precompiled into a jar, build only the target test class incrementally to reduce build time
                    # if is_precompiled:
                    #     project.add_maven_compiler_plugin(test_class_path=filePath)
                    # else:
                    #     project.add_maven_compiler_plugin()

                    # Make sure that all dependencies are added to pom.xml
                    project.ensure_dependencies(subRepo)

                    # Fetch dependency jar paths to pass to the JarTypeSolver
                    # depPaths = list(project.list_dependencies(subRepo))

                    print("\n-----------------------------------------\nAnalyzing Oracles for Test Class: {}\n-----------------------------------------\n".format(className))
                    for test in classTests:
                        # Copy only the original test class's parent directory from cache
                        project.restore_test_dir(subRepo, testClass["classPath"])

                        if testId >= START_FROM:
                            # Get Test Code
                            test_name = test["testName"]
                            test_lines = read_file(filePath, int(test["startLn"]), int(test["endLn"]))
                            test_lines = tecofy_testlines(test_lines)
                            test_lines = place_placeholder(test_lines, int(test["startLn"]), int(test["oracleLn"]))
                            if len(test_lines) == 0: continue
                            test_code = " ".join(test_lines)

                            # Get Focal Path
                            focal_path = os.path.join(project.repo_dir, test["focalFile"])

                            # Get Oracle Code
                            oracle_code = test['oracle']

                            # Add pit plugin with test_class_path and focal_file_path
                            project.add_pit_plugin(subRepo=subRepo, test_file_path=filePath, focal_file_path=focal_path)

                            gen_oracles = df_res[(df_res['ClassName']==className) & (df_res['TestName']==test_name)]['GenOracle'].values.tolist()
                            for oracle in gen_oracles:
                                if 'instanceof' in oracle:
                                    qualified_oracle = 'org.junit.Assert.' + oracle.split('instanceof')[0] + ' instanceof ' + oracle.split('instanceof')[1]
                                else:
                                    qualified_oracle = 'org.junit.Assert.' + oracle

                                try:
                                    print('Oracle: {}\n'.format(oracle))

                                    if pd.isnull(df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'MutationStrength'].iloc[0]):
                                        if is_functional(project.repo_dir, filePath, subRepo, className, test_name, test_code, qualified_oracle):
                                            print('Is functional? - True\n')
                                            df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'Compiles'] = '1'
                                        else:
                                            print('Is functional? - False\n')
                                            df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'Compiles'] = '0'

                                    # if df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'Compiles'].iloc[0] == 1:
                                    #     if pd.isnull(df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'MutationStrength'].iloc[0]):
                                    #         line_coverage, mutation_coverage, test_strength, tests_ran = run_pitest(project.repo_dir, filePath, subRepo, className, test_name, test_code, qualified_oracle)

                                            # df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'line_coverage'] = line_coverage
                                            # df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'mutation_coverage'] = mutation_coverage
                                            # df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'MutationStrength'] = test_strength
                                            # df_res.loc[(df_res['ClassName']==className) & (df_res['TestName']==test_name) & (df_res['GenOracle']==oracle), 'tests_ran'] = tests_ran
                                except Exception as e:
                                    traceback.print_exc()
                                    print('Exception: {}\n'.format(str(e)))

                        # Increment test counter
                        testId += 1
                        if testId >= GO_UNTIL: break

                    # When tests from a certain class is finished restore that class to avoid compilation errors
                    project.restore_test_dir(subRepo, testClass["classPath"])

                    # test class level: break
                    if testId >= GO_UNTIL: break

                    # Save updated df_res after every 5 tests
                    if (testId+1) % 5 == 0:
                        df_res.to_csv(os.path.join(DATA_DIR, 'mutation', '{}_{}.tsv'.format(res_file, sample_id)), sep='\t', index=False)

                # project level: break
                if testId >= GO_UNTIL: break
                
                # Save updated df_res after every 5 tests
                if (testId+1) % 5 == 0:
                    df_res.to_csv(os.path.join(DATA_DIR, 'mutation', '{}_{}.tsv'.format(res_file, sample_id)), sep='\t', index=False)
        
        # Sanity save
        df_res.to_csv(os.path.join(DATA_DIR, 'mutation', '{}_{}.tsv'.format(res_file, sample_id)), sep='\t', index=False)
    except Exception as e:
        print('Exception has occurred: {}\n'.format(e))
        traceback.print_exc()

if __name__ == "__main__":
    try:
        # main()
        draw_violin_plot()
    except Exception as e:
        print(e)