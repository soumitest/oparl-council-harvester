import os
from dataclasses import dataclass, field


def _csv(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    oparl_system_urls: list[str] = field(default_factory=list)
    # Keep only bodies whose AGS (official municipality key) starts with one of these.
    # "06" = Hesse (Frankfurt am Main is 06412000). Empty list = no geographic filter.
    body_ags_prefixes: list[str] = field(default_factory=lambda: ["06"])
    http_timeout: float = 20.0
    http_max_retries: int = 4

    @classmethod
    def from_env(cls) -> "Settings":
        # No credentials in source code: everything comes from the environment / .env.
        return cls(
            database_url=os.getenv("DATABASE_URL") or None,
            oparl_system_urls=_csv("OPARL_SYSTEM_URLS"),
            body_ags_prefixes=_csv("OPARL_BODY_AGS_PREFIXES", "06"),
            http_timeout=float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            http_max_retries=int(os.getenv("HTTP_MAX_RETRIES", "4")),
        )
