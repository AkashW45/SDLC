def generate_mermaid_from_architecture(graph: dict) -> str:
    lines = []
    lines.append("graph TD")

    for node in graph.get("nodes", []):
        node_id = node["id"]
        label = f'{node["name"]}'
        lines.append(f'{node_id}["{label}"]')

    for edge in graph.get("edges", []):
        lines.append(
            f'{edge["source"]} -->|{edge["protocol"]}| {edge["target"]}'
        )

    return "\n".join(lines)