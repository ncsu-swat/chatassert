import sys
import os

from py4j.java_gateway import JavaGateway
from py4j.java_collections import ListConverter

sys.path.append('../')
from project import Project

# file_path: path of the class under test
# src_path: project directory upto src -> ... /tmp/repos/repoName/subRepoName/src
def fetch_abstraction_targets(file_path, src_path, dep_paths, test_code):
    # print('File path: {}\nSrc path: {}\nDep paths: {}\nTest code:\n{}\n\n'.format(file_path, src_path, dep_paths, test_code))

    # Creating Java Gateway Server
    gateway = JavaGateway()
    # Converting python list to java list for communicating to java through PY4J
    dep_path_java_list = ListConverter().convert(dep_paths, gateway._gateway_client)

    # Retrieving dictionary of method calls and classes metadata for each line in the test prefix
    java_dict = gateway.entry_point.fetchMethodsClasses(test_code, file_path, src_path, dep_path_java_list)
    if java_dict is not None:
        java_dict = dict(java_dict)

        # Retrieving class body
        class_body = dict()
        for lineNumber, methodOrClass in java_dict.items():
            for k, v in methodOrClass.items():
                if k=='classes':
                    for className, classDetails in v.items():
                        mainPath = os.path.join(src_path, 'main/java', classDetails['package'].replace('.', '/'))
                        testPath = os.path.join(src_path, 'test/java', classDetails['package'].replace('.', '/'))

                        # Removing the particular test method from the class body so that when we are asking ChatGPT to explain the class, we don't inadvertently leak the test method containing the actual assertion
                        for root, dirs, files in os.walk(mainPath):
                            for f in files:
                                if f.endswith(classDetails['class'] + '.java'):
                                    with open(os.path.join(root, f), 'r') as classSource:
                                        # Before asking ChatGPT to explain a test class, we are removing the current test method from the test class in order to avoid inadvertent leakage of test dataset (if test_code cannot be parsed, then all the test methods in the test class are removed)
                                        class_body[classDetails['class']] = gateway.entry_point.removeTestMethodsFromTestClass(classSource.read(), test_code)

                        for root, dirs, files in os.walk(testPath):
                            for f in files:
                                if f.endswith(classDetails['class'] + '.java'):
                                    with open(os.path.join(root, f), 'r') as classSource:
                                        class_body[classDetails['class']] = classSource.read()

        meta = dict()
        meta['lines'] = java_dict
        meta['classBody'] = class_body

        return meta
    
    return None

def generate_abstraction_prompts(meta):
    abstraction_prompts = []
    done_set = set()

    # We prioritize the abstraction queries that are related to method calls and variable updates
    for lineNumber, line in meta['lines'].items():
        for methodOrClass, details in line.items():
            # generate prompt
            if methodOrClass=='methods':
                for classDotMethodName, methodDetails in details.items():
                    # Asking to explain method body if the method if from the application package. If the method is from the application package, the dictionary key "body" will have the method body (ref. AbstractionVisitor class in Java).
                    if len(methodDetails['body']) > 0 and classDotMethodName not in done_set:
                        abstraction_prompts.append('In line {}, method {} of class {} is invoked. Can you explain the following method code?\n```{}```\n'.format(str(lineNumber), methodDetails['name'], methodDetails['class'], methodDetails['body']))
                        done_set.add(classDotMethodName)
                    else:
                        abstraction_prompts.append('Take note that in line {}, method {} from class {} is invoked.'.format(str(lineNumber), methodDetails['name'], methodDetails['class']))
            elif methodOrClass=='vars':
                for varName, varDetails in details.items():
                    # Asking to tell the updated value of an assigned local variable or global variable
                    abstraction_prompts.append('After executing line {}, what is the updated value of variable {}?'.format(str(lineNumber), varName))

    # Abstraction queries related to object instantiation is being performed after we are done with all the method calls and variable udpates related abstraction queries so that we don't run out of token limit due to large class source code
    for lineNumber, line in meta['lines'].items():
        for methodOrClass, details in line.items():
            if methodOrClass=='classes':
                for className, classDetails in details.items():
                    # Asking to explain class body if the class if from the application package. meta['classBody'] is a cache containing the code of the unique classes that are declared in the prefix.
                    if className in meta['classBody'] and className not in done_set:
                        abstraction_prompts.append('In line {}, an object of class {} is instantiated. Can you explain the following class code?\n```{}```'.format(str(lineNumber), className, meta['classBody'][className]))
                        done_set.add(className)
                    else:
                        abstraction_prompts.append('Take note that in line {}, an object of class {} is created.'.format(str(lineNumber), className))

    return abstraction_prompts

def test():
    test_code = "@org.junit.Test\npublic void testAbstraction()\n{\nFooClass foo = new FooClass();\nfoo.sqr(foo.add(5, 3.0));\n(new FooClass()).add(foo.sqr(3), (float)foo.sqr(4));\n}"
    file_path = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors/src/test/java/ncsusoftware/AnotherTest.java"
    src_path = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors/src"

    # In the Project class __init__, the line containing self.init_env() should be commented for this specific test and uncommented after finishing this test
    p = Project()
    p.repo_dir = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors"
    dep_path = list(p.list_dependencies())

    # Creating Java Gateway Server
    gateway = JavaGateway()
    # Converting python list to java list for communicating to java through PY4J
    dep_path_java_list = ListConverter().convert(dep_path, gateway._gateway_client)

    # Retrieving dictionary of method calls and classes metadata for each line in the test prefix
    meta = dict(gateway.entry_point.fetchMethodsClasses(test_code, file_path, src_path, dep_path_java_list))

    print(meta[1]['classes'])