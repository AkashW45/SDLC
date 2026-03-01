def generate_mermaid_from_graph(arch):

    lines = ["flowchart LR"]

    for comp in arch.get("components", []):
        comp_id = comp["name"].lower().replace(" ", "_")
        lines.append(f'{comp_id}["{comp["name"]}"]')

    for interaction in arch.get("interactions", []):
        src = interaction["source"].lower().replace(" ", "_")
        tgt = interaction["target"].lower().replace(" ", "_")
        label = interaction.get("protocol", "")
        lines.append(f'{src} -->|{label}| {tgt}')

    return "\n".join(lines)