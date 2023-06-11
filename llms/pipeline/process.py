import csv
from incoder.fim import generate_incoder, dispose_mem_incoder, initialize_incoder
from starcoder.completion import generate_starcoder, dispose_mem_starcoder, initialize_starcoder
import sys
import json
import re

filename = "test-focal-oracle.tsv"

ASSERTION_MARK = "<AssertPlaceHolder>"
NUM_QUERIES_EXAMPLE = 1
OUTPUT_FILENAME = "output.json"
INFILL_MARK = "<insert>"

DEBUG = True

def extract_oracles_from_output(out):
    # sometimes it returns multiple ones...
    return re.findall("Assert[^;]*;", out)

def incoder_adapter(num_iteration, example):
    if DEBUG:
        print("I", end="")
    # TODO: check if this is reasonable. The default temp value for
    # the example in the incoder repo was 0.2 -Marcelo
    temp = 0.1 + (num_iteration - 1) * 0.05
    return generate_incoder(example, max_to_generate=30, temperature=temp)

def starcoder_adapter(num_iteration, example):
    if DEBUG:
        print("S", end="")
    # TODO: check if this is reasonable. The default temp value for
    # the example in the starcoder repo was 1.5 -Marcelo
    temp = 1.4 + (num_iteration - 1) * 0.05    
    return generate_starcoder(example, temperature=temp)

def complete(llm, test, focal, oracle):
    # completion
    prefix = test[:test.find(ASSERTION_MARK)]+" Assert."
    oras = set() # store in a set to discard duplicates
    for i in range(NUM_QUERIES_EXAMPLE):
        if llm == "incoder":
            out = incoder_adapter(i, prefix)
            for ora in extract_oracles_from_output(out):
                oras.add(ora)            
        elif llm == "starcoder":
            outs = starcoder_adapter(i, prefix)
            for out in outs: # starcode can produce many string outputs
                for ora in extract_oracles_from_output(out):
                    oras.add(ora)                        
        else:
            raise Exception("not implemented")
        # extracting assertion from string

    return oras


dictionary = {}
llms = ["starcoder", "incoder"]
# need to do one llm at a time (to keep model in memory)
for llm in llms:

    # setup: we don't want to load model when file is accessed
    if llm == "incoder":
        initialize_incoder()
    elif llm == "starcoder":
        initialize_starcoder()
    else:
        raise Exception("not implemented")        

    with open(filename) as file:    
        tsv_file = csv.reader(file, delimiter="\t")
        for line in tsv_file:
            id = line[0]
            test = line[1] #TODO: refer by column name
            focal = line[2] #TODO: refer by column name
            oracle = line[3] #TODO: refer by column name
            if id == 'Id': # skip line with column names
                continue
            if dictionary.get(id) is None:
                dictionary[id] = {} # initialize dictionary
            print(id)
            oras = complete(llm, test, focal, oracle)
            # update dictionary
            dictionary[id][llm] = list(oras)

    print("releasing mem")
    # teardown: releasing memory!
    if llm == "incoder":
        dispose_mem_incoder()
    elif llm == "starcoder":
        dispose_mem_starcoder()
    else:
        raise Exception("not implemented")
    print("done releasing mem")
        
# dump output to json file
with open(OUTPUT_FILENAME, "w") as outfile:
    json.dump(dictionary, outfile, indent=4)        
