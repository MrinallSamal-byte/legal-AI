"""Ingest real court opinions from CourtListener (a free, public legal database) into the
vector store, so Lexa can ground answers in actual case law.

CourtListener API: https://www.courtlistener.com/help/api/rest/  (free; a token raises
rate limits - set COURTLISTENER_TOKEN). This script needs outbound network access, so run
it on your own machine, not in a locked-down sandbox.

Usage:
    python -m scripts.ingest_courtlistener --query "qualified immunity" --pages 2
    python -m scripts.ingest_courtlistener --court scotus --pages 1
"""
from __future__ import annotations

import argparse
import re
import sys

import httpx

# Allow running as `python scripts/ingest_courtlistener.py` too.
sys.path.insert(0, ".")

from app.config import settings  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.rag.store import Record  # noqa: E402

BASE = "https://www.courtlistener.com/api/rest/v4"


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_opinions(query: str | None, court: str | None, pages: int) -> list[Record]:
    headers = {"Authorization": f"Token {settings.courtlistener_token}"} if settings.courtlistener_token else {}
    records: list[Record] = []
    params = {"type": "o", "order_by": "score desc"}
    if query:
        params["q"] = query
    if court:
        params["court"] = court
    url = f"{BASE}/search/"
    with httpx.Client(timeout=settings.request_timeout_seconds, headers=headers) as client:
        for _ in range(pages):
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            for item in data.get("results", []):
                op_id = item.get("id")
                cluster = item.get("cluster_id") or op_id
                # Fetch full opinion text.
                text = ""
                try:
                    od = client.get(f"{BASE}/opinions/{op_id}/").json()
                    text = _clean(od.get("plain_text") or od.get("html") or od.get("html_lawbox") or "")
                except Exception:  # noqa: BLE001
                    text = _clean(item.get("snippet", ""))
                if not text:
                    continue
                case = item.get("caseName") or item.get("caseNameShort") or f"Opinion {op_id}"
                date = (item.get("dateFiled") or "")[:10] or "unknown"
                cite = item.get("citation") or case
                records.append(Record(
                    id=f"cl-{op_id}",
                    text=text[:8000],  # cap; retriever chunks it
                    citation=f"{case}" + (f", {cite[0] if isinstance(cite, list) and cite else cite}" if cite else ""),
                    source_id=f"courtlistener/opinion/{op_id}",
                    source_url=f"https://www.courtlistener.com/opinion/{cluster}/",
                    effective_date=date,
                ))
            params["cursor"] = data.get("next") and httpx.URL(data["next"]).params.get("cursor")
            if not params.get("cursor"):
                break
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest CourtListener opinions into Lexa's vector store.")
    ap.add_argument("--query", default=None, help="full-text search query")
    ap.add_argument("--court", default=None, help="court id, e.g. scotus, ca9")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--append", action="store_true",
                    help="add to existing index instead of replacing (default replaces with seed+new)")
    args = ap.parse_args()

    print(f"Fetching opinions (query={args.query!r}, court={args.court!r}, pages={args.pages})…")
    new_records = fetch_opinions(args.query, args.court, args.pages)
    print(f"Fetched {len(new_records)} opinions.")
    if not new_records:
        print("Nothing to ingest.")
        return

    r = Retriever()
    from app.rag.corpus import SEED_DOCS
    existing_docs = SEED_DOCS if not args.append else []
    # Rebuild from seed + new (simple + deterministic). For large corpora, switch to an
    # incremental store (pgvector) and append instead of rebuild.
    total = r.build_index(existing_docs + new_records)
    print(f"Index now holds {total} chunks at {settings.vector_store_path}.")


if __name__ == "__main__":
    main()
