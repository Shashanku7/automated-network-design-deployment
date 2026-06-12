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
    name="d2_diagram_generator",
    description="Generates D2 diagram code.",
    system_prompt=(
        "You are a D2 Diagram Specialist.\n"
        "Generate valid D2 code. Rule: 'direction: down' first. Aggregated nodes only. "
        "Core -> Building -> Floor (Access + Devices + WiFi). "
        "Output ONLY D2 code."
    ), llm=llm_qwen_coder,
)

PHASES = [
    (1, "Prompt Rephrasing", agent1),
    (2, "Network Topology Design", agent2),
    (3, "Device Selection & BOM", agent3),
    (4, "D2 Diagram Generation", agent4),
]
