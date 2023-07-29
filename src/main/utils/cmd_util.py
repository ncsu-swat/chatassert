import subprocess
import io

def execute_cmd_with_output(cmd, working_dir=None):
    output, error = "", ""

    try:
        print("\nExecuting: {}".format(cmd))
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=working_dir)
        output, error = process.communicate()
        
        # Only returning output since the stderr was redirected to stdout for later unified checking
        return output.decode('ISO-8859-1')
    except Exception as e:
        print("Execution failed: " + str(e))
        return None, None