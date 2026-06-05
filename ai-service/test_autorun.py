"""
Auto-run the full workflow via WebSocket with test data.
Sends a campus prompt, auto-approves all 4 phases, and prints results.

Usage:
    python test_autorun.py                  # default test data
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

TEST_PROMPT = """Design a campus network for an organization with 2 building(s). Across all buildings, there are approximately 620 students/visitors, 65 staff/faculty, 8 administrators, 18 VOIP phones, and 6 IPTV devices.

## Building & Floor Breakdown

### Building 1: Main Academic Block (3 floors)
| Floor | Department / Name | Students | Staff | Admins | VOIP Phones | IPTV Devices |
|-------|-------------------|----------|-------|--------|-------------|--------------|
| 1 | Administration & Reception | 20 | 15 | 3 | 6 | 2 |
| 2 | Computer Science Dept | 200 | 20 | 2 | 5 | 2 |
| 3 | Electronics Dept | 150 | 12 | 1 | 4 | 1 |
| **Total** | | **370** | **47** | **6** | **15** | **5** |

### Building 2: Library & Research (2 floors)
| Floor | Department / Name | Students | Staff | Admins | VOIP Phones | IPTV Devices |
|-------|-------------------|----------|-------|--------|-------------|--------------|
| 1 | Main Library | 200 | 10 | 1 | 2 | 1 |
| 2 | Research Labs | 50 | 8 | 1 | 1 | 0 |
| **Total** | | **250** | **18** | **2** | **3** | **1** |

Devices needed: laptops, printers, phones, cameras, wifi.
Sensitive areas requiring extra security: server, library.
Special roles to consider: Principal, Finance Head.
Uptime requirement: important.
Expecting growth of 50-200.
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
                    print(f"    {R}🔧 Tool call: {tool}{RST}")

                elif event_type == "rag_result":
                    total = data.get("total", 0)
                    print(f"    {M}📚 RAG: {total} chunks retrieved{RST}")

                elif event_type == "tool_result":
                    tool = data.get("tool_name", "")
                    print(f"    {R}📋 Tool result: {tool}{RST}")

                elif event_type == "agent_response":
                    agent = data.get("agent", "")
                    content = data.get("content", "")
                    # Strip "assistant: " prefix
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
                    print(f"\n    {R}⚠️  Diagram warning: {msg}{RST}")

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
            # Show first 5 lines
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
