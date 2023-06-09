from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

checkpoint = "bigcode/starcoder"
# device = "cuda" # for GPU usage or "cpu" for CPU usage
device = "mps" if torch.backends.mps.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(checkpoint)
# to save memory consider using fp16 or bf16 by specifying torch_dtype=torch.float16 for example
model = AutoModelForCausalLM.from_pretrained(checkpoint).to(device)
#inputs = tokenizer.encode("def print_hello_world():", return_tensors="pt").to(device)
codetocomplete = "@Test public void testParamCountOneItem ( ) { final OSimpleKeyIndexDefinition keyIndexDefinition = new OSimpleKeyIndexDefinition ( OType . INTEGER ); Assert."
inputs = tokenizer.encode(codetocomplete, return_tensors="pt").to(device)
outputs = model.generate(inputs, temperature=1.5, max_new_tokens=30)
# clean_up_tokenization_spaces=False prevents a tokenizer edge case which can result in spaces being removed around punctuation
generation = [tokenizer.decode(tensor, clean_up_tokenization_spaces=True, skip_special_tokens=True) for tensor in outputs]
print(f'{len(generation)} inputs')
for g in generation:
    print(g)
