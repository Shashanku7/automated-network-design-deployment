import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.agent.workflow import AgentWorkflow, AgentInput, AgentOutput, ToolCall, ToolCallResult

from webapp.config import llm, STATIC_DIR, OLLAMA_MODEL, IMAGE_SERVICE_URL
from webapp.agents import agent1, agent2, agent3, agent4
from webapp.utils import strip_ansi, parse_chunks, generate_diagram_via_service, generate_topology_code, save_run
from webapp.kafka_provider import kafka_provider

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list = []


# Global state for task tracking (for demonstration, better to use Redis/DB for real persistence)
active_tasks = {}


async def process_kafka_task(task_data: dict):
    project_id = task_data.get("project_id")
    task_id = task_data.get("task_id")
    content = task_data.get("input_context")

    # Handle Resume/Feedback
    if task_id in active_tasks:
        active_tasks[task_id]["feedback_queue"].put_nowait(task_data)
        return

    # Start new workflow
    asyncio.create_task(run_kafka_workflow(task_data))


async def run_kafka_workflow(task_data: dict):
    project_id = task_data.get("project_id")
    task_id = task_data.get("task_id")
    prompt = task_data.get("input_context")

    feedback_queue = asyncio.Queue()
    active_tasks[task_id] = {"feedback_queue": feedback_queue}

    try:
        await _send_kafka(project_id, task_id, "token", content=f"Echo: {prompt}")

        rephrased = await _run_phase_kafka(project_id, task_id, 1, "Prompt Rephrasing", agent1, prompt, feedback_queue, OLLAMA_MODEL)
        topology = await _run_phase_kafka(project_id, task_id, 2, "Network Topology Design", agent2, rephrased, feedback_queue, OLLAMA_MODEL)
        devices = await _run_phase_kafka(project_id, task_id, 3, "Device Selection & BOM", agent3, f"Req: {prompt}\nTopo: {topology}", feedback_queue, OLLAMA_MODEL)
        diagram_code = await _run_phase_kafka(project_id, task_id, 4, "D2 Diagram Generation", agent4, f"Topo: {topology}\nBOM: {devices}", feedback_queue, "qwen3-coder")

        res = await generate_diagram_via_service(diagram_code)
        url = f"{IMAGE_SERVICE_URL}{res['url']}" if res.get(
            "success") else None

        if url:
            await _send_kafka(project_id, task_id, "final_answer", content=f"Diagram ready: {url}", payload={"diagram_url": url})

        save_run(prompt, rephrased, topology, devices, diagram_code, url)
        await _send_kafka(project_id, task_id, "final_answer", content="Workflow complete.", is_final=True)

    except Exception as e:
        await _send_kafka(project_id, task_id, "error", content=str(e))
    finally:
        active_tasks.pop(task_id, None)


async def _send_kafka(project_id, task_id, event_type, content=None, payload=None, is_final=False):
    event = {
        "project_id": project_id,
        "task_id": task_id,
        "agent_name": "ai-service",
        "event_type": event_type,
        "data": content,
        "payload": payload,
        "is_final": is_final
    }
    await kafka_provider.send_event(event)


async def _run_phase_kafka(project_id, task_id, phase_num, phase_name, agent, initial_msg, feedback_queue, model_name=""):
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    history: list[ChatMessage] = []
    msg = initial_msg

    while True:
        await _send_kafka(project_id, task_id, "token", content=f"Starting Phase {phase_num}: {phase_name}")
        response_text = ""
        handler = wf.run(user_msg=msg) if not history else wf.run(
            chat_history=history + [ChatMessage(role=MessageRole.USER, content=msg)])

        async for ev in handler.stream_events():
            if isinstance(ev, AgentInput):
                await _send_kafka(project_id, task_id, "token", content=f"Agent {ev.current_agent_name} running...")
            elif isinstance(ev, ToolCall):
                await _send_kafka(project_id, task_id, "tool_call", content=ev.tool_name, payload=ev.tool_kwargs)
            elif isinstance(ev, ToolCallResult):
                await _send_kafka(project_id, task_id, "tool_result", content=ev.tool_name, payload={"output": str(ev.tool_output)})

        resp = await handler
        response_text = str(resp)
        history.append(ChatMessage(role=MessageRole.USER, content=msg))
        history.append(ChatMessage(
            role=MessageRole.ASSISTANT, content=response_text))

        # Approval request via Kafka (Gateway/Frontend must handle this as a task requiring response)
        await _send_kafka(project_id, task_id, "final_answer", content=f"Phase {phase_num} complete. Awaiting approval.", payload={"phase": phase_num, "awaiting_approval": True})

        # Wait for feedback via Kafka
        feedback_task = await feedback_queue.get()
        # Kafka task data matches AgentTask schema. Use history or content for feedback.
        # Check for approval in content or specific field if schema updated.
        content = feedback_task.get("input_context", "").lower()
        approved = "approved" in content or feedback_task.get(
            "approved", False)

        if approved:
            return response_text
        msg = feedback_task.get("input_context", "Please revise.")


@router.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    messages = [ChatMessage(
        role=MessageRole.SYSTEM, content="Network Design Assistant. Technical and concise.")]
    for h in req.history[-10:]:
        role = MessageRole.USER if h.get(
            "role") == "user" else MessageRole.ASSISTANT
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
            handler = wf.run(user_msg=msg) if not history else wf.run(
                chat_history=history + [ChatMessage(role=MessageRole.USER, content=msg)])
            async for ev in handler.stream_events():
                if isinstance(ev, AgentInput):
                    await _send(ws, type="agent_input", agent=ev.current_agent_name, model=model_name)
                elif isinstance(ev, ToolCall):
                    await _send(ws, type="tool_call", tool_name=ev.tool_name, tool_kwargs=ev.tool_kwargs)
                elif isinstance(ev, ToolCallResult):
                    out = str(ev.tool_output)
                    if ev.tool_name in ("search_product_specs", "search_across_products"):
                        chunks = parse_chunks(out)
                        await _send(ws, type="rag_result", tool_name=ev.tool_name, chunks=chunks, total=len(chunks))
                    else:
                        await _send(ws, type="tool_result", tool_name=ev.tool_name, output=out)
                elif isinstance(ev, AgentOutput):
                    response_text = str(ev.response)
                    await _send(ws, type="agent_response", agent=ev.current_agent_name, content=response_text)
            resp = await handler
            response_text = str(resp)
        except Exception as e:
            await _send(ws, type="error", message=str(e))
            return ""
        history.append(ChatMessage(role=MessageRole.USER, content=msg))
        history.append(ChatMessage(
            role=MessageRole.ASSISTANT, content=response_text))
        await _send(ws, type="approval_request", phase=phase_num, name=phase_name)
        data = json.loads(await ws.receive_text())
        if data.get("approved"):
            return response_text
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
        # ── Phase 4: React Topology Generation ─────────────────────────────
        # Agent 4 generates React Flow code. The gatekeeper validates it.
        # On validation failure, we feed the error back to Agent 4 and retry
        # silently (user only sees the phase spinner, never a crash screen).
        MAX_CORRECTION_ATTEMPTS = 3
        react_code = None
        phase4_msg = f"Topo: {topology}\nBOM: {devices}"

        for attempt in range(MAX_CORRECTION_ATTEMPTS):
            raw_output = await _run_phase(
                ws, 4, "React Topology Generation", agent4, phase4_msg, "qwen2.5-coder"
            )
            if not raw_output:
                break

            # Send to gatekeeper
            try:
                gate_result = await generate_topology_code(raw_output)
            except Exception as gate_err:
                await _send(ws, type="error", message=f"Gatekeeper unreachable: {gate_err}")
                break

            if gate_result.get("status") == "ok":
                react_code = gate_result["code"]
                await _send(ws, type="topology_code_ready", code=react_code)
                break
            else:
                # Self-correction: inject error back as the next prompt for Agent 4
                error_msg = gate_result.get(
                    "message", "Unknown validation error.")
                phase4_msg = (
                    f"Your previous React code had a validation error:\n{error_msg}\n\n"
                    f"Original context:\nTopo: {topology}\nBOM: {devices}\n\n"
                    "Please fix the error and output the corrected JSON."
                )
                if attempt == MAX_CORRECTION_ATTEMPTS - 1:
                    await _send(ws, type="error", message=f"Topology generation failed after {MAX_CORRECTION_ATTEMPTS} attempts: {error_msg}")

        fp = save_run(prompt, rephrased, topology, devices)
        await _send(ws, type="workflow_complete", saved_to=str(fp))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await _send(ws, type="error", message=str(e))
