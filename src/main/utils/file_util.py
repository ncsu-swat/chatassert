from distutils.dir_util import copy_tree
import os
import shutil

def copy_folder(src, dst):
    copy_tree(src, dst)


def delete_folder(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)


def extract_content_within_line_range(filepath,startline, endline):
    """
    Extract the context within the line range.
    """
    context = ""
    with open(filepath, "r") as f:
        lines = f.readlines()
        for i in range(startline-1, endline):
            context += lines[i]
    return context

def read_file_(filepath):
    """
    Read the content of the file.
    """
    with open(filepath, "r") as f:
        content = f.read()
    return content


# TODO: this is very inefficient. refactor/optimize when needed. -Marcelo
def read_file(filepath, lo=0, hi=0):
    if lo == 0 and hi == 0:
        return read_file_(filepath=filepath)
    with open(filepath, 'r', encoding='UTF-8') as _file:
        res = []
        for (idx, line) in enumerate(_file):
            if idx+1 >= lo and idx+1 <= hi:
                res.append(line)
        return res

