# LocalForge Coach

Local-first interview answer coach that runs a multi-step pipeline with Ollama.

## Quick start (backend)

1. Create local prompts folder (not committed):

```
mkdir -p prompts_local
```

2. Add the prompt files listed in `prompts_local/` (see below).

3. Set environment variables:

```
export PROMPTS_DIR="$(pwd)/prompts_local"
```

4. Install deps and run API:

```
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

## Frontend

Once the API is running, open:

- `http://127.0.0.1:8000/` (or your chosen port)

The frontend uses the same FastAPI server and calls `/api/*` directly.

## Prompt files (local-only)

These are required in `prompts_local/`:

- `step1_question_analysis.txt`
- `step2_jd_analysis.txt`
- `step3_resume_analysis.txt`
- `step4_answer.txt`
- `step5_custom_transform.txt`
- `step6_judge.txt`
- `step2_jd_analysis_retry.txt`

Prompts are formatted with Python `.format()` placeholders like `{question}` and `{jd_text}`.
If you need literal `{` or `}`, escape them as `{{` and `}}`.

Expected placeholders by file:

- `step1_question_analysis.txt`: `{question}`
- `step2_jd_analysis.txt`: `{jd_text}`
- `step2_jd_analysis_retry.txt`: `{jd_text}`, `{critique}`
- `step3_resume_analysis.txt`: `{resume_text}`
- `step4_answer.txt`: `{question}`, `{jd_text}`, `{resume_text}`, `{step1_json}`, `{step2_json}`, `{step3_json}`
- `step5_custom_transform.txt`: `{custom_prompt_text}`, `{draft_answer}`, `{evidence_map}`
- `step6_judge.txt`: `{question}`, `{jd_text}`, `{resume_text}`, `{final_output}`, `{step1_json}`, `{step2_json}`, `{step3_json}`, `{judge_strictness}`

## API

- `POST /api/run`
- `GET /api/run/{run_id}`
- `GET /api/models`

The API stores runs in memory for now.
