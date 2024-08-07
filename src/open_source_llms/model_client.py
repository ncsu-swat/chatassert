import requests
import sys
from utils.context_util import Context
import msgpack
import time

sys.path.append("../")

from transformers import AutoTokenizer

model_name = "mistralai/Mistral-7B-Instruct-v0.3"
tokenizer = AutoTokenizer.from_pretrained(model_name, token="...", padding_side='left')

def merge_consecutive_messages(messages):
    """Merge consecutive messages so it fits the alternating user/assistant scheme that mistral expects"""
    if not messages:
        return []

    merged_messages = [messages[0]]
    for current in messages[1:]:
        last = merged_messages[-1]
        if last['role'] == current['role']:
            last['content'] += "\n" + current['content']
        else:
            merged_messages.append(current)
    return merged_messages

session = requests.Session()


def get_model_response(temperature=1.0, context=None):
    filtered_messages = [{"role": msg["role"], "content": msg["content"]} for msg in context.history if msg["role"] != "system"]
    # filtered_messages = context.history 
    messages = merge_consecutive_messages(filtered_messages)

    total_tokens = sum(len(tokenizer(msg["content"])["input_ids"]) for msg in messages)
    
    if total_tokens > 30000:
        context.reset()
        filtered_messages = [{"role": msg["role"], "content": msg["content"]} for msg in context.history if msg["role"] != "system"]
        messages = merge_consecutive_messages(filtered_messages)
    
    
    url = 'http://localhost:5000/interact'
    data = {'content': messages, 'temperature': temperature}
    packed_data = msgpack.packb(data)

    while True:
        try:
            response = session.post(url, data=packed_data, headers={'Content-Type': 'application/x-msgpack'})
            response.raise_for_status()  # Check if the request was successful
            unpacked_response = msgpack.unpackb(response.content)
            return unpacked_response['response']
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            print(f"Retrying in {60} seconds...")
            time.sleep(60)

# Uses a raw string instead of a dict with user/assistant roles
def get_model_response_gptsort(temperature=1.0, context=None):
    filtered_messages = [{"role": msg["role"], "content": msg["content"]} for msg in context if msg["role"] != "system"]
    messages = merge_consecutive_messages(filtered_messages)
    
    url = 'http://localhost:5000/interact'
    data = {'content': messages, 'temperature': temperature}
    packed_data = msgpack.packb(data)
    
    response = session.post(url, data=packed_data, headers={'Content-Type': 'application/x-msgpack'})
    
    unpacked_response = msgpack.unpackb(response.content)

    return unpacked_response['response']

if __name__ == "__main__":
    content = "You are a Java developer. Write java code for a JUnit test for this class:\n\npublic class MyUnit {\n\n    public String concatenate(String one, String two){\n        return one + two;\n    }\n}"
    response = get_model_response(content, 0.8)
    print(response)
