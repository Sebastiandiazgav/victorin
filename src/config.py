from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv
import streamlit as st


load_dotenv()


@dataclass(frozen=True)
class SupabaseSettings:
    url: Optional[str]
    anon_key: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.anon_key)


ENV_URL_KEYS = ("SUPABASE_URL", "supabase_url")
ENV_KEY_KEYS = ("SUPABASE_ANON_KEY", "supabase_anon_key")


def _read_secret(name: str) -> Optional[str]:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return None


def _read_first_available(keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        secret_value = _read_secret(key)
        if secret_value:
            return secret_value
        env_value = os.getenv(key)
        if env_value:
            return env_value
    return None


def load_supabase_settings() -> SupabaseSettings:
    return SupabaseSettings(
        url=_read_first_available(ENV_URL_KEYS),
        anon_key=_read_first_available(ENV_KEY_KEYS),
    )
