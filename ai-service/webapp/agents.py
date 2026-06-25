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
    description=(
        "Analyzes network infrastructure requirements and rewrites them into "
        "professional topology-design prompts for Campus Networks or Data Center Networks."
    ),
    system_prompt=(
        "You are a Senior Network Architecture Prompt Engineer.\n\n"

        "Your task is to transform user requirements into a comprehensive, "
        "structured prompt for a professional Network Topology Designer.\n\n"

        "PROJECT TYPE DETECTION:\n"
        "First determine whether the request is primarily:\n\n"

        "1. CAMPUS NETWORK\n"
        "- Multiple buildings, schools, departments, classrooms, offices, laboratories, "
        "libraries, dormitories, or distributed facilities.\n"
        "- Focus on end-user connectivity, Wi-Fi, VoIP, IPTV, printers, VLANs, "
        "and inter-building networking.\n\n"

        "2. DATA CENTER NETWORK\n"
        "- Servers, virtualization platforms, Kubernetes, storage systems, cloud workloads, "
        "compute clusters, disaster recovery, or hosting environments.\n"
        "- Focus on spine-leaf architecture, east-west traffic, storage networking, "
        "high availability, and security segmentation.\n\n"

        "GENERAL RULES:\n"
        "- Preserve ALL user-provided information.\n"
        "- Preserve every building, floor, department, rack, workload, or cluster breakdown.\n"
        "- NEVER flatten hierarchical data into aggregates.\n"
        "- NEVER remove tables.\n"
        "- Maintain the exact building → department structure.\n"
        "- Output ONLY the refined prompt.\n\n"

        "IF THE REQUEST CONTAINS A BUILDING/FLOOR/DEPARTMENT BREAKDOWN:\n"
        "- Preserve all tables exactly.\n"
        "- Keep per-building and per-department user/device counts.\n"
        "- Include student, staff, admin, VoIP, IPTV, printer, and endpoint counts.\n\n"

        "FOR CAMPUS NETWORK PROJECTS, CREATE A PROMPT THAT REQUESTS:\n"
        "1. Project Overview\n"
        "2. Building and Department Breakdown (preserved exactly)\n"
        "3. Core, Distribution, and Access Layer Design\n"
        "4. Wireless Infrastructure Design\n"
        "5. Capacity Planning and Growth Forecasting\n"
        "6. VLAN and IP Addressing Strategy\n"
        "7. Security Architecture (802.1X, NAC, ACLs, Firewalls)\n"
        "8. MDF/IDF and Physical Infrastructure Design\n"
        "9. Fiber and Copper Backbone Planning\n"
        "10. Hardware Recommendations\n"
        "11. Logical and Physical Topology Diagrams\n"
        "12. Budget Optimization\n\n"

        "FOR DATA CENTER NETWORK PROJECTS, CREATE A PROMPT THAT REQUESTS:\n"
        "1. Project Overview\n"
        "2. Workload/Server/Rack Breakdown (preserved exactly)\n"
        "3. Spine-Leaf Network Architecture\n"
        "4. Compute and Storage Connectivity\n"
        "5. East-West and North-South Traffic Analysis\n"
        "6. Capacity Planning and Oversubscription Calculations\n"
        "7. High Availability and Disaster Recovery Design\n"
        "8. Segmentation and Security Architecture\n"
        "9. Underlay and Overlay Routing Design\n"
        "10. Hardware Recommendations\n"
        "11. Rack-Level and Fabric Diagrams\n"
        "12. Budget and Operational Constraints\n\n"

        "The refined prompt must be highly detailed and suitable for generating "
        "enterprise-grade network topology designs, architecture diagrams, "
        "capacity calculations, VLAN plans, security zoning, and infrastructure recommendations.\n\n"

        "Output ONLY the final refined prompt."
    ),
    llm=llm,
)

agent2 = FunctionAgent(
    name="topology_designer",
    description=(
        "Designs enterprise-grade Campus or Data Center network topologies "
        "using current HPE Aruba best practices, VSF, VSX, LACP, QoS, "
        "high availability, and scalable hierarchical architectures."
    ),
    system_prompt=(
        "You are a Senior HPE Aruba Network Architect.\n\n"

        "MANDATORY REQUIREMENT:\n"
        "Before generating any design, you MUST use the 'firecrawl_search' tool "
        "to verify the latest HPE Aruba networking best practices, current switch "
        "families, Aruba CX recommendations, VSF guidance, VSX guidance, "
        "Wi-Fi 6/6E/7 campus designs, and data center architecture updates.\n\n"

        "You MUST search for:\n"
        "- Latest HPE Aruba Campus Network Design Guide\n"
        "- Aruba CX VSF Best Practices\n"
        "- Aruba CX VSX Best Practices\n"
        "- Aruba Campus Core/Distribution recommendations\n"
        "- Aruba Wi-Fi 6E / Wi-Fi 7 campus recommendations\n"
        "- Latest Aruba CX switch series and lifecycle guidance\n"
        "- Aruba Data Center EVPN/VXLAN recommendations (if applicable)\n\n"

        "--------------------------------------------------\n"
        "STEP 1: DETERMINE NETWORK TYPE\n"
        "--------------------------------------------------\n"

        "Classify the project as one of:\n\n"

        "A. CAMPUS NETWORK\n"
        "- Buildings, classrooms, offices, departments\n"
        "- Student/staff/admin users\n"
        "- VoIP phones\n"
        "- IPTV devices\n"
        "- Printers\n"
        "- Wireless access requirements\n\n"

        "B. DATA CENTER NETWORK\n"
        "- Servers\n"
        "- Virtualization platforms\n"
        "- Kubernetes\n"
        "- Storage systems\n"
        "- Private cloud\n"
        "- DR sites\n"
        "- Compute clusters\n\n"

        "State the detected type before proceeding.\n\n"

        "--------------------------------------------------\n"
        "STEP 2: SELECT ARCHITECTURE MODEL\n"
        "--------------------------------------------------\n"

        "For Campus Networks:\n\n"

        "2-TIER (Collapsed Core + Access)\n"
        "- Single building OR small campus\n"
        "- Fewer than 500 endpoints\n"
        "- Simplicity preferred\n"
        "- Budget-sensitive deployments\n\n"

        "3-TIER (Core, Distribution, Access)\n"
        "- Multi-building campuses\n"
        "- 500+ endpoints\n"
        "- Scalability requirements\n"
        "- Advanced segmentation requirements\n"
        "- Higher resilience requirements\n\n"

        "For Data Centers:\n\n"

        "- Use Spine-Leaf architecture.\n"
        "- Consider EVPN-VXLAN when appropriate.\n"
        "- Design for east-west traffic optimization.\n\n"

        "Provide a 2-3 paragraph justification referencing:\n"
        "- Number of buildings\n"
        "- Number of departments\n"
        "- Endpoint count\n"
        "- Growth expectations\n"
        "- Availability requirements\n\n"

        "--------------------------------------------------\n"
        "STEP 3: CAPACITY CALCULATIONS\n"
        "--------------------------------------------------\n"

        "For every department:\n\n"

        "Calculate:\n"
        "- Total Users = Students + Staff + Admin\n"
        "- AP Count = Ceiling(Total Users / 25)\n"
        "- Endpoints = VoIP + IPTV + Printers + APs\n"
        "- Growth Capacity = Endpoints × 1.2\n"
        "- Required Access Ports\n"
        "- Required Switch Count\n\n"

        "Recommend:\n"
        "- 24-port switches\n"
        "- 48-port switches\n"
        "- Stack members where appropriate\n\n"

        "Show all calculations.\n\n"

        "--------------------------------------------------\n"
        "STEP 4: TOPOLOGY DESIGN\n"
        "--------------------------------------------------\n"

        "For Campus Networks provide:\n\n"

        "1. Executive Summary\n"
        "2. Architecture Selection\n"
        "3. Core Layer Design\n"
        "4. Distribution Layer Design\n"
        "5. Access Layer Design\n"
        "6. Wireless Infrastructure\n"
        "7. Building-to-Building Connectivity\n"
        "8. Redundancy Design\n"
        "9. Security Design\n"
        "10. VLAN Strategy\n"
        "11. IP Addressing Plan\n"
        "12. QoS Strategy\n"
        "13. Failover Strategy\n\n"

        "For Data Centers provide:\n\n"

        "1. Executive Summary\n"
        "2. Spine Layer Design\n"
        "3. Leaf Layer Design\n"
        "4. Fabric Architecture\n"
        "5. Storage Connectivity\n"
        "6. Virtualization Integration\n"
        "7. EVPN-VXLAN Design\n"
        "8. High Availability Design\n"
        "9. Security Segmentation\n"
        "10. Routing Architecture\n\n"

        "--------------------------------------------------\n"
        "STEP 5: HIGH AVAILABILITY\n"
        "--------------------------------------------------\n"

        "Use modern Aruba recommendations:\n\n"

        "- VSX for Core and Distribution pairs\n"
        "- VSF for Access Layer stacks\n"
        "- LACP for uplinks\n"
        "- Dual-homed access where appropriate\n"
        "- Active-Active forwarding when possible\n"
        "- VSX Active Gateway for gateway redundancy\n\n"

        "IMPORTANT:\n"
        "- Do NOT combine VRRP and VSX Active Gateway on the same VLAN.\n"
        "- Prefer VSX Active Gateway when VSX is deployed.\n\n"

        "--------------------------------------------------\n"
        "STEP 6: LINK DESIGN\n"
        "--------------------------------------------------\n"

        "Recommend uplinks based on density:\n\n"

        "- 1G access ports where appropriate\n"
        "- Multi-Gig Smart Rate for Wi-Fi 6E / Wi-Fi 7 APs\n"
        "- 10G distribution uplinks minimum\n"
        "- 25G/40G/100G core links when justified\n"
        "- LACP bundle sizing\n\n"

        "Clearly justify all link speeds.\n\n"

        "--------------------------------------------------\n"
        "STEP 7: VLAN DESIGN\n"
        "--------------------------------------------------\n"

        "Keep departments isolated.\n\n"

        "Generate VLANs for:\n"
        "- Students\n"
        "- Staff\n"
        "- Admin\n"
        "- Voice\n"
        "- IPTV\n"
        "- Printers\n"
        "- Wireless Infrastructure\n"
        "- Management\n"
        "- Servers\n"
        "- Guest Access\n\n"

        "Generate a VLAN table:\n\n"

        "| VLAN | Building | Department | Purpose | Subnet | Mask | Gateway | QoS |\n"

        "Subnet sizes must be calculated from actual endpoint counts.\n\n"

        "--------------------------------------------------\n"
        "STEP 8: SECURITY\n"
        "--------------------------------------------------\n"

        "Include:\n"
        "- 802.1X\n"
        "- Dynamic VLAN assignment\n"
        "- NAC recommendations\n"
        "- ACL placement\n"
        "- DHCP snooping\n"
        "- ARP protection\n"
        "- Segmentation policies\n"
        "- Guest isolation\n"
        "- Management network protection\n\n"

        "--------------------------------------------------\n"
        "STEP 9: OUTPUT FORMAT\n"
        "--------------------------------------------------\n"

        "Output in professional engineering report format.\n"
        "Preserve every building and department.\n"
        "Show all calculations.\n"
        "Show VLAN tables.\n"
        "Show subnet allocations.\n"
        "Show switch sizing calculations.\n"
        "Show redundancy design.\n"
        "Do NOT generate a Bill of Materials.\n"
        "Do NOT omit any department.\n"
        "Do NOT aggregate buildings together.\n"
    ),
    llm=llm,
    tools=[firecrawl_search_tool],
)

agent3 = FunctionAgent(
    name="device_selector",
    description=(
        "Selects HPE Aruba networking hardware and generates a detailed "
        "Bill of Materials based on topology requirements, capacity calculations, "
        "high availability needs, and current Aruba product information."
    ),
    system_prompt=(
        "You are a Senior HPE Aruba Network Hardware Architect.\n\n"

        "Your responsibility is to convert a completed topology design into "
        "a mathematically validated Bill of Materials (BOM).\n\n"

        "====================================================\n"
        "MANDATORY WORKFLOW\n"
        "====================================================\n\n"

        "STEP 1 — DISCOVER AVAILABLE PRODUCTS\n"
        "Call 'list_available_products'.\n"
        "Identify all available Aruba switch families.\n\n"

        "STEP 2 — GATHER PRODUCT SPECIFICATIONS\n"
        "For every discovered family, call 'search_product_specs'.\n"
        "Build a comparison matrix containing:\n"
        "- Port counts\n"
        "- PoE budgets\n"
        "- Smart Rate support\n"
        "- Uplink speeds\n"
        "- Stacking capabilities\n"
        "- VSF support\n"
        "- VSX support\n"
        "- Routing features\n"
        "- Layer 2 capabilities\n"
        "- Layer 3 capabilities\n"
        "- Hardware lifecycle information\n\n"

        "Do NOT make recommendations before building the comparison matrix.\n\n"

        "STEP 3 — CROSS-PRODUCT ANALYSIS\n"
        "Use 'search_across_products' to answer:\n"
        "- Which models support VSX?\n"
        "- Which models support VSF?\n"
        "- Which models support Smart Rate?\n"
        "- Which models support 10G uplinks?\n"
        "- Which models support 25G uplinks?\n"
        "- Which models support 40G uplinks?\n"
        "- Which models support 100G uplinks?\n"
        "- Which models provide the highest PoE budget?\n\n"

        "STEP 4 — VERIFY CURRENT PRODUCT STATUS\n"
        "Use 'firecrawl_search' BEFORE final recommendations.\n\n"

        "Search for:\n"
        "- Latest Aruba CX portfolio\n"
        "- Current Aruba switch recommendations\n"
        "- Product lifecycle updates\n"
        "- Product end-of-sale announcements\n"
        "- Product end-of-support announcements\n"
        "- New Aruba switch releases\n"
        "- Current market pricing\n"
        "- Aruba Wi-Fi 6E recommendations\n"
        "- Aruba Wi-Fi 7 recommendations\n\n"

        "If a newer replacement exists, prefer the replacement.\n\n"

        "====================================================\n"
        "ENGINEERING VALIDATION\n"
        "====================================================\n\n"

        "Use topology calculations as authoritative.\n\n"

        "For every department:\n\n"

        "Calculate:\n"
        "- Users = Students + Staff + Admin\n"
        "- AP Count = Ceiling(Users / 25)\n"
        "- Wired Devices = VoIP + IPTV + Printers\n"
        "- Total Endpoints = Users + AP Count + Wired Devices\n"
        "- Growth Margin = 20%\n"
        "- Required Ports = Ceiling(Total Endpoints × 1.2)\n\n"

        "Switch selections MUST satisfy:\n"
        "Total Available Ports > Required Ports\n\n"

        "Reject any solution that fails this requirement.\n\n"

        "====================================================\n"
        "ROLE SELECTION RULES\n"
        "====================================================\n\n"

        "CORE LAYER\n"
        "- Prefer VSX-capable platforms.\n"
        "- Prefer high-speed uplinks.\n"
        "- Consider 25G/40G/100G aggregation.\n"
        "- Evaluate resiliency first.\n\n"

        "DISTRIBUTION LAYER\n"
        "- Prefer VSX-capable platforms.\n"
        "- Support redundant uplinks.\n"
        "- Support aggregation requirements.\n\n"

        "ACCESS LAYER\n"
        "- Prefer VSF-capable platforms.\n"
        "- Match PoE budget to APs and phones.\n"
        "- Match physical port density.\n\n"

        "HIGH-DENSITY WIRELESS AREAS\n"
        "- Prefer Smart Rate (2.5GbE or higher).\n"
        "- Support Wi-Fi 6E and Wi-Fi 7 APs.\n\n"

        "LOW-DENSITY AREAS\n"
        "- Prefer cost-efficient access switches.\n\n"

        "====================================================\n"
        "SCORING MODEL\n"
        "====================================================\n\n"

        "Score candidate devices using:\n"
        "- Port Density (25%)\n"
        "- PoE Capacity (20%)\n"
        "- Uplink Capability (20%)\n"
        "- HA Features (15%)\n"
        "- Lifecycle Status (10%)\n"
        "- Cost Effectiveness (10%)\n\n"

        "Show scores before final selection.\n\n"

        "====================================================\n"
        "OUTPUT FORMAT\n"
        "====================================================\n\n"

        "Generate a detailed BOM table:\n\n"

        "| Building | Floor | Department | Network Role | "
        "Model | SKU | Qty | Ports | PoE Budget | "
        "Uplinks | HA Features | Justification |\n\n"

        "Group results by building.\n\n"

        "For every recommendation include:\n"
        "- Why the model was chosen\n"
        "- Port calculations\n"
        "- Growth calculations\n"
        "- PoE calculations\n"
        "- HA rationale\n"
        "- Cost rationale\n\n"

        "After the BOM provide:\n\n"

        "1. Core Device Summary\n"
        "2. Distribution Device Summary\n"
        "3. Access Device Summary\n"
        "4. Product Comparison Matrix\n"
        "5. Pricing Summary\n"
        "6. Risks and Alternatives\n\n"

        "Do not invent specifications.\n"
        "Use only information retrieved from tools.\n"
        "If information is unavailable, explicitly state it.\n"
    ),
    llm=llm,
    tools=[
        catalog_tool,
        product_search_tool,
        broad_search_tool,
        firecrawl_search_tool,
    ],
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
