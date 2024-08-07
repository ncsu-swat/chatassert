from flask import Flask, request, jsonify, Response
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import logging
from concurrent.futures import ThreadPoolExecutor
import msgpack
import os
import threading
import time
import transformers 

os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

logging.basicConfig(filename='model_server.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

app = Flask(__name__)

model_path = "mistralai/Mistral-7B-Instruct-v0.3"

def initialize_pipeline():
    tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True, use_auth_token="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")
    if not isinstance(tokenizer, transformers.PreTrainedTokenizerFast):
        raise ValueError("The loaded tokenizer is not a fast tokenizer. Please ensure you have specified use_fast=True.")
    tokenizer.add_prefix_space = True

    quantization_config = BitsAndBytesConfig(
        load_in_8bit=False,  
        load_in_4bit=False,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        # quantization_config=quantization_config,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        use_auth_token="...",
        device_map="auto"
    )

    # print(model.config.__class__.__name__)
    # for name, param in model.named_parameters():
    #     print(f"{name}: {param.dtype}")

    pipeline_instance = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        do_sample=True
    )
    return pipeline_instance

gpu_pipeline = initialize_pipeline()

max_concurrent_requests = 3
executor = ThreadPoolExecutor(max_workers=max_concurrent_requests)

# Semaphore to limit the number of concurrent accesses to the GPU
# gpu_semaphore = threading.Semaphore(max_concurrent_requests)


# def check_memory_availability(required_memory):
#     for device in range(torch.cuda.device_count()):
#         total_memory = torch.cuda.get_device_properties(device).total_memory
#         allocated_memory = torch.cuda.memory_allocated(device)
#         reserved_memory = torch.cuda.memory_reserved(device)
#         free_memory = total_memory - (allocated_memory + reserved_memory)
#             # logging.info(f"Total: {total_memory / (1024 ** 3):.2f} GB, "
#     #              f"Allocated: {allocated_memory / (1024 ** 3):.2f} GB, "
#     #              f"Reserved: {reserved_memory / (1024 ** 3):.2f} GB, "
#     #              f"Free: {free_memory / (1024 ** 3):.2f} GB")
#         if free_memory < required_memory:
#             return False
#     return True

@app.route('/interact', methods=['POST'])
def interact():
    print('Handling Request!')
    packed_data = request.get_data()
    unpacked_data = msgpack.unpackb(packed_data)
    content = unpacked_data['content']
    temperature = unpacked_data.get('temperature', 1.0)

    model_inputs = gpu_pipeline.tokenizer.apply_chat_template(content, tokenize=True)

    max_token_length = min(len(model_inputs), 30000)
    input_tokens = model_inputs[-max_token_length:]
    model_inputs = gpu_pipeline.tokenizer.decode(input_tokens)
    max_length = max_token_length + 100

    def generate_response():
        # required_memory = 10 * 1024 * 1024 * 1024 
        # while not check_memory_availability(required_memory):
        #     torch.cuda.empty_cache()
        #     time.sleep(2)
        return gpu_pipeline(
            model_inputs,
            max_length=max_length,
            num_return_sequences=1,
            temperature=temperature
        )

    try:
        # gpu_semaphore.acquire()
        future = executor.submit(generate_response)
        sequences = future.result()
        response_text = sequences[0]['generated_text']
        packed_response = msgpack.packb({"response": response_text[len(content):].strip()})
        torch.cuda.empty_cache()
        return Response(packed_response, mimetype='application/x-msgpack')
    except RuntimeError as e:
        logging.error(f"RuntimeError during model inference: {e}")
        return jsonify(error="An error occurred during model inference. Please try again later."), 500
    # finally:
        # gpu_semaphore.release()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
