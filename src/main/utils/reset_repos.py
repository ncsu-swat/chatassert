import os
import sys
import json

sys.path.append('../') # Since Project module is in the parent directory

from project import Project

def reset_all():
    for dir in os.listdir('../../tmp/repos'):
        reset_one(dir)

def reset_one(target_repo):
    if target_repo in os.listdir('../../tmp/repos'):
        os.system('rm -rf ../../tmp/repos/{}'.format(target_repo))

    configuration_file = os.path.join("../..", "new_data.json")
    with open(configuration_file) as f:
        data = json.load(f)
        testId = 0
        for project_data in data["projects"]:
            userName = project_data["userName"]
            repoName = project_data["repoName"]

            if repoName == target_repo:
                print('\nRESETTING REPO: {}'.format(repoName))
                subDir = project_data["subRepo"] if "subRepo" in project_data else ""
                gitURL = "git@github.com:{}/{}.git".format(userName, repoName)
                commit = project_data["commitSHA"]
                allTests = project_data["allTests"]
                # create project object
                project = Project(repoName, subDir, gitURL, commit)
                # clone the project
                project.init_env()
            
                return project

if len(sys.argv) > 1:
    reset_one(sys.argv[1])
else:
    reset_all()