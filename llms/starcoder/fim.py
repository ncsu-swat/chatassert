from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

checkpoint = "bigcode/starcoder"
# device = "cuda" # for GPU usage or "cpu" for CPU usage
device = "mps" if torch.backends.mps.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(checkpoint, truncation_side="left")
model = AutoModelForCausalLM.from_pretrained(checkpoint).to(device)
#input_text = "<fim_prefix>def fib(n):<fim_suffix>    else:\n        return fib(n - 2) + fib(n - 1)<fim_middle>"
input_text = "<fim_prefix>def fib(n):<fim_suffix>    else:\n        return fib(n - 2) + fib(n - 1)<fim_middle>"
inputs = tokenizer(input_text, return_tensors="pt").to(device) #.to("cuda")
outputs = model.generate(**inputs, max_new_tokens=25)
generation = [tokenizer.decode(tensor, skip_special_tokens=False) for tensor in outputs]
print(generation[0])
