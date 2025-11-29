import json
import httpx
import os
import io
import pandas as pd
from urllib.parse import urljoin
from llm_client import ask_llm


BROWSERLESS_KEY = os.getenv("BROWSERLESS_API_KEY")


async def fetch_rendered_html(url):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://chrome.browserless.io/content?token={BROWSERLESS_KEY}",
            json={"url": url}
        )
        r.raise_for_status()
        return r.text


async def parse_quiz(html):
    prompt = f"""
Extract the following from this rendered HTML page:
- Question/instruction
- Submit endpoint URL
- Required answer format
- Download file URLs
Return VALID JSON ONLY with keys: question, submit_url, answer_format, file_urls.
Do NOT add code fences. Do NOT add markdown. Do NOT add explanations.
HTML: {html}
"""

    resp = await ask_llm(prompt)
    print("\n=== RAW LLM RESPONSE (parse_quiz) ===\n", resp, "\n=== END ===\n")

    cleaned = resp.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except:
        raise RuntimeError(f"LLM returned non-JSON output: {resp[:200]}")




async def classify_question(question):
    prompt = f"""
Your job is to classify WHAT TYPE of operation is required to answer the question.
Possible categories (choose exactly one):
- scrape → information must be fetched/extracted from another page/URL shown in the question
- tabular → math/aggregation must be done on CSV/HTML-table data
- file_lookup → answer exists inside a file (CSV/PDF/audio/etc.) but does NOT require aggregation
- other → general reasoning, solve without external files or scraping
IMPORTANT: Do NOT choose 'direct_value' or attempt to return the answer directly even if numbers appear in the question.
If the question only shows a number, this is likely misleading — choose based on the overall task type instead.
Return STRICT JSON ONLY:
{{
  "task": "<scrape | tabular | file_lookup | other>"
}}
Question:
{question}
"""
    resp = await ask_llm(prompt)
    cleaned = resp.strip().replace("```", "").replace("json", "")
    try:
        return json.loads(cleaned).get("task", "other")
    except:
        return "other"







async def compute_tabular(question, file_contents):
    dfs = []
    for fc in file_contents:
        name = fc["filename"]
        text = fc["content"]
        if name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(io.StringIO(text))
                dfs.append(df)
            except:
                continue

    if not dfs:
        return None

    # Combine all CSVs (side by side or stacked — whichever matches)
    df = pd.concat(dfs, axis=0, ignore_index=True)

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return None

    # Compute everything possible
    results = {}
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        results[col] = {
            "sum": float(series.sum()),
            "mean": float(series.mean()),
            "count": int(series.count()),
            "max": float(series.max()),
            "min": float(series.min())
        }

    # Ask LLM which among these results is the answer
    prompt = f"""
You are given a question and a table summary. Identify the correct numeric result.
Question:
{question}
Available computed values:
{results}
Which of these values is the correct final answer?
Return ONLY the number.
"""
    resp = await ask_llm(prompt)
    cleaned = resp.strip().replace("```", "").replace(",", "")
    try:
        return float(cleaned)
    except:
        return None




async def compute_answer(question, file_urls, answer_format, current_page_url):
    """
    Core solver: classifies question, fetches referenced pages/files, and routes
    to the proper solving engine (tabular / file lookup / scrape / LLM fallback).
    """
    task = await classify_question(question)
    print(f"🧠 CLASSIFIED TASK → {task}")

    # -------------------------------
    # 1) SCRAPE — fetch referenced pages first
    # -------------------------------
    if task == "scrape":
        scrape_url_prompt = f"""
    Extract the URL(s) that must be scraped from this question text.
    Return ONLY JSON: {{ "urls": [ ... ] }}
    Question: {question}
    """
        try:
            u = await ask_llm(scrape_url_prompt)
            scrape_urls = json.loads(u.replace("```", "")).get("urls", [])
        except:
            scrape_urls = []
    
        # Visit scraped URLs
        page_contents = []
        async with httpx.AsyncClient(timeout=60) as client:
            for u in scrape_urls:
                abs_url = urljoin(current_page_url, u)
                html = (await client.get(abs_url)).text
                page_contents.append({"url": abs_url, "content": html})
    
        # Detect numeric tables (even without <table> tag)
        import re
        for p in page_contents:
            nums = re.findall(r"\d+(?:\.\d+)?", p["content"])
            # 3+ distinct numbers usually indicate summing/aggregation
            if len(set(nums)) >= 3:
                try:
                    tables = pd.read_html(p["content"])
                    dfs = pd.concat(tables, axis=0, ignore_index=True)
                except Exception:
                    # Synthetic CSV if no actual table but numeric grid exists
                    df = pd.DataFrame({"value": list(map(float, nums))})
                    dfs = df
    
                csv_str = dfs.to_csv(index=False)
                new_fc = [{"filename": "scraped_table.csv", "content": csv_str}]
                tab_ans = await compute_tabular(question, new_fc)
                if tab_ans is not None:
                    print(f"✔ TABULAR COMPUTE SUCCESS (via scrape) → {tab_ans}")
                    return tab_ans
    
        # Else → not tabular, extract text from scraped pages
        return await ask_llm(
            f"Extract the exact final answer from the scraped content.\n"
            f"Scraped pages: {page_contents}\n"
            f"Return ONLY the answer in this format = {answer_format}"
        )


    # ----------------------------------------------------
    # 2) DOWNLOAD FILES — used by tabular / lookup / fallback
    # ----------------------------------------------------
    file_contents = []
    if file_urls:
        async with httpx.AsyncClient(timeout=60) as client:
            for url in file_urls:
                abs_url = urljoin(current_page_url, url)
                print("DOWNLOADING FILE:", url, "→", abs_url)
                resp = await client.get(abs_url)
                try:
                    text = resp.content.decode(errors="ignore")
                except:
                    text = ""
                file_contents.append({"filename": url.split("/")[-1], "content": text})

    # --------------------------------------
    # 3) TABULAR ALWAYS TAKES PRIORITY
    # --------------------------------------
    if file_contents:
        tab_ans = await compute_tabular(question, file_contents)
        if tab_ans is not None:
            print(f"✔ TABULAR COMPUTE SUCCESS → {tab_ans}")
            return tab_ans

    # --------------------------------------
    # 4) FILE LOOKUP
    # --------------------------------------
    if task == "file_lookup" and file_contents:
        return await ask_llm(
            f"Use ONLY the downloaded files to locate the answer.\n"
            f"Files: {file_contents}\n"
            f"Question: {question}\n"
            f"Return only the answer in format = {answer_format}"
        )

    # --------------------------------------
    # 5) FINAL FALLBACK
    # --------------------------------------
    return await ask_llm(
        f"Solve the question.\n"
        f"Files (if any): {file_contents}\n"
        f"Question: {question}\n"
        f"Return ONLY the answer in format = {answer_format}"
    )



async def solve_quiz(email, secret, initial_url):
    current = initial_url
    for _ in range(20):
        html = await fetch_rendered_html(current)
        parsed = await parse_quiz(html)

        answer = await compute_answer(
            parsed["question"],
            parsed["file_urls"],
            parsed["answer_format"],
            current
        )

        payload = {"email": email, "secret": secret, "url": current, "answer": answer}

        submit_url = urljoin(current, parsed["submit_url"])
        print("SUBMIT URL =>", parsed["submit_url"], "→", submit_url)

        async with httpx.AsyncClient(timeout=60) as client:
            result = (await client.post(submit_url, json=payload)).json()

        if not result.get("correct"):
            if result.get("url"):
                current = result["url"]
                continue
            return {"status": "completed", "correct": False, "reason": result.get("reason")}

        if not result.get("url"):
            return {"status": "completed", "correct": True}

        current = result["url"]

    raise RuntimeError("Quiz loop exceeded 20 iterations")
