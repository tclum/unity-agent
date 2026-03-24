import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")


def is_llm_available() -> bool:
    """
    Check if the LLM can be used (API key present).
    """
    return bool(OPENAI_API_KEY)


def get_client() -> OpenAI:
    """
    Create OpenAI client instance.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY missing in .env")

    return OpenAI(api_key=OPENAI_API_KEY)


def strip_code_fences(text: str) -> str:
    """
    Remove markdown code fences like ```json ... ```
    that models sometimes return.
    """
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def extract_json(text: str) -> str:
    """
    Extract JSON object from model output safely.
    """
    text = strip_code_fences(text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(f"No JSON object detected in LLM output:\n{text}")

    return text[start:end + 1]


def generate_patch_proposal(
    task_title: str,
    file_path: str,
    file_content: str,
    filtered_log: str = "",
    scene_context: str = ""
) -> dict:
    """
    Ask the LLM to generate a safe patch proposal for a Unity C# file.

    Returns:
    {
        "diagnosis": str,
        "summary": str,
        "new_content": str
    }
    """

    client = get_client()

    system_prompt = """
You are a senior Unity engineer.

You are generating a SAFE patch proposal for a Unity C# file.

Rules:
- Return VALID JSON only.
- Do NOT wrap JSON in markdown.
- Preserve unrelated code.
- Make the smallest safe change possible.
- Do not invent APIs that don't exist.

Your JSON must contain:
diagnosis
summary
new_content
"""

    user_prompt = f"""
Task:
{task_title}

Target file:
{file_path}

Current file content:
{file_content}

Relevant Unity logs:
{filtered_log}

Relevant scene context:
{scene_context}

Return JSON with keys:
diagnosis
summary
new_content
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

    raw_text = response.output_text.strip()

    try:
        json_text = extract_json(raw_text)
        return json.loads(json_text)

    except Exception as e:
        raise ValueError(
            f"LLM returned invalid JSON.\n\nFull response:\n{raw_text}"
        ) from e