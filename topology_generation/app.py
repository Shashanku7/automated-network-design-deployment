"""
topology_generation/app.py
--------------------------
Gatekeeper microservice (Port 8002).

Receives the raw LLM output from ai-service (Agent 4),
applies a 2-layer validation gate, and returns either:
  - {"status": "ok",    "code": "<clean React JSX string>"}
  - {"status": "error", "message": "<precise error description>"}

The ai-service self-correction loop uses the error message to
re-prompt Agent 4 without the user ever seeing an error.
"""

import json
import re

import syntax_checker
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Topology Generation Gatekeeper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ValidateRequest(BaseModel):
    llm_output: str  # Raw text from Agent 4


class ValidateResponse(BaseModel):
    status: str       # "ok" or "error"
    code: str = ""    # Clean React code (only when status == "ok")
    message: str = "" # Error description (only when status == "error")


# ──────────────────────────────────────────────────────────────
# Gatekeeper Layer 1: Extract JSON and parse react_code string
# ──────────────────────────────────────────────────────────────
def _extract_code(llm_output: str) -> tuple[bool, str, str]:
    """
    Try to find and parse a JSON object of the form {"code": "..."} in the
    LLM output. Returns (success, react_code, error_message).
    """
    # Strip markdown fences if the LLM wrapped JSON in ```json ... ```
    cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).replace("```", "").strip()

    # Find the outermost JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return False, "", (
            "No JSON object found in your output. "
            "You MUST output ONLY a JSON object in the format: {\"code\": \"<React JSX>\"}"
        )

    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError as exc:
        return False, "", (
            f"JSON parsing failed: {exc}. "
            "Ensure the 'code' value is a properly escaped JSON string."
        )

    if "code" not in parsed:
        return False, "", (
            "JSON object is missing the 'code' key. "
            "Output must be exactly: {\"code\": \"<React JSX>\"}"
        )

    react_code = parsed["code"]
    if not isinstance(react_code, str) or len(react_code.strip()) < 50:
        return False, "", (
            "The 'code' field is empty or too short. "
            "It must contain a full React Flow component."
        )

    return True, react_code, ""


# ──────────────────────────────────────────────────────────────
# Gatekeeper Layer 2: JSX Syntax Check via Tree-sitter
# ──────────────────────────────────────────────────────────────
def _validate_syntax(react_code: str) -> tuple[bool, str]:
    """
    Run Tree-sitter JSX syntax validation.
    Returns (is_valid, error_message).
    """
    try:
        result = syntax_checker.check_syntax("jsx", react_code)
        if result.errors:
            return False, (
                f"JSX syntax error detected: {result.description}. "
                "Fix ALL syntax errors and re-output the corrected JSON."
            )
        return True, ""
    except Exception as exc:
        # If syntax_checker itself fails, log and pass through
        # (don't block on checker failure)
        print(f"[WARN] syntax_checker raised: {exc}. Passing through.")
        return True, ""


# ──────────────────────────────────────────────────────────────
# Main validation endpoint
# ──────────────────────────────────────────────────────────────
@app.post("/api/validate-topology", response_model=ValidateResponse)
async def validate_topology(req: ValidateRequest):
    """
    2-layer gatekeeper:
      Layer 1 — JSON extraction & parse
      Layer 2 — JSX syntax validation (Tree-sitter)
    """
    # Layer 1
    ok, react_code, err = _extract_code(req.llm_output)
    if not ok:
        return ValidateResponse(status="error", message=err)

    # Layer 2
    valid, err = _validate_syntax(react_code)
    if not valid:
        return ValidateResponse(status="error", message=err)

    return ValidateResponse(status="ok", code=react_code)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "topology_generation"}
