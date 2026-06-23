"""FastAPI router for the AI service — chat, WebSocket streaming, and Kafka task processing."""

import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.agent.workflow import AgentWorkflow, AgentInput, AgentOutput, ToolCall, ToolCallResult
from llama_index.core.memory import ChatMemoryBuffer

from webapp.config import llm, chat_store, OLLAMA_MODEL, IMAGE_SERVICE_URL, CHAT_TOKEN_LIMIT
from webapp.agents import PHASES
from webapp.utils import _strip_ansi, _parse_chunks, _generate_diagram_via_service, _save, generate_topology_code
from webapp.kafka_handler import KafkaManager
from config import unload_embedding_model

router = APIRouter()

# ── Chat model ───────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list = []
    conversation_id: str = "default"
    project_id: str = "default"
    screen_context: str = ""



@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Simple LLM chat endpoint for the copilot sidebar. Persists via PostgresChatStore."""
    key = f"{req.project_id}:{req.conversation_id}"
    memory = ChatMemoryBuffer.from_defaults(
        token_limit=CHAT_TOKEN_LIMIT,
        chat_store=chat_store,
        chat_store_key=key,
    )
    context = (
        "You are a Network Design AI Assistant. Answer questions about network design, "
        "HPE Aruba - CX products, VLANs, QoS, VSF, VSX, LAG, and general networking. "
        "Be concise and technical."
    )
    if req.screen_context:
        context += f"\n\nCurrent workflow context:\n{req.screen_context}"
    system_msg = ChatMessage(role=MessageRole.SYSTEM, content=context)
    messages = [system_msg] + memory.get()
    messages.append(ChatMessage(role=MessageRole.USER, content=req.message))
    resp = await llm.achat(messages)
    memory.put(ChatMessage(role=MessageRole.USER, content=req.message))
    memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=str(resp.message.content)))
    return {
        "role": "assistant",
        "content": str(resp.message.content),
        "timestamp": datetime.now().isoformat(),
    }


def _normalize_role(role_obj) -> str:
    raw = getattr(role_obj, "value", str(role_obj))
    if "." in raw:
        raw = raw.split(".")[-1]
    return raw.lower()


def _to_serializable_messages(messages, source_key: str):
    serializable = []
    for msg in messages or []:
        serializable.append(
            {
                "role": _normalize_role(getattr(msg, "role", "assistant")),
                "content": str(getattr(msg, "content", "")),
                "source_key": source_key,
            }
        )
    return serializable


def _dedupe_messages(messages: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for msg in messages:
        key = (str(msg.get("role", "")), str(msg.get("content", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(msg)
    return unique


@router.get("/api/chat-history/{project_id}")
async def get_chat_history(project_id: str, conversation_id: str = Query(default="default")):
    """Return persistent chat history from PostgresChatStore for frontend replay."""
    conversation_key = f"{project_id}:{conversation_id}"
    phase_keys = [f"{project_id}:phase{i}" for i in range(1, 6)]

    conversation_messages = []
    phase_messages = {}
    merged_messages = []

    try:
        conversation_messages = _to_serializable_messages(
            chat_store.get_messages(conversation_key), conversation_key
        )
        merged_messages.extend(conversation_messages)
    except Exception as err:
        print(f"CHAT_HISTORY conversation_key_error key={conversation_key} err={err}", flush=True)

    for key in phase_keys:
        try:
            msgs = _to_serializable_messages(chat_store.get_messages(key), key)
            phase_messages[key] = msgs
            merged_messages.extend(msgs)
        except Exception as err:
            print(f"CHAT_HISTORY phase_key_error key={key} err={err}", flush=True)
            phase_messages[key] = []

    return {
        "project_id": project_id,
        "conversation_id": conversation_id,
        "conversation_key": conversation_key,
        "conversation_messages": conversation_messages,
        "phase_messages": phase_messages,
        "merged_messages": _dedupe_messages(merged_messages),
    }


# ── Kafka task processor ─────────────────────────
kafka_mgr = KafkaManager()


async def process_kafka_task(task_data: dict):
    project_id = task_data["project_id"]
    task_id = task_data["task_id"]
    phase_idx = task_data["phase"]
    input_ctx = task_data["input_context"]
    history = task_data["history"]
    requested_agent_target = task_data.get("agent_target")
    print(f"PROCESS_TASK project_id={project_id} task_id={task_id} phase={phase_idx}", flush=True)
    print(f"PROCESS_TASK input_context={'None' if input_ctx is None else ('len=' + str(len(str(input_ctx))))}", flush=True)
    print(f"PROCESS_TASK history_len={len(history)}", flush=True)

    matching_phases = [p for p in PHASES if p[0] == phase_idx]
    if not matching_phases:
        await kafka_mgr.send_event({
            "project_id": project_id, "task_id": task_id, "agent_name": "system",
            "event_type": "ERROR", "data": f"Invalid phase: {phase_idx}", "is_final": True
        })
        return

    _, phase_name, agent = matching_phases[0]
    if requested_agent_target and requested_agent_target != agent.name:
        print(
            f"PROCESS_TASK agent_target_mismatch requested={requested_agent_target} resolved={agent.name} "
            f"task_id={task_id}",
            flush=True,
        )
        
    if phase_idx == 4:
        await _run_phase4_kafka(kafka_mgr, project_id, task_id, phase_idx, phase_name, agent, input_ctx, history, model_name=OLLAMA_MODEL)
    else:
        await _run_phase_kafka(kafka_mgr, project_id, task_id, phase_idx, phase_name, agent, input_ctx, history, model_name=OLLAMA_MODEL)

    if phase_idx == 5:
        unload_embedding_model()



# ── WebSocket streaming helpers ──────────────────
async def _send(ws, **kw):
    await ws.send_text(json.dumps(kw))


async def _run_phase(ws, phase_num, phase_name, agent, initial_msg, model_name="", project_id="default"):
    """Run one agent phase with event streaming, HITL approval, and persistent memory."""
    key = f"{project_id}:phase{phase_num}"
    memory = ChatMemoryBuffer.from_defaults(
        token_limit=CHAT_TOKEN_LIMIT,
        chat_store=chat_store,
        chat_store_key=key,
    )
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    msg = initial_msg
    iteration = 0
    tool_events: list[dict] = []

    while True:
        iteration += 1
        await _send(ws, type="phase_start", phase=phase_num, name=phase_name, iteration=iteration)
        history = memory.get()

        max_retries = 3
        response_text = ""
        for attempt in range(1, max_retries + 1):
            try:
                if history:
                    handler = wf.run(chat_history=history + [ChatMessage(role=MessageRole.USER, content=msg)])
                else:
                    handler = wf.run(user_msg=msg)

                async for ev in handler.stream_events():
                    if isinstance(ev, AgentInput):
                        await _send(ws, type="agent_input", agent=ev.current_agent_name, model=model_name)
                    elif isinstance(ev, ToolCall):
                        await _send(ws, type="tool_call", tool_name=ev.tool_name, tool_kwargs=ev.tool_kwargs)
                    elif isinstance(ev, ToolCallResult):
                        out = str(ev.tool_output)
                        tool_events.append({
                            "tool_name": ev.tool_name,
                            "input": str(getattr(ev, "tool_kwargs", ev.tool_name)),
                            "output": out,
                        })
                        if ev.tool_name in ("search_product_specs", "search_across_products"):
                            chunks = _parse_chunks(out)
                            await _send(ws, type="rag_result", tool_name=ev.tool_name, chunks=chunks, total=len(chunks))
                        elif ev.tool_name == "search_config_guides":
                            await _send(ws, type="config_rag_result", tool_name=ev.tool_name, output=out, total_chars=len(out))
                        else:
                            await _send(ws, type="tool_result", tool_name=ev.tool_name, output=out)
                    elif isinstance(ev, AgentOutput):
                        response_text = str(ev.response)
                        if ev.tool_calls:
                            for tc in ev.tool_calls:
                                await _send(ws, type="tool_call", tool_name=tc.tool_name, tool_kwargs=tc.tool_kwargs)
                        else:
                            await _send(ws, type="agent_response", agent=ev.current_agent_name, content=response_text)

                resp = await handler
                response_text = str(resp)
                break
            except Exception as llm_err:
                import traceback
                traceback.print_exc()
                if attempt < max_retries:
                    await _send(ws, type="agent_response", agent=agent.name,
                                content=f"⚠️ LLM error (attempt {attempt}/{max_retries}): {str(llm_err)[:200]}. Retrying in 5s…")
                    await asyncio.sleep(5)
                else:
                    await _send(ws, type="agent_response", agent=agent.name,
                                content=f"❌ LLM failed after {max_retries} attempts: {str(llm_err)[:300]}. Approving with partial result.")
        memory.put(ChatMessage(role=MessageRole.USER, content=msg))
        memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

        await _send(ws, type="approval_request", phase=phase_num, name=phase_name)
        data = json.loads(await ws.receive_text())

        if data.get("approved"):
            await _send(ws, type="phase_approved", phase=phase_num, name=phase_name)
            return response_text, tool_events
        else:
            msg = data.get("feedback", "Please revise.")
            tool_events.append({
                "tool_name": "__revision_request__",
                "input": msg,
                "output": f"Phase {phase_num} revised with feedback",
            })
            await _send(ws, type="phase_revision", phase=phase_num, feedback=msg)



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

async def _run_phase4_kafka(kafka_mgr, project_id, task_id, phase_num, phase_name, agent, initial_msg, history=None, model_name=""):
    import json, re
    from llama_index.core.llms import ChatMessage, MessageRole
    from llama_index.core.agent.workflow import AgentInput, AgentOutput, ToolCall, ToolCallResult
    
    print(f"\n=== START PHASE 4 (GATEKEEPER): {phase_name} ===", flush=True)
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    
    key = f"{project_id}:phase{phase_num}"
    memory = ChatMemoryBuffer.from_defaults(
        token_limit=CHAT_TOKEN_LIMIT,
        chat_store=chat_store,
        chat_store_key=key,
    )
    chat_history = memory.get()
    
    MAX_CORRECTION_ATTEMPTS = 5
    msg = initial_msg
    react_code = None
    
    # Send Token to start
    await kafka_mgr.send_event({
        "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
        "event_type": "TOKEN", "data": f"Starting phase {phase_num}: {phase_name}", "is_final": False
    })
    
    for attempt in range(1, MAX_CORRECTION_ATTEMPTS + 1):
        print(f"=== [Phase 4] Generation Attempt {attempt}/{MAX_CORRECTION_ATTEMPTS} ===", flush=True)
        response_text = ""
        try:
            handler = wf.run(user_msg=msg) if not chat_history else wf.run(
                chat_history=chat_history + [ChatMessage(role=MessageRole.USER, content=msg)])
            async for ev in handler.stream_events():
                base_event = {"project_id": project_id, "task_id": task_id, "agent_name": agent.name, "is_final": False}
                if isinstance(ev, ToolCall):
                    await kafka_mgr.send_event({**base_event, "event_type": "TOOL_CALL", "data": ev.tool_name, "payload": ev.tool_kwargs})
                elif isinstance(ev, ToolCallResult):
                    await kafka_mgr.send_event({**base_event, "event_type": "TOOL_RESULT", "payload": {"output": str(ev.tool_output)}})
                elif isinstance(ev, AgentOutput):
                    if not ev.tool_calls:
                        await kafka_mgr.send_event({**base_event, "event_type": "TOKEN", "data": "Building node coordinates and establishing physical connection paths..."})
            resp = await handler
            response_text = str(resp)
        except Exception as e:
            print(f"Agent run failed: {e}")
            await kafka_mgr.send_event({
                "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                "event_type": "ERROR", "data": str(e), "is_final": True
            })
            return None

        # Truncation Check
        trimmed_text = response_text.strip()
        cleaned_trimmed = re.sub(r"```(?:json)?\s*", "", trimmed_text).replace("```", "").strip()
        if cleaned_trimmed.startswith("{") and not cleaned_trimmed.endswith("}"):
            error_msg = "Your JSON response was truncated/cut off. Please output the complete JSON object, and shorten descriptions if needed."
            msg = error_msg
            chat_history.append(ChatMessage(role=MessageRole.USER, content=msg))
            chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
            continue

        # Persist history
        chat_history.append(ChatMessage(role=MessageRole.USER, content=msg))
        chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

        # Gatekeeper validation
        try:
            print("Sending output to Gatekeeper for 4-layer validation...")
            # We don't have topology and devices string vars in the local scope of this kafka function easily accessible,
            # so we'll just pass empty strings since the gatekeeper primarily needs llm_output
            gate_result = await generate_topology_code(cleaned_trimmed, "", "")
        except Exception as gate_err:
            print(f"Gatekeeper unreachable: {gate_err}")
            gate_result = {"status": "error", "message": f"Gatekeeper unreachable: {gate_err}. Please ensure Topology Gatekeeper is running."}

        if gate_result.get("status") == "ok":
            try:
                parsed = json.loads(gate_result.get("code", cleaned_trimmed))
                nodes_json = json.dumps(parsed.get("nodes", []), indent=2)
                edges_json = json.dumps(parsed.get("edges", []), indent=2)
                react_code = build_react_flow_code(nodes_json, edges_json)
                print("JSON successfully wrapped in React Flow template.")
            except Exception as parse_err:
                print(f"Failed to format React template: {parse_err}")
                react_code = gate_result.get("code", cleaned_trimmed)
            
            # Now call image service to get the final preview URL for frontend diagram_ready event
            try:
                img_result = await _generate_diagram_via_service(react_code)
                url = f"{IMAGE_SERVICE_URL}{img_result['url']}"
                filename = img_result.get("filename", "")
            except Exception as e:
                print(f"Image generation failed: {e}")
                url = None
                filename = ""
            
            await kafka_mgr.send_event({
                "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                "event_type": "DIAGRAM_READY", "data": react_code,
                "payload": {
                    "url": url,
                    "filename": filename,
                    "download_url": f"{url}/download" if url else None
                },
                "is_final": False
            })

            await kafka_mgr.send_event({
                "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                "event_type": "FINAL_ANSWER", "data": react_code, "is_final": True
            })
            
            # Save final memory
            memory.put(ChatMessage(role=MessageRole.USER, content=msg))
            memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=react_code))
            return react_code
        else:
            gate_err = gate_result.get("message", "Unknown validation error")
            print(f"Validation failed (Attempt {attempt}): {gate_err}")
            
            if attempt < MAX_CORRECTION_ATTEMPTS:
                error_msg = f"Your JSON failed validation: {gate_err}. Please fix these errors and output only the corrected JSON."
                msg = error_msg
                await kafka_mgr.send_event({
                    "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                    "event_type": "TOKEN", "data": f"⚠️ JSON Validation Failed. Gatekeeper rejected output. Retrying ({attempt}/{MAX_CORRECTION_ATTEMPTS})...", "is_final": False
                })
            else:
                error_msg = "Maximum correction attempts reached. Gatekeeper validation failed."
                print(error_msg)
                await kafka_mgr.send_event({
                    "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                    "event_type": "ERROR", "data": error_msg, "is_final": True
                })
                return None


async def _run_phase_kafka(kafka_mgr, project_id, task_id, phase_num, phase_name, agent, initial_msg, history=None, model_name=""):
    """Run one agent phase and stream events to Kafka. Uses PostgresChatStore for memory."""
    print(f"\n=== START PHASE {phase_num}: {phase_name} ===", flush=True)
    print(f"Project: {project_id}", flush=True)
    print(f"Task: {task_id}", flush=True)
    print(f"Agent: {agent.name}", flush=True)
    print(f"initial_msg={'None' if initial_msg is None else ('len=' + str(len(str(initial_msg))))}", flush=True)
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    gateway_history = []
    if history:
        for h in history:
            raw_role = str(h.get("role", "")).lower()
            role = MessageRole.USER if raw_role == "user" else MessageRole.ASSISTANT
            content = h.get("content", "")
            print(f"RUN_PHASE convert history role={role} content={'None' if content is None else ('len=' + str(len(str(content))))}", flush=True)
            gateway_history.append(ChatMessage(role=role, content=content))

    key = f"{project_id}:phase{phase_num}"
    memory = ChatMemoryBuffer.from_defaults(
        token_limit=CHAT_TOKEN_LIMIT,
        chat_store=chat_store,
        chat_store_key=key,
    )
    chat_history = memory.get()
    if chat_history:
        last_user = next(
            (m for m in reversed(chat_history) if getattr(m, "role", None) == MessageRole.USER),
            None,
        )
        last_assistant = next(
            (m for m in reversed(chat_history) if getattr(m, "role", None) == MessageRole.ASSISTANT),
            None,
        )
        if last_user and last_assistant and str(getattr(last_user, "content", "")) == str(initial_msg):
            print(
                f"RUN_PHASE task_id={task_id} appears_already_processed phase={phase_num}; skipping duplicate run",
                flush=True,
            )
            await kafka_mgr.send_event(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "agent_name": agent.name,
                    "event_type": "FINAL_ANSWER",
                    "data": str(getattr(last_assistant, "content", "")),
                    "is_final": True,
                }
            )
            return str(getattr(last_assistant, "content", ""))

    if not chat_history and gateway_history:
        print(f"RUN_PHASE seeding DB with {len(gateway_history)} messages from gateway history", flush=True)
        chat_store.set_messages(key, gateway_history)
        chat_history = gateway_history

    await kafka_mgr.send_event({
        "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
        "event_type": "TOKEN", "data": f"Starting phase {phase_num}: {phase_name}", "is_final": False
    })

    try:
        if chat_history:
            handler = wf.run(chat_history=chat_history + [ChatMessage(role=MessageRole.USER, content=initial_msg)])
        else:
            handler = wf.run(user_msg=initial_msg)

        async for ev in handler.stream_events():
            base_event = {"project_id": project_id, "task_id": task_id, "agent_name": agent.name, "is_final": False}
            if isinstance(ev, AgentInput):
                pass
            elif isinstance(ev, ToolCall):
                await kafka_mgr.send_event({**base_event, "event_type": "TOOL_CALL", "data": ev.tool_name, "payload": ev.tool_kwargs})
            elif isinstance(ev, ToolCallResult):
                await kafka_mgr.send_event({**base_event, "event_type": "TOOL_RESULT", "payload": {"output": str(ev.tool_output)}})
            elif isinstance(ev, AgentOutput):
                if not ev.tool_calls:
                    await kafka_mgr.send_event({**base_event, "event_type": "TOKEN", "data": str(ev.response)})

        resp = await handler
        existing_after = memory.get()
        last_user = next(
            (m for m in reversed(existing_after) if getattr(m, "role", None) == MessageRole.USER),
            None,
        )
        last_assistant = next(
            (m for m in reversed(existing_after) if getattr(m, "role", None) == MessageRole.ASSISTANT),
            None,
        )
        if not last_user or str(getattr(last_user, "content", "")) != str(initial_msg):
            memory.put(ChatMessage(role=MessageRole.USER, content=initial_msg))
        if not last_assistant or str(getattr(last_assistant, "content", "")) != str(resp):
            memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=str(resp)))
        await kafka_mgr.send_event({
            "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
            "event_type": "FINAL_ANSWER", "data": str(resp), "is_final": True
        })

        if phase_num == 4:
            diagram_code = str(resp)
            try:
                result = await _generate_diagram_via_service(diagram_code)
                if result.get("success"):
                    url = f"{IMAGE_SERVICE_URL}{result['url']}"
                    await kafka_mgr.send_event({
                        "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                        "event_type": "DIAGRAM_READY", "data": str(resp),
                        "payload": {
                            "url": url,
                            "filename": result.get("filename", ""),
                            "download_url": f"{IMAGE_SERVICE_URL}{result['url']}/download"
                        },
                        "is_final": False
                    })
                else:
                    await kafka_mgr.send_event({
                        "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                        "event_type": "DIAGRAM_ERROR", "data": str(resp),
                        "payload": {
                            "message": result.get("error", "Unknown error from image service"),
                            "diagram_code": diagram_code
                        },
                        "is_final": False
                    })
            except Exception as img_err:
                await kafka_mgr.send_event({
                    "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
                    "event_type": "DIAGRAM_ERROR", "data": str(resp),
                    "payload": {"message": f"Image service unavailable: {str(img_err)}"},
                    "is_final": False
                })

        return str(resp)
    except Exception as e:
        await kafka_mgr.send_event({
            "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
            "event_type": "ERROR", "data": str(e), "is_final": True
        })
        raise e


# WebSocket endpoint — currently unused (all flows go through Gateway + Kafka)
@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        data = json.loads(await ws.receive_text())
        prompt = data["content"]
        await _send(ws, type="user_echo", content=prompt)

        rephrased, _ = await _run_phase(ws, 1, "Prompt Rephrasing", PHASES[0][2], prompt, OLLAMA_MODEL)
        topology, _ = await _run_phase(ws, 2, "Network Topology Design", PHASES[1][2], rephrased, OLLAMA_MODEL)
        devices, _ = await _run_phase(ws, 3, "Device Selection & BOM", PHASES[2][2], f"Req: {prompt}\nTopo: {topology}", OLLAMA_MODEL)
        react_code, _ = await _run_phase(ws, 4, "React Topology Generation", PHASES[3][2], f"UserReq: {prompt}\nTopo: {topology}\nBOM: {devices}", OLLAMA_MODEL)

        fp = _save(prompt, rephrased, topology, devices, react_code)
        await _send(ws, type="workflow_complete", saved_to=str(fp))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await _send(ws, type="error", message=str(e))
