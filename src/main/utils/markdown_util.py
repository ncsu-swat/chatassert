import re


def extract_code_block_from_markdown_text(md_text):
    # return re.findall(r'([\w\W]*?)|^ (.+)$',
    #                   md_text, re.MULTILINE)
    arr = re.findall(r'(Assert\..*)', md_text)
    if len(arr) == 0:
        return None # could not find anything
    if len(arr) > 1:
        return Exception("unexpected")
    return arr[0]




