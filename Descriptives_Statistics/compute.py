"""Descriptive statistics for V3 coding: one workbook and one self-contained report.

The source database is opened read-only. No interview or coding is changed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
APP = (
    ROOT.parent
    if (ROOT.parent / "apps").is_dir()
    else ROOT.parent / "Manual_Coding_App"
)
if not (APP / "apps").is_dir():
    # Development checks can explicitly point to an isolated application copy.
    import os

    APP = Path(os.environ.get("HANDCODING_V3_APP", str(APP)))
sys.path.insert(0, str(APP / "apps"))
sys.path.insert(0, str(APP / "scripts"))
import networkx as nx  # noqa: E402 — shared V3 core is located beside this folder.
import pandas as pd  # noqa: E402 — shared V3 core is located beside this folder.
from app_config import locations, read_values, slug  # noqa: E402
from graph_metrics import analyze, packed, table_for  # noqa: E402 — shared V3 core is located beside this folder.
from graph_relations import JUNCTION_KINDS  # noqa: E402
from graph_store import GraphStore, atomic_workbook  # noqa: E402 — shared V3 core is located beside this folder.

EDGE_COLUMNS = [
    "relation_key",
    "relation_type",
    "source",
    "target",
    "n_participants",
    "n_final_participants",
    "denominator",
    "frequency",
    "n_expressed_pairs",
    "n_snapshot_pairs",
    "value_json",
]
MOTIF_COLUMNS = [
    "source",
    "middle",
    "target",
    "n_participants",
    "denominator",
    "frequency",
    "n_dag_versions",
    "n_expressed_pairs",
    "value_json",
]


def read_snapshot(path, author, dataset=None):
    if not path.is_file():
        raise ValueError("La base V3 est absente. Lancez d’abord l’application V3.")
    db = sqlite3.connect(
        "file:" + quote(str(path.resolve())) + "?mode=ro", uri=True, timeout=10
    )
    db.row_factory = sqlite3.Row
    try:
        db.execute("BEGIN")
        studies = [
            dict(r) for r in db.execute("SELECT * FROM study_info ORDER BY dataset")
        ]
        if dataset is None and len(studies) != 1:
            raise ValueError(
                "Précisez --dataset lorsque la base contient plusieurs études."
            )
        study = next(
            (r for r in studies if dataset is None or r["dataset"] == dataset), None
        )
        if not study:
            raise ValueError("Étude introuvable dans cette base.")
        canonical = GraphStore._canonical(db, study["dataset"])
        records = [
            GraphStore._decode(r)
            for r in db.execute(
                "SELECT * FROM documents WHERE dataset=? AND author=? ORDER BY pair",
                (study["dataset"], author),
            )
        ]
        analysis = analyze(canonical, records, GraphStore._reader(db))
        metadata = [
            tuple(row)
            for row in db.execute(
                "SELECT key,revision,digest FROM documents WHERE dataset=? ORDER BY key",
                (study["dataset"],),
            )
        ]
        signature = hashlib.sha256(
            packed(
                {"documents": metadata, "pairs": canonical.to_dict(orient="records")}
            ).encode()
        ).hexdigest()
        return canonical, records, analysis, study, signature
    finally:
        db.close()


def entity_label(value):
    if value.get("type") in JUNCTION_KINDS:
        kind = value["type"]
        if kind == "priority":
            return (
                "> (prioritaire : " + entity_label(value["dominant"]) + ")"
                if value.get("dominant")
                else ">"
            )
        return {"coexistence": "&", "addition": "+", "definition": "="}[kind]
    code = value.get("code", value.get("type", "?"))
    if value.get("subtopics"):
        code += " (" + ", ".join(value["subtopics"]) + ")"
    if value.get("scopes"):
        code += " [" + ", ".join(value["scopes"]) + "]"
    return code


def summarize(analysis, level="qualified", include_partial=False):
    pairs = table_for(analysis, "pairs")
    people = set(pairs.participant.astype(str)) if len(pairs) else set()
    incomplete = {
        r["participant"]
        for r in analysis["pairs"]
        if not r["coding_valid"] or not r["lineage_valid"]
    }
    eligible = people if include_partial else people - incomplete
    valid_pairs = {
        r["pair_id"]
        for r in analysis["pairs"]
        if r["participant"] in eligible and r["status"] == "coded" and r["coding_valid"]
    }
    if include_partial:
        eligible = {
            r["participant"] for r in analysis["pairs"] if r["pair_id"] in valid_pairs
        }
    denominator = len(eligible)
    rows = [
        r
        for r in analysis["occurrences"]
        if r["participant"] in eligible
        and r["pair_id"] in valid_pairs
        and r["review"] != "withdrawn"
    ]
    final_dags = {
        (r["pair_id"], r["dag_id"]) for r in analysis["dags"] if r.get("terminal")
    }
    topics = defaultdict(
        lambda: {
            "people": set(),
            "expressed": set(),
            "snapshots": set(),
            "final": set(),
        }
    )
    edges = defaultdict(
        lambda: {
            "people": set(),
            "expressed": set(),
            "snapshots": set(),
            "final": set(),
        }
    )
    for row in rows:
        if row["kind"] == "topic":
            target = topics[row["code"]]
        elif row["kind"] == "relation":
            key = (
                row["feature_key"]
                if level == "qualified"
                else row["topic_relation_key"]
            )
            target = edges[key]
            target["value_json"] = (
                row["value_json"] if level == "qualified" else row["topic_value_json"]
            )
        else:
            continue
        target["people"].add(row["participant"])
        if (row["pair_id"], row["dag_id"]) in final_dags:
            target["final"].add(row["participant"])
        target["snapshots"].add((row["participant"], row["pair_id"]))
        if row["expressed"]:
            target["expressed"].add((row["participant"], row["pair_id"]))
    topic_table = pd.DataFrame(
        [
            {
                "topic": code,
                "n_participants": len(v["people"]),
                "n_final_participants": len(v["final"]),
                "denominator": denominator,
                "frequency": len(v["people"]) / denominator if denominator else None,
                "n_expressed_pairs": len(v["expressed"]),
                "n_snapshot_pairs": len(v["snapshots"]),
            }
            for code, v in sorted(
                topics.items(), key=lambda item: (-len(item[1]["people"]), item[0])
            )
        ],
        columns=[
            "topic",
            "n_participants",
            "n_final_participants",
            "denominator",
            "frequency",
            "n_expressed_pairs",
            "n_snapshot_pairs",
        ],
    )
    edge_rows = []
    for key, v in edges.items():
        value = json.loads(v["value_json"])
        edge_rows.append(
            {
                "relation_key": key,
                "relation_type": value["relation"],
                "source": entity_label(value["source"]),
                "target": entity_label(value["target"]),
                "n_participants": len(v["people"]),
                "n_final_participants": len(v["final"]),
                "denominator": denominator,
                "frequency": len(v["people"]) / denominator if denominator else None,
                "n_expressed_pairs": len(v["expressed"]),
                "n_snapshot_pairs": len(v["snapshots"]),
                "value_json": v["value_json"],
            }
        )
    edge_table = pd.DataFrame(
        sorted(edge_rows, key=lambda r: (-r["n_participants"], r["relation_key"])),
        columns=EDGE_COLUMNS,
    )
    # Motifs are enumerated at the occurrence level, inside ONE pair and DAG.
    # Never chain aggregate edges or edges from distinct occurrences of B.
    dag_edges = defaultdict(list)
    for row in rows:
        if row["kind"] == "relation" and row["relation_type"] == "causal":
            dag_edges[(row["participant"], row["pair_id"], row["dag_id"])].append(row)
    motifs = {}
    for (person, pair, dag), relations in dag_edges.items():
        for first in relations:
            for second in relations:
                if (
                    first["target_id"] != second["source_id"]
                    or first["source_id"] == second["target_id"]
                ):
                    continue
                a = json.loads(
                    first["value_json"]
                    if level == "qualified"
                    else first["topic_value_json"]
                )
                b = json.loads(
                    second["value_json"]
                    if level == "qualified"
                    else second["topic_value_json"]
                )
                value = [a["source"], a["target"], b["target"]]
                key = packed(value)
                item = motifs.setdefault(
                    key,
                    {
                        "people": set(),
                        "versions": set(),
                        "expressed": set(),
                        "value": value,
                    },
                )
                item["people"].add(person)
                item["versions"].add((person, pair, dag))
                if first["expressed"] and second["expressed"]:
                    item["expressed"].add((person, pair))
    motif_table = pd.DataFrame(
        [
            {
                "source": entity_label(v["value"][0]),
                "middle": entity_label(v["value"][1]),
                "target": entity_label(v["value"][2]),
                "n_participants": len(v["people"]),
                "denominator": denominator,
                "frequency": len(v["people"]) / denominator if denominator else None,
                "n_dag_versions": len(v["versions"]),
                "n_expressed_pairs": len(v["expressed"]),
                "value_json": k,
            }
            for k, v in sorted(
                motifs.items(), key=lambda item: (-len(item[1]["people"]), item[0])
            )
        ],
        columns=MOTIF_COLUMNS,
    )
    cohort = pd.DataFrame(
        [
            {
                "participant": p,
                "included": p in eligible,
                "reason": "included_partial"
                if include_partial and p in incomplete and p in eligible
                else "included_complete"
                if p in eligible
                else "incomplete_or_unresolved",
            }
            for p in sorted(people)
        ],
        columns=["participant", "included", "reason"],
    )
    # Cumulative observed distinct concepts, not the number of copied boxes.
    cumulative = []
    for p in sorted(eligible):
        histories = {}
        for row in sorted(
            (r for r in analysis["pairs"] if r["participant"] == p),
            key=lambda r: (r["interview_id"], r["pair_order"]),
        ):
            seen = histories.setdefault(row["interview_id"], set())
            if row["pair_id"] in valid_pairs:
                seen.update(
                    v["code"]
                    for v in rows
                    if v["kind"] == "topic" and v["pair_id"] == row["pair_id"]
                )
            cumulative.append(
                {
                    "participant": p,
                    "interview_id": row["interview_id"],
                    "pair_id": row["pair_id"],
                    "pair_order": row["pair_order"],
                    "cumulative_topics": len(seen),
                }
            )
    group_rows = {}
    for row in rows:
        if row["kind"] == "group":
            value = json.loads(row["value_json"])
            group_rows[row["feature_key"]] = {
                "group_key": row["feature_key"],
                "operator": entity_label(value),
                "members": ", ".join(entity_label(m) for m in value["members"]),
                "dominant": entity_label(value["dominant"])
                if value.get("dominant")
                else "",
                "value_json": row["value_json"],
            }
    groups = pd.DataFrame(
        list(group_rows.values()),
        columns=["group_key", "operator", "members", "dominant", "value_json"],
    )
    return {
        "cohort": cohort,
        "groups": groups,
        "pairs": pairs,
        "dags": table_for(analysis, "dags"),
        "topics": topic_table,
        "relations": edge_table,
        "motifs": motif_table,
        "evolution": pd.DataFrame(
            cumulative,
            columns=[
                "participant",
                "interview_id",
                "pair_id",
                "pair_order",
                "cumulative_topics",
            ],
        ),
        "denominator": denominator,
    }


def svg_figure(fig):
    import matplotlib.pyplot as plt

    text = io.StringIO()
    fig.savefig(text, format="svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    return (
        "<svg" + text.getvalue().split("<svg", 1)[1]
        if "<svg" in text.getvalue()
        else ""
    )


def plot_evolution(data):
    if data.empty:
        return "<p>Aucun entretien admissible pour cette figure.</p>"
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.5))
    for index, ((person, interview), frame) in enumerate(
        data.groupby(["participant", "interview_id"], sort=True)
    ):
        ax.plot(
            frame.pair_order,
            frame.cumulative_topics,
            color="black",
            linewidth=1.1,
            linestyle=["-", "--", ":", "-."][index % 4],
            alpha=0.65,
            label="Entretien " + str(index + 1),
        )
    ax.set_xlabel("Ordre de la paire dans l’entretien")
    ax.set_ylabel("Topics distincts cumulés")
    ax.spines[["top", "right"]].set_visible(False)
    if data.groupby(["participant", "interview_id"]).ngroups <= 8:
        ax.legend(fontsize=7, frameon=False)
    return svg_figure(fig)


def plot_topics(data):
    if data.empty:
        return "<p>Aucun topic dans le périmètre retenu.</p>"
    import matplotlib.pyplot as plt

    frame = data.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, max(2.2, len(frame) * 0.28)))
    ax.barh(frame.topic, frame.frequency, color="#555")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Proportion de participants")
    ax.spines[["top", "right"]].set_visible(False)
    return svg_figure(fig)


def _network(data, min_participants=1):
    eligible = data.loc[data.n_participants.ge(min_participants)] if len(data) else data
    selected = eligible.head(40).copy()
    # Keep the complete membership of every displayed group, even beyond the
    # readability limit. A detached & would lose its scientific meaning.
    while len(data):
        group_keys = set()
        for raw in selected.value_json:
            value = json.loads(raw)
            group_keys.update(
                e["group_key"]
                for e in [value["source"], value["target"]]
                if "group_key" in e
            )
        added = []
        for index, row in data.iterrows():
            if index in selected.index or row.relation_type != "membership":
                continue
            if json.loads(row.value_json)["target"].get("group_key") in group_keys:
                added.append(index)
        if not added:
            break
        selected = pd.concat([selected, data.loc[added]])
    nodes = {}
    edges = []
    for _, row in selected.iterrows():
        value = json.loads(row.value_json)
        a, b = packed(value["source"]), packed(value["target"])
        nodes[a] = value["source"]
        nodes[b] = value["target"]
        edges.append((a, b, dict(row)))
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((a, b) for a, b, _ in edges)
    positions = nx.spring_layout(graph, seed=17, iterations=180) if graph else {}
    causal = nx.DiGraph()
    causal.add_edges_from((a, b) for a, b, r in edges if r["relation_type"] == "causal")
    cyclic = bool(causal and not nx.is_directed_acyclic_graph(causal))
    return selected, nodes, edges, positions, cyclic


def generalized_figure(data, min_participants=1):
    selected, nodes, edges, pos, cyclic = _network(data, min_participants)
    if not edges:
        return "<p>Aucune relation au seuil choisi.</p>", "", False, 0
    import textwrap

    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    fig, ax = plt.subplots(figsize=(10, 6))
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    groups = [k for k, v in nodes.items() if v.get("type") in JUNCTION_KINDS]
    ordinary = [k for k in nodes if k not in groups]
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=ordinary,
        node_color="white",
        edgecolors="black",
        node_size=1750,
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=groups,
        node_color="white",
        edgecolors="black",
        node_size=600,
        node_shape="D",
        ax=ax,
    )
    symbols = {
        "definition": "=",
        "coexistence": "&",
        "addition": "+",
        "priority": ">",
        "membership": "",
    }
    for index, (a, b, row) in enumerate(edges):
        kind = row["relation_type"]
        frequency = float(row["frequency"])
        parallel = sum(1 for x, y, _ in edges if {x, y} == {a, b}) > 1
        rad = 0.13 * (index % 2 * 2 - 1) if parallel else 0
        ax.add_patch(
            FancyArrowPatch(
                pos[a],
                pos[b],
                arrowstyle="-|>" if kind == "causal" else "-",
                connectionstyle="arc3,rad=" + str(rad),
                mutation_scale=14,
                linewidth=4 * frequency,
                color="black",
                shrinkA=22,
                shrinkB=22,
            )
        )
        x, y = (pos[a] + pos[b]) / 2
        symbol = symbols.get(kind, "")
        ax.text(
            x,
            y + rad * 0.15,
            (symbol + " " if symbol else "") + f"{frequency:.0%}",
            fontsize=7,
            ha="center",
            va="center",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
        )
    for key, value in nodes.items():
        ax.text(
            *pos[key],
            "\n".join(textwrap.wrap(entity_label(value).replace("_", " "), 18)),
            fontsize=7,
            ha="center",
            va="center",
        )
    ax.set_axis_off()
    ax.margins(0.2)
    return svg_figure(fig), generalized_tikz(nodes, edges, pos), cyclic, len(selected)


def tex_text(text):
    mapping = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        ">": r"\textgreater{}",
        "<": r"\textless{}",
    }
    return "".join(mapping.get(c, c) for c in text)


def generalized_tikz(nodes, edges, positions):
    lines = [
        r"\documentclass[tikz,border=5pt]{standalone}",
        r"\usetikzlibrary{arrows.meta}",
        r"\begin{document}",
        r"\begin{tikzpicture}[every node/.style={draw,fill=white,rounded corners,align=center,font=\scriptsize,text width=24mm,inner sep=3pt}]",
    ]
    ids = {key: "n" + str(i) for i, key in enumerate(nodes)}
    for key, value in nodes.items():
        x, y = positions[key]
        label = tex_text(entity_label(value).replace("_", " "))
        lines.append(
            r"\node ("
            + ids[key]
            + f") at ({float(x) * 6:.4f},{float(y) * 4:.4f}) "
            + "{"
            + label
            + "};"
        )
    symbols = {
        "definition": "=",
        "coexistence": r"\&",
        "addition": "+",
        "priority": "$>$",
        "membership": "",
    }
    for i, (a, b, row) in enumerate(edges):
        kind = row["relation_type"]
        frequency = float(row["frequency"])
        style = "-{Latex}," if kind == "causal" else ""
        parallel = sum(1 for x, y, _ in edges if {x, y} == {a, b}) > 1
        if parallel:
            style += "bend " + ("left" if i % 2 else "right") + "=12,"
        label = (
            (symbols.get(kind, "") + " " if symbols.get(kind) else "")
            + f"{frequency * 100:.0f}"
            + r"\%"
        )
        lines.append(
            r"\draw["
            + style
            + f"line width={frequency * 1.8:.4f}pt] ("
            + ids[a]
            + ") to node[draw=none,rounded corners=0pt,text width=,inner sep=1pt] {"
            + label
            + "} ("
            + ids[b]
            + ");"
        )
    return "\n".join(lines + [r"\end{tikzpicture}", r"\end{document}"])


def _html_table(frame, limit=30):
    if frame.empty:
        return "<p>Aucune observation admissible.</p>"
    visible = (
        frame.drop(columns=[c for c in ["relation_key", "value_json"] if c in frame])
        .head(limit)
        .copy()
    )
    if "frequency" in visible:
        visible["frequency"] = visible.frequency.map(lambda x: f"{x:.1%}")
    return visible.to_html(index=False, escape=True, border=0, classes="data")


def create_report(summary, protocol, min_participants):
    network, tex, cycle, n_shown = generalized_figure(
        summary["relations"], min_participants
    )
    n = summary["denominator"]
    excluded = len(summary["cohort"]) - n
    download = base64.b64encode(tex.encode()).decode() if tex else ""
    content = [
        f"<h1>Statistiques descriptives du codage V3</h1><p><strong>{n} participants inclus</strong> · {excluded} exclus du périmètre courant.</p>",
        "<p>Les fréquences principales comptent chaque participant une fois. Une présence dans un DAG cumulatif et une expression étayée par une citation dans une réponse sont deux mesures distinctes.</p>",
        "<h2>Évolution individuelle</h2><p>Cumul de topics distincts présents dans les DAGs validés. Les copies et redessins ne multiplient pas les concepts. L’ordre des questions peut varier entre entretiens.</p>",
        plot_evolution(summary["evolution"]),
        "<h2>Topics les plus fréquents</h2><p>Quinze premiers topics par nombre de participants.</p>",
        plot_topics(summary["topics"]),
        "<h2>Graphe généralisé</h2><p>Chaque lien est représenté une seule fois, avec une épaisseur proportionnelle à sa fréquence et son pourcentage. Les traits vers &amp; et + restent des appartenances sans pointe causale.</p>",
        network,
        f"<p>{n_shown} liens affichés au seuil de {min_participants} participant(s), avec 40 liens principaux au maximum et les appartenances nécessaires pour garder les groupes complets. Le classeur conserve toutes les relations.</p>",
        "<p><strong>Un cycle apparaît dans le réseau agrégé.</strong> Il est conservé ; les relations ne sont pas supprimées pour imposer un DAG.</p>"
        if cycle
        else "",
        "<p>Exemple de lecture : si une personne code A→B→C et une autre B→C, le réseau porte A→B à 50 % et B→C à 100 %. Le motif complet A→B→C reste à 50 %. Les chemins ne sont pas reconstruits à partir des seules fréquences marginales.</p>",
        f'<p><a download="generalized_graph.tex" href="data:application/x-tex;base64,{download}">Télécharger le code TikZ de cette figure</a></p>'
        if tex
        else "",
        "<h2>Relations</h2>",
        _html_table(summary["relations"]),
        "<h2>Motifs causaux à deux liens</h2><p>Chemins observés dans un même DAG validé, avec continuité des occurrences intermédiaires. Leur support est dédupliqué par participant. Une absence du tableau ne signifie pas un rejet du raisonnement.</p>",
        _html_table(summary["motifs"]),
        "<h2>Périmètre et reproductibilité</h2>",
        protocol.to_html(index=False, escape=True, border=0),
        "<p>Le nombre de réponses citées (n_expressed_pairs) exige une attribution à cette réponse avec une citation exacte. n_snapshot_pairs compte les figures validées contenant le lien, y compris les reprises. Les codages de différents codeurs ne sont pas mélangés. Les flèches décrivent le raisonnement codé des participants, sans établir une causalité empirique.</p>",
    ]
    style = "body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#171717}svg{max-width:100%;height:auto}h1{font-size:26px}h2{font-size:20px;margin-top:38px}.data,table{border-collapse:collapse;font-size:12px;display:block;overflow:auto}th,td{padding:7px;border-bottom:1px solid #ddd;text-align:left}a{color:#222}p{max-width:1000px}"
    return (
        '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Codage V3 — statistiques descriptives</title><style>'
        + style
        + "</style><body>"
        + "".join(content)
        + "</body></html>"
    )


def run(
    db_path,
    author,
    output,
    level="qualified",
    include_partial=False,
    min_participants=1,
    dataset=None,
):
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams.update(
        {"svg.hashsalt": "climate-v3-descriptives", "font.family": "DejaVu Sans"}
    )
    canonical, records, analysis, study, signature = read_snapshot(
        db_path, author, dataset
    )
    summary = summarize(analysis, level, include_partial)
    code_files = [Path(__file__)] + [
        APP / "apps" / name
        for name in [
            "graph_metrics.py",
            "graph_comparison.py",
            "graph_tracking.py",
            "graph_model.py",
            "graph_evidence.py",
            "graph_relations.py",
        ]
    ]
    code_signature = hashlib.sha256(
        b"".join(p.read_bytes() for p in code_files)
    ).hexdigest()
    protocol = pd.DataFrame(
        [
            {"parameter": k, "value": str(v)}
            for k, v in {
                "coding_version": "V3.0.0",
                "analysis_code_sha256": code_signature,
                "codeur": author,
                "dataset": study["dataset"],
                "coding_scheme": study["scheme_version"],
                "snapshot_signature": signature,
                "level": level,
                "include_partial": include_partial,
                "network_min_participants": min_participants,
                "denominator": summary["denominator"],
                "participant_weight": "one per relation or motif",
                "expressed_pair_rule": "human attribution + exact response quotation",
                "network_scope": "ever present in a validated DAG",
                "motif_scope": "two causal edges in one coherent DAG occurrence",
                "missing_rule": "missing is not absence",
                "python": sys.version.split()[0],
                "pandas": pd.__version__,
                "networkx": nx.__version__,
                "matplotlib": matplotlib.__version__,
            }.items()
        ]
    )
    report = create_report(summary, protocol, min_participants)
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        name: summary[name]
        for name in [
            "cohort",
            "pairs",
            "dags",
            "topics",
            "groups",
            "relations",
            "motifs",
            "evolution",
        ]
    }
    atomic_workbook(protocol, output / "descriptives.xlsx", tables)
    import os
    import tempfile

    fd, name = tempfile.mkstemp(prefix=".report-", dir=output)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(report)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, output / "report.html")
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=locations(APP)["database"],
    )
    parser.add_argument("--author", default=read_values(APP)["HANDCODING_AUTHOR"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--level", choices=["qualified", "topic"], default="qualified")
    parser.add_argument("--include-partial", action="store_true")
    parser.add_argument("--min-participants", type=int, default=1)
    parser.add_argument("--dataset")
    args = parser.parse_args()
    if (
        args.author
        not in [
            name.strip() for name in read_values(APP)["HANDCODING_AUTHORS"].split(",")
        ]
        and args.author != "Harmonized"
    ):
        parser.error(
            "Choisissez un codeur déclaré dans Configurer.command, ou Harmonized."
        )
    if args.min_participants < 1:
        parser.error("Le seuil doit être un entier positif.")
    try:
        summary = run(
            args.db.expanduser().resolve(),
            args.author,
            (args.output or locations(APP)["analyses"] / slug(args.author))
            .expanduser()
            .resolve(),
            args.level,
            args.include_partial,
            args.min_participants,
            args.dataset,
        )
    except (ValueError, sqlite3.Error, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print("Rapport et classeur créés. Participants inclus :", summary["denominator"])


if __name__ == "__main__":
    main()
