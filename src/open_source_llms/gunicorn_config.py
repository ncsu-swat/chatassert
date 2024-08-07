import os
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
# from preload_model import tokenizer, model
# import multiprocessing 

# model_path = "/mnt/beegfs/amscott9/magicoder"
# tokenizer = None
# model = None
# model_initialized = False
workers = 3
bind = '0.0.0.0:5000'  
timeout = 1024
# multiprocessing.set_start_method('spawn')

def pre_fork(server, worker):
    pass
    # global tokenizer, model
    # tokenizer, model = preload_model()
    

def post_fork(server, worker):
    worker_pid = worker.pid
    print(f"worker.pid: {worker_pid}")
    num_gpus = 3
    print(f"num_gpus: {num_gpus}")

    # Assign GPU ID to each worker
    worker_id = int(worker_pid) % num_gpus
    os.environ['MY_DEVICE'] = str(0)
    os.environ['CUDA_VISIBLE_DEVICES'] = str(worker_id) #worker_id

    print(f"Assigned GPU {worker_id} to worker with PID {worker_pid}")

# Set the pre_fork and post_fork functions
pre_fork = pre_fork
post_fork = post_fork
