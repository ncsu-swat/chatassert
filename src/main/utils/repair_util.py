import re
import random

def adhoc_repair(java_gateway, project, gpt_oracle, feedback, file_path, test_name):
    fuzzed_mutants = []

    fuzzed_mutants += check_and_fix_method_not_found(java_gateway, project, gpt_oracle, feedback, file_path, test_name)

    return fuzzed_mutants

def check_and_fix_method_not_found(java_gateway, project, gpt_oracle, feedback, file_path, test_name):
    fuzzed_mutants = []

    jGateway = java_gateway.entry_point
    jGateway.setFile(file_path)

    # Creating prefix holes for method calls that were not found in a test method during compilation
    checkIfMethodNotFound = re.search(r'\s*symbol:\s*method\s*([^\s\(]+)\(', feedback)
    methodNotFound = checkIfMethodNotFound.group(1) if checkIfMethodNotFound is not None else ""
    holedAssertion = jGateway.prefixHoleForMethodNotFound(gpt_oracle, methodNotFound)

    # Checking if we need fillers
    if '<insert>' in holedAssertion:
        # We need fillers - get the possible fillers
        holeFillers = list(jGateway.findHoleFillers(test_name))

        # Fill holes
        for holeFiller in holeFillers:
            fuzzed_mutants.append(holedAssertion.replace('<insert>', holeFiller))

        # Check from the index, which class methodNotFound belongs to and use the class name as filler
        if methodNotFound in project.index:
            for idx_item in project.index[methodNotFound]:
                fuzzed_mutants.append(holedAssertion.replace('<insert>', idx_item.class_name))

        random.shuffle(fuzzed_mutants)

    return fuzzed_mutants

    