from utils.git_util import reset_repo, clone_repo
from utils.cmd_util import execute_cmd_with_output
from utils.file_util import delete_folder

import os
from path_config import TMP_DIR
import re
import xml.etree.ElementTree as ET

from index_item import IndexItem

class Project():
    def __init__(self, project_name="", subDir="", project_url="", cur_com="", java_gateway=None, base_dir=TMP_DIR):
        self.project_name = project_name
        self.sub_dir = subDir
        self.project_url = project_url        
        self.cur_com = cur_com 
        self.repo_dir = os.path.join(base_dir, "repos", project_name)
        self.java_gateway = java_gateway

        # clone the project
        self.init_env()

        # java_gateway will be not None when invoked from doall.py script
        if java_gateway is not None:
            # index the project ( Deprecated )
            # self.index = dict()
            # self.index_project()
        
            # modify pom
            self.modify_pom()

    def init_env(self): 
        # delete folder if it exists
        # delete_folder(self.repo_dir) # Commenting to avoid repeated downloads

        if not os.path.exists(self.repo_dir):
            # cloning the repo
            print("Cloning the repo to {}...".format(self.repo_dir))
            clone_repo(self.repo_dir, self.project_url)

            # reset
            print("Reseting the repo to {}...".format(self.cur_com))
            reset_repo(self.repo_dir, self.cur_com)
            print("Done.")

            # ensure dependencies and plugins
            # print("Ensuring dependencies and plugins")
            # self.ensure_dependencies()
            # print("Done.")

    # This method lists all the jars associated with the dependencies of a particular sub-module of this project
    def list_dependencies(self, subRepo=""):
        dependencies = []

        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        pom = ET.parse(os.path.join(self.repo_dir, subRepo, 'pom.xml'))
        root = pom.getroot()

        # Find the curly brace prefix
        pom_link = re.search(r'({.*}).*', root.tag)
        if pom_link is not None: pom_link = pom_link.group(1)

        for item in root.findall('{}dependencies'.format(pom_link, pom_link)):
            for child in item:
                groupId = child.find('{}groupId'.format(pom_link))
                if groupId is not None:
                    artifactId = child.find('{}artifactId'.format(pom_link)).text
                    version = child.find('{}version'.format(pom_link)).text
                    target_jar = artifactId + '-' + version + '.jar'
                    path = os.path.join(os.path.expanduser('~'), '.m2/repository')
                    
                    for _p in groupId.text.split('.'):
                        path = os.path.join(path, _p)
                    
                    temp = []
                    for root, dirs, files in os.walk(path, topdown=True):
                        for _file in files:
                            if _file.startswith(artifactId) and _file.endswith('.jar'):
                                temp.append(os.path.join(root, _file))

                    if 'LATEST' in version:
                        temp_path_dict = dict()
                        for temp_path in temp:
                            if temp_path.endswith('.jar') and artifactId in temp_path:
                                temp_path_version = temp_path.split('-')[-1].split('.jar')[0]
                                
                                if artifactId not in temp_path_dict: temp_path_dict[artifactId] = []
                                temp_path_dict[artifactId].append([temp_path_version, temp_path])
                        for k, v in temp_path_dict.items():
                            sorted(v, key=lambda _v: _v[0], reverse=True) # Sort by version number
                            dependencies.append(v[0][1])
                    else:
                        for temp_path in temp:
                            if target_jar in temp_path:
                                dependencies.append(temp_path)

        return dependencies

    def ensure_dependencies(self):
        pom = ET.parse(os.path.join(self.repo_dir, 'pom.xml'))
        root = pom.getroot()

        print(root.attrib)

        for elem in root.iter('artifactId'):
            print(elem.attrib)

    def index_project(self):
        jGateway = self.java_gateway.entry_point
        indexed_methods = dict(jGateway.indexMethods(self.repo_dir))

        for (key, value) in indexed_methods.items():
            if key not in self.index: self.index[key] = []

            value = list(value)
            for v in value:
                class_name = v[0]
                class_path = v[1]
                start_ln = v[2]
                end_ln = v[3]

                # Convert IndexItem to a list for duplicate keys
                item = IndexItem(key, class_name, class_path, start_ln, end_ln)
                self.index[key].append(item)

        # Debugging
        # for (key, value) in self.index.items():
        #     print('Method: {}'.format(key))
        #     for index_item in value:
        #         print(index_item)

    def modify_pom(self):
        self.add_maven_compiler_plugin()

    def add_maven_compiler_plugin(self, compiler_version='3.8.1', java_version='1.8'):
        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        poms = set([os.path.join(self.repo_dir, r) for (r, ds, fs) in os.walk(self.repo_dir) for fn in fs if fn=='pom.xml'])
        
        for pom_file in poms:
            compiler_plugin_found = False

            if pom_file is None: break

            pom = ET.parse(os.path.join(pom_file, 'pom.xml'))
            root = pom.getroot()

            # Backing-up existing pom.xml as old_pom.xml
            pom.write(os.path.join(pom_file, 'old_pom.xml'))

            # Find the curly brace prefix
            pom_link = re.search(r'({.*}).*', root.tag)
            if pom_link is not None: pom_link = pom_link.group(1)

            for item in root.findall('{}build/{}plugins'.format(pom_link, pom_link)):
                for child in item:
                    artifactId = child.find('{}artifactId'.format(pom_link))
                    if artifactId is not None and 'maven-compiler-plugin' in artifactId.text:
                        compiler_plugin_found = True

                        version = child.find('{}version'.format(pom_link))
                        if version is not None: version.text = compiler_version
                        else: ET.SubElement(child, '{}version'.format(pom_link)).text = compiler_version

                        configuration = child.find('{}configuration'.format(pom_link))
                        if configuration is not None:
                            source = configuration.find('{}source'.format(pom_link))
                            target = configuration.find('{}target'.format(pom_link))
                            
                            if source is not None: source.text = java_version
                            else: ET.SubElement(configuration, '{}source'.format(pom_link)).text = java_version

                            if target is not None: target.text = java_version
                            else: ET.SubElement(configuration, '{}target'.format(pom_link)).text = java_version
                        else:
                            ET.SubElement(child, '{}configuration'.format(pom_link))
                            ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}source'.format(pom_link)).text = java_version
                            ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}target'.format(pom_link)).text = java_version
                        
                        break

            if not compiler_plugin_found:
                plugin, configuration = None, None

                if root.find('{}build/{}plugins'.format(pom_link, pom_link)) is not None:
                    plugin = ET.SubElement(root.find('{}build/{}plugins'.format(pom_link, pom_link)), '{}plugin'.format(pom_link))
                
                if plugin is not None:
                    groupId = ET.SubElement(plugin, '{}groupId'.format(pom_link)).text = 'org.apache.maven.plugins'
                    artifactId = ET.SubElement(plugin, '{}artifactId'.format(pom_link)).text = 'maven-compiler-plugin'
                    version = ET.SubElement(plugin, '{}version'.format(pom_link)).text = compiler_version
                    configuration = ET.SubElement(plugin, '{}configuration'.format(pom_link))
                
                if configuration is not None:
                    source = ET.SubElement(configuration, '{}source'.format(pom_link)).text = java_version
                    target = ET.SubElement(configuration, '{}target'.format(pom_link)).text = java_version

            pom.write(os.path.join(pom_file, 'pom.xml'))

    def run_test(self, subRepo, className, testName):
        res_dict = {"build_failure": False, "tests": 0, "failures": 0, "errors": 0}
        print("Running maven tests...")
        
        print(className, testName)
        output = execute_cmd_with_output("cd {}/{}; mvn clean test -Dgpg.skip -Dtest={}#{} -Dorg.slf4j.simpleLogger.defaultLogLevel=info".format(self.repo_dir, subRepo, className, testName))

        # parse the result
        print("Parsing the result...")
        if "BUILD FAILURE" in output:
            res_dict["build_failure"] = True

        for line in output.splitlines():
            if "Tests run:" in line and "Time" not in line:
                ar = re.findall(r'\d+', line)
                if len(ar) != 4:
                    raise Exception("Check! expecting 4 elements in the output.\n   For example: [INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0")
                res_dict["tests"] = int(ar[0])
                res_dict["failures"] = int(ar[1])
                res_dict["errors"] = int(ar[2])
        
        return res_dict, output

    def run_tests(self):
        res_dict = {"build_failure": False, "tests": 0, "failures": 0, "errors": 0}
        print("Running maven tests...")
        
        output = execute_cmd_with_output("cd {}; mvn clean test -Dorg.slf4j.simpleLogger.defaultLogLevel=info".format(self.repo_dir))
        # print("\n\n\nDone.\n\n\n")

        # parse the result
        print("Parsing the result...")
        if "BUILD FAILURE" in output:
            res_dict["build_failure"] = True
            return res_dict
        for line in output.splitlines():
            if "Tests run:" in line and not "Time" in line:
                ar = re.findall(r'\d+', line)
                if len(ar) != 4:
                    raise Exception("Check! expecting 4 elements in the output.\n   For example: [INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0")
                res_dict["tests"] = int(ar[0])
                res_dict["failures"] = int(ar[1])
                res_dict["errors"] = int(ar[2])
                return res_dict

    # Deprecated - use MethodInjector instead
    def replace_oracle_atln(self, filepath, neworacle, ln):
        ## read file into array
        with open(filepath, 'r') as file:
            # read a list of lines into data
            data = file.readlines()
        # for x in range(len(data)):
        #     print('{}: {}'.format(x, data[x]))

        # defensive programming; check that we are replacing an assertion
        if not "ssert" in data[ln-1]:
            return Exception("unexpected: trying to replace a line without assertion")                            
        # update the array
        data[ln-1] = neworacle + '\n'
        # write array to file
        with open(filepath, 'w') as file:
            file.writelines(data)