"""Typed relation units; priority belongs to an operand, never a screen side."""

JUNCTION_KINDS = frozenset({"coexistence", "addition", "definition", "priority"})
BINARY_KINDS = frozenset({"definition", "priority"})


def member_ids(document, node_id):
    return [
        e["source"]
        for e in document["edges"]
        if e["kind"] == "membership" and e["target"] == node_id
    ]


def junction_symbol(document, node):
    if node["kind"] != "priority":
        return {"coexistence": "&", "addition": "+", "definition": "="}.get(
            node["kind"], ""
        )
    members = list(dict.fromkeys(member_ids(document, node["id"])))
    dominant = node.get("dominant")
    if dominant not in members or len(members) != 2:
        return "<" if node.get("label") == "<" else ">"
    other = next(v for v in members if v != dominant)
    boxes = document["layout"]["nodes"]
    a, b = boxes[dominant], boxes[other]
    dx = (a["x"] + a["width"] / 2) - (b["x"] + b["width"] / 2)
    if abs(dx) > 1e-6:
        return ">" if dx < 0 else "<"
    return ">" if a["y"] + a["height"] / 2 <= b["y"] + b["height"] / 2 else "<"
