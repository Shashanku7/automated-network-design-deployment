"""
topology_generation/app.py
--------------------------
Gatekeeper microservice (Port 8002).

Receives the raw JSON data output from ai-service Agent 6,
applies a 4-layer validation gate, and returns:
  - {"status": "ok",    "code": "<clean React Flow JSON string>"}
  - {"status": "error", "message": "<precise error description>"}
"""

import json
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Topology Generation Gatekeeper", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ValidateRequest(BaseModel):
    llm_output: str
    topology_text: str = ""
    bom_text: str = ""


class ValidateResponse(BaseModel):
    status: str
    code: str = ""
    message: str = ""


def _extract_json(llm_output: str) -> tuple[bool, dict, str]:
    cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return False, {}, (
            "No JSON object found in your response. "
            "Ensure you output ONLY a single valid JSON object containing 'nodes' and 'edges'."
        )
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError as exc:
        return False, {}, (
            f"JSON parsing failed: {exc}. "
            "Ensure all strings are properly closed, quotes are escaped, "
            "and commas are correctly placed."
        )
    return True, parsed, ""


def _validate_structure(data: dict) -> tuple[bool, str]:
    if "nodes" not in data or not isinstance(data["nodes"], list) or len(data["nodes"]) == 0:
        return False, "Missing or empty 'nodes' list. You must define a list of nodes."
    if "edges" not in data or not isinstance(data["edges"], list):
        return False, "Missing 'edges' list. You must define a list of edges."

    node_ids = set()
    for idx, node in enumerate(data["nodes"]):
        node_id = node.get("id")
        if not node_id:
            return False, f"Node at index {idx} is missing a unique 'id' field."
        if node_id in node_ids:
            return False, f"Duplicate node 'id' detected: '{node_id}'. All node IDs must be unique."
        node_ids.add(node_id)

        pos = node.get("position")
        if not pos or not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
            return False, f"Node '{node_id}' is missing a valid 'position' object with 'x' and 'y' coordinates."
        if not (isinstance(pos["x"], (int, float)) and isinstance(pos["y"], (int, float))):
            return False, f"Node '{node_id}' position coordinates must be numeric."

        data_obj = node.get("data") or {}
        label = data_obj.get("label") if isinstance(data_obj, dict) else None
        if not label or not isinstance(label, str) or len(label.strip()) < 5:
            return False, f"Node '{node_id}' must have a descriptive label in 'data.label' (at least 5 characters)."

        ALLOWED_ICONS = {"Cloud", "Gateway", "Chassis", "Switch", "AP", "Server", "Laptop", "Phone", "Printer", "IPTV", "Camera", "WLC", "NAC", "IoT", "Storage", "LoadBalancer"}
        icon_type = data_obj.get("iconType")
        if not icon_type or icon_type not in ALLOWED_ICONS:
            return False, f"Node '{node_id}' has invalid or missing 'iconType' ({icon_type}). Must be one of: {', '.join(sorted(ALLOWED_ICONS))}"

    return True, ""


def _validate_referential_integrity(data: dict) -> tuple[bool, str]:
    node_ids = {node["id"] for node in data["nodes"]}
    for idx, edge in enumerate(data["edges"]):
        edge_id = edge.get("id")
        source = edge.get("source")
        target = edge.get("target")
        if not edge_id:
            return False, f"Edge at index {idx} is missing an 'id' field."
        if not source or not target:
            return False, f"Edge '{edge_id}' is missing 'source' or 'target' node ID."
        if source not in node_ids:
            return False, f"Edge '{edge_id}' points to non-existent source node ID: '{source}'."
        if target not in node_ids:
            return False, f"Edge '{edge_id}' points to non-existent target node ID: '{target}'."
    return True, ""


def _parse_bom_devices(bom_text: str) -> list[dict]:
    devices = []
    if not bom_text:
        return devices

    NODE_CATEGORIES = (
        "switch", "router", "ap", "access point", "wireless", "server",
        "host", "firewall", "gateway", "controller", "phone", "pc",
        "iptv", "camera", "printer", "nvr", "storage", "load balancer", "adc",
        "spine", "leaf", "core", "access", "distribution", "chassis",
        "wlc", "nac", "clearpass", "ise", "iot", "sensor", "hvac",
        "laptop", "desktop", "workstation", "client", "endpoint", "cloud"
    )
    PASSIVE_KEYWORDS = {"cable", "transceiver", "sfp", "dac", "fiber", "license", "power supply", "psu", "bracket", "rail kit", "mount", "fan", "card", "module"}

    lines = bom_text.splitlines()
    table_started = False
    comp_idx = -1
    model_idx = -1
    qty_idx = -1

    for line in lines:
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            table_started = False
            comp_idx = -1
            model_idx = -1
            qty_idx = -1
            continue

        parts = [p.strip() for p in line.split("|")]
        if parts and parts[0] == "":
            parts.pop(0)
        if parts and parts[-1] == "":
            parts.pop()
        if not parts:
            continue
        if all(re.match(r"^:?-+:?$", p) for p in parts):
            continue

        if not table_started:
            headers = [h.lower() for h in parts]
            comp_idx = next((idx for idx, h in enumerate(headers) if "component" in h or "type" in h), -1)
            model_idx = next((idx for idx, h in enumerate(headers) if "model" in h or "device" in h or "product" in h), -1)
            qty_idx = next((idx for idx, h in enumerate(headers) if "qty" in h or "quantity" in h or "count" in h), -1)
            if model_idx != -1 and qty_idx != -1:
                table_started = True
            continue

        if model_idx >= len(parts) or qty_idx >= len(parts):
            continue

        c_idx = comp_idx if (comp_idx != -1 and comp_idx < len(parts)) else 0
        component = parts[c_idx].replace("**", "").strip() if len(parts) > 0 else ""
        model = parts[model_idx].replace("**", "").replace("`", "").strip()
        qty_str = parts[qty_idx].replace("**", "").replace("`", "").strip()

        if not model or model.lower() in ("model", "qty", "quantity", "component", "part number"):
            continue

        combined = f"{component} {model}".lower()
        is_node_device = any(re.search(rf"\b{re.escape(kw)}\b", combined) for kw in NODE_CATEGORIES)
        is_passive = any(kw in combined for kw in PASSIVE_KEYWORDS)
        if not is_node_device or is_passive:
            continue

        match = re.search(r"\d+", qty_str)
        if match:
            qty = int(match.group())
            if qty < 500:
                devices.append({"model": model, "qty": qty})
            else:
                devices.append({"model": model, "qty": 1})

    return devices


def _validate_semantic_alignment(data: dict, topology_text: str, bom_text: str) -> tuple[bool, str]:
    nodes = data["nodes"]

    NODE_CATEGORIES = (
        "switch", "router", "ap", "access point", "wireless", "server",
        "host", "firewall", "gateway", "controller", "phone", "pc",
        "iptv", "camera", "printer", "nvr", "storage", "load balancer", "adc",
        "spine", "leaf", "core", "access", "distribution", "chassis",
        "wlc", "nac", "clearpass", "ise", "iot", "sensor", "hvac",
        "laptop", "desktop", "workstation", "client", "endpoint", "cloud"
    )
    ACTIVE_ICONS = {
        "chassis", "switch", "ap", "server", "gateway", "cloud", "laptop",
        "phone", "printer", "iptv", "camera", "wlc", "nac", "iot", "storage",
        "loadbalancer"
    }
    PASSIVE_KEYWORDS = {"cable", "transceiver", "sfp", "dac", "fiber", "license", "power supply", "psu", "bracket", "rail kit", "mount", "fan", "card", "module"}

    for node in nodes:
        label_dict = node.get("data") or {}
        label = label_dict.get("label", "").lower() if isinstance(label_dict, dict) else ""
        node_id = node.get("id", "unknown")
        has_active_kw = any(re.search(rf"\b{re.escape(kw)}\b", label) for kw in NODE_CATEGORIES)
        node_icon = label_dict.get("iconType", "").lower() if isinstance(label_dict, dict) else ""
        is_active_icon = node_icon in ACTIVE_ICONS
        has_passive_kw = any(kw in label for kw in PASSIVE_KEYWORDS)
        is_active_device = has_active_kw or (is_active_icon and not has_passive_kw)
        if not is_active_device:
            return False, f"Hallucinated node detected: Node '{node_id}' with label '{label}' does not appear to be an active network device."

    expected_devices = _parse_bom_devices(bom_text)
    for item in expected_devices:
        model = item["model"]
        expected_qty = item["qty"]
        model_nums = re.findall(r"\d{3,}", model)
        actual_qty = 0
        for node in nodes:
            label_dict = node.get("data") or {}
            label = label_dict.get("label", "").lower() if isinstance(label_dict, dict) else ""
            if model_nums:
                match_found = any(num in label for num in model_nums)
            else:
                match_found = model.strip().lower() in label
            if match_found:
                match_qty = re.search(r"(?:x\s*|qty:\s*|\(\s*)(\d+)", label.lower())
                actual_qty += int(match_qty.group(1)) if match_qty else 1

        is_switch = any(kw in model.lower() for kw in ("switch", "cx", "aruba cx", "core", "access", "distribution", "8360", "6300", "6200", "6100", "10000", "8100", "8325"))
        model_part = ' or '.join(model_nums) if model_nums else model.strip()

        if is_switch:
            if actual_qty < expected_qty:
                return False, (
                    f"BOM Mismatch: BOM specifies {expected_qty} x '{model}', "
                    f"but diagram has {actual_qty} node(s) matching '{model_part}'."
                )
        elif expected_qty > 0 and actual_qty < 1:
            return False, (
                f"BOM Mismatch: BOM specifies '{model}', "
                f"but diagram has 0 nodes matching '{model_part}'."
            )

    node_labels_lower = ""
    for node in nodes:
        d = node.get("data") or {}
        lbl = d.get("label", "") if isinstance(d, dict) else ""
        node_labels_lower += (lbl or "").lower()

    is_dc = "spine" in node_labels_lower or "leaf" in node_labels_lower

    for node in nodes:
        node_id = node.get("id", "unknown")
        pos = node.get("position") or {}
        y = pos.get("y", 0) if isinstance(pos, dict) else 0
        data_obj = node.get("data") or {}
        icon_type = data_obj.get("iconType", "") if isinstance(data_obj, dict) else ""

        if is_dc:
            if icon_type == "Chassis" and abs(y - 0) > 200:
                return False, f"Spine node '{node_id}' (Chassis) should be near y=0, but is at y={y}."
            elif icon_type == "Server" and abs(y - 440) > 200 and abs(y - 320) > 200 and abs(y - 480) > 200:
                return False, f"Server node '{node_id}' should be near y=440, but is at y={y}."
        else:
            if icon_type in ("Chassis", "Gateway") and abs(y - 0) > 200:
                return False, f"Core node '{node_id}' ({icon_type}) should be near y=0, but is at y={y}."
            elif icon_type in ("AP", "Server") and abs(y - 480) > 200:
                return False, f"Endpoint node '{node_id}' ({icon_type}) should be near y=480, but is at y={y}."

    return True, ""


@app.post("/validate-topology", response_model=ValidateResponse)
async def validate_topology(req: ValidateRequest):
    ok, parsed_dict, err = _extract_json(req.llm_output)
    if not ok:
        print(f"[Gatekeeper Layer 1] JSON parse failed: {err}")
        return ValidateResponse(status="error", message=err)

    valid, err = _validate_structure(parsed_dict)
    if not valid:
        print(f"[Gatekeeper Layer 2] Schema check failed: {err}")
        return ValidateResponse(status="error", message=err)

    valid, err = _validate_referential_integrity(parsed_dict)
    if not valid:
        print(f"[Gatekeeper Layer 3] Integrity check failed: {err}")
        return ValidateResponse(status="error", message=err)

    valid, err = _validate_semantic_alignment(parsed_dict, req.topology_text, req.bom_text)
    if not valid:
        print(f"[Gatekeeper Layer 4] Semantic alignment failed: {err}")
        return ValidateResponse(status="error", message=err)

    print("[Gatekeeper] All 4 layers passed.")
    return ValidateResponse(status="ok", code=json.dumps(parsed_dict))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "topology_generation"}
