"""
SQLAlchemy document storage for Napoleon Mastermind.

Repo markdown/TOML files remain the seed source. Runtime reads and writes go
through this module so containers only need persistent SQLite state.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from python_header import get, get_int  # noqa: F401 - loads config.conf/.env
from sqlalchemy import DateTime, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "STATE"

ALLOWED_FOLDERS = {"config", "members_ai", "members", "members_agents", "sessions", "PROMPT"}
ALLOWED_ROOT_SUFFIXES = {".md"}
ALLOWED_SUFFIXES = {".md", ".toml"}


def _table_prefix() -> str:
    raw = get("NAPOLEON_DB_PREFIX", "napoleon")
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw.strip())
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return f"{cleaned}_" if cleaned else ""


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = f"{_table_prefix()}documents"

    path: Mapped[str] = mapped_column(String(512), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="seed")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


_ENGINE = None
_SESSION = None


def database_url() -> str:
    backend = get("NAPOLEON_DB_BACKEND", "sqlite").lower()
    if backend == "blank":
        backend = "sqlite"
    if backend == "sqlite":
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{STATE_DIR / 'napoleon.sqlite3'}"

    host = get("NAPOLEON_DB_HOST")
    port = get("NAPOLEON_DB_PORT")
    name = get("NAPOLEON_DB_NAME")
    user = quote_plus(get("NAPOLEON_DB_USER"))
    password = quote_plus(get("NAPOLEON_DB_PW"))
    auth = f"{user}:{password}@" if user or password else ""
    port_part = f":{port}" if port else ""

    if backend in {"postgres", "postgresql"}:
        return f"postgresql+psycopg://{auth}{host}{port_part}/{name}"
    if backend in {"mysql", "mariadb"}:
        return f"mysql+pymysql://{auth}{host}{port_part}/{name}"
    raise RuntimeError(f"Unsupported NAPOLEON_DB_BACKEND={backend!r}")


def engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(database_url(), future=True)
    return _ENGINE


def session_factory():
    global _SESSION
    if _SESSION is None:
        _SESSION = sessionmaker(engine(), expire_on_commit=False, future=True)
    return _SESSION


def normalize_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("forbidden path")
    normalized = candidate.as_posix().lstrip("./")
    if not normalized:
        raise ValueError("empty path")

    suffix = Path(normalized).suffix
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("only .md/.toml allowed")

    parts = normalized.split("/")
    if len(parts) == 1:
        if suffix not in ALLOWED_ROOT_SUFFIXES:
            raise ValueError("forbidden root file")
        return normalized

    if parts[0] not in ALLOWED_FOLDERS:
        raise ValueError("forbidden folder")
    return normalized


def init_db() -> None:
    Base.metadata.create_all(engine())


def document_count() -> int:
    init_db()
    with session_factory()() as session:
        return int(session.scalar(select(func.count()).select_from(Document)) or 0)


def read_document(path: str) -> str | None:
    normalized = normalize_path(path)
    init_db()
    with session_factory()() as session:
        doc = session.get(Document, normalized)
        return doc.content if doc else None


def document_exists(path: str) -> bool:
    return read_document(path) is not None


def write_document(path: str, content: str, source: str = "user") -> None:
    normalized = normalize_path(path)
    init_db()
    with session_factory()() as session:
        doc = session.get(Document, normalized)
        if doc is None:
            doc = Document(path=normalized, content=content, source=source)
            session.add(doc)
        else:
            doc.content = content
            doc.source = source
        session.commit()


def append_document(path: str, text: str) -> None:
    current = read_document(path) or ""
    write_document(path, f"{current}{text}", source="user")


def list_document_paths(folder: str | None = None, suffix: str = ".md") -> list[str]:
    init_db()
    with session_factory()() as session:
        paths = session.scalars(select(Document.path).order_by(Document.path)).all()
    result: list[str] = []
    prefix = f"{folder}/" if folder else ""
    for path in paths:
        if folder and not path.startswith(prefix):
            continue
        if "/" in path[len(prefix):]:
            continue
        if suffix and not path.endswith(suffix):
            continue
        result.append(path)
    return result


def list_document_names(folder: str, suffix: str = ".md") -> list[str]:
    return sorted(Path(path).name for path in list_document_paths(folder, suffix=suffix))


def list_document_stems(folder: str, suffix: str = ".md") -> list[str]:
    return sorted(Path(path).stem for path in list_document_paths(folder, suffix=suffix))


def list_root_markdown() -> list[str]:
    return sorted(Path(path).name for path in list_document_paths(None, suffix=".md") if "/" not in path)


def _seed_paths() -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for relative in ["config/mastermind_config.toml", "rules.md"]:
        path = BASE_DIR / relative
        if path.is_file():
            paths.append((relative, path))
    for folder in ["members_ai", "members", "members_agents", "sessions", "PROMPT"]:
        source_dir = BASE_DIR / folder
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.glob("*.md")):
            paths.append((f"{folder}/{path.name}", path))
    return paths


def import_presets(force: bool = False) -> dict:
    init_db()
    if not force and document_count() > 0:
        return {"ok": True, "imported": 0, "skipped": True}

    imported = 0
    with session_factory()() as session:
        if force:
            session.query(Document).delete()
        for relative, source_path in _seed_paths():
            content = source_path.read_text(encoding="utf-8")
            doc = session.get(Document, relative)
            if doc is None:
                session.add(Document(path=relative, content=content, source="seed"))
                imported += 1
            elif force:
                doc.content = content
                doc.source = "seed"
                imported += 1
        session.commit()
    return {"ok": True, "imported": imported, "skipped": False}


def import_if_empty() -> dict:
    return import_presets(force=False)


def export_to_files() -> dict:
    init_db()
    exported = 0
    with session_factory()() as session:
        docs = session.scalars(select(Document).order_by(Document.path)).all()
        for doc in docs:
            normalized = normalize_path(doc.path)
            target = (BASE_DIR / normalized).resolve()
            if not target.is_relative_to(BASE_DIR):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(doc.content, encoding="utf-8")
            exported += 1
    return {"ok": True, "exported": exported}
