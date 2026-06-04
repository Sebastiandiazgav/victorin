from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

CAPITAL_TYPE_LABELS = {
    "initial": "Capital inicial",
    "income_15": "Ingreso 15",
    "income_30": "Ingreso 30",
}

CAPITAL_LABEL_TO_TYPE = {label: key for key, label in CAPITAL_TYPE_LABELS.items()}

LOAN_MODE_LABELS = {
    "detailed": "Detalle por persona",
    "aggregate": "Solo total",
}

LOAN_LABEL_TO_MODE = {label: key for key, label in LOAN_MODE_LABELS.items()}

SUMMARY_COLUMNS = [
    "section",
    "record_type",
    "subtype",
    "name",
    "amount",
    "entry_date",
    "balance_after",
    "note",
]


def format_currency(value: float | int | None) -> str:
    amount = float(value or 0)
    return f"${amount:,.2f}"


def to_amount(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def coerce_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if value:
        return str(value)[:10]
    return date.today().isoformat()


def normalize_table(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    if df.empty:
        return df
    frame = df.copy()
    if table_name == "capital_entries":
        frame["entry_type_label"] = frame["entry_type"].map(CAPITAL_TYPE_LABELS).fillna(frame["entry_type"])
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
        frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.date
    elif table_name == "loan_entries":
        frame["entry_mode_label"] = frame["entry_mode"].map(LOAN_MODE_LABELS).fillna(frame["entry_mode"])
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
        frame["loan_date"] = pd.to_datetime(frame["loan_date"], errors="coerce").dt.date
    return frame


def build_metrics(capital_df: pd.DataFrame, loan_df: pd.DataFrame) -> dict[str, float]:
    capital_total = float(capital_df["amount"].sum()) if not capital_df.empty else 0.0
    loans_total = float(loan_df["amount"].sum()) if not loan_df.empty else 0.0
    available_balance = capital_total - loans_total

    initial_total = 0.0
    income_15_total = 0.0
    income_30_total = 0.0
    if not capital_df.empty and "entry_type" in capital_df:
        initial_total = float(capital_df.loc[capital_df["entry_type"] == "initial", "amount"].sum())
        income_15_total = float(capital_df.loc[capital_df["entry_type"] == "income_15", "amount"].sum())
        income_30_total = float(capital_df.loc[capital_df["entry_type"] == "income_30", "amount"].sum())

    return {
        "capital_total": capital_total,
        "loans_total": loans_total,
        "available_balance": available_balance,
        "initial_total": initial_total,
        "income_15_total": income_15_total,
        "income_30_total": income_30_total,
    }


def build_balance_timeline(capital_df: pd.DataFrame, loan_df: pd.DataFrame) -> pd.DataFrame:
    capital_source = pd.DataFrame()
    if not capital_df.empty:
        capital_source = capital_df.assign(
            section="Capital",
            record_type="capital",
            subtype=capital_df["entry_type"].map(CAPITAL_TYPE_LABELS).fillna(capital_df["entry_type"]),
            name=capital_df.get("note", "").fillna(""),
            amount=pd.to_numeric(capital_df["amount"], errors="coerce").fillna(0.0),
            entry_date=pd.to_datetime(capital_df["entry_date"], errors="coerce"),
            note=capital_df.get("note", "").fillna(""),
        )[["section", "record_type", "subtype", "name", "amount", "entry_date", "note"]]

    loan_source = pd.DataFrame()
    if not loan_df.empty:
        names = loan_df["borrower_name"].fillna("Total agregado") if "borrower_name" in loan_df else pd.Series(["Total agregado"] * len(loan_df))
        loan_source = loan_df.assign(
            section="Préstamos",
            record_type="loan",
            subtype=loan_df["entry_mode"].map(LOAN_MODE_LABELS).fillna(loan_df["entry_mode"]),
            name=names,
            amount=-pd.to_numeric(loan_df["amount"], errors="coerce").fillna(0.0),
            entry_date=pd.to_datetime(loan_df["loan_date"], errors="coerce"),
            note=loan_df.get("note", "").fillna(""),
        )[["section", "record_type", "subtype", "name", "amount", "entry_date", "note"]]

    combined = pd.concat([capital_source, loan_source], ignore_index=True)
    if combined.empty:
        return combined

    combined = combined.sort_values(["entry_date", "section"], ascending=[True, True]).reset_index(drop=True)
    combined["balance_after"] = combined["amount"].cumsum()
    combined["entry_date"] = pd.to_datetime(combined["entry_date"]).dt.date
    return combined[["section", "record_type", "subtype", "name", "amount", "entry_date", "balance_after", "note"]]


def build_export_dataframe(capital_df: pd.DataFrame, loan_df: pd.DataFrame) -> pd.DataFrame:
    timeline = build_balance_timeline(capital_df, loan_df)
    if timeline.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    export_df = timeline.copy()
    export_df["amount"] = export_df["amount"].astype(float)
    export_df["balance_after"] = export_df["balance_after"].astype(float)
    export_df["entry_date"] = export_df["entry_date"].astype(str)
    return export_df[SUMMARY_COLUMNS]


def capital_payload(entry_type: str, amount: float, entry_date: str, note: str) -> dict[str, Any]:
    return {
        "entry_type": entry_type,
        "amount": float(amount),
        "entry_date": entry_date,
        "note": note.strip() or None,
    }


def loan_payload(entry_mode: str, amount: float, loan_date: str, borrower_name: str, note: str) -> dict[str, Any]:
    return {
        "entry_mode": entry_mode,
        "amount": float(amount),
        "loan_date": loan_date,
        "borrower_name": borrower_name.strip() or None,
        "note": note.strip() or None,
    }


def editable_capital_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["entry_type_label", "amount", "entry_date", "note"])
    frame = df.copy()
    frame["entry_type_label"] = frame["entry_type"].map(CAPITAL_TYPE_LABELS).fillna(frame["entry_type"])
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.date
    return frame.set_index("id")[["entry_type_label", "amount", "entry_date", "note"]]


def editable_loan_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["entry_mode_label", "borrower_name", "amount", "loan_date", "note"])
    frame = df.copy()
    frame["entry_mode_label"] = frame["entry_mode"].map(LOAN_MODE_LABELS).fillna(frame["entry_mode"])
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    frame["loan_date"] = pd.to_datetime(frame["loan_date"], errors="coerce").dt.date
    return frame.set_index("id")[["entry_mode_label", "borrower_name", "amount", "loan_date", "note"]]


def changed_rows(original: pd.DataFrame, edited: pd.DataFrame, table_name: str) -> list[dict[str, Any]]:
    if original.empty:
        return []
    original = original.set_index("id") if "id" in original.columns else original
    edited = edited.set_index("id") if "id" in edited.columns else edited
    updates: list[dict[str, Any]] = []
    for row_id, row in edited.iterrows():
        if row_id not in original.index:
            continue
        source = original.loc[row_id]
        payload: dict[str, Any] = {}
        if table_name == "capital_entries":
            mapped_type = CAPITAL_LABEL_TO_TYPE.get(str(row.get("entry_type_label", "")), str(row.get("entry_type_label", "")))
            if str(source.get("entry_type")) != mapped_type:
                payload["entry_type"] = mapped_type
            amount_value = float(row.get("amount") or 0)
            if float(source.get("amount") or 0) != amount_value:
                payload["amount"] = amount_value
            new_date = coerce_date(row.get("entry_date"))
            if coerce_date(source.get("entry_date")) != new_date:
                payload["entry_date"] = new_date
            new_note = row.get("note")
            if (source.get("note") or "") != (new_note or ""):
                payload["note"] = new_note or None
        else:
            mapped_mode = LOAN_LABEL_TO_MODE.get(str(row.get("entry_mode_label", "")), str(row.get("entry_mode_label", "")))
            if str(source.get("entry_mode")) != mapped_mode:
                payload["entry_mode"] = mapped_mode
            borrower_name = row.get("borrower_name") or None
            if (source.get("borrower_name") or None) != borrower_name:
                payload["borrower_name"] = borrower_name
            amount_value = float(row.get("amount") or 0)
            if float(source.get("amount") or 0) != amount_value:
                payload["amount"] = amount_value
            new_date = coerce_date(row.get("loan_date"))
            if coerce_date(source.get("loan_date")) != new_date:
                payload["loan_date"] = new_date
            new_note = row.get("note")
            if (source.get("note") or "") != (new_note or ""):
                payload["note"] = new_note or None
        if payload:
            updates.append({"id": row_id, "payload": payload})
    return updates
