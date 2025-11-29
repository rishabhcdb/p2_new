# LLM Analysis Quiz Solver

This repository contains an automated system that solves the **TDS LLM Analysis Quiz**.  
The application exposes a public API endpoint that receives quiz tasks, retrieves content from quiz pages, computes the correct answer, and submits it automatically within the allowed time window.

---

## Features

- Accepts POST requests with quiz tasks
- Renders JavaScript pages using Browserless to extract dynamic HTML
- Parses questions, submit URL, answer format, and downloadable file links
- Handles multiple types of tasks:
  - Web scraping
  - Tabular numeric computation (CSV / HTML tables)
  - File-based lookup (text/csv/pdf/audio)
  - General reasoning using an LLM
- Supports multi-step quizzes: follows new URLs until completion
- Uses DeepSeek API as the primary LLM and AI-Pipe API as fallback
- Deployable on Hugging Face Spaces

---

## API Specification
POST /
# Expected Payload
{
  "email": "<student email>",
  "secret": "<secret string>",
  "url": "<quiz URL>"
}

# Successful Completion
{
  "status": "completed",
  "correct": true
}

# Incorrect Completion
{
  "status": "completed",
  "correct": false,
  "reason": "<reason>"
}

# Error Responses
{ "error": "Invalid secret" }

{ "error": "Invalid payload" }



## System Flow

POST request received with email, secret, and quiz URL

Secret is validated

Quiz page is rendered with Browserless (to execute dynamic JavaScript)

LLM extracts:

Question/instruction

Submit endpoint URL

Answer format

File download URLs

Solver computes answer by:

Scraping referenced pages if required

Downloading and parsing CSV/table files using pandas

Looking up information inside files when needed

Calling LLM for reasoning and final formatting

Answer is submitted to the page's submit URL

If the response provides a new quiz URL, the process repeats until the quiz ends


## Deployment

This project is configured for Hugging Face Spaces (Docker environment recommended).

Environment variables
BROWSERLESS_API_KEY=<browserless key>
DEEPSEEK_API_KEY=<primary LLM key>
AIPIPE_API_KEY=<fallback LLM key>

Install dependencies
pip install -r requirements.txt

Local run
uvicorn app:app --host 0.0.0.0 --port 7860

Project Structure
/app.py           → API entrypoint
/solver.py        → Quiz solving pipeline
/llm_client.py    → DeepSeek + AI-Pipe LLM API wrapper
/requirements.txt → Python dependencies
/Dockerfile       → Deployment config for Hugging Face Spaces

## Security Notes

Only requests with the correct secret are processed

No file writes; everything is executed in memory

No user code execution

## License

This project is licensed under the MIT License.
