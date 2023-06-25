import re

assertions_nargs = {
    'assertEquals': 2,
    'assertNotEquals': 2,
    'assertArrayEquals': 2,
    'assertSame': 2,
    'assertTrue': 1,
    'assertFalse': 1,
    'assertNull': 1,
    'assertNotNull': 1
}

def extract_assertion(text):
    print('\nRESPONSE: \n{}\n'.format(text))

    assertStatement = re.search(r"assert[\S]+[\s]*\([\s\S]+\);|assert[\S]+[\s]*\([\s\S]+\)[\r\n]*|assert[\S]+[\s]*\([\s\S]+\)[`]*", text)

    if assertStatement is None:
        return None
    return clean_args(assertStatement.group(0))

def extract_assertions(text):
    print('\nRESPONSE: \n{}\n'.format(text))

    assertStatements = text.split('\n')

    asserts = []
    for line in assertStatements:
        assertStatement = re.search(r"assert[\S]+[\s]*\([\s\S]+\);|assert[\S]+[\s]*\([\s\S]+\)[\r\n]*|assert[\S]+[\s]*\([\s\S]+\)[`]*", line)
        if assertStatement is not None: asserts.append(clean_args(abstract_string_literals(assertStatement.group(0))))

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

# Removing assertion error message and delta for assertEquals
def clean_args(assertStatement):
    # print("\nCLEANING: \n{}\n".format(assertStatement))

    assertType = get_assert_type(assertStatement)
    args = get_assert_args(assertStatement)

    if assertType in assertions_nargs.keys():
        if len(args) == assertions_nargs[assertType]+1:
            # Check if first arg is string
            if "\"" in args[0]:
                # First arg is a string
                args.pop(0)
            # Else last arg is delta
            else:
                # First arg is not a string, so last arg must be delta
                args.pop(-1)
        # Else args must contain both string message and delta
        elif len(args) == assertions_nargs[assertType]+2:
            args.pop(0)
            args.pop(-1)

    finalAssertStatement = assertType + '('
    for (i, arg) in enumerate(args):
        finalAssertStatement += arg
        if i < len(args)-1:
            finalAssertStatement += ','

    if len(finalAssertStatement.split('\n')) > 1:
        finalAssertStatement = finalAssertStatement.split('\n')[0]
    finalAssertStatement += ');'

    return 'org.junit.Assert.' + finalAssertStatement.replace('( ', '(')

# Check if commutating args of assertEquals gives exact match
def check_commutative_equal(gpt_oracle, oracle_code):
    gpt_oracle = gpt_oracle.replace("org.junit.Assert.", "").replace("Assert.", "").replace(" ", "").strip()
    oracle_code = oracle_code.replace("org.junit.Assert.", "").replace("Assert.", "").replace(" ", "").strip()

    assertType = get_assert_type(gpt_oracle)
    args = get_assert_args(gpt_oracle)

    if assertType == "assertEquals":
        if len(args) == 2:
            finalAssertStatement = assertType + "(" + args[1] + "," + args[0] + ");"
            if finalAssertStatement == oracle_code: return finalAssertStatement

    return gpt_oracle
