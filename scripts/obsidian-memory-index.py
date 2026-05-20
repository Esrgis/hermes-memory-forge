import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_INDEX_PATH = (
    Path(os.environ["LOCALAPPDATA"]) / "hermes" / "blackboard" / "obsidian_memory_index.sqlite"
    if os.environ.get("LOCALAPPDATA")
    else Path.home() / ".hermes" / "blackboard" / "obsidian_memory_index.sqlite"
)
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
DEFAULT_EXCLUDE_PARTS = {
    ".obsidian",
    ".git",
    "node_modules",
    "__pycache__",
}
DEFAULT_EXCLUDE_NAMES = {
    ".env",
    "auth.json",
}


@dataclass(frozen=True)
class Chunk:
    path: str
    heading: str
    ordinal: int
    content: str


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def connect(index_path: Path) -> sqlite3.Connection:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(index_path)
    con.row_factory = sqlite3.Row
    con.execute("pragma journal_mode=wal")
    con.execute("pragma synchronous=normal")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        create table if not exists meta (
            key text primary key,
            value text not null
        );

        create table if not exists documents (
            id integer primary key,
            path text not null unique,
            mtime real not null,
            size integer not null,
            indexed_at text not null
        );

        create virtual table if not exists chunks using fts5(
            path unindexed,
            heading,
            content,
            tokenize='unicode61'
        );
        """
    )
    con.commit()


def should_skip(path: Path, vault_path: Path) -> bool:
    rel = path.relative_to(vault_path)
    if any(part in DEFAULT_EXCLUDE_PARTS for part in rel.parts):
        return True
    if path.name in DEFAULT_EXCLUDE_NAMES:
        return True
    if path.suffix.lower() != ".md":
        return True
    return False


def iter_markdown(vault_path: Path) -> list[Path]:
    paths: list[Path] = []
    for path in vault_path.rglob("*.md"):
        if not should_skip(path, vault_path):
            paths.append(path)
    return sorted(paths, key=lambda p: str(p.relative_to(vault_path)).lower())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_markdown(path: Path, vault_path: Path, max_chars: int) -> list[Chunk]:
    rel_path = str(path.relative_to(vault_path)).replace("\\", "/")
    text = read_text(path)
    lines = text.splitlines()
    chunks: list[Chunk] = []
    heading = path.stem
    buffer: list[str] = []
    ordinal = 0

    def flush() -> None:
        nonlocal ordinal, buffer
        content = "\n".join(buffer).strip()
        if not content:
            buffer = []
            return
        while len(content) > max_chars:
            part = content[:max_chars]
            cut = max(part.rfind("\n"), part.rfind(". "), part.rfind(" "))
            if cut < max_chars // 2:
                cut = max_chars
            chunks.append(Chunk(rel_path, heading, ordinal, content[:cut].strip()))
            ordinal += 1
            content = content[cut:].strip()
        if content:
            chunks.append(Chunk(rel_path, heading, ordinal, content))
            ordinal += 1
        buffer = []

    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            flush()
            heading = match.group(2).strip()
            continue
        buffer.append(line)
    flush()

    if not chunks and text.strip():
        chunks.append(Chunk(rel_path, heading, 0, text.strip()[:max_chars]))
    return chunks


def rebuild_index(vault_path: Path, index_path: Path, max_chars: int) -> dict:
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault path not found: {vault_path}")
    if not vault_path.is_dir():
        raise NotADirectoryError(f"Vault path is not a directory: {vault_path}")

    paths = iter_markdown(vault_path)
    with connect(index_path) as con:
        init_db(con)
        con.execute("delete from chunks")
        con.execute("delete from documents")
        indexed_at = now_iso()
        chunk_count = 0
        for path in paths:
            stat = path.stat()
            con.execute(
                "insert into documents(path, mtime, size, indexed_at) values (?, ?, ?, ?)",
                (str(path.relative_to(vault_path)).replace("\\", "/"), stat.st_mtime, stat.st_size, indexed_at),
            )
            for chunk in chunk_markdown(path, vault_path, max_chars):
                con.execute(
                    "insert into chunks(path, heading, content) values (?, ?, ?)",
                    (chunk.path, chunk.heading, chunk.content),
                )
                chunk_count += 1
        con.execute(
            "insert or replace into meta(key, value) values ('vault_path', ?), ('indexed_at', ?)",
            (str(vault_path), indexed_at),
        )
        con.commit()
    return {"documents": len(paths), "chunks": chunk_count, "index_path": str(index_path)}


def search_index(index_path: Path, query: str, limit: int) -> list[dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found: {index_path}")

    def run_search(con: sqlite3.Connection, fts_query: str) -> list[sqlite3.Row]:
        return con.execute(
            """
            select
                path,
                heading,
                snippet(chunks, 2, '[', ']', '...', 24) as snippet,
                bm25(chunks) as score
            from chunks
            where chunks match ?
            order by score
            limit ?
            """,
            (fts_query, limit),
        ).fetchall()

    def fallback_query(raw_query: str) -> str:
        tokens = re.findall(r"[\w-]+", raw_query, flags=re.UNICODE)
        tokens = [token.strip("-_") for token in tokens]
        tokens = [token for token in tokens if token]
        if not tokens:
            return raw_query
        return " OR ".join(f'"{token}"' for token in tokens)

    with connect(index_path) as con:
        init_db(con)
        try:
            rows = run_search(con, query)
        except sqlite3.OperationalError:
            rows = []
        if not rows:
            rows = run_search(con, fallback_query(query))
    return [dict(row) for row in rows]


def index_stats(index_path: Path) -> dict:
    if not index_path.exists():
        return {"exists": False, "index_path": str(index_path)}
    with connect(index_path) as con:
        init_db(con)
        meta = {row["key"]: row["value"] for row in con.execute("select key, value from meta")}
        documents = con.execute("select count(*) c from documents").fetchone()["c"]
        chunks = con.execute("select count(*) c from chunks").fetchone()["c"]
    return {"exists": True, "index_path": str(index_path), "documents": documents, "chunks": chunks, "meta": meta}


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build and query a local SQLite FTS5 index for Obsidian markdown memory.")
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build")
    build.add_argument("--vault-path", type=Path, required=True)
    build.add_argument("--max-chars", type=int, default=4000)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)

    sub.add_parser("stats")

    args = parser.parse_args()
    index_path = args.index_path.expanduser().resolve()

    if args.cmd == "build":
        print_json(rebuild_index(args.vault_path.expanduser().resolve(), index_path, args.max_chars))
    elif args.cmd == "search":
        print_json(search_index(index_path, args.query, args.limit))
    elif args.cmd == "stats":
        print_json(index_stats(index_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
