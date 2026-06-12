import re, json, os
from datetime import datetime
from webapp.config import OUTPUT_DIR, IMAGE_SERVICE_URL, OLLAMA_MODEL

def strip_ansi(t):
    return re.sub(r"\033\[[0-9;]*m", "", t)

def parse_chunks(raw):
    chunks = []
    # Pattern 1: Product-specific
    pattern_ranked = r"--- (?:.*?)Chunk (\d+)(?: \(score: ([\d.]+)\))? ---\nSource: (.+?)\n(.*?)(?=--- (?:.*?)Chunk |\Z)"
    for m in re.finditer(pattern_ranked, raw, re.DOTALL):
        chunks.append({
            "index": int(m.group(1)),
            "score": float(m.group(2)) if m.group(2) else 0.0,
            "source": m.group(3).strip(),
            "text": m.group(4).strip()[:500],
        })
    # Pattern 2: Cross-product
    if not chunks:
        pattern_cross = r"--- Chunk (\d+) \[(.+?)\](?: \(score: ([\d.]+)\))? ---\nSource: (.+?)\n(.*?)(?=--- Chunk |\Z)"
        for m in re.finditer(pattern_cross, raw, re.DOTALL):
            chunks.append({
                "index": int(m.group(1)),
                "score": float(m.group(3)) if m.group(3) else 0.0,
                "source": f"[{m.group(2)}] {m.group(4).strip()}",
                "text": m.group(5).strip()[:500],
            })
    return chunks

async def generate_diagram_via_service(diagram_code: str) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{IMAGE_SERVICE_URL}/api/generate-diagram",
            json={"diagram_code": diagram_code},
        )
        resp.raise_for_status()
        return resp.json()

def save_run(prompt, rephrased, topology, devices, diagram_code="", diagram_url=None):
    ts = datetime.now()
    fp = OUTPUT_DIR / f"{ts:%Y-%m-%d_%H-%M-%S}_run.md"
    content = (
        f"# Network Automation Run\n\n**Date:** {ts:%Y-%m-%d %H:%M:%S}  \n"
        f"**Model:** {OLLAMA_MODEL}\n\n---\n\n## User Prompt\n\n{prompt}\n\n---\n\n"
        f"## Phase 1: Rephrased Prompt\n\n{strip_ansi(rephrased)}\n\n---\n\n"
        f"## Phase 2: Network Topology\n\n{strip_ansi(topology)}\n\n---\n\n"
        f"## Phase 3: Device Selection & BOM\n\n{strip_ansi(devices)}\n\n---\n\n"
        f"## Phase 4: D2 Diagram Code\n\n```d2\n{strip_ansi(diagram_code)}\n```\n"
    )
    if diagram_url:
        content += f"\n---\n\n## Topology Diagram\n\nGenerated diagram: `{diagram_url}`\n"
    fp.write_text(content, encoding="utf-8")
    return fp
