import os
import json
import openai
from main.utils.gpt_util import if_exceed_token_limit
from main.project import Project
from path_config import DATA_DIR,API_KEY_FILEPATH,CONFIG_DIR, PRO_DIR
from utils.file_util import read_file
from main.utils.git_util import get_parent_commit
from main.utils.file_util import extract_content_within_line_range, read_file
from main.utils.markdown_util import extract_code_block_from_markdown_text
from main.utils.prompt_generator_util import get_vulnerable_function_attributes

# Setup                                                                                                                                                                                                       
openai.api_key = read_file(API_KEY_FILEPATH)  # OpenAPI key                                                                                                                                                   
MAX_INTERACTION = 5  # Maximum number of interactions                                                                                                                                                         
MODEL_NAME = "gpt-3.5-turbo"

def interact_with_openai(prompt):
    # Function for interacting with the API                                                                                                                                                                   

    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a chatbot for oracle generation."},
            {"role": "user", "content": prompt},
        ]
    )

    result = ""
    for choice in response.choices:
        result += choice.message.content

    return result


def prompt_generator(interact_index, test_seq=""):
    return "Generate an org.junit.Assert statement for the following test code:\n{}".format(test_seq)


if __name__ == "__main__":

    configuration_file = os.path.join(PRO_DIR, "configuration.json")
    with open(configuration_file) as f:
        data = json.load(f)
        for project_data in data["projects"]:
            name = project_data["name"]
            giturl = project_data["giturl"]
            commit = project_data["commit"]
            oracles = project_data["oracles"]
            # create project object
            project = Project(name, giturl, commit)
            # clone the project
            project.init_env()
            # run the tests
            res = project.run_tests()
            if res["tests"] == 0:
                raise Exception("unexpected: could not find tests in this project")
            if res["failures"]+res["errors"] > 0:
                raise Exception("expecting all tests to pass")
                        
            print("analyzing oracles")
            for oracle in oracles:
                filepath = os.path.join(project.repo_dir, oracle["file"])
                test_code = "".join(read_file(filepath, int(oracle["tseq_start_ln"]), int(oracle["tseq_end_ln"])))
                oracle_code = "".join(read_file(filepath, int(oracle["oracle_ln"]), int(oracle["oracle_ln"])))
                print("".join(test_code))
                print("".join(oracle_code))

                #TODO: ask gpt to generate oracles
                '''
                1. replace oracle with whatever gpt gives
                2. compile and run tests
                3. stop if finds a solution
                4. repeat for a number of times
                '''

                # Initialize the conversation history                                                                                                                                                                     
                conversation_history = ""

                for i in range(1, MAX_INTERACTION + 1):

                    # Add user input to the conversation history                                                                                                                                                          
                    prompt = prompt_generator(i, test_seq=test_code)
                    prompt = f"{conversation_history}\n{prompt}"
                    if if_exceed_token_limit(prompt, MODEL_NAME):
                        break

                    # Get the model's response                                                                                                                                                                            
                    model_response = interact_with_openai(prompt)                    
                    gpt_oracle = extract_code_block_from_markdown_text(model_response)
                    if gpt_oracle == None:
                        continue ## could not find anything apparently

                    # use fully-qualified name for Assertion type
                    # TODO (low prio): Better solution is to use a type solver https://www.javadoc.io/doc/com.github.javaparser/javaparser-symbol-solver-core/3.6.10/com/github/javaparser/symbolsolver/JavaSymbolSolver.html
                    gpt_oracle = gpt_oracle.lstrip()
                    if "Assert." in gpt_oracle:
                        gpt_oracle = gpt_oracle.replace("Assert.", "org.junit.Assert.")

                    # Check if the oracle is plausible
                    project.replace_oracle_atln(filepath=filepath, neworacle=gpt_oracle, ln=int(oracle["oracle_ln"]))

                    res = project.run_tests()

                    if res["build_failure"]:
                        continue # build failure

                    if res["tests"] == 0:
                        raise Exception("unexpected: could not find tests in this project")

                    if res["failures"]+res["errors"] == 0:
                        print("Plausible oracle detected")
                        ##TODO: check if oracle is identical
                        break # DONE with this oracle