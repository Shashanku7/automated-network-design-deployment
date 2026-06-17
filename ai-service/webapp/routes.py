import json
import asyncio
import re
import logging
from datetime import datetime
from pathlib import Path
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

# ──────────────────────────────────────────────────────────────
# Observability: Dedicated Log Configuration
# ──────────────────────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "agent4.log"

DEBUG_DIR = Path(__file__).resolve().parent.parent / "temp_debug"
DEBUG_DIR.mkdir(exist_ok=True)

def debug_log_io(phase_num, phase_name, iteration, input_msg, output_msg, extra_code="", run_id="default_run"):
    ts = f"{datetime.now():%H-%M-%S}"
    try:
        run_dir = DEBUG_DIR / run_id
        run_dir.mkdir(exist_ok=True)
        prefix = f"phase{phase_num}_{phase_name.replace(' ', '_')}_iter{iteration}_{ts}"
        with open(run_dir / f"{prefix}_input.txt", "w", encoding="utf-8") as f:
            f.write(input_msg)
        with open(run_dir / f"{prefix}_output.txt", "w", encoding="utf-8") as f:
            f.write(output_msg)
        if extra_code:
            with open(run_dir / f"{prefix}_react_code.jsx", "w", encoding="utf-8") as f:
                f.write(extra_code)
    except Exception as e:
        logger.error(f"Failed to write debug log: {e}")

logger = logging.getLogger("agent4_logger")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    # File Handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class ChatRequest(BaseModel):
    message: str
    history: list = []
    screenContext: str = ""


# Global state for task tracking
active_tasks = {}


async def process_kafka_task(task_data: dict):
    project_id = task_data.get("projectId") or task_data.get("project_id")
    task_id = task_data.get("taskId") or task_data.get("task_id")
    
    # Handle Resume/Feedback
    if task_id in active_tasks:
        active_tasks[task_id]["feedback_queue"].put_nowait(task_data)
        return

    # Start new workflow
    asyncio.create_task(run_kafka_workflow(task_data))


class KafkaSender:
    def __init__(self, project_id, task_id):
        self.project_id = project_id
        self.task_id = task_id
    
    async def send_text(self, text: str):
        data = json.loads(text)
        await _send_kafka(self.project_id, self.task_id, **data)
        
    async def receive_text(self) -> str:
        feedback_task = await active_tasks[self.task_id]["feedback_queue"].get()
        return json.dumps({
            "approved": feedback_task.get("approved", False), 
            "feedback": feedback_task.get("feedback", "Please revise.")
        })

async def run_kafka_workflow(task_data: dict):
    project_id = task_data.get("projectId") or task_data.get("project_id")
    task_id = task_data.get("taskId") or task_data.get("task_id")
    prompt = task_data.get("inputContext") or task_data.get("input_context") or task_data.get("content")

    feedback_queue = asyncio.Queue()
    active_tasks[task_id] = {"feedback_queue": feedback_queue}
    run_id = f"run_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    
    ws = KafkaSender(project_id, task_id)

    try:
        await _send_kafka(project_id, task_id, type="user_echo", content=prompt)

        rephrased = await _run_phase(ws, 1, "Prompt Rephrasing", agent1, prompt, OLLAMA_MODEL, run_id=run_id)
        if not rephrased: return
        topology = await _run_phase(ws, 2, "Network Topology Design", agent2, rephrased, OLLAMA_MODEL, run_id=run_id)
        if not topology: return
        devices = await _run_phase(ws, 3, "Device Selection & BOM", agent3, f"Req: {prompt}\nTopo: {topology}", OLLAMA_MODEL, run_id=run_id)
        if not devices: return
        
        react_code = await _run_phase4_automated(ws, 4, "React Topology Generation", agent4, prompt, topology, devices, OLLAMA_MODEL, run_id=run_id)

        fp = save_run(prompt, rephrased, topology, devices, react_code=react_code)
        await _send_kafka(project_id, task_id, type="workflow_complete", saved_to=str(fp), is_final=True)

    except Exception as e:
        await _send_kafka(project_id, task_id, type="error", message=str(e))
    finally:
        active_tasks.pop(task_id, None)


async def _send_kafka(project_id, task_id, **kw):
    event_type = kw.pop("type", "unknown")
    content = kw.pop("content", "")
    is_final = kw.pop("is_final", False)
    
    event = {
        "projectId": project_id,
        "taskId": task_id,
        "agentName": "ai-service",
        "event_type": event_type,
        "data": content,
        "payload": kw,
        "is_final": is_final
    }
    await kafka_provider.send_event(event)


@router.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    messages = [ChatMessage(
        role=MessageRole.SYSTEM, content="Network Design Assistant. Technical and concise.")]
    
    if req.screenContext:
        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=req.screenContext))

    for h in req.history[-10:]:
        role = MessageRole.USER if h.get(
            "role") == "user" else MessageRole.ASSISTANT
        messages.append(ChatMessage(role=role, content=h.get("content", "")))
    messages.append(ChatMessage(role=MessageRole.USER, content=req.message))
    resp = await llm.achat(messages)
    return {"role": "assistant", "content": str(resp.message.content), "timestamp": datetime.now().isoformat()}


# ──────────────────────────────────────────────────────────────
# React Flow Code Generator Template
# ──────────────────────────────────────────────────────────────
def build_react_flow_code(nodes_json: str, edges_json: str) -> str:
    """
    Combines the nodes and edges JSON lists into a standard, fully functional
    React Flow application wrapper using custom SVG icon nodes.
    """
    return f"""import React from 'react';
import ReactFlow, {{ Background, Controls, MiniMap }} from 'reactflow';
import 'reactflow/dist/style.css';

const nodes = {nodes_json};
const edges = {edges_json};

export default function App() {{
  return (
    <div style={{{{width:'100vw',height:'100vh',background:'#fdfdfd'}}}}>
      <ReactFlow
        nodes={{nodes}}
        edges={{edges}}
        fitView
        defaultEdgeOptions={{{{ type: 'smoothstep' }}}}
      >
        <Background color='#e8e8e8' gap={{20}} />
        <Controls />
        <MiniMap nodeStrokeColor='#00A3AD' nodeColor='#e1e4e8' />
      </ReactFlow>
    </div>
  );
}}"""


async def _run_phase4_automated(ws, phase_num, phase_name, agent, prompt, topology, devices, model_name="", run_id="default_run"):
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    history: list[ChatMessage] = []
    MAX_CORRECTION_ATTEMPTS = 5
    
    msg = f"UserReq: {prompt}\nTopo: {topology}\nBOM: {devices}"
    react_code = None
    
    for attempt in range(1, MAX_CORRECTION_ATTEMPTS + 1):
        await _send(ws, type="phase_start", phase=phase_num, name=phase_name, iteration=attempt)
        
        logger.info(f"=== [Phase 4] Generation Attempt {attempt}/{MAX_CORRECTION_ATTEMPTS} ===")
        logger.info(f"Input Context Size: {len(msg)} characters")
        
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
                    await _send(ws, type="tool_result", tool_name=ev.tool_name, output=str(ev.tool_output))
                elif isinstance(ev, AgentOutput):
                    response_text = str(ev.response)
                    # Hide raw JSON from frontend chat log, send a friendly status message
                    await _send(ws, type="agent_response", agent=ev.current_agent_name, content="Building node coordinates and establishing physical connection paths...")
            resp = await handler
            response_text = str(resp)
            
            logger.info(f"Response received ({len(response_text)} characters).")
            logger.info(f"Snippet: {response_text[:300]}...")
            debug_log_io(phase_num, phase_name, attempt, msg, response_text, run_id=run_id)
        except Exception as e:
            await _send(ws, type="error", message=str(e))
            logger.error(f"Agent run failed: {e}")
            return None

        # Truncation Check
        trimmed_text = response_text.strip()
        cleaned_trimmed = re.sub(r"```(?:json)?\s*", "", trimmed_text).replace("```", "").strip()
        if cleaned_trimmed.startswith("{") and not cleaned_trimmed.endswith("}"):
            logger.warning("Response starts with '{' but does not end with '}'. Assuming output truncation.")
            error_msg = "Your JSON response was truncated/cut off. Please output the complete JSON object, and shorten descriptions if needed."
            await _send(ws, type="error", message=error_msg)
            msg = error_msg
            # Persist history
            history.append(ChatMessage(role=MessageRole.USER, content=msg))
            history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
            continue

        # Persist history
        history.append(ChatMessage(role=MessageRole.USER, content=msg))
        history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

        # Gatekeeper validation
        try:
            logger.info("Sending output to Gatekeeper for 4-layer validation...")
            gate_result = await generate_topology_code(response_text, topology, devices)
        except Exception as gate_err:
            await _send(ws, type="error", message=f"Gatekeeper unreachable: {gate_err}")
            logger.error(f"Gatekeeper unreachable: {gate_err}")
            return None

        if gate_result.get("status") == "ok":
            # Extract JSON and build the React template
            try:
                parsed = json.loads(gate_result["code"])
                nodes_json = json.dumps(parsed.get("nodes", []), indent=2)
                edges_json = json.dumps(parsed.get("edges", []), indent=2)
                react_code = build_react_flow_code(nodes_json, edges_json)
                logger.info("JSON successfully wrapped in React Flow template.")
                debug_log_io(phase_num, phase_name, attempt, msg, response_text, react_code, run_id=run_id)
            except Exception as parse_err:
                logger.error(f"Failed to format React template: {parse_err}")
                await _send(ws, type="error", message=f"Template formatting error: {parse_err}")
                return None

            await _send(ws, type="topology_code_ready", code=react_code)
            
            # Wait for User Approval OR Sandpack Runtime Error
            await _send(ws, type="approval_request", phase=phase_num, name=phase_name)
            data = json.loads(await ws.receive_text())
            
            if data.get("approved"):
                logger.info("React Flow diagram approved by the user.")
                return react_code
            
            # If not approved, it means it crashed in Sandpack or user requested a change
            error_msg = data.get("feedback", "Please revise.")
            logger.warning(f"Sandpack Runtime Error / User Feedback: {error_msg}")
            msg = (
                f"Your previous network topology JSON had a runtime rendering error or needed revision:\n{error_msg}\n\n"
                "Please fix the error and output the corrected JSON."
            )
        else:
            # Gatekeeper validation error
            error_msg = gate_result.get("message", "Unknown validation error.")
            logger.warning(f"Gatekeeper validation failed: {error_msg}")
            msg = (
                f"Your previous network topology JSON had a validation error:\n{error_msg}\n\n"
                "Please correct the issues and output the corrected JSON."
            )

        if attempt == MAX_CORRECTION_ATTEMPTS:
            await _send(ws, type="error", message=f"Topology generation failed after {MAX_CORRECTION_ATTEMPTS} attempts: {error_msg}")
            logger.error(f"Topology generation failed after {MAX_CORRECTION_ATTEMPTS} attempts.")
            return None

    return react_code


async def _send(ws, **kw):
    await ws.send_text(json.dumps(kw))


async def _run_phase(ws, phase_num, phase_name, agent, initial_msg, model_name="", run_id="default_run"):
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
            debug_log_io(phase_num, phase_name, iteration, msg, response_text, run_id=run_id)
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
    import time
    run_id = f"run_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    try:
        data = json.loads(await ws.receive_text())
        prompt = data["content"]
        await _send(ws, type="user_echo", content=prompt)
        rephrased = await _run_phase(ws, 1, "Prompt Rephrasing", agent1, prompt, OLLAMA_MODEL, run_id=run_id)
        topology = await _run_phase(ws, 2, "Network Topology Design", agent2, rephrased, OLLAMA_MODEL, run_id=run_id)
        devices = await _run_phase(ws, 3, "Device Selection & BOM", agent3, f"Req: {prompt}\nTopo: {topology}", OLLAMA_MODEL, run_id=run_id)
        
        # Phase 4: React Topology Generation (JSON Template & 4-Layer Gatekeeper validation)
        react_code = await _run_phase4_automated(ws, 4, "React Topology Generation", agent4, prompt, topology, devices, OLLAMA_MODEL, run_id=run_id)

        fp = save_run(prompt, rephrased, topology, devices, react_code=react_code)
        await _send(ws, type="workflow_complete", saved_to=str(fp))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await _send(ws, type="error", message=str(e))
