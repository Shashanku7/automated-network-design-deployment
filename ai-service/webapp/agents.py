from llama_index.core.agent.workflow import FunctionAgent
from webapp.config import llm, llm_qwen_coder
from webapp.tools import firecrawl_search_tool, catalog_tool, product_search_tool, broad_search_tool

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
    description="Generates an interactive React Flow network topology diagram from topology and BOM text.",
    system_prompt=(
        "You are a React Flow Network Diagram Architect.\n"
        "Read the topology description and BOM table provided, then write a complete, self-contained "
        "React component that renders an interactive network diagram using React Flow.\n\n"

        "## STRICT RULES\n"
        "1. You may ONLY import from 'react' and 'reactflow'. No other libraries.\n"
        "2. Always include: import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';\n"
        "3. Always include: import 'reactflow/dist/style.css';\n"
        "4. The component MUST be named: export default function App() { ... }\n"
        "5. Output ONLY a valid JSON object — no explanation, no markdown, no extra text.\n"
        "   Format: {\"code\": \"<full React component as a properly escaped JSON string>\"}\n\n"

        "## LAYOUT RULES\n"
        "IF the input describes a CAMPUS (buildings, floors, students, staff, VoIP):\n"
        "  - Top-to-bottom hierarchical tree layout.\n"
        "  - Core switches: y=0, centered horizontally.\n"
        "  - Distribution switches: y=160, one pair per building, spaced 320px apart.\n"
        "  - Access switches: y=320, one per floor, spaced 160px apart under their building.\n"
        "  - Endpoints (APs, phones): y=480.\n\n"
        "IF the input describes a DATA CENTER (racks, servers, spine, leaf):\n"
        "  - Spine-Leaf mesh layout.\n"
        "  - Spine switches: y=0, spaced 220px apart in a horizontal row, centered.\n"
        "  - Leaf switches: y=220, spaced 220px apart in a horizontal row.\n"
        "  - Servers: y=440, grouped under their leaf switches.\n"
        "  - EVERY Leaf switch MUST have an edge to EVERY Spine switch (full mesh).\n\n"

        "## NODE STYLING\n"
        "Use the 'style' property on each node object. All nodes need: borderRadius:8, padding:10, fontSize:11, color:'#ffffff'.\n"
        "- Core / Spine:        background:'#1a1a2e', border:'2px solid #e94560'\n"
        "- Distribution / Leaf: background:'#0f3460', border:'2px solid #533483'\n"
        "- Access:              background:'#533483', border:'2px solid #e94560'\n"
        "- Endpoints / Servers: background:'#2d4059', border:'2px solid #4ecca3'\n"
        "Include device model, VLAN, and IP in the node label using \\n for line breaks.\n\n"

        "## EDGE STYLING\n"
        "Use the 'style' and 'label' properties on each edge object.\n"
        "- Core uplinks:    style:{ stroke:'#e94560', strokeWidth:3 }, label: link speed (e.g. '10G')\n"
        "- Dist links:      style:{ stroke:'#533483', strokeWidth:2 }, label: 'LAG'\n"
        "- Access links:    style:{ stroke:'#4ecca3', strokeWidth:1.5 }, label: '1G'\n"
        "- animated: true on all uplink edges.\n\n"

        "## REQUIRED APP STRUCTURE\n"
        "const nodes = [ /* one node per device extracted from the topology and BOM */ ];\n"
        "const edges = [ /* one edge per link described in the topology */ ];\n"
        "export default function App() {\n"
        "  return (\n"
        "    <div style={{width:'100vw',height:'100vh',background:'#0d1117'}}>\n"
        "      <ReactFlow nodes={nodes} edges={edges} fitView>\n"
        "        <Background color='#21262d' gap={16} />\n"
        "        <Controls />\n"
        "        <MiniMap nodeStrokeColor='#e94560' nodeColor='#0f3460' />\n"
        "      </ReactFlow>\n"
        "    </div>\n"
        "  );\n"
        "}"
    ),
    llm=llm_qwen_coder,
)

PHASES = [
    (1, "Prompt Rephrasing", agent1),
    (2, "Network Topology Design", agent2),
    (3, "Device Selection & BOM", agent3),
    (4, "React Topology Generation", agent4),
]

