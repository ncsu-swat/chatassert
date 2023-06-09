from transformers import AutoTokenizer, AutoModelForCausalLM
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codegen2-1B")
model = AutoModelForCausalLM.from_pretrained("Salesforce/codegen2-1B", trust_remote_code=True, revision="main")


def format(prefix, suffix):
  return prefix + "<mask_1>" + suffix + "<|endoftext|>" + "<sep>" + "<mask_1>"


prefix = "def hello_world():\n    "
suffix = "    return name"
text = format(prefix, suffix)
input_ids = tokenizer(text, return_tensors="pt").input_ids
generated_ids = model.generate(input_ids, max_length=128)
print(tokenizer.decode(generated_ids[0], skip_special_tokens=False)[len(text):])
