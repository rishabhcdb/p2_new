import os
import httpx

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
AIPIPE_KEY = os.getenv("AIPIPE_API_KEY")


async def deepseek_call(prompt):
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(
            "https://api.deepseek.com/chat/completions",
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}]},
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"}
        )
        return r.json()["choices"][0]["message"]["content"]


async def aipipe_call(prompt):
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(
            "https://api.ai-pipe.com/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]},
            headers={"Authorization": f"Bearer {AIPIPE_KEY}"}
        )
        return r.json()["choices"][0]["message"]["content"]


async def ask_llm(prompt):
    try:
        return await deepseek_call(prompt)
    except Exception as e:
        print("LLM ERROR:", e)
        return ""   # never fallback to another provider
