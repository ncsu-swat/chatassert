import os
import json
import re

def check_compilation_failures():
    total, compilation_err, symbol_err, within_test_symbol_err = 0, 0, 0, 0

    classNames = []
    with open('../../teco_eval/teco/input/test_mkey.jsonl', 'r') as testKeyFile:
        for line in testKeyFile:
            classNames.append(json.loads(line).split('/')[-1].split('#')[0].lower())

    for f in os.scandir('../execution_log'):
        if f.is_file():
            with open(f.path, 'r') as logFile:
                fileContent = logFile.read().lower()

                if 'compilation failure' in fileContent:
                    compilation_err += 1
                    if 'cannot find symbol' in fileContent:
                        symbol_err += 1

                        pattern = re.compile(r'location:\s*class\s*(.*)\n', re.IGNORECASE)
                        match = pattern.findall(fileContent)

                        if len(match) > 0:
                            for m in match:
                                if m.split('.')[-1] in classNames:
                                    within_test_symbol_err += 1
                                    break
        total += 1
    
    print(compilation_err)
    print(symbol_err)
    print(within_test_symbol_err)
    print(total)

check_compilation_failures()