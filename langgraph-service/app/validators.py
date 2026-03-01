def get_node(graph, node_id):
    return next(n for n in graph["nodes"] if n["id"] == node_id)

def validate_api_gateway_enforcement(graph):
    violations = []

    for edge in graph["edges"]:
        source = get_node(graph, edge["source"])
        target = get_node(graph, edge["target"])

        if source["zone"] == "external" and target["id"] != "api_gateway":
            violations.append("External traffic bypasses API Gateway")

    return violations


def validate_pci_isolation(graph):
    violations = []

    for edge in graph["edges"]:
        source = get_node(graph, edge["source"])
        target = get_node(graph, edge["target"])

        if source["zone"] == "pci" and target["zone"] == "external":
            violations.append("PCI component exposed externally")

    return violations


def run_architecture_validation(graph):
    violations = []
    violations += validate_api_gateway_enforcement(graph)
    violations += validate_pci_isolation(graph)

    return violations