import os
from crewai import LLM

os.environ["LITELLM_DROP_PARAMS"] = "true"

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    temperature=0.3,
)

response = llm.call("Say hello in one sentence.")
print(response)