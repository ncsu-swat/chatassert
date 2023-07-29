from utils.git_util import reset_repo, clone_repo
from utils.cmd_util import execute_cmd_with_output
from utils.file_util import copy_file, delete_file, copy_folder, delete_folder

import os
import subprocess
import shutil
from path_config import TMP_DIR
import re
import xml.etree.ElementTree as ET

from py4j.java_gateway import JavaGateway
from traceback import print_exc

import time

class Project():
    def __init__(self, project_name="", subDir="", project_url="", cur_com="", base_dir=TMP_DIR):
        self.project_name = project_name
        self.sub_dir = subDir
        self.project_url = project_url
        self.cur_com = cur_com 
        self.repo_dir = os.path.join(base_dir, "repos", project_name)            # Working directory
        self.cache_dir = os.path.join(base_dir, "cached_repos", project_name)    # Caching directory (to avoid time consuming downloads everytime)
        self.java_gateway = JavaGateway()

        # clone the project
        self.init_env()

    def init_env(self):
        if not os.path.exists(self.cache_dir):
            # cloning the repo
            print("Cloning the repo to {}...".format(self.cache_dir))
            clone_repo(self.cache_dir, self.project_url)

            # reset
            print("Reseting the repo to {}...".format(self.cur_com))
            reset_repo(self.cache_dir, self.cur_com)

        # ensuring dependencies and plugins (self.ensure_dependencies) is invoke from doall script since we need to know the subRepo name
        # copying repo from cache dir to working dir (self.copy_cache) is invoked from doall script since we need to know the subRepo name

        print("Done.")

    # This method lists all the jars associated with the dependencies of a particular sub-module of this project
    def list_dependencies(self, subRepo=""):
        dependencies = []

        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        pom = ET.parse(os.path.join(self.repo_dir, subRepo, 'pom.xml'))
        root = pom.getroot()

        # Find the curly brace prefix
        pom_link = re.search(r'({.*}).*', root.tag)
        if pom_link is not None: pom_link = pom_link.group(1)

        for item in root.findall('{}dependencies'.format(pom_link)):
            for child in item:
                groupId = child.find('{}groupId'.format(pom_link))
                if groupId is not None:
                    artifactId = child.find('{}artifactId'.format(pom_link))
                    if artifactId is not None: artifactId = artifactId.text
                    version = child.find('{}version'.format(pom_link))
                    if version is not None: 
                        version = version.text
                    else:
                        version = 'LATEST'
                    
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

    # This method copies only the repo from the cache directory to the working directory
    def copy_cache(self):
        try:
            # delete potentially stale repo in working directory if it exists
            print('Deleting potentially stale repo in working directory')
            delete_folder(self.repo_dir) # Commenting to avoid repeated copy

            # copying from cache to working directory
            print('Copying repo from cache dir to working dir')
            copy_folder(os.path.join(self.cache_dir), os.path.join(self.repo_dir))
        except:
            print_exc()
            print('\n!!! ERROR COPYING SUBREPO !!!\n')

    # This method copies only the pom.xml from cache
    def restore_pom(self, subRepo):
        # Delete existing pom.xml file and copy the original one
        delete_file(os.path.join(self.repo_dir, subRepo, 'pom.xml'))
        delete_file(os.path.join(self.repo_dir, subRepo, 'old_pom.xml'))
        copy_file(os.path.join(self.cache_dir, subRepo, 'pom.xml'), os.path.join(self.repo_dir, subRepo, 'pom.xml'))

    # This method copies the test class's parent directory from cache
    def restore_test_dir(self, subRepo, test_class_relative_path):
        test_dir = '/'.join(test_class_relative_path.split('/')[:-1])

        # Delete existing target test class directory and copy the original directory from cache
        delete_folder(os.path.join(self.repo_dir, test_dir))
        copy_folder(os.path.join(self.cache_dir, test_dir), os.path.join(self.repo_dir, test_dir))

    def precompile_jar(self, subRepo=None):
        is_precompiled = False

        # Check if jar is already installed
        if subRepo is not None and len(subRepo) > 0:
            if os.path.exists(os.path.join(os.environ['HOME'], '.m2/repository/chatassert', self.project_name, subRepo, 'chatassert.{}.{}'.format(self.project_name, subRepo), '1.0/chatassert.{}.{}-1.0.jar'.format(self.project_name, subRepo))):
                is_precompiled = True
        elif os.path.exists(os.path.join(os.environ['HOME'], '.m2/repository/chatassert', self.project_name, 'chatassert.{}'.format(self.project_name), '1.0/chatassert.{}-1.0.jar'.format(self.project_name))):
            is_precompiled = True

        #===================================================================================================================

        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        pom_file = os.path.join(self.repo_dir, subRepo, 'pom.xml')
        pom = ET.parse(pom_file)
        root = pom.getroot()

        # Find the curly brace prefix
        pom_link = re.search(r'({.*}).*', root.tag)
        if pom_link is not None: pom_link = pom_link.group(1)

        if not is_precompiled:
            print('\nAdding Jar Plugin: chatassert.{}.{}\n'.format(self.project_name, subRepo))

            # Add jar plugin
            build = root.find('{}build'.format(pom_link))
            if build is None: build = ET.SubElement(root, '{}build'.format(pom_link))

            plugins = build.find('{}plugins'.format(pom_link))
            if plugins is None: plugins = ET.SubElement(build, '{}plugins'.format(pom_link))

            plugin = ET.SubElement(plugins, '{}plugin'.format(pom_link))
            ET.SubElement(plugin, '{}groupId'.format(pom_link)).text = 'org.apache.maven.plugins'
            ET.SubElement(plugin, '{}artifactId'.format(pom_link)).text = 'maven-jar-plugin'
            ET.SubElement(plugin, '{}version'.format(pom_link)).text = '3.2.0'

            pom.write(os.path.join(pom_file))

            # Creating jar of project
            output = execute_cmd_with_output("mvn -X package -DskipTests=true", os.path.join(self.repo_dir, subRepo))
            print(output)
            if 'BUILD FAILURE' in output: return False

            #===================================================================================================================
            jar_name = None
            for f in os.listdir(os.path.join(self.repo_dir, subRepo, 'target')):
                if '.jar' in f and 'test' not in f:
                    jar_name = f
                    break
            
            print('Jar name: {}'.format(jar_name))

            if jar_name is None:
                return False

            # Install precompiled jar
            if subRepo is not None and len(subRepo) > 0:
                output = execute_cmd_with_output("mvn install:install-file -Dfile={} -DgroupId={} -DartifactId={} -Dversion={} -Dpackaging=jar".format(os.path.join(self.repo_dir, subRepo, 'target', jar_name), 'chatassert.{}.{}'.format(self.project_name, subRepo), 'chatassert.{}.{}'.format(self.project_name, subRepo), '1.0'), os.path.join(self.repo_dir, subRepo))
            else:
                output = execute_cmd_with_output("mvn install:install-file -Dfile={} -DgroupId={} -DartifactId={} -Dversion={} -Dpackaging=jar".format(os.path.join(self.repo_dir, subRepo, 'target', jar_name), 'chatassert.{}'.format(self.project_name), 'chatassert.{}'.format(self.project_name), '1.0'), os.path.join(self.repo_dir, subRepo))
            if 'BUILD FAILURE' in output: return False

        #===================================================================================================================

        # Add the precompiled jar as a dependency
        dependencies = root.find('{}dependencies'.format(pom_link))
        if dependencies is None:
            dependencies = ET.SubElement(root, '{}dependencies'.format(pom_link))
        
        dependency = ET.SubElement(dependencies, '{}dependency'.format(pom_link))
        if subRepo is not None and len(subRepo) > 0:
            ET.SubElement(dependency, '{}groupId'.format(pom_link)).text = 'chatassert.{}.{}'.format(self.project_name, subRepo)
            ET.SubElement(dependency, '{}artifactId'.format(pom_link)).text = 'chatassert.{}.{}'.format(self.project_name, subRepo)
            ET.SubElement(dependency, '{}version'.format(pom_link)).text = '1.0'
        else:
            ET.SubElement(dependency, '{}groupId'.format(pom_link)).text = 'chatassert.{}'.format(self.project_name)
            ET.SubElement(dependency, '{}artifactId'.format(pom_link)).text = 'chatassert.{}'.format(self.project_name)
            ET.SubElement(dependency, '{}version'.format(pom_link)).text = '1.0'

        pom.write(os.path.join(pom_file))

        return True

    def ensure_dependencies(self, subRepo=""):
        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        pom_file = os.path.join(self.cache_dir, subRepo, 'pom.xml')
        pom = ET.parse(pom_file)
        root = pom.getroot()

        # Find the curly brace prefix
        pom_link = re.search(r'({.*}).*', root.tag)
        if pom_link is not None: pom_link = pom_link.group(1)

        deps_to_add = [
            {
                'groupId': 'javax.xml.bind',
                'artifactId': 'jaxb-api',
                'version': '2.3.0'
            },
            {
                'groupId': 'org.slf4j',
                'artifactId': 'slf4j-api',
                'version': '2.0.0'
            },
            {
                'groupId': 'org.slf4j',
                'artifactId': 'slf4j-simple',
                'version': '2.0.0'
            },
            {
                'groupId': 'org.apache.logging.log4j',
                'artifactId': 'log4j-api',
                'version': '2.21.0'
            },
            {
                'groupId': 'org.apache.logging.log4j',
                'artifactId': 'log4j-core',
                'version': '2.21.0'
            },
            {
                'groupId': 'org.apache.logging.log4j',
                'artifactId': 'log4j-slf4j-impl',
                'version': '2.21.0'
            }
        ]

        for dep in deps_to_add:
            dep_exists = False
            for item in root.findall('{}dependencies'.format(pom_link)):
                for child in item:
                    artifactId = child.find('{}artifactId'.format(pom_link))
                    if artifactId is not None: 
                        if artifactId.text == dep['artifactId']:
                            dep_exists = True
                            break
                    
                if dep_exists:
                    break

            if not dep_exists:
                dependencies = root.find('{}dependencies'.format(pom_link))
                if dependencies is None:
                    dependencies = ET.SubElement(root, '{}dependencies'.format(pom_link))
               
                dependency = ET.SubElement(dependencies, '{}dependency'.format(pom_link))
                
                groupId = ET.SubElement(dependency, '{}groupId'.format(pom_link))
                groupId.text = dep['groupId']
                artifactId = ET.SubElement(dependency, '{}artifactId'.format(pom_link))
                artifactId.text = dep['artifactId']
                version = ET.SubElement(dependency, '{}version'.format(pom_link))
                version.text = dep['version']

        pom.write(os.path.join(pom_file))

    def add_maven_compiler_plugin(self, compiler_version='3.8.1', java_version='1.8', test_class_path=None):
        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        poms = set([os.path.join(self.repo_dir, r) for (r, ds, fs) in os.walk(self.repo_dir) for fn in fs if fn=='pom.xml'])
        
        for pom_file in poms:
            # print(pom_file)
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
                        
                            if test_class_path is not None:
                                includes = configuration.find('{}includes'.format(pom_link))
                                if includes is not None:
                                    ET.SubElement(includes, '{}include'.format(pom_link)).text = test_class_path.split('/src/test/java/')[1]
                                else:
                                    includes = ET.SubElement(configuration, '{}includes'.format(pom_link))
                                    ET.SubElement(includes, '{}include'.format(pom_link)).text = test_class_path.split('/src/test/java/')[1]
                        else:
                            configuration = ET.SubElement(child, '{}configuration'.format(pom_link))
                            ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}source'.format(pom_link)).text = java_version
                            ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}target'.format(pom_link)).text = java_version
                        
                            if test_class_path is not None:
                                includes = ET.SubElement(configuration, '{}includes'.format(pom_link))
                                ET.SubElement(includes, '{}include'.format(pom_link)).text = test_class_path.split('/src/test/java/')[1]
                        break

            if not compiler_plugin_found:
                plugin, configuration = None, None

                if root.find('{}build/{}plugins'.format(pom_link, pom_link)) is not None:
                    plugin = ET.SubElement(root.find('{}build/{}plugins'.format(pom_link, pom_link)), '{}plugin'.format(pom_link))
                
                if plugin is not None:
                    groupId = ET.SubElement(plugin, '{}groupId'.format(pom_link))
                    groupId.text = 'org.apache.maven.plugins'
                    artifactId = ET.SubElement(plugin, '{}artifactId'.format(pom_link))
                    artifactId.text = 'maven-compiler-plugin'
                    version = ET.SubElement(plugin, '{}version'.format(pom_link))
                    version.text = compiler_version
                    
                    configuration = ET.SubElement(plugin, '{}configuration'.format(pom_link))

                if configuration is not None:
                    source = ET.SubElement(configuration, '{}source'.format(pom_link))
                    source.text = java_version
                    target = ET.SubElement(configuration, '{}target'.format(pom_link))
                    target.text = java_version

                    if test_class_path is not None:
                        includes = ET.SubElement(configuration, '{}includes'.format(pom_link))
                        ET.SubElement(includes, '{}include'.format(pom_link)).text = test_class_path.split('/src/test/java/')[1]

            pom.write(os.path.join(pom_file, 'pom.xml'))

    def add_pit_plugin(self, subRepo="", pit_version='1.15.1', test_file_path='', focal_file_path='', max_mutations_per_class=21, timeout_factor=1):
        # Get class path glob of test_file_path and focal_file_path
        self.java_gateway.entry_point.setFile(test_file_path)
        target_test_glob = self.java_gateway.entry_point.getPackageName() + '.' + test_file_path.split('/')[-1].replace('.java', '')
        self.java_gateway.entry_point.setFile(focal_file_path)
        target_class_glob = self.java_gateway.entry_point.getPackageName() + '.' + focal_file_path.split('/')[-1].replace('.java', '')

        # Add pit plugin
        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')

        pom_file = os.path.join(self.repo_dir, subRepo, 'pom.xml')
        pom = ET.parse(pom_file)
        root = pom.getroot()
        
        pit_plugin_found = False

        if pom_file is None: return None

        # Backing-up existing pom.xml as old_pom.xml
        pom.write(os.path.join(self.repo_dir, subRepo, 'old_pom.xml'))

        # Find the curly brace prefix
        pom_link = re.search(r'({.*}).*', root.tag)
        if pom_link is not None: pom_link = pom_link.group(1)

        for item in root.findall('{}build/{}plugins'.format(pom_link, pom_link)):
            for child in item:
                artifactId = child.find('{}artifactId'.format(pom_link))
                if artifactId is not None and 'pitest-maven' in artifactId.text:
                    pit_plugin_found = True

                    groupId = child.find('{}groupId'.format(pom_link))
                    if groupId is not None: groupId.text = 'org.pitest'
                    else: ET.SubElement(child, '{}groupId'.format(pom_link)).text = 'org.pitest'

                    version = child.find('{}version'.format(pom_link))
                    if version is not None: version.text = pit_version
                    else: ET.SubElement(child, '{}version'.format(pom_link)).text = pit_version

                    configuration = child.find('{}configuration'.format(pom_link))
                    if configuration is not None:
                        child.remove(configuration)
                    
                    ET.SubElement(child, '{}configuration'.format(pom_link))
                    # ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}targetClasses'.format(pom_link))
                    # ET.SubElement(child.find('{}configuration/{}targetClasses'.format(pom_link, pom_link)), '{}param'.format(pom_link)).text = target_class_glob
                    ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}targetTests'.format(pom_link))
                    ET.SubElement(child.find('{}configuration/{}targetTests'.format(pom_link, pom_link)), '{}param'.format(pom_link)).text = target_test_glob
                    ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}features'.format(pom_link))
                    ET.SubElement(child.find('{}configuration/{}features'.format(pom_link, pom_link)), '{}feature'.format(pom_link)).text = "+CLASSLIMIT(limit[{}])".format(str(max_mutations_per_class))
                    ET.SubElement(child.find('{}configuration'.format(pom_link)), '{}timeoutFactor'.format(pom_link)).text = str(timeout_factor)
                    
                    break

        if not pit_plugin_found:
            plugin, configuration = None, None

            if root.find('{}build/{}plugins'.format(pom_link, pom_link)) is not None:
                plugin = ET.SubElement(root.find('{}build/{}plugins'.format(pom_link, pom_link)), '{}plugin'.format(pom_link))
            
            if plugin is not None:
                groupId = ET.SubElement(plugin, '{}groupId'.format(pom_link))
                groupId.text = 'org.pitest'
                artifactId = ET.SubElement(plugin, '{}artifactId'.format(pom_link))
                artifactId.text = 'pitest-maven'
                version = ET.SubElement(plugin, '{}version'.format(pom_link))
                version.text = pit_version
                
                configuration = ET.SubElement(plugin, '{}configuration'.format(pom_link))
            
            if configuration is not None:
                # target_class = ET.SubElement(configuration, '{}targetClasses'.format(pom_link))
                # target_class_param = ET.SubElement(target_class, '{}param'.format(pom_link))
                # target_class_param.text = target_class_glob

                target_test = ET.SubElement(configuration, '{}targetTests'.format(pom_link))
                target_test_param = ET.SubElement(target_test, '{}param'.format(pom_link))
                target_test_param.text = target_test_glob

                features = ET.SubElement(configuration, '{}features'.format(pom_link))
                feature = ET.SubElement(features, '{}feature'.format(pom_link))
                feature.text = "+CLASSLIMIT(limit[{}])".format(str(max_mutations_per_class))

                timeoutFactor = ET.SubElement(configuration, '{}timeoutFactor'.format(pom_link))
                timeoutFactor.text = str(timeout_factor)

        pom.write(os.path.join(self.repo_dir, subRepo, 'pom.xml'))

    @staticmethod
    def run_test(repo_dir, subRepo, className, testName):
        res_dict = {"build_failure": False, "tests": 0, "failures": 0, "errors": 0}
        print("Running maven tests...")
        
        print(className, testName)
        output = execute_cmd_with_output("mvn clean test -Dgpg.skip -Dtest={}#{}".format(className, testName), os.path.join(repo_dir, subRepo))
        
        # print('\n\nOUTPUT:\n\n{}\n'.format(output))
        # print('=================================================\n')

        # parse the result
        print("Parsing the result...")
        if "BUILD FAILURE" in output:
            res_dict["build_failure"] = True

        for line in output.splitlines():
            if "Tests run:" in line and "Time" not in line:
                ar = re.findall(r'\d+', line)
                if len(ar) < 4:
                    raise Exception("Check! expecting 4 elements in the output.\n   For example: [INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0")
                res_dict["tests"] = int(ar[0])
                res_dict["failures"] = int(ar[1])
                res_dict["errors"] = int(ar[2])
        
        return res_dict, output

    def run_tests(self):
        res_dict = {"build_failure": False, "tests": 0, "failures": 0, "errors": 0}
        print("Running maven tests...")
        
        output, error = execute_cmd_with_output("cd {}; mvn clean test -Dorg.slf4j.simpleLogger.defaultLogLevel=info".format(self.repo_dir))
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

    @staticmethod
    def run_pitest(repo_dir, subRepo):
        line_coverage, mutation_coverage, test_strength, tests_ran = 0, 0, 0, 0

        output = execute_cmd_with_output("mvn -q -DwithHistory -Dthreads=4 test-compile org.pitest:pitest-maven:mutationCoverage".format(repo_dir, subRepo), os.path.join(repo_dir, subRepo))
        print(output)

        if 'BUILD FAILURE' in output:
            return -1, -1, -1, -1

        if m := re.search(r'Line Coverage .* \((\d+)%\)', output):
            line_coverage = m.group(1)
        if m := re.search(r'Generated \d+ mutations Killed 0 \((\d+)%\)', output):
            mutation_coverage = m.group(1)
        if m := re.search(r'Mutations with no coverage (\d+)\. Test strength (\d+)%', output):
            test_strength = m.group(2)
        if m := re.search(r'Ran (\d+) tests', output):
            tests_ran = m.group(1)
            
        return line_coverage, mutation_coverage, test_strength, tests_ran

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