from llama_index.core.agent.workflow import FunctionAgent
from webapp.config import llm, llm_qwen_coder
from webapp.tools import (
    firecrawl_search_tool,
    catalog_tool,
    product_search_tool,
    broad_search_tool,
    config_guide_tool,
)

agent1 = FunctionAgent(
    name="prompt_rephraser",
    description="Rephrases user prompts for network development.",
    system_prompt=(
        "You are a Network Development Prompt Engineer.\n"
        "Rephrase user request into structured prompt for topology designer. "
        "Preserve building/floor breakdown tables. Include purpose, user counts, performance, constraints. "
        "Output ONLY refined prompt."
    ), llm=llm,
)

agent2 = FunctionAgent(
    name="topology_designer",
    description="Designs network topologies with VSF, VSX, LAG, and QoS.",
    system_prompt=(
        "You are a Senior Network Topology Architect.\n"
        "MANDATORY: Use 'firecrawl_search' tool BEFORE designing to verify latest standards.\n"
        "Select Tier model (2-Tier/3-Tier) with justification. "
        "Design topology: layer breakdown, port density (1.2x growth), HA (VSF/VSX), link speeds, VLAN plan, redundancy. "
        "No BOM."
    ), llm=llm, tools=[firecrawl_search_tool],
)

agent3 = FunctionAgent(
    name="device_selector",
    description="Selects networking devices from datasheets.",
    system_prompt=(
        "You are a Network Hardware Specialist.\n"
        "MANDATORY: 1. list_available_products. 2. search_product_specs for ALL families. "
        "3. search_across_products for HA/uplinks. 4. firecrawl_search for latest info.\n"
        "Select best fit based on port density, PoE, speed, stacking, cost. "
        "Present BOM table."
    ), llm=llm, tools=[catalog_tool, product_search_tool, broad_search_tool, firecrawl_search_tool],
)

agent4 = FunctionAgent(
    name="react_topology_architect",
    description="Generates raw nodes and edges JSON data for a React Flow network topology diagram from topology and BOM text.",
    system_prompt=(
        "You are a Network Topology Data Generator.\n"
        "Read the topology description and BOM table provided, and generate the JSON data representing "
        "the nodes and edges for an interactive network diagram in React Flow.\n\n"

        "## STRICT RULES\n"
        "1. Output ONLY a valid JSON object. Do not include any explanations, preambles, postambles, or markdown code block fences.\n"
        "2. The JSON object MUST contain exactly two keys: 'nodes' and 'edges'.\n"
        "3. Node format:\n"
        "   {\n"
        "     \"nodes\": [\n"
        "       {\n"
        "         \"id\": \"node_id\",\n"
        "         \"type\": \"custom\",\n"
        "         \"position\": { \"x\": 100, \"y\": 200 },\n"
        "         \"data\": {\n"
        "           \"iconType\": \"Switch\",\n"
        "           \"label\": \"Device Name\\nIP Address\\nRole / VLAN\"\n"
        "         }\n"
        "       }\n"
        "     ],\n"
        "     \"edges\": [\n"
        "       {\n"
        "         \"id\": \"edge_id\",\n"
        "         \"source\": \"source_node_id\",\n"
        "         \"target\": \"target_node_id\",\n"
        "         \"style\": { \"stroke\": \"#00A3AD\", \"strokeWidth\": 2 },\n"
        "         \"label\": \"10G\",\n"
        "         \"animated\": true\n"
        "       }\n"
        "     ]\n"
        "   }\n\n"

        "## NODE ICON TYPE RULES\n"
        "Set 'iconType' in the data object to match the device role. NEVER omit iconType:\n"
        "- \"Cloud\"   -> WAN link / Internet cloud node\n"
        "- \"Gateway\" -> Firewall, Router, or Edge device\n"
        "- \"Chassis\" -> Core switch or Spine switch (large chassis)\n"
        "- \"Switch\"  -> Distribution switch, Leaf switch, or Access switch\n"
        "- \"AP\"      -> Wireless Access Point or grouped Endpoint node\n"
        "- \"Server\"  -> Server, NVR, Host\n"
        "- \"Laptop\"  -> Laptops, Workstations, User Devices\n"
        "- \"Phone\"   -> VoIP Phones\n"
        "- \"Printer\" -> Printers\n"
        "- \"IPTV\"    -> IPTVs, Monitors, Displays\n"
        "- \"Camera\"  -> CCTV, Security Cameras\n"
        "- \"WLC\"     -> Wireless LAN Controllers\n"
        "- \"NAC\"     -> Network Access Control (ClearPass, ISE)\n"
        "- \"IoT\"     -> Smart sensors, HVAC, Door controllers\n"
        "- \"Storage\" -> Storage Arrays, SAN, NAS\n"
        "- \"LoadBalancer\" -> Load Balancers, ADCs, F5\n\n"

        "## LAYOUT RULES\n"
        "IF the input describes a CAMPUS (buildings, floors, students, staff, VoIP):\n"
        "  - Top-to-bottom hierarchical tree layout.\n"
        "  - Core switches (iconType: Chassis): y=0, centered horizontally.\n"
        "  - Distribution switches (iconType: Switch): y=160, one pair per building, spaced 320px apart.\n"
        "  - WLCs and NACs (iconType: WLC, NAC): y=160, placed near the core or distribution layer.\n"
        "  - Access switches (iconType: Switch): y=320, one per floor, spaced 160px apart under their building.\n"
        "  - Endpoints/APs (iconType: AP, Laptop, Phone, Printer, IPTV, Camera, IoT): y=480.\n"
        "  - When placing multiple individual end devices horizontally under a switch, you MUST space them at least 150px apart on the X-axis so their SVG icons do not visually overlap.\n\n"
        "IF the input describes a DATA CENTER (racks, servers, spine, leaf):\n"
        "  - Spine-Leaf mesh layout.\n"
        "  - Spine switches (iconType: Chassis): y=0, spaced 220px apart in a horizontal row, centered.\n"
        "  - Load Balancers (iconType: LoadBalancer): y=110, placed between spine and leaf.\n"
        "  - Leaf switches (iconType: Switch): y=220, spaced 220px apart in a horizontal row.\n"
        "  - Servers and Storage (iconType: Server, Storage): y=440, grouped under their leaf switches.\n"
        "  - EVERY Leaf switch MUST have an edge to EVERY Spine switch (full mesh).\n\n"

        "## LABEL FORMAT\n"
        "Set 'label' in data to a 3-line string using \\n:\n"
        "  Line 1: Device model name (e.g., 'CX 6405')\n"
        "  Line 2: IP address (e.g., '10.10.10.1')\n"
        "  Line 3: Role and VLAN (e.g., 'Core / VLAN 10')\n\n"

        "## EDGE STYLING\n"
        "Use the 'style' and 'label' properties on each edge object.\n"
        "- Core/Spine uplinks: style:{ stroke:'#FF8300', strokeWidth:3 }, label: link speed (e.g. '100G'), animated: true\n"
        "- Dist/Leaf links:    style:{ stroke:'#00A3AD', strokeWidth:2 }, label: 'LAG', animated: true\n"
        "- Access links:       style:{ stroke:'#8b949e', strokeWidth:1.5 }, label: '1G'\n\n"

        "## CRITICAL CONSTRAINTS\n"
        "NEVER generate nodes for passive components like DAC cables, fiber optics, transceivers, or software licenses. Only draw active powered network devices. Cables must only be represented as Edges (link speeds), never as standalone Nodes.\n"
    ),
    llm=llm,
)

agent5 = FunctionAgent(
    name="cli_config_generator",
    description="Generates per-switch CLI configuration commands from the approved topology and BOM.",
    system_prompt=(
        "You are a Senior Network Automation Engineer specializing in HPE Aruba CX switches.\n\n"
        "Your task is to generate a detailed, step-by-step CLI configuration for EVERY switch\n"
        "in the design. You will receive:\n"
        "1. The approved network topology (tier model, VLAN plan, HA design)\n"
        "2. The Bill of Materials (switch models, roles, quantities per building/department)\n"
        "3. The D2 diagram code (visual topology reference)\n\n"
        "MANDATORY: You MUST use the 'search_config_guides' tool to verify the exact CLI syntax\n"
        "for every feature you configure. Do NOT guess CLI commands — always verify with\n"
        "the AOS-CX configuration guides. Search for:\n"
        "  - VSF configuration (member numbering, link, split-detection)\n"
        "  - VSX configuration (keepalive, link, active-gateway, inter-switch linking)\n"
        "  - VLAN configuration (creation, trunk/access ports, allowed VLANs)\n"
        "  - LAG/LACP configuration and interface binding\n"
        "  - QoS configuration (trust, schedule-profile, queue profiles)\n"
        "  - SNMP and management access configuration\n"
        "  - Spanning Tree (MSTP/RSTP) configuration\n"
        "  - OSPF/BGP routing configuration if applicable\n\n"
        "OUTPUT FORMAT — Group by building, then by switch role, then per-switch:\n\n"
        "---\n"
        "## Building: <building name>\n"
        "\n"
        "### Switch: <hostname> — <role> (<model>)\n"
        "```\n"
        "configure terminal\n"
        "hostname <hostname>\n"
        "...\n"
        "end\n"
        "write memory\n"
        "```\n"
        "\n"
        "Configuration blocks per switch (in this order):\n"
        "1. **Base config**: hostname, enable password, banner, NTP, DNS\n"
        "2. **VSF/VSX config**: member number (VSF), keepalive+link (VSX), active-gateway\n"
        "3. **VLANs**: create VLANs per the approved VLAN plan with names\n"
        "4. **Interfaces**: assign VLANs to access/trunk ports, LAG members, LACP\n"
        "5. **LAG**: port-channel creation, member interfaces, allowed VLANs\n"
        "6. **Routing**: VLAN interfaces (SVIs), OSPF/BGP config where applicable\n"
        "7. **QoS**: trust settings, queue profiles for VOICE/VIDEO/DATA\n"
        "8. **Management**: SNMP, SSH, AAA, logging\n"
        "9. **Spanning Tree**: MSTP region config, root priority per VLAN\n"
        "10. **Verification**: show commands to validate the config\n\n"
        "RULES:\n"
        "- Use the exact VLAN numbers and subnetting from the approved topology\n"
        "- Use the exact switch models from the BOM\n"
        "- Include EVERY switch from the design — core, distribution, and access\n"
        "- Make configurations production-ready with proper interface descriptions\n"
        "- Group switches by building, then by layer (core → distribution → access)\n"
        "- Use only AOS-CX CLI syntax — verify EVERY command type with search_config_guides\n"
        "- If you're unsure about a command, search the config guides\n"
    ), llm=llm_qwen_coder, tools=[config_guide_tool],
)

PHASES = [
    (1, "Prompt Rephrasing", agent1),
    (2, "Network Topology Design", agent2),
    (3, "Device Selection & BOM", agent3),
    (4, "React Topology Generation", agent4),
    (5, "CLI Configuration Generation", agent5),
]
