import csv
from incoder.fim import infill, generate
import sys
import json

filename = "test-focal-oracle.tsv"

ASSERTION_MARK="<AssertPlaceHolder>"
NUM_QUERIES_EXAMPLE=10
OUTPUT_FILENAME="output.json"

def incoder_adapter(num_iteration, example):
    temp = 0.1 + (num_iteration - 1) * 0.05
    return generate(example, max_to_generate=30, temperature=temp)

def complete(test, focal, oracle):
    # completion
    prefix = test[:test.find(ASSERTION_MARK)]+" Assert."
    oras = set() # store in a set to discard duplicates
    for i in range(NUM_QUERIES_EXAMPLE):
        #TODO: should call other adapters
        out = incoder_adapter(i, prefix)
        # extracting assertion from string
        tmp = out[out.find("Assert."):]
        ora = tmp[:tmp.find(';')]
        ora = ora.replace(" ", "") # remove empty spaces to facilitate deduplication
        oras.add(ora)
    return oras

with open(filename) as file:
    tsv_file = csv.reader(file, delimiter="\t")
    dictionary = {}
    for line in tsv_file:
        id = line[0]
        test = line[1] #TODO: refer by column name
        focal = line[2] #TODO: refer by column name
        oracle = line[3] #TODO: refer by column name
        if id == 'Id': # skip line with column names
            continue
        oras = complete(test, focal, oracle)
        # update dictionary
        dictionary[id] = list(oras)

        break
    # dump output to json file
    with open(OUTPUT_FILENAME, "w") as outfile:
        json.dump(dictionary, outfile, indent=4)        
