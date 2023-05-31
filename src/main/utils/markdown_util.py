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
    assertStatement = re.search(r"assert[\S]+[\s]*\([\s\S]+\)[\s]*[;\n\{]", text)

    if assertStatement is None:
        return None
    return clean_args(assertStatement.group(0))

# Removing assertion error message and delta for assertEquals
def clean_args(assertStatement):
    separator_pos = []
    in_string = False

    assertType = re.search(r"assert[^\(]+[\s]*\(", assertStatement).group(0)
    if '(' in assertType: assertType = assertType.replace('(', '')

    assertStatement = re.sub(r"assert[^\(]+[\s]*\(", "", assertStatement)
    assertStatement = re.sub(r"\);", "", assertStatement)

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

    number_of_args = len(separator_pos)-1
    if assertType in assertions_nargs.keys():
        if number_of_args == assertions_nargs[assertType]+1:
            # Check if first arg is string
            if "\"" in assertStatement[separator_pos[0]:separator_pos[1]]:
                # First arg is a string
                separator_pos.pop(0)
            # Else last arg is delta
            else:
                # First arg is not a string, so last arg must be delta
                separator_pos.pop(len(separator_pos)-1)
        # Else args must contain both string message and delta
        elif number_of_args == assertions_nargs[assertType]+2:
            separator_pos.pop(0)
            separator_pos.pop(len(separator_pos)-1)

    finalAssertStatement = assertType + '('
    for i in range(len(separator_pos)):
        if i+1 < len(separator_pos):
            finalAssertStatement += assertStatement[separator_pos[i]:separator_pos[i+1]-1]
        if i+2 < len(separator_pos):
            finalAssertStatement += ','
    finalAssertStatement += ');'

    return 'org.junit.Assert.' + finalAssertStatement.replace('( ', '(')