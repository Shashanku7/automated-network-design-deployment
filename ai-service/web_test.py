"""
Standalone test script for the Firecrawl search tool with an Ollama agent.

Usage:
    python web_test.py
    python web_test.py --query "HPE Aruba CX 6300 PoE budget"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.llms.ollama import Ollama
from llama_index.core.agent.workflow import FunctionAgent, AgentInput, ToolCall, ToolCallResult, AgentOutput

from config import OLLAMA_MODEL, OLLAMA_BASE_URL, OLLAMA_API_KEY
from webapp.app import firecrawl_search_tool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", "-q", default=None,
                        help="Single query to run (omit for interactive mode)")
    parser.add_argument("--model", default=OLLAMA_MODEL,
                        help="Ollama model to use")
    args = parser.parse_args()

    llm = Ollama(
        model=args.model,
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0,
        context_window=262144,
        is_function_calling_model=True,
        headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
    )

    agent = FunctionAgent(
        name="web_searcher",
        description="Can search the web using Firecrawl.",
        system_prompt=(
            "You are a web research agent. You have access to a Firecrawl web search tool.\n"
            "When asked a question, use firecrawl_search to find relevant information, "
            "then answer based on the results."
        ),
        llm=llm,
        tools=[firecrawl_search_tool],
    )

    queries = [args.query] if args.query else []
    if not queries:
        print("Entering interactive mode. Type 'quit' to exit.\n")
        while True:
            try:
                q = input("> ")
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("quit", "exit", "q"):
                break
            queries.append(q)
            # Process one at a time in interactive mode
            _run_agent(agent, queries)
            queries = []
    else:
        _run_agent(agent, queries)


def _run_agent(agent, queries):
    import asyncio
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")
        result = asyncio.run(_run_single(agent, query))
        print(result)


async def _run_single(agent, query):
    from llama_index.core.agent.workflow import AgentWorkflow
    from llama_index.core.llms import ChatMessage, MessageRole

    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=300.0)
    handler = wf.run(user_msg=query)

    async for ev in handler.stream_events():
        if isinstance(ev, AgentInput):
            print(f"[Agent: {ev.current_agent_name}]")
        elif isinstance(ev, ToolCall):
            print(f"\n[Tool Call: {ev.tool_name}]")
            print(f"  Args: {ev.tool_kwargs}")
        elif isinstance(ev, ToolCallResult):
            out = str(ev.tool_output)
            print(f"\n[Tool Result: {ev.tool_name}]")
            print(f"  Output ({len(out)} chars):")
            print(f"  {out[:1500]}")
        elif isinstance(ev, AgentOutput):
            print(f"\n[Agent Response]")
            print(ev.response)

    resp = await handler
    return str(resp)


if __name__ == "__main__":
    main()
