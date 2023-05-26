import json
import csv

import pandas as pd
pd.options.display.max_colwidth = 500

from file_util import read_file

from AST import AST

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
oracleLns = None
with open('../../teco_eval/teco/input/eval_locs.jsonl', 'r') as evalLocsFile:
    oracleLns = [json.loads(line)[1] for line in evalLocsFile]

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
    
# Predictions
preds = None
with open('../../teco_eval/teco/output/preds.jsonl', 'r') as predsFile:
    preds = [json.loads(line) for line in predsFile]

# Method to create nested test class json object
def buildTestClassJson(currentLineNumber):
    testClass = dict()

    testClass['className'] = testPaths[currentLineNumber].split('/')[-1].split('#')[0]
    testClass['classPath'] = ''
    if len(project['subRepo']) > 0: testClass['classPath'] += project['subRepo'] + '/'
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
def buildTestJson(currentLineNumber):
    # Teco saves all strings as STR in the AST to make the problem easy. To compare head to head with Teco, we will use the pretty printed version of the Teco provided setup, test, focal method ASTs (which include STR tags instead of string literals). Later, for GEPETO we will use the setup, test, focal method from the actual source code using the saved line numbers to test with the string literals. 

    test = dict()

    test['testName'] = testPaths[currentLineNumber].split('/')[-1].split('#')[1].split('(')[0]
    testSignature = testSignatures[currentLineNumber] # No [0] since each test signature's AST in test_sign.jsonl is a 1d array
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
    test['testMethod'] = "@Test\n" + testMethodString

    # Add oracle (remove later, use oracle line)
    test['oracle'] = "".join(golds[currentLineNumber])
    test['oracleLn'] = len(testMethod)

    # Add focal method
    test['focalFile'] = ''
    if len(project['subRepo']) > 0: test['focalFile'] += project['subRepo'] + '/'
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

def countTecoPreds():
    with open('../../teco_eval/teco/output/preds_processed.csv', 'w+') as preds_csv:
        csvWriter = csv.writer(preds_csv, delimiter='\t')
        csvWriter.writerow(['TestID', 'NumPreds', 'True Oracle', 'Gen Oracle'])
        for i, (pred, gold) in enumerate(zip(preds, golds)):
            for topPred in pred['topk']:
                # print(str(i), ''.join(gold).replace('Assert.', ''), ''.join(topPred['toks']).replace('Assert.', ''))
                goldAssert = ''.join(gold).replace('Assert.', '')
                predAssert = ''.join(topPred['toks']).replace('Assert.', '')
                csvWriter.writerow("{}\t{}\t{}\t{}".format(str(i), str(len(pred['topk'])), goldAssert, predAssert).split('\t'))

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

# Check to see if the total number of tests retrieved is equal to the total number of predictions from teco
def testCounterSanityCheck():
    counter = 0
    for project in projectsList:
        for testClass in project['allTests']:
            for test in testClass['classTests']:
                counter += 1
    assert counter == len(preds), "Not all teco tests could be retrieved, expected test count: {}, got: {}".format(len(ids), counter)

# countTecoPreds()

#-------------------------------------------------
projectsList = []
for predId, pred in enumerate(preds):
    project = None

    currentDataId = int(pred['data_id'].replace('csn-', ''))
    currentLineNumber = ids2Lines[currentDataId]

    projName = projects[currentLineNumber]
    repo = repos[repos['full_name']==projName]

    # Retrieve project if available in the projects array of dictionaries
    for prj in projectsList:
        if prj['userName']==repo['user'].to_string(index=False) and prj['repoName']==repo['repo'].to_string(index=False):
            project = prj
            break

    if project is None: # Project was not found
        project = dict()

        project['userName'] = repo['user'].to_string(index=False)
        project['repoName'] = repo['repo'].to_string(index=False)

        project['subRepo'] = ''
        if repo['mvn_multi_module'].reset_index(drop=True)[0]:
            project[subRepo] = repo['mvn_modules'][0].reset_index(drop=True)[0]

        project['commitSHA'] = repo['sha'].to_string(index=False)
        project['buildSystem'] = repo['build_system'].to_string(index=False)

        #------------------------------------------------------------------------------------------------------------------------------
        # Add allTests
        project['allTests'] = []
        testClass = buildTestClassJson(currentLineNumber)
        
        # Add test
        testClass['classTests'] = []
        test = buildTestJson(currentLineNumber)
        
        testClass['classTests'].append(test)
        project['allTests'].append(testClass)
        projectsList.append(project)
    else: # Project exists in the dictionary
        testClassFound = False
        testClass = buildTestClassJson(currentLineNumber)
        for tClass in project['allTests']:
            if tClass['className'] == testClass['className']: # Test class exists
                # Add test
                tClass['classTests'].append(buildTestJson(currentLineNumber))
                testClassFound = True
        if not testClassFound: # Test class does not exist
            # Add test class
            testClass = buildTestClassJson(currentLineNumber)

            # Add test
            testClass['classTests'] = []
            test = buildTestJson(currentLineNumber)
            
            testClass['classTests'].append(test)
            project['allTests'].append(testClass)

with open('../../new_data.json', 'w+') as newData:
    testCounterSanityCheck()

    projectsDict = { 'projects': projectsList }
    json.dump(projectsDict, newData, indent=4)

