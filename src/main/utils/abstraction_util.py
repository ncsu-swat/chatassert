

def fetch_abstraction_targets(gateway, project, test_code):
    abstraction_targets = dict()

    methods_classes_map = gateway.entry_point.findForAbstraction(test_code)

    for (k, v) in methods_classes_map.items():
        

def generate_abstraction_prompt(abstraction_target):
    return "What does the following {} do? \n ```{}```".format(abstraction_target['method_or_class'], abstraction_target['code'])