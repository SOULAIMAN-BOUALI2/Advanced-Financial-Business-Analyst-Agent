"""DEV ONLY: find which Gemini models answer quickly with your API key.

    python -m ai_agents.dev_test_models
"""
import time

from dotenv import load_dotenv
from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

client = genai.Client()
names = sorted(
    m.name.replace("models/", "")
    for m in client.models.list()
    if "flash" in m.name and "image" not in m.name and "tts" not in m.name
    and "live" not in m.name and "audio" not in m.name
)
print(f"{len(names)} flash models found. Testing each (20 s max)...\n")

for name in names:
    start = time.time()
    try:
        llm = ChatGoogleGenerativeAI(model=name, timeout=20, max_retries=0)
        answer = llm.invoke("Reply with the single word OK").content
        answer = answer if isinstance(answer, str) else str(answer)
        print(f"OK    {time.time() - start:5.1f}s  {name}  -> {answer.strip()[:20]}")
    except Exception as exc:
        print(f"FAIL  {time.time() - start:5.1f}s  {name}  -> {str(exc)[:70]}")
