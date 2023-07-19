class Prompts:
    # Name/Type-specific seed prompts (format the GENERATION_SEED and FEEDBACK_SEED from doall.py)
    SUMMARIZATION_SEED = "I will ask you to summarize a few Java method definitions and class definitions. Alright?"
    SUMMARIZATION_MOCK_SEED_RESPONSE = "Yes. I will explain the methods and classes that you give me. I will pay close attention to the steps you describe."
    
    GENERATION_SEED = "I will give you a setup method <SETUP>, test method prefix <TEST> and a focal method <FOCAL>. Can you generate only one JUnit assert statement that is the best fit for the given test prefix?"
    GENERATION_MOCK_SEED_RESPONSE = "Yes. I will consider the setup method <SETUP> if any, test method prefix <TEST>, and the focal method <FOCAL>. I will generate only one JUnit assert statement that is a best fit for the given test prefix. Can you please provide the source code of the placeholders <SETUP>, <TEST>, and <FOCAL>?"
    GENERATION_SUMM_SEED = "A summary of each statement in the test prefix <TEST> is as follows:\n\n{}"
    GENERATION_ONESHOT_SEED = "Here is an example test method for reference:\n```{}```"
    GENERATION_SEED_EXT = "The source code for the <SETUP>, <TEST>, and <FOCAL> tags are as follows:\n<SETUP>:\n```{}```,\n<TEST>:\n```{}```,\n<FOCAL>:\n```{}```. Now, can you generate only one JUnit assert statement that is the best fit for the given test prefix?"
    GENERATION_NEXT = "Can you generate another completely different assert statement?"
    
    FEEDBACK_SEED = GENERATION_SEED_EXT
    FEEDBACK_SEED_EXT = "The JUnit assert statement - `{}` results in a build failure. Can you modify this assert statement so that it compiles and executes correctly?"
    FEEDBACK_FIXED = "The fixed assertion is `{}`"

class Context:
    # Indices of specific types of messages in the history (used for resetting history)
    MSG_ALL_ROLE_INDX = 0
    
    # Indices of messages in the oracle GENeration conversation
    MSG_GEN_SEED_INDX = 1
    MSG_GEN_MOCK_SEED_RESPONSE_INDX = 2
    MSG_GEN_SUMMARY_INDX = 3
    MSG_GEN_ONESHOT_INDX = 4
    MSG_GEN_SEED_EXT_INDX = 5
    
    # Indices of messages in the SUMMarization conversation
    MSG_SUMM_SEED_INDX = 1
    MSG_SUMM_MOCK_SEED_RESPONSE_INDX = 2
    
    # Indices of messages in the FEEDback-driven repair conversation
    MSG_FEED_SEED_INDX = 1
    MSG_FEED_SEED_EXT_INDX = 2

    #---------------------------------------------------------------------------

    # Role-specific content
    SYSTEM_ROLE = "You are a programmer who is proficient in Java programming languge."

    # Name/type of context (to be later used for type specific context functionality like resetting, etc.)
    SUMMARIZATION_CONTEXT_NAME = "SUMMARIZATION"
    GENERATION_CONTEXT_NAME = "GENERATION"
    FEEDBACK_CONTEXT_NAME = "FEEDBACK"

    context_types = [SUMMARIZATION_CONTEXT_NAME, GENERATION_CONTEXT_NAME, FEEDBACK_CONTEXT_NAME]

    def __init__(self, _name=None):
        self.history = [{"role": "system", "content": Context.SYSTEM_ROLE}]

        if _name is None: raise Exception("Context name should not be None")
        if _name not in Context.context_types: raise Exception("Context name should be one of the context_types (check context_util.py)")
        self.name = _name
        self.token_count = 0

    def insert(self, role=None, content=None):
        if role is None: raise Exception("Inside the context, ROLE cannot be None")
        if content is None: raise Exception("Inside the context, CONTENT cannot be None")

        self.history.append({"role": role, "content": content})

    def remove_from(self, idx=0):
        del self.history[idx:]

    def remove_last(self):
        self.history.pop()

    def reset(self):
        if self.name == Context.SUMMARIZATION_CONTEXT_NAME:
            self.remove_from(Context.MSG_SUMM_MOCK_SEED_RESPONSE_INDX + 1)
        elif self.name == Context.GENERATION_CONTEXT_NAME:
            self.remove_from(Context.MSG_GEN_SEED_EXT_INDX + 1)
        elif self.name == Context.FEEDBACK_CONTEXT_NAME:
            self.remove_from(Context.MSG_FEED_SEED_EXT_INDX + 1)

    def show(self):
        print("\nSHOWING HISTORY OF {}:\n".format(self.name))
        for (idx, msg) in enumerate(self.history):
            print("P{}. {}\n\n".format(idx, msg))

def test():
    summ_context = Context(_name=SUMMARIZATION_CONTEXT)
    gen_context = Context(_name=GENERATION_CONTEXT)
    feed_context = Context(_name=FEEDBACK_CONTEXT)

    summ_context.insert(role="user", content=Prompts.SUMMARIZATION_SEED)
    summ_context.show()

    gen_context.insert(role="user", content=Prompts.GENERATION_SEED)
    gen_context.show()
    gen_context.insert(role="user", content="abc")
    gen_context.insert(role="user", content="def")
    gen_context.insert(role="user", content="ghi")
    gen_context.show()
    gen_context.reset()
    gen_context.show()

    feed_context.insert(role="user", content=Prompts.FEEDBACK_SEED)
    feed_context.show()



