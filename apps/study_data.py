"""Validated unphased Climate Anxiety input, read without personal identifier columns."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from graph_model import GraphError

PHASE_COLUMNS = {"phase", "phase_num", "pair_order_in_phase", "pair_id_phase"}


def read_interviews(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise GraphError("La source V3 doit être interviews.csv.")
    columns = list(pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns)
    if PHASE_COLUMNS & set(columns):
        raise GraphError("Climate_Anxiety utilise un fichier sans colonnes de phase.")
    selected = {
        "PID",
        "interview_id",
        "pair_id_interview",
        "pair_order_interview",
        "question",
        "response",
    }
    frame = pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        usecols=lambda name: name in selected,
    )
    if not {"pair_id_interview", "question", "response"} <= set(frame):
        raise GraphError("Colonnes requises : pair_id_interview, question et response.")
    ids = frame.pair_id_interview.astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise GraphError("Identifiants de paires vides ou dupliqués.")
    if PHASE_COLUMNS & set(frame):
        raise GraphError("Climate_Anxiety utilise un fichier sans colonnes de phase.")
    if not {"PID", "pair_order_interview"} <= set(frame):
        raise GraphError("Colonnes requises : PID et pair_order_interview.")
    if frame.PID.astype(str).str.strip().eq("").any():
        raise GraphError("Chaque paire doit avoir un participant.")
    order = pd.to_numeric(frame.pair_order_interview, errors="coerce")
    if order.isna().any() or (order < 1).any() or (order % 1 != 0).any():
        raise GraphError("L’ordre des paires doit être un entier positif.")
    group = ["PID"] + (["interview_id"] if "interview_id" in frame else [])
    duplicate = frame.assign(_rank=order).duplicated(group + ["_rank"])
    if duplicate.any():
        raise GraphError("Ordre de paire dupliqué dans un entretien.")
    frame = frame.assign(pair_order_interview=order.astype(int))
    return frame.sort_values(
        group + ["pair_order_interview"], kind="stable"
    ).reset_index(drop=True)


def earlier_pairs(frame: pd.DataFrame, pair: str) -> pd.DataFrame:
    if not {"PID", "pair_order_interview", "pair_id_interview"} <= set(frame):
        return frame.iloc[:0]
    row = frame.loc[frame.pair_id_interview.astype(str).eq(str(pair))].iloc[0]
    order = pd.to_numeric(frame.pair_order_interview, errors="coerce")
    current = pd.to_numeric(
        pd.Series([row.pair_order_interview]), errors="coerce"
    ).iloc[0]
    if pd.isna(current):
        return frame.iloc[:0]
    selected = frame.PID.astype(str).eq(str(row.PID)) & order.lt(current)
    if "interview_id" in frame:
        selected &= frame.interview_id.astype(str).eq(str(row.interview_id))
    return (
        frame.loc[selected]
        .assign(_order=order.loc[selected])
        .sort_values("_order", kind="stable")
        .drop(columns="_order")
    )
