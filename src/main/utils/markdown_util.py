import re

def extract_assertion(text):
    # return re.findall(r'([\w\W]*?)|^ (.+)$', md_text, re.MULTILINE)
    # arr = re.findall(r'(Assert\..*)', md_text)

    # arr = re.findall(r'(*assert.*\(.*\).*)', md_text)
    # if len(arr) == 0:
    #     return None

    startIdx, endIdx = -1, -1
    for idx, letter in enumerate(text):
        if letter == 'a' and (idx+6)<len(text) and text[idx:idx+6]=='assert':
            startIdx = idx
        if letter == ';':
            endIdx = idx
        if startIdx > -1 and endIdx > -1:
            return 'org.junit.Assert.' + text[startIdx:endIdx+1]
    
    return None




