from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from src.config import SupabaseSettings


@st.cache_resource(show_spinner=False)
def get_supabase_client(url: str, anon_key: str) -> Client:
    return create_client(url, anon_key)


def get_client(settings: SupabaseSettings) -> Client | None:
    if not settings.is_configured:
        return None
    return get_supabase_client(settings.url or "", settings.anon_key or "")


def fetch_table(client: Client, table_name: str, order_by: str) -> pd.DataFrame:
    response = client.table(table_name).select("*").order(order_by, desc=True).execute()
    data = response.data or []
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


def insert_row(client: Client, table_name: str, payload: dict[str, Any]) -> None:
    client.table(table_name).insert(payload).execute()


def update_row(client: Client, table_name: str, row_id: str, payload: dict[str, Any]) -> None:
    client.table(table_name).update(payload).eq("id", row_id).execute()


def delete_row(client: Client, table_name: str, row_id: str) -> None:
    client.table(table_name).delete().eq("id", row_id).execute()
