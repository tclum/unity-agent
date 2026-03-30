import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")


def is_llm_available() -> bool:
    return bool(ANTHROPIC_API_KEY)


def get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY missing in .env")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def strip_code_fences(text: str) -> str:
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
    Uses brace-depth counter so nested C# braces don't break extraction.
    """
    text = strip_code_fences(text)

    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object detected in LLM output:\n{text}")

    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    raise ValueError(f"Unbalanced braces in LLM output:\n{text}")


def generate_patch_proposal(
    task_title: str,
    file_path: str,
    file_content: str,
    filtered_log: str = "",
    scene_context: str = "",
    attempt: int = 1,
) -> dict:
    """
    Ask Claude to generate a safe patch proposal for a Unity C# file.

    Returns:
    {
        "diagnosis": str,
        "summary": str,
        "new_content": str
    }
    """
    client = get_client()

    base_system_prompt = """You are a senior Unity engineer specializing in C# game development.

You are generating a SAFE patch proposal for a Unity C# file.

Rules:
- Return VALID JSON only.
- Do NOT wrap JSON in markdown.
- ALWAYS return the COMPLETE file in new_content — every class, method, field, and using statement must be present.
- Never return a partial file, a single method, or a snippet. new_content must be the entire file contents.
- Make the smallest safe change possible to fix the issue.
- Do not use placeholder comments like "// ... rest unchanged" — include ALL code.
- Do not invent APIs that don't exist in Unity.
- Preserve all existing functionality.

Your JSON must contain these exact keys:
diagnosis
summary
new_content"""

    retry_additions = {
        2: "\n\nCRITICAL: Your previous attempt returned an incomplete file. You MUST include every method, field, and using directive from the original file in new_content.",
        3: "\n\nFINAL ATTEMPT: Return the ENTIRE file verbatim with only the single minimal change applied. Do not omit, summarize, or truncate any part of the file.",
    }

    system_prompt = base_system_prompt + retry_additions.get(attempt, "")

    user_prompt = f"""Task:
{task_title}

Target file:
{file_path}

Current file content:
{file_content}

Relevant Unity logs:
{filtered_log}

Relevant scene context:
{scene_context}

Return a JSON object with keys: diagnosis, summary, new_content"""

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    raw_text = message.content[0].text.strip()

    try:
        json_text = extract_json(raw_text)
        return json.loads(json_text)
    except Exception as e:
        raise ValueError(
            f"LLM returned invalid JSON.\n\nFull response:\n{raw_text}"
        ) from e
