import re
import random

def adhoc_repair(java_gateway, project, gpt_oracle, feedback, file_path, test_name, test_code, focal_code):
    fuzzed_mutants = []

    fuzzed_mutants += fuzz(java_gateway, project, gpt_oracle, feedback, file_path, test_name, focal_code)

    return fuzzed_mutants

# Identifier heuristics
def fuzz(java_gateway, project, gpt_oracle, feedback, file_path, test_name, focal_code):
    fuzzed_mutants = set()
    holed_assertions = set()

    jGateway = java_gateway.entry_point
    jGateway.setFile(file_path)

    # Creating prefix holes for method calls that were not found in a test method during compilation
    checkIfMethodNotFound = re.search(r'\s*symbol:\s*method\s*([^\s\(]+)\(', feedback)
    methodNotFound = checkIfMethodNotFound.group(1) if checkIfMethodNotFound is not None else ""
    holed_assertions.add(jGateway.prefixHoleForMethodNotFound(gpt_oracle, methodNotFound))

    # Creating prefix holes if 'focal' keyword is present in the assertion
    holed_assertions.add(jGateway.prefixHoleForFocalKeyword(gpt_oracle))

    # Creating variable holes for variables that were not found in a test method during compilation
    checkIfVariableNotFound = re.search(r'\s*symbol:\s*variable\s*([^\s\(\n]+)', feedback)
    variableNotFound = checkIfVariableNotFound.group(1) if checkIfVariableNotFound is not None else ""
    holed_assertions.add(jGateway.variableHoleForVariableNotFound(gpt_oracle, variableNotFound))

    # Checking if we need fillers
    for holed_assertion in holed_assertions:
        if '<insert>' in holed_assertion:
            # We need fillers - get the possible fillers
            holeFillers = list(jGateway.findHoleFillers(test_name, focal_code))

            # Fill holes
            for holeFiller in holeFillers:
                fuzzed_mutants.add(holed_assertion.replace('<insert>', holeFiller))

            ### Deprecated since class names are now included from the IdFinderVisitor.java
            # # Check from the index, which class methodNotFound belongs to and use the class name as filler
            # if methodNotFound in project.index:
            #     for idx_item in project.index[methodNotFound]:
            #         fuzzed_mutants.append(holed_assertion.replace('<insert>', idx_item.class_name))

    random.shuffle(list(fuzzed_mutants))

    return fuzzed_mutants

# Assignment heuristics
def check_and_fix_lhs2rhs(java_gateway, gpt_oracle, test_code):
    lhs2rhs_dict = java_gateway.entry_point.lhs2rhs(test_code)

    gpt_oracle = gpt_oracle.replace(' ', '')
    for (k, v) in lhs2rhs_dict.items():
        k = k.replace(' ', '')
        v = v.replace(' ', '')
        gpt_oracle = gpt_oracle.replace(k, v)

    return gpt_oracle

    