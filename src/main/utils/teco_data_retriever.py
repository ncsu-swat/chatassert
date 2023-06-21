import json
import csv
import random
import os
import sys

import pandas as pd
pd.options.display.max_colwidth = 500

from file_util import read_file

from AST import AST

sys.path.append('../') # Since Project module is in the parent directory
from project import Project

#-------------------------------------------

repos = pd.read_json('../../teco_eval/teco/repos/repos.json')
projects = None
with open('../../teco_eval/teco/input/proj_name.jsonl', 'r') as projectsFile:
    projects = [json.loads(line) for line in projectsFile]

# ID/Line numbers
ids, ids2Lines, lines2Ids = None, dict(), dict()
with open('../../teco_eval/teco/input/id.jsonl', 'r') as idsFile:
    ids = [json.loads(line) for line in idsFile]
    for i, dataId in enumerate(ids):
        ids2Lines[int(dataId.replace('csn-', ''))] = i
        lines2Ids[i] = int(dataId.replace('csn-', ''))

# Gold statement
golds = None
with open('../../teco_eval/teco/input/gold_stmts.jsonl', 'r') as goldsFile:
    golds = [json.loads(line) for line in goldsFile]

# Oracle line numbers in AST without comments
evalLocs = None
with open('../../teco_eval/teco/input/eval_locs.jsonl', 'r') as evalLocsFile:
    evalLocs = [json.loads(line)[1] for line in evalLocsFile]

# Focal paths and methods
focalPaths, focalMethods = None, None
with open('../../teco_eval/teco/input/focal_mkey.jsonl', 'r') as focalPathsFile, open('../../teco_eval/teco/input/focalm.jsonl', 'r') as focalMethodsFile:
    focalPaths = [json.loads(line) for line in focalPathsFile]
    focalMethods = [json.loads(line) for line in focalMethodsFile]

# Test paths, signatures, and methods
testPaths, setupMethods, testMethods, testSignatures = None, None, None, None
with open('../../teco_eval/teco/input/test_mkey.jsonl', 'r') as testPathsFile, open('../../teco_eval/teco/input/setup_methods.jsonl', 'r') as setupMethodsFile, open('../../teco_eval/teco/input/test_stmts.jsonl', 'r') as testMethodsFile, open('../../teco_eval/teco/input/test_sign.jsonl') as testSignaturesFile:
    testPaths = [json.loads(line) for line in testPathsFile]
    setupMethods = [json.loads(line) for line in setupMethodsFile]
    testMethods = [json.loads(line) for line in testMethodsFile]
    testSignatures = [json.loads(line) for line in testSignaturesFile]

# Method to create nested test class json object
def buildTestClassJson(currentLineNumber):
    testClass = dict()

    testClass['className'] = testPaths[currentLineNumber].split('/')[-1].split('#')[0]
    
    testClass['classPath'] = ''
    if len(project['subRepos']) > 0: 
        testFileName = testPaths[currentLineNumber].split('#')[0].split('$')[0].split('/')[-1] + '.java'
        testClass['subRepo'] = findSubRepoForTest(testFileName)
        testClass['classPath'] += testClass['subRepo'] + '/' 
    else:
        testClass['subRepo'] = ''
    testClass['classPath'] += 'src/test/java/' + testPaths[currentLineNumber].split('#')[0] + '.java'
    
    # Before (setup) method and Before (setup) method line numbers from AST
    setupMethodString = ''
    setupMethod = setupMethods[currentLineNumber]
    if len(setupMethod) > 0:
        setupAST = AST.deserialize(setupMethod[0])

        for setupLine in setupMethod:
            setupLineAST = AST.deserialize(setupLine)
            setupMethodString += setupLineAST.pretty_print()

        testClass['before'] = { 'setupName': setupAST.get_methodName(), 'startLn': setupAST.get_lineno_range()[0], 'endLn': setupAST.get_lineno_range()[1], 'setupMethod': setupMethodString }

    return testClass

# Method to create nested test json object
def buildTestJson(currentLineNumber, testClass):
    # Teco saves all strings as STR in the AST to make the problem easy. To compare head to head with Teco, we will use the pretty printed version of the Teco provided setup, test, focal method ASTs (which include STR tags instead of string literals). Later, for GEPETO we will use the setup, test, focal method from the actual source code using the saved line numbers to test with the string literals. 
    test = dict()

    test['testName'] = testPaths[currentLineNumber].split('/')[-1].split('#')[1].split('(')[0]
    testSignature = testSignatures[currentLineNumber]
    testAST = AST.deserialize(testSignature)
    test['startLn'] = testAST.get_lineno_range()[0]
    test['endLn'] = testAST.get_lineno_range()[1]

    testMethodString = testAST.pretty_print().strip() + ' {\n'
    testMethod = testMethods[currentLineNumber]
    for testLine in testMethod:
        testLineAST = AST.deserialize(testLine)
        testMethodString += testLineAST.pretty_print(indent=4)
    testMethodString += " " * 5 + "".join(golds[currentLineNumber])
    testMethodString += '\n}'
    test['testMethod'] = testMethodString

    # Add oracle (remove later, use oracle line)
    test['oracle'] = "".join(golds[currentLineNumber])
    test['oracleLn'] = evalLocs[currentLineNumber] # + 2 because of the @Test annotation and the test method signature

    # Add focal method
    test['focalFile'] = ''
    if len(project['subRepos']) > 0: 
        focalFileName = focalPaths[currentLineNumber].split('#')[0].split('$')[0].split('/')[-1] + '.java'
        test['focalFile'] += findSubRepoForTest(focalFileName) + '/'
    test['focalFile'] += 'src/main/java/' + focalPaths[currentLineNumber].split('#')[0] + '.java'
    
    test['focalName'] = focalPaths[currentLineNumber].split('#')[1].split('(')[0]
    if test['focalName'] == '<init>':
        test['focalName'] = test['focalFile'].split('/')[-1].replace(".java", "")

    focalMethod = focalMethods[currentLineNumber]
    focalAST = AST.deserialize(focalMethod)
    test['focalStartLn'] = focalAST.get_lineno_range()[0]
    test['focalEndLn'] = focalAST.get_lineno_range()[1]
    test['focalMethod'] = focalAST.pretty_print()

    return test

# For repositories with multiple maven modules
def findSubRepoForTest(fileName):
    gitURL = "git@github.com:{}/{}.git".format(project['userName'], project['repoName'])
    
    if not os.path.exists('../../tmp/repos/{}'.format(project['repoName'])):
        tmpProj = Project(project['repoName'], '', gitURL, project['commitSHA'], None, '../../tmp')

    def walker(subRepo, root, searchFile):
        for root, dirs, files in os.walk(root):
            for d in dirs:
                ret = walker(subRepo, os.path.join(root, d), searchFile)
                if ret is not None:
                    return ret
            for f in files:
                if searchFile == f:
                    return subRepo
            return None
    for subRepo in project['subRepos']:
        retSubRepo = walker(subRepo, os.path.join('../../tmp/repos/{}'.format(project['repoName']), subRepo), fileName)
        if retSubRepo is not None:
            # print('RET: {}\n'.format(retSubRepo))
            return retSubRepo

    print('ALERT: Could not find repository sub module for project: {}, file name: {}\n'.format(project['repoName'], fileName))

    return None

def countTecoStrs():
    counter = 0
    for test, focal, setup in zip(testMethods, focalMethods, setupMethods):
        found = False
        for t in test:
            if '"STR"' in AST.deserialize(t).pretty_print():
                counter += 1
                found = True
                break
                
        if not found:
            if '"STR"' in AST.deserialize(focal).pretty_print():
                counter += 1
                found = True

        if not found:
            for s in setup:
                if '"STR"' in AST.deserialize(s).pretty_print():
                    counter += 1
                    found = True
                    break

def sampleTeco():
    all_preds = None
    sample_size = 350
    with open('../../teco_eval/teco/output/all_preds.jsonl', 'r') as allPredsFile, open('../../teco_eval/teco/output/preds.jsonl', 'w+') as predsFile:
        all_preds = [json.loads(line) for line in allPredsFile]
        random.shuffle(all_preds)
        idxs = random.sample(range(len(all_preds)), sample_size)
        for idx in idxs:
            predsFile.write(json.dumps(all_preds[idx]) + '\n')

# Check to see if the total number of tests retrieved is equal to the total number of predictions from teco
def testCounterSanityCheck():
    counter = 0
    for project in projectsList:
        for testClass in project['allTests']:
            for test in testClass['classTests']:
                counter += 1
    assert counter == len(preds), "Not all teco tests could be retrieved, expected test count: {}, got: {}".format(len(ids), counter)

# Check which sub-modules from the projects are being used
def listUsedSubModules(sample_id):
    project_submodule_set = set()

    with open('../../sample_{}.json'.format(str(sample_id))) as sample_file:
        projects = json.loads(sample_file.read())['projects']
        for prj in projects:
            for testClass in prj['allTests']:
                if len(testClass['subRepo']) > 0:
                    project_submodule_set.add('{}_{}'.format(prj['repoName'], testClass['subRepo']))
                else:
                    project_submodule_set.add('{}_'.format(prj['repoName']))

    for item in project_submodule_set:
        print(item)

# listUsedSubModules(1)
# exit(0)

#-------------------------------------------------
isChunking = True if 'chunk' in sys.argv else False

# Predictions
preds = None
if not isChunking:
    with open('../../teco_eval/teco/output/all_preds.jsonl', 'r') as predsFile:
        preds = [json.loads(line) for line in predsFile]
else:
    with open('../../teco_eval/teco/output/preds.jsonl', 'r') as predsFile:
        preds = [json.loads(line) for line in predsFile]

#-------------------------------------------------

projectsList = []
chunkList = [[],[],[],[],[],[],[]] # 6 chunks with 50 each
currentChunk = -1

for predId, pred in enumerate(preds):
    if predId % 50 == 0:
        currentChunk += 1

    project = None

    currentDataId = int(pred['data_id'].replace('csn-', ''))
    currentLineNumber = ids2Lines[currentDataId]

    projName = projects[currentLineNumber]
    repo = repos[repos['full_name']==projName]

    # Retrieve project if available in the projects array of dictionaries
    if not isChunking:
        for prj in projectsList:
            if prj['userName']==repo['user'].to_string(index=False) and prj['repoName']==repo['repo'].to_string(index=False):
                project = prj
                break
    else:
        for prj in chunkList[currentChunk]:
            if prj['userName']==repo['user'].to_string(index=False) and prj['repoName']==repo['repo'].to_string(index=False):
                project = prj
                break

    if project is None: # Project was not found
        project = dict()

        project['userName'] = repo['user'].to_string(index=False)
        project['repoName'] = repo['repo'].to_string(index=False)

        project['subRepos'] = []
        if repo['mvn_multi_module'].reset_index(drop=True)[0]:
            for subRepo in repo['mvn_modules'].reset_index(drop=True)[0]:
                project['subRepos'].append(subRepo)

        project['commitSHA'] = repo['sha'].to_string(index=False)
        project['buildSystem'] = repo['build_system'].to_string(index=False)

        #------------------------------------------------------------------------------------------------------------------------------
        # Add allTests
        project['allTests'] = []
        testClass = buildTestClassJson(currentLineNumber)
        
        # Add test
        testClass['classTests'] = []
        test = buildTestJson(currentLineNumber, testClass)
        
        testClass['classTests'].append(test)
        project['allTests'].append(testClass)
        
        if not isChunking:
            projectsList.append(project)
        else:
            chunkList[currentChunk].append(project)

    else: # Project exists in the dictionary
        testClassFound = False
        testClass = buildTestClassJson(currentLineNumber)
        for tClass in project['allTests']:
            if tClass['className'] == testClass['className']: # Test class exists
                # Add test
                tClass['classTests'].append(buildTestJson(currentLineNumber, tClass))
                testClassFound = True
        if not testClassFound: # Test class does not exist
            # Add test class
            testClass = buildTestClassJson(currentLineNumber)

            # Add test
            testClass['classTests'] = []
            test = buildTestJson(currentLineNumber, testClass)
            
            testClass['classTests'].append(test)
            project['allTests'].append(testClass)

#-------------------------------------------------------

if not isChunking:
    with open('../../sample_all.json', 'w+') as newData:
        testCounterSanityCheck()
        projectsDict = { 'projects': projectsList }
        json.dump(projectsDict, newData, indent=4)
else:
    for (chunkId, chunk) in enumerate(chunkList):
        with open('../../sample_{}.json'.format(str(chunkId+1)), 'w+') as chunkFile:
            chunkDict = { 'projects': chunk }
            json.dump(chunkDict, chunkFile, indent=4)

