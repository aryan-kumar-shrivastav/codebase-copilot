"""
End-to-end ingest pipeline: clone -> walk -> chunk -> embed -> store.

Run synchronously for the MVP (called from a background task in the API
layer); swap for a task queue (Celery/RQ) once ingest volume or repo size
makes the request-response cycle too slow.
"""
from __future__ import annotations

import os
import shutil

from sqlalchemy.orm import Session

from app.config import settings
from app.ingest.chunker import chunk_file
from app.ingest.embedder import embed_texts
from app.models import Repo, Chunk

# skip vendored/generated/binary-heavy directories — they blow up chunk
# count with zero retrieval value
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv",
    "vendor", ".next", "target", "coverage", ".pytest_cache",
}
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".pdf", ".zip", ".lock", ".min.js", ".map",
}
MAX_FILE_BYTES = 500_000  # skip generated/data files that are unreasonably large
EMBED_BATCH_SIZE = 64


def _iter_source_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if any(fname.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            full_path = os.path.join(dirpath, fname)
            try:
                if os.path.getsize(full_path) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield full_path


def clone_repo(source_url: str, dest_dir: str, branch: str | None = None) -> str:
    """Clone with GitPython. Returns the commit SHA."""
    import git

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(os.path.dirname(dest_dir), exist_ok=True)

    kwargs = {"branch": branch} if branch else {}
    repo = git.Repo.clone_from(source_url, dest_dir, depth=1, **kwargs)
    return repo.head.commit.hexsha


def run_ingest(db: Session, repo: Repo) -> None:
    """Mutates `repo` status as it progresses; commits incrementally so the
    UI can poll status mid-ingest on large repos."""
    try:
        repo.status = "ingesting"
        db.commit()

        files_processed = 0
        pending_texts: list[str] = []
        pending_chunks: list[Chunk] = []

        def flush_batch():
            nonlocal pending_texts, pending_chunks
            if not pending_texts:
                return
            embeddings = embed_texts(pending_texts)
            for chunk_obj, emb in zip(pending_chunks, embeddings):
                chunk_obj.embedding = emb
                db.add(chunk_obj)
            db.commit()
            pending_texts, pending_chunks = [], []

        for full_path in _iter_source_files(repo.local_path):
            rel_path = os.path.relpath(full_path, repo.local_path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                continue
            if not text.strip():
                continue

            for cc in chunk_file(rel_path, text):
                chunk_obj = Chunk(
                    repo_id=repo.id,
                    file_path=cc.file_path,
                    symbol_name=cc.symbol_name,
                    symbol_type=cc.symbol_type,
                    language=cc.language,
                    start_line=cc.start_line,
                    end_line=cc.end_line,
                    content=cc.content,
                    meta=cc.meta,
                )
                # embed with a little structural context prepended — helps
                # the embedding model disambiguate near-identical snippets
                # from different files/classes
                embed_input = f"# {cc.file_path} :: {cc.symbol_name or cc.symbol_type}\n{cc.content}"
                pending_texts.append(embed_input)
                pending_chunks.append(chunk_obj)

                if len(pending_texts) >= EMBED_BATCH_SIZE:
                    flush_batch()

            files_processed += 1

        flush_batch()

        repo.file_count = files_processed
        repo.chunk_count = db.query(Chunk).filter(Chunk.repo_id == repo.id).count()
        repo.status = "ready"
        db.commit()

    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        repo.status = "error"
        repo.error_message = str(exc)
        db.commit()
        raise
