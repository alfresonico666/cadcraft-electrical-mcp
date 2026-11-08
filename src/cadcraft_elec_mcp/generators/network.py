"""Network topology sheet (PROFINET / Ethernet / IO-Link) as a tree rooted at the PLC.

Nodes are device boxes (tag, description, part number, IP); links are orthogonal polylines with
the port name at each end and the cable designation in the middle.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from ..domain.designation import natural_key
from ..domain.model import DeviceKind, NetworkLink, Protocol, SheetSpec
from ..drawing import add_rect, add_text
from ..errors import GenerationError
from .context import BuildContext

NODE_W = 40.0
NODE_H = 18.0
LEVEL_GAP = 20.0
MIN_NODE_W = 26.0
PROTOCOL_LAYER = {Protocol.IOLINK: "E-NET-IOLINK"}
PROTOCOL_LABEL = {
    Protocol.PROFINET: "PROFINET",
    Protocol.ETHERNET: "Ethernet",
    Protocol.IOLINK: "IO-Link",
    Protocol.PROFISAFE: "PROFIsafe",
}


@dataclass
class _Node:
    tag: str
    level: int
    x: float = 0.0
    y: float = 0.0  # top edge


def _root(ctx: BuildContext, tags: set[str]) -> str:
    cpus = [d.tag for d in ctx.project.devices_of(DeviceKind.PLC_CPU) if d.tag in tags]
    return cpus[0] if cpus else sorted(tags, key=natural_key)[0]


def _tree(
    ctx: BuildContext, links: list[NetworkLink]
) -> tuple[list[_Node], list[tuple[str, str, NetworkLink]]]:
    adjacency: dict[str, list[tuple[str, NetworkLink]]] = defaultdict(list)
    for link in links:
        adjacency[link.a_device].append((link.b_device, link))
        adjacency[link.b_device].append((link.a_device, link))
    remaining = set(adjacency)
    nodes: dict[str, _Node] = {}
    edges: list[tuple[str, str, NetworkLink]] = []
    seen_links: set[int] = set()
    while remaining:
        root = _root(ctx, remaining)
        queue = deque([root])
        nodes[root] = _Node(root, 0)
        remaining.discard(root)
        while queue:
            current = queue.popleft()
            for neighbour, link in sorted(adjacency[current], key=lambda item: natural_key(item[0])):
                if id(link) in seen_links:
                    continue
                seen_links.add(id(link))
                if neighbour not in nodes:
                    nodes[neighbour] = _Node(neighbour, nodes[current].level + 1)
                    remaining.discard(neighbour)
                    queue.append(neighbour)
                edges.append((current, neighbour, link))
    return list(nodes.values()), edges


def generate_network(ctx: BuildContext, spec: SheetSpec) -> list[int]:
    links = ctx.project.network
    if not links:
        raise GenerationError("No network links defined.", hint="Use network_link to connect devices.")
    for link in links:
        ctx.device(link.a_device)
        ctx.device(link.b_device)
    nodes, edges = _tree(ctx, links)
    geo = ctx.new_page(spec.title, spec.kind.value)
    x0, y0, x1, y1 = geo.area
    text = ctx.profile.text
    msp = ctx.msp

    levels: dict[int, list[_Node]] = defaultdict(list)
    for node in nodes:
        levels[node.level].append(node)
    max_per_level = max(len(v) for v in levels.values())
    width = min(NODE_W, (x1 - x0) / max_per_level - 6.0)
    if width < MIN_NODE_W:
        raise GenerationError(f"Too many devices on one network level ({max_per_level}) for one sheet.")
    level_pitch = min(NODE_H + LEVEL_GAP + 8.0, (y1 - y0 - 10.0) / max(len(levels), 1))
    for level, row in levels.items():
        slot = (x1 - x0) / len(row)
        for i, node in enumerate(row):
            node.x = x0 + (i + 0.5) * slot
            node.y = y1 - 8.0 - level * level_pitch
    by_tag = {n.tag: n for n in nodes}

    for node in nodes:
        device = ctx.device(node.tag)
        left, right = node.x - width / 2, node.x + width / 2
        add_rect(msp, left, node.y - NODE_H, right, node.y, layer="E-SYMBOL")
        add_text(
            msp,
            ctx.designation(device),
            (left + 1.5, node.y - 1.2),
            height=text.designation,
            layer="E-DESIG",
            align="TOP_LEFT",
        )
        lines = [device.description, device.part_number, device.data.get("ip", "")]
        for j, line in enumerate(line for line in lines if line):
            add_text(
                msp,
                line[: int((width - 3.0) / (text.general * 0.72))],
                (left + 1.5, node.y - 6.5 - j * 3.4),
                height=text.general,
                layer="E-TEXT",
                align="TOP_LEFT",
            )

    # children ports spread along the parent's bottom edge
    children: dict[str, list[tuple[str, NetworkLink]]] = defaultdict(list)
    for parent, child, link in edges:
        children[parent].append((child, link))
    for parent, kids in children.items():
        p = by_tag[parent]
        kids.sort(key=lambda item: by_tag[item[0]].x)  # left-to-right: links never cross
        for k, (child, link) in enumerate(kids):
            c = by_tag[child]
            start_x = p.x - width / 2 + width * (k + 1) / (len(kids) + 1)
            start = (start_x, p.y - NODE_H)
            end = (c.x, c.y)
            layer = PROTOCOL_LAYER.get(link.protocol, "E-NET")
            if c.level > p.level:
                mid_y = c.y + LEVEL_GAP / 2
                points = [start, (start_x, mid_y), (c.x, mid_y), end]
            else:  # cross link inside a level (ring / redundant path)
                points = [(p.x + width / 2, p.y - NODE_H / 2), (c.x - width / 2, c.y - NODE_H / 2)]
            msp.add_lwpolyline(points, dxfattribs={"layer": layer})
            parent_port = link.a_port if link.a_device == parent else link.b_port
            child_port = link.b_port if link.b_device == child else link.a_port
            if parent_port:
                add_text(
                    msp,
                    parent_port,
                    (points[0][0] + 0.8, points[0][1] - 0.8),
                    height=text.terminal,
                    layer="E-TERMINAL",
                    align="TOP_LEFT",
                )
            if child_port:
                add_text(
                    msp,
                    child_port,
                    (end[0] + 0.8, end[1] + 0.8),
                    height=text.terminal,
                    layer="E-TERMINAL",
                    align="BOTTOM_LEFT",
                )
            if len(points) == 4:
                label = PROTOCOL_LABEL[link.protocol] + (f" {link.cable}" if link.cable else "")
                if link.length_m:
                    label += f" {link.length_m:g} m"
                # written along the child's vertical drop: never collides with sibling links
                add_text(
                    msp,
                    label,
                    (end[0] - 0.8, points[2][1] - 1.0),
                    height=text.terminal,
                    layer="E-TEXT",
                    align="BOTTOM_RIGHT",
                    rotation=90,
                )
    if spec.note:
        add_text(msp, spec.note, (x0 + 1.0, y0 + 2.0), height=text.general, layer="E-TEXT")
    return [geo.number]
