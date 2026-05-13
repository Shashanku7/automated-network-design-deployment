"""
Image Generation Service — Standalone microservice for network topology diagrams.

Accepts topology design text + BOM, generates a D2 diagram, renders it to
PNG via kroki.io, and serves the image for download.

Uses D2 (https://d2lang.com) for diagram generation — a modern, declarative
diagramming language with clean output and container support ideal for
network topologies.

Runs on port 8001 by default.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ── Config ────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent / "generated_diagrams"
OUTPUT_DIR.mkdir(exist_ok=True)

KROKI_URL = os.getenv("KROKI_URL", "https://kroki.io")

# ── FastAPI App ───────────────────────────────────
app = FastAPI(
    title="Network Diagram Image Service",
    description="Generates PNG topology diagrams from network design text using D2",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────
class DiagramRequest(BaseModel):
    """Request body for diagram generation."""
    topology: str          # The approved topology design text (Phase 2 output)
    bom: str = ""          # The device selection / BOM text (Phase 3 output)


class DiagramResponse(BaseModel):
    """Response with diagram URL and metadata."""
    success: bool
    filename: str = ""
    url: str = ""
    diagram_code: str = ""
    error: str = ""


# ── D2 Code Generator ────────────────────────────

def _sanitize_id(text: str) -> str:
    """Convert a label into a valid D2 identifier."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s.lower() or "node"


def _build_d2_from_topology(topology: str, bom: str = "") -> str:
    """
    Parse topology text and generate a D2 diagram.

    D2 uses containers for grouping (buildings → floors), connections
    with arrows, and styling for visual hierarchy.
    """
    lines = []

    # ── Direction & global styles ──
    lines.append("direction: down")
    lines.append("")

    # Parse buildings from topology text
    buildings = _extract_buildings(topology)
    has_core = bool(re.search(r"core", topology, re.IGNORECASE))

    # ── Core Layer ──
    if has_core:
        lines.append("core: Core Layer (VSX Pair) {")
        lines.append("  style: {")
        lines.append("    fill: \"#1a1a2e\"")
        lines.append("    stroke: \"#e94560\"")
        lines.append("    stroke-width: 3")
        lines.append("    font-color: \"#ffffff\"")
        lines.append("    border-radius: 8")
        lines.append("  }")
        lines.append("}")
        lines.append("")

    # ── Server / Management block ──
    has_server = bool(re.search(r"server|management|data.?center", topology, re.IGNORECASE))
    if has_server:
        lines.append("server_room: Server Room & Management {")
        lines.append("  style: {")
        lines.append("    fill: \"#2d4059\"")
        lines.append("    stroke: \"#ea5455\"")
        lines.append("    stroke-width: 2")
        lines.append("    font-color: \"#ffffff\"")
        lines.append("    border-radius: 8")
        lines.append("  }")
        lines.append("}")
        lines.append("")
        if has_core:
            lines.append("core -> server_room: 10G Uplink {")
            lines.append("  style.stroke: \"#ea5455\"")
            lines.append("}")
            lines.append("")

    # ── Buildings ──
    if buildings:
        for b_idx, building in enumerate(buildings):
            b_name = building.get("name", f"Building {b_idx + 1}")
            b_id = _sanitize_id(b_name) or f"building_{b_idx}"
            floors = building.get("floors", [])

            # Building container with distribution switch
            lines.append(f"{b_id}: {b_name} {{")
            lines.append("  style: {")
            lines.append("    fill: \"#0f3460\"")
            lines.append("    stroke: \"#533483\"")
            lines.append("    stroke-width: 2")
            lines.append("    font-color: \"#ffffff\"")
            lines.append("    border-radius: 10")
            lines.append("  }")
            lines.append("")

            # Distribution switch inside building
            dist_id = "dist_switch"
            lines.append(f"  {dist_id}: Distribution Switch {{")
            lines.append("    style: {")
            lines.append("      fill: \"#16213e\"")
            lines.append("      stroke: \"#0f3460\"")
            lines.append("      stroke-width: 2")
            lines.append("      font-color: \"#ffffff\"")
            lines.append("      border-radius: 6")
            lines.append("    }")
            lines.append("  }")
            lines.append("")

            # Floor containers
            for f_idx, floor in enumerate(floors):
                f_name = floor.get("name", f"Floor {f_idx + 1}")
                f_id = _sanitize_id(f_name) or f"floor_{f_idx}"
                students = floor.get("students", "0")
                staff = floor.get("staff", "0")
                admins = floor.get("admins", "0")

                total_users = (
                    (int(students) if str(students).isdigit() else 0)
                    + (int(staff) if str(staff).isdigit() else 0)
                    + (int(admins) if str(admins).isdigit() else 0)
                )

                lines.append(f"  {f_id}: {f_name} {{")
                lines.append("    style: {")
                lines.append("      fill: \"#1a1a40\"")
                lines.append("      stroke: \"#533483\"")
                lines.append("      font-color: \"#ffffff\"")
                lines.append("      border-radius: 6")
                lines.append("    }")
                lines.append("")

                # Access switch
                lines.append(f"    access: Access Switch {{")
                lines.append("      style: {")
                lines.append("        fill: \"#533483\"")
                lines.append("        stroke: \"#e94560\"")
                lines.append("        font-color: \"#ffffff\"")
                lines.append("        border-radius: 4")
                lines.append("      }")
                lines.append("    }")
                lines.append("")

                # User groups
                user_parts = []
                if int(students) if str(students).isdigit() else 0:
                    user_parts.append(f"{students} Students")
                if int(staff) if str(staff).isdigit() else 0:
                    user_parts.append(f"{staff} Staff")
                if int(admins) if str(admins).isdigit() else 0:
                    user_parts.append(f"{admins} Admins")

                if user_parts:
                    user_label = " | ".join(user_parts)
                    lines.append(f"    users: {user_label} {{")
                    lines.append("      style: {")
                    lines.append("        fill: \"#e94560\"")
                    lines.append("        stroke: \"#ff6b6b\"")
                    lines.append("        font-color: \"#ffffff\"")
                    lines.append("        border-radius: 4")
                    lines.append("      }")
                    lines.append("    }")
                    lines.append("")
                    lines.append(f"    access -> users: Endpoints")

                # Wi-Fi AP count
                if total_users > 0:
                    ap_count = max(1, total_users // 25)
                    lines.append(f"    wifi: {ap_count} Wi-Fi APs {{")
                    lines.append("      style: {")
                    lines.append("        fill: \"#4ecca3\"")
                    lines.append("        stroke: \"#36b37e\"")
                    lines.append("        font-color: \"#1a1a2e\"")
                    lines.append("        border-radius: 4")
                    lines.append("      }")
                    lines.append("    }")
                    lines.append(f"    access -> wifi: PoE")

                lines.append("  }")  # close floor
                lines.append("")

                # Connect distribution → floor access switch
                lines.append(f"  {dist_id} -> {f_id}.access: LAG {{")
                lines.append("    style.stroke: \"#533483\"")
                lines.append("  }")
                lines.append("")

            lines.append("}")  # close building
            lines.append("")

            # Connect core → building distribution
            if has_core:
                lines.append(f"core -> {b_id}.{dist_id}: 10G Fiber {{")
                lines.append("  style.stroke: \"#e94560\"")
                lines.append("}")
                lines.append("")
    else:
        # No buildings parsed — fallback generic diagram
        lines.extend(_build_generic_d2(topology))

    # ── Security / sensitive areas ──
    sensitive = _extract_sensitive_areas(topology)
    if sensitive:
        lines.append("security: Security Zones {")
        lines.append("  style: {")
        lines.append("    fill: \"#800020\"")
        lines.append("    stroke: \"#ff4444\"")
        lines.append("    font-color: \"#ffffff\"")
        lines.append("    border-radius: 8")
        lines.append("  }")
        for area in sensitive:
            area_id = _sanitize_id(area)
            lines.append(f"  {area_id}: {area}")
        lines.append("}")
        if has_core:
            lines.append("core -> security: Firewall")
        lines.append("")

    return "\n".join(lines)


def _extract_buildings(text: str) -> list:
    """Extract building/floor data from topology text using regex heuristics."""
    buildings = []

    # Pattern 1: Look for "Building N: Name (M floors)" style
    building_pattern = r"(?:Building\s*\d+[:\s]*)?([A-Za-z][A-Za-z0-9 _-]+?)\s*\((\d+)\s*floors?\)"
    building_matches = list(re.finditer(building_pattern, text, re.IGNORECASE))

    if building_matches:
        for m in building_matches:
            b_name = m.group(1).strip()
            floor_count = int(m.group(2))
            floors = _extract_floors_for_building(text, b_name, floor_count)
            buildings.append({"name": b_name, "floors": floors})
    else:
        # Pattern 2: Look for building headers like "### Building 1: ..."
        header_pattern = r"###?\s*Building\s*\d+[:\s]*([^\n(]+)"
        for m in re.finditer(header_pattern, text):
            b_name = m.group(1).strip()
            floors = _extract_floors_for_building(text, b_name, 3)
            buildings.append({"name": b_name, "floors": floors})

    return buildings


def _extract_floors_for_building(text: str, building_name: str, default_count: int) -> list:
    """Extract floor details from text near a building reference."""
    floors = []

    # Look for table rows with floor data: | 1 | Name | students | staff | admins |
    table_pattern = r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"

    # Find section around the building name
    b_pos = text.lower().find(building_name.lower())
    if b_pos >= 0:
        section = text[b_pos:b_pos + 2000]
        for m in re.finditer(table_pattern, section):
            floors.append({
                "name": m.group(2).strip(),
                "students": m.group(3),
                "staff": m.group(4),
                "admins": m.group(5),
            })

    if not floors:
        for i in range(default_count):
            floors.append({
                "name": "Ground Floor" if i == 0 else f"Floor {i}",
                "students": "?",
                "staff": "?",
                "admins": "?",
            })

    return floors


def _extract_sensitive_areas(text: str) -> list:
    """Extract mentioned sensitive/security areas from topology text."""
    areas = []
    keywords = [
        "finance", "examination", "server room", "library",
        "research lab", "medical", "data center", "dmz",
    ]
    for kw in keywords:
        if re.search(kw, text, re.IGNORECASE):
            areas.append(kw.title())
    return areas


def _build_generic_d2(topology: str) -> list:
    """Build a generic network diagram when we can't parse specific buildings."""
    lines = []

    lines.append("core: Core Switch (VSX Pair) {")
    lines.append("  style: {")
    lines.append("    fill: \"#1a1a2e\"")
    lines.append("    stroke: \"#e94560\"")
    lines.append("    stroke-width: 3")
    lines.append("    font-color: \"#ffffff\"")
    lines.append("    border-radius: 8")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("dist1: Distribution Block 1 {")
    lines.append("  style: {")
    lines.append("    fill: \"#16213e\"")
    lines.append("    stroke: \"#0f3460\"")
    lines.append("    font-color: \"#ffffff\"")
    lines.append("    border-radius: 8")
    lines.append("  }")
    lines.append("  acc1: Access Switch 1")
    lines.append("  acc2: Access Switch 2")
    lines.append("  acc1 -> ep1: Endpoints A")
    lines.append("  acc2 -> ep2: Endpoints B")
    lines.append("}")
    lines.append("")
    lines.append("dist2: Distribution Block 2 {")
    lines.append("  style: {")
    lines.append("    fill: \"#16213e\"")
    lines.append("    stroke: \"#0f3460\"")
    lines.append("    font-color: \"#ffffff\"")
    lines.append("    border-radius: 8")
    lines.append("  }")
    lines.append("  acc3: Access Switch 3")
    lines.append("  acc3 -> ep3: Endpoints C")
    lines.append("}")
    lines.append("")
    lines.append("core -> dist1: 10G LAG")
    lines.append("core -> dist2: 10G LAG")
    lines.append("")

    return lines


# ── Rendering ─────────────────────────────────────
async def _render_via_kroki(code: str, diagram_type: str = "d2") -> bytes:
    """Render D2 diagram code to SVG via kroki.io."""
    url = f"{KROKI_URL}/{diagram_type}/svg"
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            url,
            content=code.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Kroki returned {resp.status_code}: {resp.text[:300]}"
            )
        return resp.content


# ── API Endpoints ─────────────────────────────────

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "image-generation", "diagram_lang": "d2", "output_dir": str(OUTPUT_DIR)}


@app.post("/api/generate-diagram", response_model=DiagramResponse)
async def generate_diagram(req: DiagramRequest):
    """
    Generate a network topology diagram SVG from topology text.

    1. Parses the topology text to extract building/floor structure
    2. Builds a D2 diagram
    3. Renders to SVG via kroki.io
    4. Saves to generated_diagrams/ folder
    5. Returns the download URL
    """
    try:
        # Step 1: Generate D2 diagram code
        diagram_code = _build_d2_from_topology(req.topology, req.bom)

        # Step 2: Render to SVG via kroki
        svg_data = await _render_via_kroki(diagram_code, "d2")

        # Step 3: Save to disk
        ts = datetime.now()
        filename = f"{ts:%Y-%m-%d_%H-%M-%S}_topology.svg"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(svg_data)

        return DiagramResponse(
            success=True,
            filename=filename,
            url=f"/api/diagrams/{filename}",
            diagram_code=diagram_code,
        )

    except Exception as e:
        return DiagramResponse(
            success=False,
            error=f"Diagram generation failed: {str(e)}",
        )


@app.get("/api/diagrams/{filename}")
async def get_diagram(filename: str):
    """Serve a generated diagram SVG for viewing or download."""
    filepath = OUTPUT_DIR / filename
    if not filepath.exists() or not filename.endswith(".svg"):
        raise HTTPException(status_code=404, detail="Diagram not found")
    return FileResponse(
        filepath,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@app.get("/api/diagrams/{filename}/download")
async def download_diagram(filename: str):
    """Force-download a generated diagram SVG."""
    filepath = OUTPUT_DIR / filename
    if not filepath.exists() or not filename.endswith(".svg"):
        raise HTTPException(status_code=404, detail="Diagram not found")
    return FileResponse(
        filepath,
        media_type="image/svg+xml",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/diagrams")
async def list_diagrams():
    """List all generated diagrams."""
    files = sorted(OUTPUT_DIR.glob("*.svg"), reverse=True)
    return {
        "diagrams": [
            {
                "filename": f.name,
                "url": f"/api/diagrams/{f.name}",
                "download_url": f"/api/diagrams/{f.name}/download",
                "size_bytes": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
            }
            for f in files
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
