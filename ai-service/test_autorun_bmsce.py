"""
Auto-run the full workflow via WebSocket with test data.
Sends a campus prompt, auto-approves all 4 phases, and prints results.

Usage:
    python test_autorun.py                 # default test data
    python test_autorun.py --prompt "..."   # custom prompt
"""

import asyncio
import json
import argparse
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

# ── ANSI colors ──
C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"
M = "\033[95m"; B = "\033[1m"; D = "\033[2m"; RST = "\033[0m"

TEST_PROMPT = """Design a campus network for the BMS College of Engineering (BMSCE) utilizing 3 of its primary academic blocks. Across these buildings, there are approximately 1,900 students/visitors, 205 staff/faculty, 22 administrators, 48 VOIP phones, 17 IPTV devices, and 12 printers.

## Building & Department Breakdown

### Building 1: PG Block (3 departments)
| Department | Floor No. | Students | Staff | Admins | VOIP Phones | IPTV Devices | Printers |
|------------|-----------|----------|-------|--------|-------------|--------------|----------|
| BMSCE Data Center & Admin | 1 | 20 | 15 | 5 | 8 | 2 | 4 |
| Master of Computer Applications (MCA) | 2 | 200 | 20 | 2 | 5 | 2 | 3 |
| Management Studies and Research Centre | 3 | 180 | 15 | 2 | 4 | 1 | 2 |
| **Total** | | **400** | **50** | **9** | **17** | **5** | **9** |

### Building 2: New Academic Block (3 departments)
| Department | Floor No. | Students | Staff | Admins | VOIP Phones | IPTV Devices | Printers |
|------------|-----------|----------|-------|--------|-------------|--------------|----------|
| Central Library & Reading Room | 1 | 300 | 15 | 2 | 4 | 2 | 1 |
| CSE, AI & Data Science (AI & DS) | 2 | 400 | 40 | 3 | 8 | 4 | 5 |
| Electronics & Communication Engg (ECE) | 3 | 300 | 35 | 2 | 6 | 3 | 4 |
| **Total** | | **1000** | **90** | **7** | **18** | **9** | **10** |

### Building 3: Core Engineering Block (3 departments)
| Department | Floor No. | Students | Staff | Admins | VOIP Phones | IPTV Devices | Printers |
|------------|-----------|----------|-------|--------|-------------|--------------|----------|
| Mechanical Engg & Workshops | 1 | 200 | 25 | 2 | 5 | 1 | 2 |
| Civil & Environmental Engg Labs | 2 | 150 | 20 | 2 | 4 | 1 | 1 |
| Chemical Engg & Bio-Technology | 3 | 150 | 20 | 2 | 4 | 1 | 1 |
| **Total** | | **500** | **65** | **6** | **13** | **3** | **4** |
"""


async def autorun(ws_url: str, prompt: str):
    print(f"\n{C}{B}{'━' * 70}")
    print(f"  🚀  AUTO-RUN WORKFLOW")
    print(f"{'━' * 70}{RST}")
    print(f"  {D}WebSocket:{RST} {ws_url}")
    print(f"  {D}Time:{RST}      {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  {D}Prompt:{RST}    {prompt[:80]}...\n")

    results = {}
    current_phase = 0

    async with websockets.connect(ws_url, max_size=10 * 1024 * 1024, ping_interval=30, ping_timeout=120) as ws:
        # Send the prompt
        await ws.send(json.dumps({"content": prompt}))
        print(f"  {G}✓ Prompt sent{RST}\n")

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=600)
                data = json.loads(raw)
                event_type = data.get("type", "")

                if event_type == "user_echo":
                    print(f"  {D}[echo] Prompt received by server{RST}")

                elif event_type == "phase_start":
                    current_phase = data.get("phase", 0)
                    name = data.get("name", "")
                    iteration = data.get("iteration", 1)
                    print(f"\n{Y}{B}  ▸ Phase {current_phase}: {name} (iteration {iteration}){RST}")

                elif event_type == "agent_input":
                    agent = data.get("agent", "")
                    print(f"    {D}Agent: {agent} | Model: {data.get('model', '?')}{RST}")

                elif event_type == "tool_call":
                    tool = data.get("tool_name", "")
                    tool_input = data.get("input", {})
                    print(f"    {R}🔧 Tool call: {tool}{RST}")
                    if tool_input and tool_input != {".no_value.": ""}:
                        try:
                            input_str = json.dumps(tool_input, indent=4)
                            indented = "\n".join(f"      {line}" for line in input_str.splitlines())
                            print(f"    {D}Input:{RST}\n{indented}")
                        except Exception:
                            pass

                elif event_type == "tool_result":
                    tool = data.get("tool_name", "")
                    result_data = data.get("result", "")
                    output_data = data.get("output", "")
                    full_result = result_data if result_data else output_data
                    print(f"    {R}📋 Tool result: {tool}{RST}")
                    try:
                        if isinstance(full_result, (dict, list)):
                            result_str = json.dumps(full_result, indent=4)
                        else:
                            result_str = str(full_result)
                        result_str = result_str.replace("\\n", "\n").replace("\\t", "\t")
                        for line in result_str.splitlines():
                            print(f"      {line}")
                    except Exception as e:
                        print(f"      Error printing result: {e}")

                elif event_type == "agent_response":
                    agent = data.get("agent", "")
                    content = data.get("content", "")
                    if content.startswith("assistant: "):
                        content = content[11:]
                    results[current_phase] = content
                    preview = content[:150].replace("\n", " ")
                    print(f"    {G}💬 {agent}: {preview}...{RST}")

                elif event_type == "approval_request":
                    phase = data.get("phase", current_phase)
                    name = data.get("name", "")
                    print(f"\n    {G}{B}✅ AUTO-APPROVING Phase {phase}: {name}{RST}")
                    await ws.send(json.dumps({"approved": True}))

                elif event_type == "phase_approved":
                    print(f"    {G}✓ Phase {data.get('phase', '?')} approved{RST}")

                elif event_type == "diagram_ready":
                    url = data.get("url", "")
                    print(f"\n    {M}{B}🖼️  Diagram ready: {url}{RST}")
                    results["diagram_url"] = url

                elif event_type == "diagram_error":
                    msg = data.get("message", "")
                    d2 = data.get("diagram_code", "")
                    print(f"\n    {R}⚠️  Diagram error: {msg}{RST}")
                    if d2:
                        print(f"\n    {Y}Raw D2 code sent to kroki:{RST}")
                        print(f"    {Y}{'─' * 60}{RST}")
                        for line in d2.splitlines():
                            print(f"    {D}{line}{RST}")
                        print(f"    {Y}{'─' * 60}{RST}")
                        print(f"    {Y}Paste into https://play.d2lang.com/ to debug{RST}")

                elif event_type == "workflow_complete":
                    saved = data.get("saved_to", "")
                    diagram = data.get("diagram_url", "")
                    print(f"\n{G}{B}{'━' * 70}")
                    print(f"  🎉  WORKFLOW COMPLETE!")
                    print(f"{'━' * 70}{RST}")
                    print(f"  {D}Saved to:{RST} {saved}")
                    if diagram:
                        print(f"  {D}Diagram:{RST}  {diagram}")
                    print()
                    break

                elif event_type == "error":
                    msg = data.get("message", "Unknown error")
                    print(f"\n  {R}{B}❌ ERROR: {msg}{RST}\n")
                    break

            except asyncio.TimeoutError:
                print(f"\n  {R}⏰ Timeout waiting for response (600s){RST}")
                break

    # Print summary
    print(f"\n{C}{B}{'━' * 70}")
    print(f"  📋  RESULTS SUMMARY")
    print(f"{'━' * 70}{RST}")
    phase_names = {1: "Rephrased Prompt", 2: "Topology Design", 3: "Device Selection & BOM", 4: "D2 Diagram Code"}
    for phase_num, name in phase_names.items():
        if phase_num in results:
            length = len(results[phase_num])
            print(f"\n  {Y}{B}Phase {phase_num}: {name}{RST} ({length} chars)")
            lines = results[phase_num].split("\n")[:5]
            for line in lines:
                print(f"    {D}{line}{RST}")
            if len(results[phase_num].split("\n")) > 5:
                print(f"    {D}... ({len(results[phase_num].split(chr(10)))} lines total){RST}")

    if "diagram_url" in results:
        print(f"\n  {M}{B}Diagram URL:{RST} {results['diagram_url']}")

    print(f"\n{G}{B}Done!{RST}\n")


def main():
    parser = argparse.ArgumentParser(description="Auto-run the network design workflow with test data")
    parser.add_argument("--prompt", type=str, default=TEST_PROMPT, help="Custom prompt to send")
    parser.add_argument("--host", type=str, default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    ws_url = f"ws://{args.host}:{args.port}/ws"
    asyncio.run(autorun(ws_url, args.prompt))


if __name__ == "__main__":
    main()
