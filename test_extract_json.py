"""
Test suite for extract_json in core/llm_client.py.
Run from the unity-agent root:
    python test_extract_json.py
"""

import sys
import json
sys.path.insert(0, ".")

from core.llm_client import extract_json


def run(name: str, raw: str, expect_keys: list[str] = None, should_fail: bool = False):
    try:
        result = json.loads(extract_json(raw))
        if should_fail:
            print(f"  FAIL  {name} — expected failure but got: {result}")
            return False
        if expect_keys:
            missing = [k for k in expect_keys if k not in result]
            if missing:
                print(f"  FAIL  {name} — missing keys: {missing}")
                return False
        print(f"  PASS  {name}")
        return True
    except Exception as e:
        if should_fail:
            print(f"  PASS  {name} (correctly raised: {e})")
            return True
        print(f"  FAIL  {name} — unexpected error: {e}")
        return False


tests_passed = 0
tests_total = 0

def test(name, raw, expect_keys=None, should_fail=False):
    global tests_passed, tests_total
    tests_total += 1
    if run(name, raw, expect_keys, should_fail):
        tests_passed += 1


# --- Basic cases ---

test(
    "Simple JSON",
    '{"diagnosis": "null ref", "summary": "fix it", "new_content": "void Awake() {}"}',
    expect_keys=["diagnosis", "summary", "new_content"]
)

test(
    "JSON wrapped in markdown fences",
    '```json\n{"diagnosis": "x", "summary": "y", "new_content": "z"}\n```',
    expect_keys=["diagnosis", "summary", "new_content"]
)

test(
    "JSON with prose before it",
    'Here is the patch:\n{"diagnosis": "x", "summary": "y", "new_content": "z"}',
    expect_keys=["diagnosis", "summary", "new_content"]
)

# --- The real bug: C# code with nested braces in new_content ---

test(
    "C# string interpolation in new_content",
    r'''{"diagnosis": "stale panel", "summary": "reset text", "new_content": "public void ShowResults(List<PlayerState> players)\n{\n    if (TitleText != null)\n        TitleText.text = string.Empty;\n    Debug.Log($\"[ResultsUI] ShowResults on {gameObject.name}\");\n}"}''',
    expect_keys=["diagnosis", "summary", "new_content"]
)

test(
    "Multiple C# methods with nested braces",
    r'''{"diagnosis": "d", "summary": "s", "new_content": "void Awake() {\n    Debug.Log($\"Hello {name}\");\n    Hide();\n}\n\nvoid Hide() {\n    if (panel != null) { panel.SetActive(false); }\n}"}''',
    expect_keys=["diagnosis", "summary", "new_content"]
)

test(
    "C# with deeply nested braces",
    r'''{"diagnosis": "d", "summary": "s", "new_content": "void Show() {\n    if (x) {\n        if (y) {\n            foreach (var p in players) {\n                Debug.Log($\"{p.name}\");\n            }\n        }\n    }\n}"}''',
    expect_keys=["diagnosis", "summary", "new_content"]
)

# --- Error cases ---

test(
    "No JSON at all",
    "Sorry, I cannot generate a patch for this file.",
    should_fail=True
)

test(
    "Unbalanced braces",
    '{"diagnosis": "x", "summary": "y", "new_content": "void Foo() {",',
    should_fail=True
)

# --- Summary ---
print()
print(f"Results: {tests_passed}/{tests_total} passed")
if tests_passed == tests_total:
    print("All tests passed. extract_json is working correctly.")
else:
    print("Some tests failed — check output above.")
    sys.exit(1)
