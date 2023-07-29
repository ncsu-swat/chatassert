import os
import shutil
from shutil import copyfile, copytree, rmtree
import time

from traceback import print_exc

def _copyfileobj_patched(fsrc, fdst, length=16*1024*1024):
    """Patches shutil method to hugely improve copy speed"""
    """Ref: https://stackoverflow.com/questions/21799210/python-copy-larger-file-too-slow"""
    while 1:
        buf = fsrc.read(length)
        if not buf:
            break
        fdst.write(buf)
shutil.copyfileobj = _copyfileobj_patched

def copy_file(src, dest):
    with open(dest, 'w+'):
        copyfile(src, dest)

def delete_file(file):
    try:
        os.remove(file)
    except FileNotFoundError as e:
        print('Delete file: {} - does not exist'.format(str(file)))

def copy_folder(src, dst):
    try:
        copytree(src, dst, symlinks=False, ignore_dangling_symlinks=True, dirs_exist_ok=True)
        time.sleep(1)
    except:
        print_exc()
        print("Copy error in file_util")

def delete_folder(folder):
    # print(folder)
    rmtree(folder, ignore_errors=True)


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
    try:
        with open(filepath, "r") as f:
            content = f.read()
        return content
    except Exception as e:
        print("Read file exception")
        return ""


# TODO: this is very inefficient. refactor/optimize when needed. -Marcelo
def read_file(filepath, lo=0, hi=0):
    if lo == 0 and hi == 0:
        return read_file_(filepath=filepath)
    try:
        with open(filepath, 'r', encoding='UTF-8') as _file:
            res = []
            for (idx, line) in enumerate(_file):
                if idx+1 >= lo and idx+1 <= hi:
                    res.append(line)
            return res
    except Exception as e:
        print("Read file exception")
        return ""

