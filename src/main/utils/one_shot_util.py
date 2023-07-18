import os
os.environ["TOKENIZERS_PARALLELISM"] = "false" # To avoid deadlocks due to forks/parallelism

import numpy as np
from numpy import dot
from numpy.linalg import norm

from transformers import AutoTokenizer, AutoModel
import torch

from utils.file_util import read_file

from py4j.java_gateway import JavaGateway

import json

tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
model = AutoModel.from_pretrained("microsoft/graphcodebert-base")

def get_embeddings(code):
    global tokenizer, model

    code_tokens = tokenizer.tokenize(code)
    tokens = [tokenizer.cls_token] + code_tokens + [tokenizer.sep_token]
    tokens_ids = [tokenizer.convert_tokens_to_ids(tokens)]

    embeddings = model(torch.tensor(tokens_ids))[0][0][0].detach().numpy()

    return embeddings

def find_similar(target_class, target_name, target_code):
    # Similarity measure
    max_sim = -np.inf
    max_sim_method = None

    # Extract target embeddings
    target_embeddings = get_embeddings(target_code)

    # Retrieve reference test methods from the same test file
    ref_tests = []
    with open("../sample_all.json", "r") as all:
        all_json = json.load(all)
        for project in all_json['projects']:
            for _class in project['allTests']:
                if _class['className'] == target_class:
                    for _test in _class['classTests']:
                        if _test['testName'] != target_name:
                            ref_tests.append(_test['testMethod'])

    # Extract reference embeddings and measure distance from target embeddings
    for test_method in ref_tests:
        ref_embeddings = get_embeddings(test_method)
        cos_sim = dot(target_embeddings, ref_embeddings)/(norm(target_embeddings)*norm(ref_embeddings))

        if cos_sim > max_sim:
            max_sim = cos_sim
            max_sim_method = test_method

    return max_sim_method

def test():
    file_path = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors/src/test/java/ncsusoftware/AnotherTest.java"
    test_code = '\n'.join(read_file(file_path, lo=53, hi=83))
    src_path = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/astvisitors/src"

    find_similar('ActivityDefinitionTest', 'testAbstraction', test_code)