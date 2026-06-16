"""
topology_generation/app.py
--------------------------
Gatekeeper microservice (Port 8002).

Receives the raw JSON data output from ai-service (Agent 4),
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
    status: str       # "ok" or "error"
    code: str = ""    # Clean JSON string (only when status == "ok")
    message: str = "" # Error description (only when status == "error")


# ──────────────────────────────────────────────────────────────
# Gatekeeper Layer 1: JSON Extraction and Parse
# ──────────────────────────────────────────────────────────────
def _extract_json(llm_output: str) -> tuple[bool, dict, str]:
    """
    Finds and parses the JSON object in LLM output.
    Uses regex to extract the outermost curly braces, ignoring conversational preambles/postambles.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).replace("```", "").strip()

    # Find the outermost curly braces
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
            "Ensure all strings are properly closed, quotes are escaped (as \\\" inside strings), "
            "and commas are correctly placed."
        )

    return True, parsed, ""


# ──────────────────────────────────────────────────────────────
# Gatekeeper Layer 2: Structural Schema Check
# ──────────────────────────────────────────────────────────────
def _validate_structure(data: dict) -> tuple[bool, str]:
    """
    Verifies that the JSON has the required keys, types, and coordinate formats.
    """
    if "nodes" not in data or not isinstance(data["nodes"], list) or len(data["nodes"]) == 0:
        return False, "Missing or empty 'nodes' list. You must define a list of nodes."
    if "edges" not in data or not isinstance(data["edges"], list):
        return False, "Missing 'edges' list. You must define a list of edges."

    # Validate each node
    node_ids = set()
    for idx, node in enumerate(data["nodes"]):
        node_id = node.get("id")
        if not node_id:
            return False, f"Node at index {idx} is missing a unique 'id' field."
        if node_id in node_ids:
            return False, f"Duplicate node 'id' detected: '{node_id}'. All node IDs must be unique."
        node_ids.add(node_id)

        # Check position
        pos = node.get("position")
        if not pos or not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
            return False, f"Node '{node_id}' is missing a valid 'position' object with 'x' and 'y' coordinates."
        if not (isinstance(pos["x"], (int, float)) and isinstance(pos["y"], (int, float))):
            return False, f"Node '{node_id}' position coordinates 'x' and 'y' must be numeric values."

        # Check label
        data_obj = node.get("data") or {}
        label = data_obj.get("label") if isinstance(data_obj, dict) else None
        if not label or not isinstance(label, str) or len(label.strip()) < 5:
            return False, f"Node '{node_id}' must have a descriptive label in 'data.label' (at least 5 characters)."

        # Check iconType Enum
        ALLOWED_ICONS = {"Cloud", "Gateway", "Chassis", "Switch", "AP", "Server", "Laptop", "Phone", "Printer", "IPTV", "Camera", "WLC", "NAC", "IoT", "Storage", "LoadBalancer"}
        icon_type = data_obj.get("iconType")
        if not icon_type or icon_type not in ALLOWED_ICONS:
            return False, f"Node '{node_id}' has an invalid or missing 'iconType' ({icon_type}). Must be one of: {', '.join(ALLOWED_ICONS)}"

    return True, ""


# ──────────────────────────────────────────────────────────────
# Gatekeeper Layer 3: Referential Integrity Check
# ──────────────────────────────────────────────────────────────
def _validate_referential_integrity(data: dict) -> tuple[bool, str]:
    """
    Verifies that every edge's source and target connects to a real node ID.
    This prevents runtime rendering crashes in React Flow.
    """
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
            return False, f"Edge '{edge_id}' points to a non-existent source node ID: '{source}'."
        if target not in node_ids:
            return False, f"Edge '{edge_id}' points to a non-existent target node ID: '{target}'."

    return True, ""


# ──────────────────────────────────────────────────────────────
# Gatekeeper Layer 4: Cross-Phase Semantic Validation
# ──────────────────────────────────────────────────────────────
def _parse_bom_devices(bom_text: str) -> list[dict]:
    """
    Parses BOM markdown table dynamically to extract models and expected quantities,
    adapting to any column ordering generated by the LLM.
    """
    devices = []
    if not bom_text:
        return devices

    # Active network nodes that must be represented in a topology diagram
    NODE_CATEGORIES = (
        "switch", "router", "ap", "access point", "wireless", "server", 
        "host", "firewall", "gateway", "controller", "phone", "pc", 
        "iptv", "camera", "printer", "nvr", "storage", "load balancer", "adc",
        "spine", "leaf", "core", "access", "distribution", "chassis",
        "wlc", "nac", "clearpass", "ise", "iot", "sensor", "hvac",
        "db", "database", "web", "app", "master", "slave", "node", "vm",
        "laptop", "desktop", "workstation", "client", "endpoint", "cloud"
    )

    lines = bom_text.splitlines()
    table_started = False
    comp_idx = -1
    model_idx = -1
    qty_idx = -1

    for line in lines:
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            if table_started:
                # Reset table state when leaving the table block
                table_started = False
                comp_idx = -1
                model_idx = -1
                qty_idx = -1
            continue

        # Split and clean parts, removing empty elements at the ends due to leading/trailing '|'
        parts = [p.strip() for p in line.split("|")]
        if parts and parts[0] == "":
            parts.pop(0)
        if parts and parts[-1] == "":
            parts.pop()

        if not parts:
            continue

        # Skip table markdown separators (e.g., |:---|:---:|)
        if all(re.match(r"^:?-+:?$", p) for p in parts):
            continue

        # Check if we are at the header row
        if not table_started:
            headers = [h.lower() for h in parts]
            
            # Find the Component/Type column index
            for idx, h in enumerate(headers):
                if "component" in h or "type" in h:
                    comp_idx = idx
                    break
            
            # Find the Model column index
            for idx, h in enumerate(headers):
                if "model" in h or "device" in h or "product" in h:
                    model_idx = idx
                    break
            
            # Find the Quantity column index
            for idx, h in enumerate(headers):
                if "qty" in h or "quantity" in h or "count" in h:
                    qty_idx = idx
                    break
            
            # If BOTH model and quantity are found, we successfully identified the BOM table
            if model_idx != -1 and qty_idx != -1:
                table_started = True
            continue

        # If we are inside a validated BOM table, parse the data row
        if model_idx >= len(parts) or qty_idx >= len(parts):
            continue

        c_idx = comp_idx if (comp_idx != -1 and comp_idx < len(parts)) else 0
        component = parts[c_idx].replace("**", "").strip() if len(parts) > 0 else ""
        model = parts[model_idx].replace("**", "").replace("`", "").strip()
        qty_str = parts[qty_idx].replace("**", "").replace("`", "").strip()

        if not model or model.lower() in ("model", "qty", "quantity", "component", "part number"):
            continue

        # Whitelist Check: Verify if the component belongs to active network categories
        combined_text = f"{component} {model}".lower()
        is_node_device = any(re.search(rf"\b{re.escape(kw)}\b", combined_text) for kw in NODE_CATEGORIES)
        
        # Avoid matching passive accessories (like cables, PSUs, mounting kits)
        PASSIVE_KEYWORDS = {"cable", "transceiver", "sfp", "dac", "fiber", "license", "power supply", "psu", "bracket", "rail kit", "mount", "fan", "card", "module"}
        is_passive = any(kw in combined_text for kw in PASSIVE_KEYWORDS)
        if not is_node_device or is_passive:
            continue

        # Extract number from the quantity string
        match = re.search(r"\d+", qty_str)
        if match:
            qty = int(match.group())
            # Basic sanity check to avoid parsing model numbers like "635" from "AP-635" as quantity
            if qty < 500:
                devices.append({"model": model, "qty": qty})
            else:
                # If it's a huge number, it's likely a model string that ended up in the Qty column. Assume qty 1.
                devices.append({"model": model, "qty": 1})

    return devices


def _validate_semantic_alignment(data: dict, topology_text: str, bom_text: str) -> tuple[bool, str]:
    """
    Checks that the diagram nodes match the BOM and coordinates match layout guidelines.
    """
    nodes = data["nodes"]
    edges = data["edges"]
    
    # 0. Strict Reverse Reconciliation (No Hallucinated Nodes)
    # Ensure every node drawn maps to an active network category (i.e. no passive cables/licenses)
    NODE_CATEGORIES = (
        "switch", "router", "ap", "access point", "wireless", "server", 
        "host", "firewall", "gateway", "controller", "phone", "pc", 
        "iptv", "camera", "printer", "nvr", "storage", "load balancer", "adc",
        "spine", "leaf", "core", "access", "distribution", "chassis",
        "wlc", "nac", "clearpass", "ise", "iot", "sensor", "hvac",
        "db", "database", "web", "app", "master", "slave", "node", "vm",
        "laptop", "desktop", "workstation", "client", "endpoint", "cloud"
    )
    ACTIVE_ICONS = {
        "chassis", "switch", "ap", "server", "gateway", "cloud", "laptop", 
        "phone", "printer", "iptv", "camera", "wlc", "nac", "iot", "storage", 
        "loadbalancer"
    }
    PASSIVE_KEYWORDS = {
        "cable", "transceiver", "sfp", "dac", "fiber", "license", "power supply", 
        "psu", "bracket", "rail kit", "mount", "fan", "card", "module"
    }
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
            return False, f"Hallucinated node detected: Node '{node_id}' with label '{label}' does not appear to be an active network device. Cables, transceivers, and software licenses MUST NOT be drawn as physical nodes."

    # 1. BOM Device Matching
    expected_devices = _parse_bom_devices(bom_text)
    for item in expected_devices:
        model = item["model"]
        expected_qty = item["qty"]
        
        # Extract model number digits for robust matching (e.g. 6300, 6200, 515)
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
                # Check for stacked/multi quantities in label, e.g. "x2", "Qty: 2"
                match_qty = re.search(r"(?:x\s*|qty:\s*|\(\s*)(\d+)", label.lower())
                if match_qty:
                    actual_qty += int(match_qty.group(1))
                else:
                    actual_qty += 1
                    
        # Check if it's a Switch vs Endpoint/AP
        is_switch = any(kw in model.lower() for kw in ("switch", "cx", "aruba cx", "core", "access", "distribution", "8360", "6300", "6200", "6100", "10000", "8100", "8325"))
        
        model_part = ' or '.join(model_nums) if model_nums else model.strip()

        if is_switch:
            if actual_qty < expected_qty:
                return False, (
                    f"BOM Mismatch: The recommended BOM specifies {expected_qty} x '{model}', "
                    f"but your diagram only has {actual_qty} node(s) matching '{model_part}' in their labels. "
                    "Ensure every device in the BOM is represented in the diagram."
                )
        else:
            # Endpoints or APs - just check if at least 1 exists
            if expected_qty > 0 and actual_qty < 1:
                return False, (
                    f"BOM Mismatch: The recommended BOM specifies '{model}' (e.g., Access Points or Endpoints), "
                    f"but your diagram has 0 node(s) matching '{model_part}' in their labels. "
                    "Please ensure at least one representative node is drawn."
                )
            
    # 2. Layout & Coordinates Check (using distinct styling colors for zero regex mismatches)
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

        # Use iconType to detect node role and check rough y-coordinate correctness
        # Tolerance is generous (200px) to avoid false rejections from slight LLM variations
        if is_dc:
            if icon_type == "Chassis":  # Spine switch at y=0
                if abs(y - 0) > 200:
                    return False, f"Spine node '{node_id}' (iconType: Chassis) should be near y=0, but is at y={y}."
            elif icon_type == "Server":  # Servers at y=440
                if abs(y - 440) > 200 and abs(y - 320) > 200 and abs(y - 480) > 200:
                    return False, f"Server node '{node_id}' should be near y=440, but is at y={y}."
            # Switch (Leaf) at y=220 — skip strict check, position varies
        else:  # Campus layout
            if icon_type in ("Chassis", "Gateway"):  # Core at y=0
                if abs(y - 0) > 200:
                    return False, f"Core node '{node_id}' (iconType: {icon_type}) should be near y=0, but is at y={y}."
            elif icon_type in ("AP", "Server"):  # Endpoints at y=480
                if abs(y - 480) > 200:
                    return False, f"Endpoint node '{node_id}' (iconType: {icon_type}) should be near y=480, but is at y={y}."
            # Switch nodes (Dist y=160, Access y=320) — skip strict check, both are Switch iconType

    core_ids = [n.get("id") for n in nodes if "core" in (n.get("data") or {}).get("label", "").lower()]
    if len(core_ids) >= 2 and topology_text and "vsx" in topology_text.lower():
        has_isl = False
        for edge in edges:
            src, tgt = edge.get("source"), edge.get("target")
            if (src == core_ids[0] and tgt == core_ids[1]) or (src == core_ids[1] and tgt == core_ids[0]):
                has_isl = True
                break
        if not has_isl:
            print(f"Warning: Core switches are configured as a VSX pair, but the diagram is missing the Inter-Switch Link (ISL) edge between the core switches.")

    # Access Stacks dual-homed LACP uplinks
    access_ids = [n.get("id") for n in nodes if "access" in (n.get("data") or {}).get("label", "").lower()]
    if access_ids and len(core_ids) >= 2:
        if topology_text and any(kw in topology_text.lower() for kw in ("lacp", "lag", "redundant link", "dual-homed", "uplink redundancy")):
            for acc_id in access_ids:
                connected_cores = set()
                for edge in edges:
                    src, tgt = edge.get("source"), edge.get("target")
                    if src == acc_id and tgt in core_ids:
                        connected_cores.add(tgt)
                    elif tgt == acc_id and src in core_ids:
                        connected_cores.add(src)
                if len(connected_cores) < 2:
                    print(f"Warning: Access switch '{acc_id}' must be connected to both Core switches for uplink redundancy (LAG/LACP) as defined in the topology design.")

    return True, ""


# ──────────────────────────────────────────────────────────────
# Main validation endpoint
# ──────────────────────────────────────────────────────────────
@app.post("/api/validate-topology", response_model=ValidateResponse)
async def validate_topology(req: ValidateRequest):
    """
    Runs the 4-layer validation pipeline on Agent 4 output.
    """
    # Layer 1: JSON Extraction
    ok, parsed_dict, err = _extract_json(req.llm_output)
    if not ok:
        print(f"[Gatekeeper Layer 1] JSON parse failed: {err}")
        return ValidateResponse(status="error", message=err)

    # Layer 2: Structural Schema Check
    valid, err = _validate_structure(parsed_dict)
    if not valid:
        print(f"[Gatekeeper Layer 2] Schema check failed: {err}")
        return ValidateResponse(status="error", message=err)

    # Layer 3: Referential Integrity Check
    valid, err = _validate_referential_integrity(parsed_dict)
    if not valid:
        print(f"[Gatekeeper Layer 3] Integrity check failed: {err}")
        return ValidateResponse(status="error", message=err)

    # Layer 4: Cross-Phase Semantic Validation
    valid, err = _validate_semantic_alignment(parsed_dict, req.topology_text, req.bom_text)
    if not valid:
        print(f"[Gatekeeper Layer 4] Semantic alignment failed: {err}")
        return ValidateResponse(status="error", message=err)

    print("[Gatekeeper] All 4 layers passed. Output JSON is verified.")
    return ValidateResponse(status="ok", code=json.dumps(parsed_dict))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "topology_generation"}
