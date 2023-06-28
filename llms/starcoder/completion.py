from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

checkpoint = "bigcode/starcoder"
# device = "cuda" # for GPU usage or "cpu" for CPU usage
device = "mps" if torch.backends.mps.is_available() else "cpu"

tokenizer = None
model = None

def initialize_starcoder():
    global tokenizer
    global model
    print("loading starcoder tokenizer")
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    # to save memory consider using fp16 or bf16 by specifying torch_dtype=torch.float16 for example
    print("loading starcoder model")
    model = AutoModelForCausalLM.from_pretrained(checkpoint).to(device)
    #inputs = tokenizer.encode("def print_hello_world():", return_tensors="pt").to(device)
    print("loading complete")

def dispose_mem_starcoder():
    global model
    global tokenizer
    del model
    del tokenizer
    torch.mps.empty_cache()

def generate_starcoder(codetocomplete, temperature):
    inputs = tokenizer.encode(codetocomplete, return_tensors="pt").to(device)
    outputs = model.generate(inputs, pad_token_id=tokenizer.eos_token_id, temperature=temperature, max_new_tokens=30)
    # clean_up_tokenization_spaces=False prevents a tokenizer edge
    # case which can result in spaces being removed around punctuation
    return [tokenizer.decode(tensor, clean_up_tokenization_spaces=True, skip_special_tokens=True) for tensor in outputs]

#codetocomplete = "@Test public void testParamCountOneItem ( ) { final OSimpleKeyIndexDefinition keyIndexDefinition = new OSimpleKeyIndexDefinition ( OType . INTEGER ); Assert."
    
