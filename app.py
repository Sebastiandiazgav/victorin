from __future__ import annotations

import io
from datetime import date

import pandas as pd
import streamlit as st

from src.config import load_supabase_settings
from src.db import delete_row, get_client, fetch_table, insert_row, update_row
from src.services import (
    CAPITAL_TYPE_LABELS,
    LOAN_MODE_LABELS,
    build_balance_timeline,
    build_export_dataframe,
    build_metrics,
    capital_payload,
    changed_rows,
    editable_capital_frame,
    editable_loan_frame,
    format_currency,
    loan_payload,
    normalize_table,
)


st.set_page_config(
    page_title="Victorín | Gestión de préstamos",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)


CSS = """
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .hero-card {
        background: linear-gradient(135deg, #0f172a 0%, #134e4a 50%, #14b8a6 100%);
        color: white;
        padding: 1.4rem 1.5rem;
        border-radius: 1.2rem;
        box-shadow: 0 18px 40px rgba(2, 6, 23, 0.18);
        margin-bottom: 1rem;
    }
    .hero-card h1, .hero-card p { color: white; }
    .metric-card {
        background: white;
        border: 1px solid rgba(15, 118, 110, 0.12);
        padding: 1rem 1.1rem;
        border-radius: 1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.04);
    }
    .small-label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #5b6b7a;
        margin-bottom: 0.2rem;
    }
    .big-number {
        font-size: 1.7rem;
        font-weight: 700;
        color: #102a43;
        line-height: 1.1;
    }
    .section-card {
        background: rgba(255,255,255,0.96);
        border: 1px solid rgba(15, 118, 110, 0.1);
        border-radius: 1rem;
        padding: 1rem 1rem 0.5rem 1rem;
        margin-bottom: 1rem;
    }
</style>
"""


def add_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_fetch(table_name: str, order_by: str, refresh_token: int, client_url: str) -> pd.DataFrame:
    settings = load_supabase_settings()
    client = get_client(settings)
    if client is None:
        return pd.DataFrame()
    return normalize_table(fetch_table(client, table_name, order_by), table_name)


def render_metric(label: str, value: str, delta: str | None = None) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="small-label">{label}</div>
            <div class="big-number">{value}</div>
            {f'<div style="color:#5b6b7a;margin-top:0.25rem;">{delta}</div>' if delta else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_config() -> None:
    st.sidebar.markdown("### Victorín")
    st.sidebar.caption("Gestión de préstamos, capital e ingresos")
    st.sidebar.markdown("---")
    st.sidebar.write("Categorías de ingreso")
    st.sidebar.write("- Capital inicial")
    st.sidebar.write("- Ingreso 15")
    st.sidebar.write("- Ingreso 30")


def show_summary(metrics: dict[str, float]) -> None:
    cols = st.columns(4)
    with cols[0]:
        render_metric("Capital total", format_currency(metrics["capital_total"]))
    with cols[1]:
        render_metric("Total prestado", format_currency(metrics["loans_total"]))
    with cols[2]:
        render_metric("Saldo disponible", format_currency(metrics["available_balance"]))
    with cols[3]:
        render_metric("Capital inicial", format_currency(metrics["initial_total"]))

    extra = st.columns(2)
    with extra[0]:
        render_metric("Ingreso 15", format_currency(metrics["income_15_total"]))
    with extra[1]:
        render_metric("Ingreso 30", format_currency(metrics["income_30_total"]))


def capital_form(client, refresh_token: int) -> None:
    st.subheader("Registrar capital o ingreso")
    with st.form("capital_form", clear_on_submit=True):
        category = st.selectbox("Categoría", list(CAPITAL_TYPE_LABELS.values()))
        amount = st.number_input("Monto", min_value=0.0, step=1000.0, format="%.2f")
        entry_date = st.date_input("Fecha", value=date.today())
        note = st.text_input("Observación", placeholder="Opcional")
        submitted = st.form_submit_button("Guardar capital")
        if submitted:
            insert_row(
                client,
                "capital_entries",
                capital_payload(
                    entry_type={v: k for k, v in CAPITAL_TYPE_LABELS.items()}[category],
                    amount=amount,
                    entry_date=entry_date.isoformat(),
                    note=note,
                ),
            )
            st.session_state.refresh_token = refresh_token + 1
            st.success("Capital guardado correctamente")
            st.rerun()


def loan_form(client, refresh_token: int) -> None:
    st.subheader("Registrar préstamo")
    with st.form("loan_form", clear_on_submit=True):
        mode = st.radio("Modo de registro", list(LOAN_MODE_LABELS.values()), horizontal=True)
        borrower_name = ""
        if mode == "Detalle por persona":
            borrower_name = st.text_input("Nombre de la persona", placeholder="Ej. Juan Pérez")
        amount = st.number_input("Monto prestado", min_value=0.0, step=1000.0, format="%.2f")
        loan_date = st.date_input("Fecha del préstamo", value=date.today(), key="loan_date")
        note = st.text_input("Observación del préstamo", placeholder="Opcional")
        submitted = st.form_submit_button("Guardar préstamo")
        if submitted:
            if mode == "Detalle por persona" and not borrower_name.strip():
                st.error("Debes escribir el nombre de la persona.")
                return
            insert_row(
                client,
                "loan_entries",
                loan_payload(
                    entry_mode={v: k for k, v in LOAN_MODE_LABELS.items()}[mode],
                    amount=amount,
                    loan_date=loan_date.isoformat(),
                    borrower_name=borrower_name,
                    note=note,
                ),
            )
            st.session_state.refresh_token = refresh_token + 1
            st.success("Préstamo guardado correctamente")
            st.rerun()


def render_history(capital_df: pd.DataFrame, loan_df: pd.DataFrame) -> None:
    st.subheader("Historial y balance")
    timeline = build_balance_timeline(capital_df, loan_df)
    if timeline.empty:
        st.info("Aún no hay movimientos para mostrar.")
        return
    chart_df = timeline.copy()
    chart_df["entry_date"] = pd.to_datetime(chart_df["entry_date"])
    chart_df = chart_df.set_index("entry_date")[["balance_after"]]
    st.line_chart(chart_df, height=280)
    st.dataframe(timeline, use_container_width=True, hide_index=True)


def render_capital_manager(client, capital_df: pd.DataFrame, refresh_token: int) -> None:
    st.subheader("Editar capital e ingresos")
    editable = editable_capital_frame(capital_df)
    if editable.empty:
        st.info("No hay registros de capital para editar.")
        return
    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "entry_type_label": st.column_config.SelectboxColumn(
                "Categoría",
                options=list(CAPITAL_TYPE_LABELS.values()),
                required=True,
            ),
            "amount": st.column_config.NumberColumn("Monto", min_value=0.0, format="$%.2f"),
            "entry_date": st.column_config.DateColumn("Fecha"),
            "note": st.column_config.TextColumn("Observación"),
        },
        key=f"capital_editor_{refresh_token}",
    )
    left, right = st.columns([1, 1])
    with left:
        if st.button("Guardar cambios de capital", type="primary"):
            updates = changed_rows(capital_df, edited, "capital_entries")
            for item in updates:
                update_row(client, "capital_entries", item["id"], item["payload"])
            st.success("Cambios de capital guardados")
            st.rerun()
    with right:
        delete_ids = st.multiselect("Eliminar registros", options=editable.index.tolist(), format_func=lambda record_id: str(record_id))
        if st.button("Eliminar seleccionados de capital") and delete_ids:
            for record_id in delete_ids:
                delete_row(client, "capital_entries", record_id)
            st.success("Registros eliminados")
            st.rerun()


def render_loan_manager(client, loan_df: pd.DataFrame, refresh_token: int) -> None:
    st.subheader("Editar préstamos")

    # Pago aplicado a un préstamo existente: reduce total prestado y, por diferencia,
    # aumenta el saldo disponible en el dashboard.
    if not loan_df.empty:
        st.markdown("#### Registrar pago")
        payment_source = loan_df.copy()
        payment_source["borrower_name"] = payment_source["borrower_name"].fillna("Total agregado")
        payment_source["loan_date"] = pd.to_datetime(payment_source["loan_date"], errors="coerce").dt.date
        payment_source["amount"] = pd.to_numeric(payment_source["amount"], errors="coerce").fillna(0.0)
        payment_source = payment_source[payment_source["amount"] > 0]

        if payment_source.empty:
            st.info("No hay préstamos con saldo pendiente para aplicar pagos.")
        else:
            option_map = {
                row["id"]: f"{row['borrower_name']} | Saldo: ${row['amount']:,.2f} | Fecha: {row['loan_date']}"
                for _, row in payment_source.iterrows()
            }
            pay_col1, pay_col2, pay_col3 = st.columns([2, 1, 1])
            with pay_col1:
                selected_loan_id = st.selectbox(
                    "Préstamo",
                    options=list(option_map.keys()),
                    format_func=lambda loan_id: option_map[loan_id],
                    key=f"payment_loan_{refresh_token}",
                )
            with pay_col2:
                payment_amount = st.number_input(
                    "Monto de pago",
                    min_value=0.01,
                    step=1000.0,
                    format="%.2f",
                    key=f"payment_amount_{refresh_token}",
                )
            with pay_col3:
                apply_payment = st.button("Aplicar pago", type="secondary")

            if apply_payment:
                selected_row = payment_source.loc[payment_source["id"] == selected_loan_id].iloc[0]
                current_amount = float(selected_row["amount"])
                if payment_amount > current_amount:
                    st.error("El pago no puede ser mayor al saldo pendiente del préstamo.")
                else:
                    new_amount = round(current_amount - float(payment_amount), 2)
                    existing_note = selected_row.get("note") or ""
                    payment_note = f"Pago aplicado: ${float(payment_amount):,.2f} ({date.today().isoformat()})"
                    merged_note = f"{existing_note} | {payment_note}".strip(" |")
                    update_row(
                        client,
                        "loan_entries",
                        selected_loan_id,
                        {
                            "amount": new_amount,
                            "note": merged_note,
                        },
                    )
                    st.success("Pago aplicado correctamente.")
                    st.rerun()

        st.markdown("---")

    editable = editable_loan_frame(loan_df)
    if editable.empty:
        st.info("No hay préstamos para editar.")
        return
    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "entry_mode_label": st.column_config.SelectboxColumn(
                "Modo",
                options=list(LOAN_MODE_LABELS.values()),
                required=True,
            ),
            "borrower_name": st.column_config.TextColumn("Persona"),
            "amount": st.column_config.NumberColumn("Monto", min_value=0.0, format="$%.2f"),
            "loan_date": st.column_config.DateColumn("Fecha"),
            "note": st.column_config.TextColumn("Observación"),
        },
        key=f"loan_editor_{refresh_token}",
    )
    left, right = st.columns([1, 1])
    with left:
        if st.button("Guardar cambios de préstamos", type="primary"):
            updates = changed_rows(loan_df, edited, "loan_entries")
            for item in updates:
                update_row(client, "loan_entries", item["id"], item["payload"])
            st.success("Cambios de préstamos guardados")
            st.rerun()
    with right:
        delete_ids = st.multiselect("Eliminar préstamos", options=editable.index.tolist(), format_func=lambda record_id: str(record_id))
        if st.button("Eliminar seleccionados de préstamos") and delete_ids:
            for record_id in delete_ids:
                delete_row(client, "loan_entries", record_id)
            st.success("Préstamos eliminados")
            st.rerun()


def render_export(capital_df: pd.DataFrame, loan_df: pd.DataFrame) -> None:
    st.subheader("Exportar información")
    export_df = build_export_dataframe(capital_df, loan_df)
    csv_data = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Descargar registros en CSV",
        data=csv_data,
        file_name="victorin_registros.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.dataframe(export_df, use_container_width=True, hide_index=True)


def main() -> None:
    add_css()
    st.markdown(
        """
        <div class="hero-card">
            <h1>Victorín</h1>
            <p>Gestión de préstamos, capital e ingresos</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sidebar_config()
    settings = load_supabase_settings()
    client = get_client(settings)
    if client is None:
        st.error("Configura SUPABASE_URL y SUPABASE_ANON_KEY para activar la app.")
        st.code("SUPABASE_URL=...\nSUPABASE_ANON_KEY=...", language="text")
        st.stop()

    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = 0

    refresh_token = int(st.session_state.refresh_token)
    capital_df = cached_fetch("capital_entries", "entry_date", refresh_token, settings.url or "")
    loan_df = cached_fetch("loan_entries", "loan_date", refresh_token, settings.url or "")
    metrics = build_metrics(capital_df, loan_df)

    show_summary(metrics)

    st.markdown("---")
    tabs = st.tabs(["Registrar", "Historial", "Editar", "Exportar"])

    with tabs[0]:
        left, right = st.columns(2)
        with left:
            capital_form(client, refresh_token)
        with right:
            loan_form(client, refresh_token)

    with tabs[1]:
        render_history(capital_df, loan_df)

    with tabs[2]:
        cap_tab, loan_tab = st.tabs(["Capital e ingresos", "Préstamos"])
        with cap_tab:
            render_capital_manager(client, capital_df, refresh_token)
        with loan_tab:
            render_loan_manager(client, loan_df, refresh_token)

    with tabs[3]:
        render_export(capital_df, loan_df)

    st.markdown("---")
    st.caption("La suma de Capital inicial + Ingreso 15 + Ingreso 30 determina el capital total; luego se descuenta el total prestado para obtener el saldo disponible.")


if __name__ == "__main__":
    main()
