import json, asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.agent.workflow import AgentWorkflow, AgentInput, AgentOutput, ToolCall, ToolCallResult

from webapp.config import llm, STATIC_DIR, OLLAMA_MODEL, IMAGE_SERVICE_URL
from webapp.agents import agent1, agent2, agent3, agent4
from webapp.utils import strip_ansi, parse_chunks, generate_diagram_via_service, save_run

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    history: list = []

@router.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")

@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    messages = [ChatMessage(role=MessageRole.SYSTEM, content="Network Design Assistant. Technical and concise.")]
    for h in req.history[-10:]:
        role = MessageRole.USER if h.get("role") == "user" else MessageRole.ASSISTANT
        messages.append(ChatMessage(role=role, content=h.get("content", "")))
    messages.append(ChatMessage(role=MessageRole.USER, content=req.message))
    resp = await llm.achat(messages)
    return {"role": "assistant", "content": str(resp.message.content), "timestamp": datetime.now().isoformat()}

async def _send(ws, **kw):
    await ws.send_text(json.dumps(kw))

async def _run_phase(ws, phase_num, phase_name, agent, initial_msg, model_name=""):
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    history: list[ChatMessage] = []
    msg = initial_msg
    iteration = 0
    while True:
        iteration += 1
        await _send(ws, type="phase_start", phase=phase_num, name=phase_name, iteration=iteration)
        response_text = ""
        try:
            handler = wf.run(user_msg=msg) if not history else wf.run(chat_history=history + [ChatMessage(role=MessageRole.USER, content=msg)])
            async for ev in handler.stream_events():
                if isinstance(ev, AgentInput): await _send(ws, type="agent_input", agent=ev.current_agent_name, model=model_name)
                elif isinstance(ev, ToolCall): await _send(ws, type="tool_call", tool_name=ev.tool_name, tool_kwargs=ev.tool_kwargs)
                elif isinstance(ev, ToolCallResult):
                    out = str(ev.tool_output)
                    if ev.tool_name in ("search_product_specs", "search_across_products"):
                        chunks = parse_chunks(out)
                        await _send(ws, type="rag_result", tool_name=ev.tool_name, chunks=chunks, total=len(chunks))
                    else: await _send(ws, type="tool_result", tool_name=ev.tool_name, output=out)
                elif isinstance(ev, AgentOutput):
                    response_text = str(ev.response)
                    await _send(ws, type="agent_response", agent=ev.current_agent_name, content=response_text)
            resp = await handler
            response_text = str(resp)
        except Exception as e:
            await _send(ws, type="error", message=str(e))
            return ""
        history.append(ChatMessage(role=MessageRole.USER, content=msg))
        history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
        await _send(ws, type="approval_request", phase=phase_num, name=phase_name)
        data = json.loads(await ws.receive_text())
        if data.get("approved"): return response_text
        msg = data.get("feedback", "Please revise.")

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        data = json.loads(await ws.receive_text())
        prompt = data["content"]
        await _send(ws, type="user_echo", content=prompt)
        rephrased = await _run_phase(ws, 1, "Prompt Rephrasing", agent1, prompt, OLLAMA_MODEL)
        topology = await _run_phase(ws, 2, "Network Topology Design", agent2, rephrased, OLLAMA_MODEL)
        devices = await _run_phase(ws, 3, "Device Selection & BOM", agent3, f"Req: {prompt}\nTopo: {topology}", OLLAMA_MODEL)
        diagram_code = await _run_phase(ws, 4, "D2 Diagram Generation", agent4, f"Topo: {topology}\nBOM: {devices}", "qwen3-coder")
        
        await _send(ws, type="phase_start", phase=5, name="Diagram Rendering", iteration=1)
        res = await generate_diagram_via_service(diagram_code)
        url = f"{IMAGE_SERVICE_URL}{res['url']}" if res.get("success") else None
        if url: await _send(ws, type="diagram_ready", url=url)
        
        fp = save_run(prompt, rephrased, topology, devices, diagram_code, url)
        await _send(ws, type="workflow_complete", saved_to=str(fp), diagram_url=url)
    except WebSocketDisconnect: pass
    except Exception as e: await _send(ws, type="error", message=str(e))
