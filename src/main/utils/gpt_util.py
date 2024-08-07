import sys
sys.path.append("../")

import openai
import tiktoken
from path_config import API_KEY_FILEPATH
from utils.context_util import Prompts
from utils.file_util import read_file

from traceback import print_exc

import time

# Organization IDs
# orgs = ["org-0wLi1kKIt9USgXMYklRCeTFQ", "org-9WS8eYC3IjH69yYgQNrk0X4w", "org-yclg2hcASx6eAd3nEyoFKrlf"]
orgs = ["org-SX6ZRhJQbRlEJCQwvqFIWBBf", "org-BThGzIrXj87JoLnOvhXP5Ff3"]
org_counter = [0, 0]
current_org = 0

# Setup                                                                                                                                                                                                    
openai.api_key = read_file(API_KEY_FILEPATH)  # OpenAPI key

MODEL_NAME = "gpt-3.5-turbo"
MODEL_MAX_TOKEN={
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16384
}

def oracle_prompt_generator(interact_index=None, context=None, summaries=None, example_method=None, setup=None, test=None, focal=None):
    if interact_index is None: raise Exception("In oracle prompt generator: interact_index cannot be None")
    if context is None: raise Exception("In oracle prompt generator: context cannot be None")
    if setup is None: setup = ""
    if test is None: raise Exception("In oracle prompt generator: test prefix cannot be None")
    if focal is None: raise Exception("In oracle prompt generator: focal method cannot be None")

    if interact_index == 0:
        # Insert seed message and a mock response( based on tests on ChatGPT WebUI ) in the oracle generation conversation
        context.insert(role="user", content=Prompts.GENERATION_SEED)                                        # INDX 1 (Ref. INDX constants in Context class in context_util.py)
        
        context.insert(role="assistant", content=Prompts.GENERATION_MOCK_SEED_RESPONSE)                     # INDX 2 (Ref. INDX constants in Context class in context_util.py)
        
        if summaries is not None:
            context.insert(role="user", content=(Prompts.GENERATION_SUMM_SEED).format(summaries))           # INDX 3 (Ref. INDX constants in Context class in context_util.py)
        else:
            context.insert(role="user", content="")                                                         # INDX 3 (Inserting a dummy empty message to maintain context history indices (which are important for resetting))
        
        if example_method is not None:
            context.insert(role="user", content=(Prompts.GENERATION_ONESHOT_SEED).format(example_method))   # INDX 4 (Ref. INDX constants in Context class in context_util.py)
        else:
            context.insert(role="user", content="")                                                         # INDX 4 (Inserting a dummy empty message to maintain context history indices (which are important for resetting))
        
        # Insert (after formatting) the prompt containing the setup method <SETUP>, test method prefix <TEST>, and focal method <FOCAL>
        context.insert(role="user", content=(Prompts.GENERATION_SEED_EXT).format(setup, test, focal))       # INDX 5 (Ref. INDX constants in Context class in context_util.py)
    else:
        context.insert(role="user", content=Prompts.GENERATION_NEXT)

def shuffle_organization():
    global openai, orgs, org_counter, current_org

    # Shuffle organizations to avoid Rate Limit Error
    if org_counter[current_org] == 2:
        org_counter[current_org] = 0
        current_org = (current_org + 1) % len(org_counter)

def interact_with_openai(temperature=1, context=None):
    if context is None: raise Exception("In interact with openai, context cannot be None")

    # global history, conversation_history, feedback_history, abstraction_history
    global openai, orgs, org_counter, current_org

    # Increase current organization's interaction counter for shuffle tracking
    openai.organization = orgs[current_org]
    org_counter[current_org] += 1

    # Get the model's response  
    while(True):
        try:
            # Function for interacting with the API                                                                                                                                                                   
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=context.history,
                temperature=temperature
            )

            result = ""
            for choice in response.choices:
                result += choice.message.content
            break
        
        except openai.error.InvalidRequestError as inv_err:
            if "maximum context length" in str(inv_err) and "reduce" in str(inv_err):
                print("\n!! Token Limit Exceeded !!\n")
                context.reset() # Resetting context in a type-specific way (check context_util.py for details)
        
        except openai.error.RateLimitError as rate_err:
            print("\n!! Rate Limit Exceeded !!\n")
            # shuffle_organization()
            time.sleep(60)

        except Exception as e:
            print("\n!! Interaction Exception !!\n" + str(e))
                
    shuffle_organization()

    return result

def num_tokens_from_string(query, model_name=MODEL_NAME):
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(model_name)
    num_tokens = len(encoding.encode(query))
    return num_tokens

def if_exceed_token_limit(query, model_name=MODEL_NAME):
    """Returns True if the number of tokens in a text string exceeds the maximum allowed."""
    if model_name not in MODEL_MAX_TOKEN:
        raise ValueError(f"Model name {model_name} not supported.")
    max_tokens = MODEL_MAX_TOKEN[model_name]
    num_tokens = num_tokens_from_string(query, model_name)
    return num_tokens > max_tokens

def cut_query(query, model_name):
    """Cuts a query to the maximum number of tokens allowed by the model."""
    encoding = tiktoken.encoding_for_model(model_name)
    max_tokens = MODEL_MAX_TOKEN[model_name]
    num_tokens = len(encoding.encode(query))
    if num_tokens > max_tokens:
        query = encoding.decode(encoding.encode(query)[:max_tokens])
    return query
