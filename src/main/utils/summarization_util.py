import sys
import os

from py4j.java_gateway import JavaGateway
from py4j.java_collections import ListConverter

sys.path.append('../')
from project import Project

from utils.context_util import Prompts, Context
from utils.gpt_util import interact_with_openai, if_exceed_token_limit
from utils.file_util import read_file

# file_path: path of the class under test
# src_path: project directory upto src -> ... /tmp/repos/repoName/subRepoName/src
def fetch_summarization_targets(file_path, src_path, dep_paths, test_code, focal_code):
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
        meta['focal'] = focal_code

        return meta
    
    return None

def generate_summarization_prompts(meta):
    summarization_prompts = [] # a list of dictionaries (keys are 'prompt', 'ask_gpt')
    done_set = set()

    # We prioritize the summarization queries that are related to method calls and variable updates
    if meta['focal'] is not None and len(meta['focal']) > 0:
        summarization_prompts.append({'prompt': 'Let\'s summarize the focal method.', 'ask_gpt': False})                               # We include this message in the context, but don't directly ask about it. We keep this in the context.
        summarization_prompts.append({'prompt': 'Can you explain the following focal method code?\n```{}```\n'.format(meta['focal']), 'ask_gpt': True})                                                                    # We ask directly about this question. Then, we drop this message from the context to save space.
    
    for lineNumber, line in meta['lines'].items():
        for methodOrClass, details in line.items():
            # generate prompt
            if methodOrClass=='constructors':
                for classDotConstructorName, constructorDetails in details.items():
                    # Asking to explain constructor body if the constructor is from the application package. If the constructor is from the application package, the dictionary key "body" will have the constructor body (ref. AbstractionVisitor class in Java).
                    if len(constructorDetails['body']) > 0 and classDotConstructorName not in done_set:
                        summarization_prompts.append({'prompt': 'In line {}, an object of class `{}` is instantiated.'.format(str(lineNumber), constructorDetails['class']), 'ask_gpt': False})                                                # We include this message in the context, but don't directly ask about it. We keep this in the context.
                        summarization_prompts.append({'prompt': 'Can you explain the following constructor code?\n```{}```\n'.format(constructorDetails['body']), 'ask_gpt': True})                                                          # We ask directly about this question. Then, we drop this message from the context to save space.
                        done_set.add(classDotConstructorName)
                    else:
                        summarization_prompts.append({'prompt': 'Take note that in line {}, constructor `{}` from class `{}` is invoked.'.format(str(lineNumber), constructorDetails['name'], constructorDetails['class']), 'ask_gpt': False})    # We include this message in the context, but don't directly ask about it. We keep this in the context.
                        summarization_prompts.append({'prompt': '', 'ask_gpt': False})    # Dummy prompt that will be dropped
            elif methodOrClass=='methods':
                for classDotMethodName, methodDetails in details.items():
                    # Asking to explain method body if the method is from the application package. If the method is from the application package, the dictionary key "body" will have the method body (ref. AbstractionVisitor class in Java).
                    if len(methodDetails['body']) > 0 and classDotMethodName not in done_set:
                        summarization_prompts.append({'prompt': 'In line {}, method `{}` of class `{}` is invoked.'.format(str(lineNumber), methodDetails['name'], methodDetails['class']), 'ask_gpt': False})                                   # We include this message in the context, but don't directly ask about it. We keep this in the context.
                        summarization_prompts.append({'prompt': 'Can you explain the following method code?\n```{}```\n'.format(methodDetails['body']), 'ask_gpt': True})                                                                    # We ask directly about this question. Then, we drop this message from the context to save space.
                        done_set.add(classDotMethodName)
                    else:
                        summarization_prompts.append({'prompt': 'Take note that in line {}, method `{}` from class `{}` is invoked.'.format(str(lineNumber), methodDetails['name'], methodDetails['class']), 'ask_gpt': False})                  # We include this message in the context, but don't directly ask about it. We keep this in the context.
                        summarization_prompts.append({'prompt': '', 'ask_gpt': False})    # Dummy prompt that will be dropped
            elif methodOrClass=='vars':
                for varName, varDetails in details.items():
                    # Asking to tell the updated value of an assigned local variable or global variable
                    summarization_prompts.append({'prompt': 'In line {}, the variable `{}` might have been updated'.format(str(lineNumber), varName), 'ask_gpt': False})                                                                       # We include this message in the context, but don't directly ask about it. We keep this in the context.
                    summarization_prompts.append({'prompt': 'After executing line {}, what is the updated value of variable `{}`?'.format(str(lineNumber), varName), 'ask_gpt': True})                                                         # We ask directly about this question. Then, we drop this message from the context to save space.

    # Summarization queries related to object instantiation is being performed after we are done with all the method calls and variable updates related summarization queries so that we don't run out of token limit due to large class source code
    for lineNumber, line in meta['lines'].items():
        for methodOrClass, details in line.items():
            if methodOrClass=='classes':
                for className, classDetails in details.items():
                    # Asking to explain class body if the class if from the application package. meta['classBody'] is a cache containing the code of the unique classes that are declared in the prefix.
                    if className in meta['classBody'] and className not in done_set:
                        summarization_prompts.append({'prompt': 'In line {}, an object of class `{}` is instantiated'.format(str(lineNumber), className), 'ask_gpt': False})                                                                   # We include this message in the context, but don't directly ask about it. We keep this in the context.
                        summarization_prompts.append({'prompt': 'Can you explain the following class code?\n```{}```'.format(meta['classBody'][className]), 'ask_gpt': True})                                                                # We ask directly about this question. Then, we drop this message from the context to save space.
                        done_set.add(className)
                    else:
                        summarization_prompts.append({'prompt': 'Take note that in line {}, an object of class `{}` is created.'.format(str(lineNumber), className), 'ask_gpt': False})                                                        # We include this message in the context, but don't directly ask about it. We keep this in the context.
                        summarization_prompts.append({'prompt': '', 'ask_gpt': False})    # Dummy prompt that will be dropped

    return summarization_prompts

def summarize(file_path, class_name, src_path, dep_paths, test_name, test_code, focal_code, enforce_regeneration=False):
    # instantiate a context manager for managing the context of the summarization related conversation
    context = Context(_name=Context.SUMMARIZATION_CONTEXT_NAME)

    # fetch methods and classes (creating a dictionary where the keys are the line numbers of the test prefix and the contents are related to which methods were called at a specific line in the test prefix or an object of which class was instantiated at a specific line in the test prefix or which variable was assigned to at a specific line in the test prefix)
    meta = fetch_summarization_targets(file_path, src_path, dep_paths, test_code, focal_code)

    if meta is not None:
        # retrieve summary from cache if exists
        summaries = retrieve_from_cache(class_name, test_name)

        if summaries is None or enforce_regeneration:
            if enforce_regeneration: print("ALERT: Regenerating Summaries")

            # all summaries for a particular test prefix (we could have used the concatenated context history messages instead but if the context is reset at some point, we will lose the context)
            summaries = ""

            # get a list of summarization prompts for each line (one line can have multiple summarization prompts because a single line in the test prefix can have multiple method invocations or have an object that is instantiated or have a variable that is assigned to):
            summarization_prompts = generate_summarization_prompts(meta)

            # Introducing the task to ChatGPT and mimicking its response from the WebUI
            context.insert(role="user", content=Prompts.SUMMARIZATION_SEED)
            context.insert(role="assistant", content=Prompts.SUMMARIZATION_MOCK_SEED_RESPONSE)
            
            idx = 0
            for summarization_prompt in summarization_prompts:
                # insert prompt into summarization context
                context.insert(role="user", content=summarization_prompt['prompt'])

                print(summarization_prompt)

                # some of the summarization prompts will be directly added to the summary instead of asking ChatGPT to summarize (e.g. "Take note ... ")
                if summarization_prompt['ask_gpt']:
                    # interact with open ai about abstraction
                    summary = interact_with_openai(context=context)
                    print('SUMMARIZATION RESPONSE: {}\n'.format(summary))

                    # gather all the summaries for a specific test prefix
                    summaries += "{}. ".format(str(idx)) + summary + "\n"
                    idx += 1

                    # remove prompt message from abstraction_history (so, we are only keeping the summaries in the context in case ChatGPT finds one of the summaries useful when summarizing another method/class/side-effect)
                    context.remove_last()

                    # insert response into context
                    context.insert(role="assistant", content=summary)
                else:
                    if len(summarization_prompt['prompt']) > 0:
                        summaries += "{}. ".format(str(idx)) + summarization_prompt['prompt'] + "\n"
                        idx += 1
            
            if len(summaries) > 0:
                summaries += "\nThat is the end of all the summaries.\n"

            save_to_cache(summaries, class_name, test_name)
        
        return summaries

    return None

def retrieve_from_cache(class_name, test_name):
    # check if summary cache exists then retrieve from the summary path, else ask ChatGPT to summarize
    summaries_cache_path = "../data/summaries/{}-{}.summary".format(class_name, test_name)

    if os.path.exists(summaries_cache_path):
        print("\nSummary cache exists")
        with open(summaries_cache_path, 'r') as summaries_cache:
            summaries = summaries_cache.read()
            if len(summaries) == 0:
                print("\nSummaries is empty")
                return None
            else:
                return summaries
    else:
        return None

def save_to_cache(summaries, class_name, test_name):
    # save generated summary to a cache for faster retrieval next time
    summaries_cache_path = "../data/summaries/{}-{}.summary".format(class_name, test_name)

    with open(summaries_cache_path, 'w+') as summaries_cache:
        summaries_cache.write(summaries)
        summaries_cache.write("\n")

    print("\nSaved summaries to cache file")

def test():
    file_path = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors/src/test/java/ncsusoftware/AnotherTest.java"
    test_code = '\n'.join(read_file(file_path, lo=53, hi=83))
    src_path = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors/src"

    # In the Project class __init__, the line containing self.init_env() should be commented for this specific test and uncommented after finishing this test
    p = Project()
    p.repo_dir = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors"
    dep_paths = list(p.list_dependencies())

    summaries = summarize(file_path, "AnotherTest", src_path, dep_paths, "testAbstraction", test_code.replace("<AssertPlaceHolder>;", ""), enforce_regeneration=True)

    print("\nSummaries:\n{}\n".format(summaries))
