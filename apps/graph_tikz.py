"""Deterministic black-and-white TikZ export; generated TeX only."""

from __future__ import annotations

import hashlib
import io
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Lock

from graph_geometry import attachment_position, point_on_route, route_points
from graph_model import GraphError, document_digest, graph_warnings, validate_document
from graph_relations import JUNCTION_KINDS, junction_symbol

PROFILE_VERSION = "monochrome-1"
UNITS_PER_MM = 4
_PDF_RENDER_LOCK = Lock()  # PDFium is not thread-safe across Streamlit sessions.
ESCAPES = {
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
}
STYLES = r"""% Narrative graph profile: monochrome-1. All text and strokes are black.
\usetikzlibrary{arrows.meta}
\tikzset{
 narrativebox/.style={rectangle,rounded corners=1.5pt,draw=black,fill=white,
   line width=.45pt,align=center,inner sep=2mm,outer sep=0pt,
   font=\fontsize{10}{12}\selectfont},
 narrativejoin/.style={draw=none,fill=white,inner sep=0pt,outer sep=0pt,
   align=center,font=\fontsize{12}{14}\selectfont},
 narrativesource/.style={draw=none,fill=white,inner sep=2mm,outer sep=0pt,
   align=center,font=\fontsize{9}{11}\selectfont},
 narrativecausal/.style={draw=black,line width=.45pt,-{Latex[length=2mm]}},
 narrativerelation/.style={draw=black,line width=.45pt},
 narrativepriority/.style={draw=black,line width=.45pt,dashed},
 narrativeannotation/.style={draw=black,line width=.3pt,densely dotted},
 narrativelabel/.style={fill=white,text=black,inner sep=1pt,font=\fontsize{9}{11}\selectfont}
}
"""


class CompilationError(GraphError):
    pass


def escape_text(text: str) -> str:
    return "".join(ESCAPES.get(c, c) for c in text.replace("\t", " "))


def _number(value: float) -> str:
    return f"{value:.5f}".rstrip("0").rstrip(".") or "0"


def _coordinate(point) -> str:
    return f"({_number(point[0] / UNITS_PER_MM)},{_number(-point[1] / UNITS_PER_MM)})"


def _lines(text: str) -> str:
    return r"\\".join(escape_text(line) for line in text.split("\n"))


def tikz_fragment(document: dict) -> str:
    doc = validate_document(document)
    out = [
        f"% Generated narrative graph; schema 1; profile {PROFILE_VERSION}.",
        f"% Graph SHA-256: {document_digest(doc)}",
        r"\begin{tikzpicture}[x=1mm,y=1mm]",
    ]
    names = {
        n["id"]: "n" + hashlib.sha256(n["id"].encode()).hexdigest()[:16]
        for n in doc["nodes"]
    }
    for n in sorted(doc["nodes"], key=lambda n: n["id"]):
        box = doc["layout"]["nodes"][n["id"]]
        center = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        style = "narrativebox"
        draft = doc.get("editor", {}).get("node_text", {}).get(n["id"])
        label = _lines(
            draft if draft is not None else n["label"] or n["code"].replace("_", " ")
        )
        if n["kind"] in JUNCTION_KINDS:
            style = "narrativejoin"
            symbol = junction_symbol(doc, n)
            label = "$" + (r"\&" if symbol == "&" else symbol) + "$"
        elif n["kind"] == "source":
            style = "narrativesource"
            label = r"\textbar{} " + label
        if n["subtopics"] and draft is None:
            label += (
                r"\\{\fontsize{8}{10}\selectfont ("
                + _lines(", ".join(n["subtopics"]).replace("_", " "))
                + ")}"
            )
        if n["scopes"] and draft is None:
            label += (
                r"\\{\fontsize{8}{10}\selectfont ["
                + _lines(", ".join(n["scopes"]).replace("_", " "))
                + "]}"
            )
        padding = 0 if style == "narrativejoin" else 4
        width = max(1, box["width"] / UNITS_PER_MM - padding)
        out.append(
            rf"\node[{style},minimum width={_number(box['width'] / 4)}mm,minimum height={_number(box['height'] / 4)}mm,text width={_number(width)}mm] ({names[n['id']]}) at {_coordinate(center)} {{{label}}};"
        )
    for e in sorted(doc["edges"], key=lambda e: e["id"]):
        view = doc["layout"]["edges"][e["id"]]
        points = route_points(doc, e)
        style = {"causal": "narrativecausal", "priority": "narrativepriority"}.get(
            e["kind"], "narrativerelation"
        )
        if "stroke" in view:
            style += "," + view["stroke"]
        if view["route"] == "bezier":
            route = f"{_coordinate(points[0])} .. controls {_coordinate(points[1])} and {_coordinate(points[2])} .. {_coordinate(points[3])}"
        else:
            route = " -- ".join(_coordinate(p) for p in points)
        out.append(rf"\draw[{style}] {route};")
        label = (
            "="
            if e["kind"] == "definition"
            else (">" if e["dominant"] == e["source"] else "<")
            if e["kind"] == "priority"
            else r"\&"
            if e["kind"] == "coexistence"
            else "+"
            if e["kind"] == "addition"
            else None
        )
        if label:
            x, y = point_on_route(points, view["route"], view["label_t"])
            out.append(
                rf"\node[narrativelabel] at {_coordinate((x + view['label_dx'], y + view['label_dy']))} {{${label}$}};"
            )
    # Source leaders use the same geometry as the canvas; they are annotations.
    for n in sorted(doc["nodes"], key=lambda n: n["id"]):
        if n["kind"] == "source" and n["attachment"] is not None:
            box = doc["layout"]["nodes"][n["id"]]
            start = (box["x"] + box["width"] / 2, box["y"])
            out.append(
                rf"\draw[narrativeannotation] {_coordinate(start)} -- {_coordinate(attachment_position(doc, n['attachment']))};"
            )
    out.append(r"\end{tikzpicture}")
    return "\n".join(out) + "\n"


def standalone_tex(document: dict) -> str:
    return (
        r"\documentclass[border=4mm]{standalone}"
        + "\n"
        + r"\usepackage[T1]{fontenc}"
        + "\n"
        + r"\usepackage[utf8]{inputenc}"
        + "\n"
        + r"\usepackage{tikz}"
        + "\n"
        + STYLES
        + r"\begin{document}"
        + "\n"
        + tikz_fragment(document)
        + r"\end{document}"
        + "\n"
    )


def publication_bundle(document: dict, revision: int, key: str) -> dict:
    """All export artifacts identify the same immutable saved graph snapshot."""
    doc = validate_document(document)
    return {
        "tikz": tikz_fragment(doc),
        "standalone": standalone_tex(doc),
        "styles": STYLES,
        "digest": document_digest(doc),
        "revision": revision,
        "document_key": key,
    }


def compile_pdf(document: dict, timeout: float = 15) -> bytes:
    """Compile in a private temporary folder; accept no arbitrary TeX input."""
    doc = validate_document(document)
    if not doc["nodes"]:
        raise CompilationError("Ajoutez un concept avant de compiler.")
    if not doc["provenance"]["import_reviewed"]:
        raise CompilationError("Vérifiez d'abord l'interprétation de l'ancien codage.")
    if graph_warnings(doc):
        raise CompilationError(
            "Corrigez ou vérifiez les avertissements du graphe avant l'export publication."
        )
    engine = shutil.which("pdflatex")
    if engine is None:
        raise CompilationError(
            "pdfLaTeX est absent. Installez TeX Live ou MacTeX pour l'aperçu PDF ; les exports JSON et LaTeX restent disponibles."
        )
    source = standalone_tex(doc)
    with tempfile.TemporaryDirectory(prefix="narrative-tex-") as folder:
        root = Path(folder)
        (root / "figure.tex").write_text(source, encoding="utf-8")
        env = os.environ.copy()
        env.update({"openin_any": "p", "openout_any": "p", "shell_escape": "f"})
        try:
            result = subprocess.run(
                [
                    engine,
                    "-no-shell-escape",
                    "-interaction=batchmode",
                    "-halt-on-error",
                    "figure.tex",
                ],
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CompilationError(
                "La compilation a dépassé le temps autorisé. Réduisez ou divisez la figure."
            ) from exc
        output = root / "figure.pdf"
        if result.returncode or not output.is_file():
            # Logs may contain private labels: never send the raw log to a browser or CI.
            raise CompilationError(
                "Compilation LaTeX impossible. Vérifiez les caractères saisis et l'installation des paquets standalone, fontenc et tikz."
            )
        if output.stat().st_size > 10_000_000:
            raise CompilationError("Le PDF produit est trop volumineux.")
        return output.read_bytes()


def pdf_preview_png(pdf: bytes) -> bytes:
    """Rasterize our compiled one-page figure without browser PDF plug-ins.

    Input comes only from the local compiler, never an uploaded PDF. Both the
    input size and rendered pixels are bounded, independently of figure extent.
    """
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
        raise CompilationError("Le document compilé n’est pas un PDF valide.")
    if len(pdf) > 32_000_000:
        raise CompilationError("PDF trop volumineux pour l’aperçu intégré.")
    import pypdfium2 as pdfium

    with _PDF_RENDER_LOCK:
        try:
            document = pdfium.PdfDocument(pdf)
            try:
                if len(document) != 1:
                    raise CompilationError("L’aperçu doit contenir une seule figure.")
                page = document[0]
                try:
                    width, height = page.get_size()
                    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
                        raise CompilationError("Dimensions PDF invalides.")
                    scale = min(
                        2.5,
                        3000 / max(width, height),
                        math.sqrt(6_000_000 / (width * height)),
                    )
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil()
                        try:
                            output = io.BytesIO()
                            image.save(output, format="PNG")
                            return output.getvalue()
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            finally:
                document.close()
        except (pdfium.PdfiumError, ValueError, OSError) as exc:
            raise CompilationError(
                "Impossible de rendre l’aperçu du PDF compilé."
            ) from exc
