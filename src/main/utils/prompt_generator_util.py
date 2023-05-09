import os
import re
from path_config import PRO_DIR

def get_vulnerable_function_lines(language, vulnerable_file_contents, start_line_index):
    if language == 'python':
        comment_char = '#'
        detect_function_regex = '^\s*def (.*?)\('
    elif language == 'c':
        comment_char = '//'
        detect_function_regex = """^[a-zA-Z_][a-zA-Z_0-9*\(\)\[\]]*\s*[a-zA-Z_0-9*\(\)\[\]]*\s*[a-zA-Z_0-9*\(\)\[\]]*\s*[a-zA-Z_0-9*\(\)\[\]]+\s+[a-zA-Z_0-9]+\s*\([a-zA-Z0-9*_\s\[\],]*\)(?:\s*{|\s\/\*[\sA-Za-z0-9_.,*#\[\]\\\/;'\"-]+\*\/\s*{)"""
    else:
        raise Exception('unsupported language ' + language)

    #################THIS METHOD WORKS FOR FUNCTION LEVEL#####################

    #
    vulnerable_file_contents_str = ''.join(vulnerable_file_contents)
    vulnerable_file_contents_str = vulnerable_file_contents_str.replace('\r', '')
    #find the end of the function openers using the detect_function_regex
    function_def_boundaries = []
    for match in re.finditer(detect_function_regex, vulnerable_file_contents_str, re.MULTILINE):
        function_def_boundaries.append([match.start(), match.end()])

    #print(function_def_boundaries)

    #we have the end of the function, crop the lines at that point
    ##TODO: COME BACK TO THIS

    #for each function index, determine what line it finishes on by counting the number of newlines before it
    function_def_num_newlines = []
    for function_def_boundary in function_def_boundaries:
        function_def_num_newlines.append(
            [
                vulnerable_file_contents_str.count('\n', 0, function_def_boundary[0]), 
                vulnerable_file_contents_str.count('\n', 0, function_def_boundary[1])
            ]
        )   
    #print(function_def_num_newlines)
    #print(start_line_index)
    closest_newline_index = 0
    closest_newline_value = 0
    for i in range(len(function_def_num_newlines)):
        if function_def_num_newlines[i][1] > start_line_index:
            break
        if function_def_num_newlines[i][1] > closest_newline_value:
            closest_newline_value = function_def_num_newlines[i][1]
            closest_newline_index = i

    vulnerable_function_start_line_num = function_def_num_newlines[closest_newline_index][0]
    vulnerable_function_end_line_num = function_def_num_newlines[closest_newline_index][1]

    print("function starts on line " + str(vulnerable_function_start_line_num))
    print("function ends on line " + str(vulnerable_function_end_line_num))

    
    ##OLD METHOD

    #get the number of whitespace chars in the first line of the function index
    vulnerable_function_line = vulnerable_file_contents[vulnerable_function_start_line_num]
    vulnerable_function_line_stripped = vulnerable_function_line.lstrip()
    vulnerable_function_whitespace_count = len(vulnerable_function_line) - len(vulnerable_function_line_stripped)

    print("Vulnerable function no. of whitespace chars:", vulnerable_function_whitespace_count)

    #if language == 'python':
    #starting at the end function line number, go forwards until you find a non-comment line that has the same indentation level
    vulnerable_function_end_index = 0
    for i in range(vulnerable_function_end_line_num+1, len(vulnerable_file_contents)):
        line = vulnerable_file_contents[i]
        line_stripped = line.lstrip()
        if len(line_stripped.rstrip()) == 0:
            continue
        if line_stripped[0:len(comment_char)] == comment_char:
            continue

        if len(line) - len(line_stripped) == vulnerable_function_whitespace_count:
            break
        vulnerable_function_end_index = i + 1
        
    print("Vulnerable function end index:", vulnerable_function_end_index)
    print("Vulnerable function end line:", vulnerable_file_contents[vulnerable_function_end_index])

    if language == 'c' and vulnerable_file_contents[vulnerable_function_end_index].strip() == '}':
        vulnerable_function_end_index += 1 #we'll include the closing brace in the vulnerable function for C

    #make the prompt lines from 0 to vulnerable_function_index+1 (line after the function)
    vulnerable_file_prepend_lines = vulnerable_file_contents[0:vulnerable_function_start_line_num]

    #IMPORTANT: we assume that the vulnerable function has a newline between function start "{" or ":" and the body
    vulnerable_file_function_def_lines = vulnerable_file_contents[vulnerable_function_start_line_num:vulnerable_function_end_line_num+1]

    #make the vulnerable lines from prompt_line_end_index to start_line_index
    vulnerable_file_function_pre_start_lines = vulnerable_file_contents[vulnerable_function_end_line_num+1:start_line_index]

    #start line onwards
    vulnerable_file_function_start_lines_to_end = vulnerable_file_contents[start_line_index:vulnerable_function_end_index]

    #make the append lines from start_line_index to the end
    vulnerable_file_append_lines = vulnerable_file_contents[vulnerable_function_end_index:]

    #print("The function began on line", vulnerable_function_index)
    return (vulnerable_file_prepend_lines, vulnerable_file_function_def_lines, vulnerable_file_function_pre_start_lines, vulnerable_file_function_start_lines_to_end, vulnerable_file_append_lines)


def get_vulnerable_function_attributes(config, full_patch_filename):
    if config['language'] == 'python':
        file_extension = '.py'
        comment_char = '#'
    elif config['language'] == 'c':
        file_extension = '.c'
        comment_char = '//'
        assymetric_comment_char_start = '/*'
        assymetric_comment_char_end = '*/'
    else:
        raise Exception('unsupported language ' + config['language'])
    #for the iterative fix, we need to
    #1. load the vulnerable file
    #2. isolate and comment out the vulnerable code, and seperate into prompt, vulnerable, append
    #3. derive the language prompt and append it to the prompt
    #4. create the scenario dir and add the necessary files (scenario_prompt.py, scenario_append.py, scenario.json)
    
    possible_prompts = []
    
    if config['asan_scenario_buginfo'] is not None:
        #convert the asan_scenario_buginfo to a vulnerability
       
        # we will make N scenarios.
        # the first scenario is the "oracle" scenario and is devised from the original patch info
        # the other N-1 scenarios are derived from the ASAN error stack trace


        

        # let us first make the oracle scenario

        #repo_path = iterative_fix['asan_scenario_buginfo']["repo_path"]
        asan_buginfo = config['asan_scenario_buginfo']
        asan_patchinfo = asan_buginfo["real_patchinfo"]
        asan_stacktrace = asan_buginfo["stacktrace"]
        
        for patch in asan_patchinfo:
            #we will only do the first patch
            patch_filename = patch["filename"]
            patch_lines = patch["edit_lines"]
            break


        #full_patch_filename = os.path.join(repo_path, patch_filename)
        #full_patch_filename = os.path.join(iterative_fix['original_dir'], patch_filename)

        vulnerable_file_contents = []
        with open(full_patch_filename, 'r') as f:
            vulnerable_file_contents = f.readlines()

        #get every line from the file that begins with #define
        defines = []
        for line in vulnerable_file_contents:
            if line.startswith('#define'):
                defines.append(line)

        largest_lineno = max(patch_lines) - 1
        smallest_lineno = min(patch_lines) - 1

        #isolate the lines between the smallest and largest line numbers
        
        first_bad_line = vulnerable_file_contents[smallest_lineno]
        first_bad_line_whitespace_count = len(first_bad_line) - len(first_bad_line.lstrip())    
        whitespace_chars = first_bad_line[:first_bad_line_whitespace_count]
        
        #vulnerable_file_prompt_lines = vulnerable_file_contents[0:index_variable_defined_line]
        vulnerable_file_vulnerable_lines = vulnerable_file_contents[smallest_lineno:largest_lineno+1+2] #get the next 2 lines as well to aid in "joining" the generated response to the file
        #vulnerable_file_append_lines = vulnerable_file_contents[error_line_number+1:]
        vulnerable_file_append_lines = []

        #print(vulnerable_file_vulnerable_lines)

        #get the first word of the vulnerable lines
        first_vulnerable_word = ""
        for i in range(len(vulnerable_file_vulnerable_lines)):
            split = vulnerable_file_vulnerable_lines[i].strip().split()
            if len(split) > 0:
                first_vulnerable_word = split[0]
                break

        if first_vulnerable_word == '#' or first_vulnerable_word == '//' or first_vulnerable_word == '/*':
            first_vulnerable_word = ""

        #get the function lines
        (pre_function_lines, function_def_lines, pre_start_lines, lines_to_end, post_function_lines) = get_vulnerable_function_lines(config['language'], vulnerable_file_contents, smallest_lineno)

        # print("###########pre_function_lines###########")
        # print(pre_function_lines)

        # print("###########function_def_lines###########")
        # print(function_def_lines)

        # print("###########pre_start_lines###########")
        # print(pre_start_lines)

        # print("###########lines_to_end###########")
        # print(lines_to_end)

        # print("###########post_function_lines###########")
        # print(post_function_lines)


        #get the function definition
        prompt_function_ends_at_line_index = len(pre_function_lines) + len(function_def_lines)
        vulnerable_file_prompt_lines = defines + ["\n"] + function_def_lines + pre_start_lines #vulnerable_file_contents[prompt_function_ends_at_line_index:index_variable_defined_line]

        bugname = asan_buginfo["error"].replace('AddressSanitizer: ', '').replace('-', ' ')

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nofunction',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': [],
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': "",
            'language_prompt_foot': "",
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })

        language_prompt_head = \
            whitespace_chars + comment_char + "BUG: " + bugname
        language_prompt_head += "\n"
        language_prompt_foot = \
            whitespace_chars + comment_char + "FIXED:\n" + \
            whitespace_chars + first_vulnerable_word

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nomessage',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': vulnerable_file_vulnerable_lines,
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': language_prompt_foot,
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })

        language_prompt_head = \
            whitespace_chars + "/* BUG: " + bugname
        language_prompt_head += "\n"
        language_prompt_foot = \
            whitespace_chars + " * " + "FIXED:\n" + \
            whitespace_chars + " */\n" + \
            whitespace_chars + first_vulnerable_word

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nomessage-assymetric',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': vulnerable_file_vulnerable_lines,
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': language_prompt_foot,
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': True
        })

        language_prompt_head = \
            whitespace_chars + "/* BUG: " + bugname
        language_prompt_head += "\n"
        language_prompt_foot = \
            whitespace_chars + " * " + "FIXED:\n" + \
            whitespace_chars + " */\n"

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nomessage-notoken-assymetric',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': vulnerable_file_vulnerable_lines,
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': language_prompt_foot,
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': True
        })

        language_prompt_head = whitespace_chars + "/* bugfix: fixed " + bugname + " */\n" 

        possible_prompts.append({
            'name': 'asan-line2line-oracle-simple-prompt-1',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': [],
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': "",
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })

        language_prompt_head = whitespace_chars + "/* fixed " + bugname + " bug */\n" 

        possible_prompts.append({
            'name': 'asan-line2line-oracle-simple-prompt-2',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': [],
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': "",
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })


        #identify the function that contains the error
        #(vulnerable_file_prompt_lines, vulnerable_file_vulnerable_lines, vulnerable_file_append_lines) = get_vulnerable_function_lines(iterative_fix['language'], vulnerable_file_contents, start_line_index)


    
    dirs_newly_made = []
    
    for prompt in possible_prompts:

        prompt_name = prompt['name']

        vulnerable_file_prompt_lines = prompt['vulnerable_file_prompt_lines']
        vulnerable_file_vulnerable_lines = prompt['vulnerable_file_vulnerable_lines']
        vulnerable_file_append_lines = prompt['vulnerable_file_append_lines']
        language_prompt_head = prompt['language_prompt_head']
        language_prompt_foot = prompt['language_prompt_foot']
        whitespace_chars = prompt['whitespace_chars']
        scenario_derived_from_filename = prompt['derived_from_filename']
        
        # #make the scenario dirs
        # scenario_dirname = prompt['filename']+"."+prompt_name+config.ITERATIVE_FIX_SCENARIO_DIRNAME_SUFFIX
        # scenario_dir = os.path.join(iterative_fix['iterative_dir'], scenario_dirname)
        # if not os.path.exists(scenario_dir):
        #     os.makedirs(scenario_dir)
        # dirs_newly_made.append(scenario_dirname)

        #stop_word = ""
        # #get the first word from the append lines to act as a stop word
        # for line in vulnerable_file_append_lines:
        #     line_stripped = line.strip()
        #     if len(line_stripped) < 2:
        #         continue
        #     if line_stripped[0] == '#':
        #         line_stripped = line_stripped[1:]
        #     line_stripped_toks = line_stripped.split(' ')
        #     stop_word = line_stripped_toks[0].strip()
        #     if len(stop_word) > 0:
        #         break

        scenario_dir = os.path.join(PRO_DIR,"prompt", prompt['filename']+"."+prompt_name)
        if not os.path.exists(scenario_dir):
            os.makedirs(scenario_dir)
        #write the scenario code files
        scenario_prompt_filename = prompt['filename']+".prompt"+file_extension
        scenario_prompt_filename_full = os.path.join(scenario_dir, scenario_prompt_filename)
        scenario_append_filename = prompt['filename']+".append"+file_extension
        scenario_append_filename_full = os.path.join(scenario_dir, scenario_append_filename)


        #scenario_json_filename_full = os.path.join(scenario_dir, config.SCENARIO_CONFIG_FILENAME)

        #make the scenario prompt
        with open(scenario_prompt_filename_full, 'w') as f:
            f.writelines(vulnerable_file_prompt_lines)
            f.write(language_prompt_head)
            for line in vulnerable_file_vulnerable_lines:

                # TODO: add option to reproduce only the comments??

                if prompt["assymetrical_comments"]:
                    f.write(whitespace_chars + " * " + line.replace('/*', '//').replace('*/', ''))
                else:
                    f.write(whitespace_chars + comment_char + " " + line)
            f.write(language_prompt_foot)
        
        #make the scenario append
        with open(scenario_append_filename_full, 'w') as f:
            f.writelines(vulnerable_file_append_lines)
        