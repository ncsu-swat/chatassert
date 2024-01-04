import re
from py4j.java_gateway import JavaGateway

def extract_assertion(text):
    text = text.replace(' ', '')
    common_asserts = [ 'assertEquals\(', 'assertNotEquals\(', 'assertSame\(', 'assertNotSame\(', 'assertArrayEquals\(', 'assertTrue\(', 'assertFalse\(', 'assertNull\(', 'assertNotNull\(' ]

    assertion_stop = -1
    for common_assert in common_asserts:
        for _match in re.finditer(common_assert, text):
            assertion_start = _match.start(0)
            assertion_stop = -1
            parenthesis_counter = 0
            i = _match.end(0)-1
            while i+1 < len(text):
                if text[i] == '(':
                    parenthesis_counter += 1
                elif text[i] == ')':
                    parenthesis_counter -= 1
                
                if parenthesis_counter == 0 and i > assertion_start-1:
                    if text[i+1] == ';':
                        assertion_stop = i+2
                        break                
                i += 1
    if assertion_stop != -1:
        return clean_args(text[assertion_start:assertion_stop])
    
    return None

def extract_assertions(text):
    # print('\nRESPONSE: \n{}\n'.format(text))

    assertStatements = text.split('\n')

    asserts = []
    for line in assertStatements:
        assertStatement = extract_assertion(line)
        asserts.append(assertStatement)

    return asserts

def get_assert_type(assertStatement):
    assertType = re.search(r"assert[^\(]+[\s]*\(", assertStatement)
    if assertType is None: return assertStatement
    
    assertType = assertType.group(0)
    if '(' in assertType: assertType = assertType.replace('(', '')
    
    return assertType

def get_assert_args(assertStatement):
    assertType = re.search(r"assert[^\(]+[\s]*\(", assertStatement)
    if assertType is None: return assertStatement
    
    assertType = assertType.group(0)
    if '(' in assertType: assertType = assertType.replace('(', '')

    assertStatement = re.sub(r"assert[^\(]+[\s]*\(", "", assertStatement)
    assertStatement = re.sub(r"\);", "", assertStatement)
    
    separator_pos = []
    in_string = False

    separator_pos.append(0)
    nparen = 0  # Making sure that we are not including commas within method invocations
    for (idx, tok) in enumerate(assertStatement):
        if tok == "\"":
            in_string = not in_string
        if tok == "(":
            nparen += 1
        if tok == ")":
            nparen -= 1

        if not in_string and nparen == 0 and (tok == ','):
            separator_pos.append(idx+1)
    separator_pos.append(len(assertStatement)+1)
    
    args = []
    for i in range(len(separator_pos)):
        if i+1 < len(separator_pos):
            args.append(assertStatement[separator_pos[i]:separator_pos[i+1]-1].strip())

    return args

# Removing assertion error message and delta for assertEquals, assertNotEquals, assertArrayEquals and cleaning "` is a plausible ..." noise in the ChatGPT response
def clean_args(gpt_oracle):
    # print("\nCLEANING: \n{}\n".format(assertStatement))
    
    gpt_oracle = gpt_oracle.replace("org.junit.Assert.", "")
    gpt_oracle = gpt_oracle.replace("Assert.", "")
    gpt_oracle = gpt_oracle.replace(" ", "").strip()

    # Cleaning cases where ChatGPT often produces assertions that look like the following: assertEquals(1, foo.bar()` is a plausible foo.bar());
    tempAssert = gpt_oracle
    if "`isaplausible" in tempAssert:
        idx = tempAssert.find('`isaplausible')
        gpt_oracle = tempAssert[0:idx] + ');'

    # Cleaning assertion error message and delta for assertionEquals of double variables
    gateway = JavaGateway()
    gpt_oracle = gateway.entry_point.removeAssertionMessage(gpt_oracle)

    if '???' in gpt_oracle: return None

    return 'org.junit.Assert.' + gpt_oracle

# Check if commutating args of assertEquals gives exact match
def check_commutative_equal(gpt_oracle, oracle_code):
    gpt_oracle = gpt_oracle.replace("org.junit.Assert.", "")
    gpt_oracle = gpt_oracle.replace("Assert.", "")
    gpt_oracle = gpt_oracle.replace(" ", "").strip()

    oracle_code = oracle_code.replace("org.junit.Assert.", "")
    oracle_code = oracle_code.replace("Assert.", "")
    oracle_code = oracle_code.replace(" ", "").strip()

    if 'Equals' in gpt_oracle:
        gateway = JavaGateway()
        commutated_assertion = gateway.entry_point.commutateAssertEquals(gpt_oracle)
        commutated_assertion = commutated_assertion.replace(' ', '')

        if commutated_assertion == oracle_code:
            return commutated_assertion

    return gpt_oracle
    