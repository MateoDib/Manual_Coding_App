"""Small normalized analysis interface; complete graph revisions remain primary."""

from graph_metrics import TABLE_COLUMNS

INTEGER_FIELDS = {
    "pair_order",
    "revision",
    "source_revision",
    "parent_revision",
    "dag_number",
    "coding_valid",
    "history_complete",
    "lineage_valid",
    "seen_before",
    "expressed",
    "terminal",
    "quote_start",
    "quote_end",
}


def ensure_analysis_schema(db):
    changed = False
    for name, columns in TABLE_COLUMNS.items():
        fields = ["dataset TEXT NOT NULL", "author TEXT NOT NULL"] + [
            c + (" INTEGER" if c in INTEGER_FIELDS or c.startswith("n_") else " TEXT")
            for c in columns
        ]
        db.execute(
            "CREATE TABLE IF NOT EXISTS analysis_"
            + name
            + " ("
            + ",".join(fields)
            + ")"
        )
        existing = {
            r[1] for r in db.execute("PRAGMA table_info(analysis_" + name + ")")
        }
        for column in columns:
            if column not in existing:
                db.execute(
                    "ALTER TABLE analysis_"
                    + name
                    + " ADD COLUMN "
                    + column
                    + (
                        " INTEGER"
                        if column in INTEGER_FIELDS or column.startswith("n_")
                        else " TEXT"
                    )
                )
                changed = True
        db.execute(
            "CREATE INDEX IF NOT EXISTS owner_"
            + name
            + " ON analysis_"
            + name
            + "(dataset,author)"
        )
    views = {
        "pair_statistics": "SELECT * FROM analysis_pairs",
        "dag_statistics": "SELECT * FROM analysis_dags",
        "dag_derivations": "SELECT * FROM analysis_dag_parents",
        "topics": "SELECT dataset,author,participant,pair_id,pair_order,dag_id,object_id,code,origin,source_pair,source_author,source_dag,source_object,source_change,seen_before,review,expressed,quote,quote_start,quote_end FROM analysis_occurrences WHERE kind='topic'",
        "qualifications": "SELECT dataset,author,participant,pair_id,dag_id,object_id,kind,code,subtopic,scope,seen_before,expressed FROM analysis_occurrences WHERE kind IN ('subtopic','scope')",
        "relations": "SELECT dataset,author,participant,pair_id,pair_order,dag_id,object_id,relation_type,source_id,target_id,source_code,target_code,origin,source_pair,source_author,source_change,seen_before,review,expressed,quote,feature_key,value_json,topic_relation_key,topic_value_json FROM analysis_occurrences WHERE kind='relation'",
        "groups": "SELECT dataset,author,participant,pair_id,dag_id,object_id,feature_key,value_json,origin,source_pair,source_author,source_change,quote FROM analysis_occurrences WHERE kind='group'",
        "coding_changes": "SELECT * FROM analysis_changes",
        "relation_frequencies": "SELECT * FROM analysis_frequencies",
    }
    for name, query in views.items():
        # The refresh marker is cleared by any coding save in this study.
        # A stale materialized row is visible as stale, never silently current.
        wrapped = (
            "SELECT v.*, EXISTS(SELECT 1 FROM analysis_runs r WHERE r.dataset=v.dataset AND r.author=v.author) AS analysis_current FROM ("
            + query
            + ") v"
        )
        statement = "CREATE VIEW " + name + " AS " + wrapped
        old = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name=?", (name,)
        ).fetchone()
        if not old or old[0] != statement:
            db.execute("DROP VIEW IF EXISTS " + name)
            db.execute(statement)
            changed = True
    if changed:
        db.execute("DELETE FROM analysis_runs")
