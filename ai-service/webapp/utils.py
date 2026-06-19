"""Utility functions for the AI service."""

import re
import json
from datetime import datetime
from pathlib import Path

from webapp.config import OUTPUT_DIR, IMAGE_SERVICE_URL, OLLAMA_MODEL


def _strip_ansi(t):
    return re.sub(r"\033\[[0-9;]*m", "", t)


def _parse_chunks(raw):
    chunks = []
    pattern_ranked = r"--- (?:.*?)Chunk (\d+)(?: \(score: ([\d.]+)\))? ---\nSource: (.+?)\n(.*?)(?=--- (?:.*?)Chunk |\Z)"
    for m in re.finditer(pattern_ranked, raw, re.DOTALL):
        chunks.append({
            "index": int(m.group(1)),
            "score": float(m.group(2)) if m.group(2) else 0.0,
            "source": m.group(3).strip(),
            "text": m.group(4).strip()[:500],
        })
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


async def _generate_diagram_via_service(diagram_code: str) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{IMAGE_SERVICE_URL}/api/generate-diagram",
            json={"diagram_code": diagram_code},
        )
        resp.raise_for_status()
        return resp.json()


def _format_tool_events(events: list[dict]) -> str:
    if not events:
        return "_(no tool calls)_\n"
    lines: list[str] = []
    for ev in events:
        name = ev.get("tool_name", "?")
        inp = ev.get("input", "")
        out = ev.get("output", "")
        lines.append(f"### {name}\n")
        lines.append(f"**Input:**\n```\n{inp}\n```\n")
        lines.append(f"**Output:**\n```\n{_strip_ansi(out)}\n```\n")
    return "\n".join(lines)


def _save(prompt, rephrased, topology, devices, diagram_code="", diagram_url=None,
          tools_1=None, tools_2=None, tools_3=None, tools_4=None, tools_5=None,
          cli_config=""):
    ts = datetime.now()
    fp = OUTPUT_DIR / f"{ts:%Y-%m-%d_%H-%M-%S}_run.md"
    content = (
        f"# Network Automation Run\n\n**Date:** {ts:%Y-%m-%d %H:%M:%S}  \n"
        f"**Model:** {OLLAMA_MODEL}\n\n---\n\n## User Prompt\n\n{prompt}\n\n---\n\n"
        f"## Phase 1: Rephrased Prompt\n\n{_strip_ansi(rephrased)}\n\n---\n\n"
        f"## Phase 2: Network Topology\n\n{_strip_ansi(topology)}\n\n---\n\n"
        f"## Phase 3: Device Selection & BOM\n\n{_strip_ansi(devices)}\n\n---\n\n"
        f"## Phase 4: Topology Code\n\n```\n{_strip_ansi(diagram_code)}\n```\n"
    )
    if diagram_url:
        content += f"\n---\n\n## Topology Diagram\n\nGenerated diagram: `{diagram_url}`\n"
    if cli_config:
        content += f"\n---\n\n## Phase 5: CLI Configuration\n\n{_strip_ansi(cli_config)}\n"
    fp.write_text(content, encoding="utf-8")
    return fp
