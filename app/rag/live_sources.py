"""Live connectors to real government / public legal data, queried at request time.

Sources (official, free):
- Federal Register API (no key)  — US rules, notices, executive orders, presidential docs.
- CourtListener API (optional token) — US court opinions / case law.
- GovInfo API (free api.data.gov key) — US Code, CFR, bills, and more.

Each returns LiveDoc records with a real citation and the official source URL, so answers
built from them link straight back to the authoritative page. Network is required, so
these run on a machine with internet access (not the offline test sandbox). Failures in
any one source are caught and skipped so the rest of the answer still works."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from ..config import settings
from ..logging_config import get_logger

log = get_logger("lexa.live")


@dataclass
class LiveDoc:
    id: str
    text: str
    citation: str
    source_id: str
    source_url: str
    effective_date: str


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


class LiveSource(Protocol):
    name: str
    def search(self, query: str, limit: int) -> list[LiveDoc]: ...


class FederalRegisterSource:
    """https://www.federalregister.gov/developers/documentation/api/v1 — no key required."""
    name = "federal_register"

    def __init__(self, client):
        self._c = client

    def search(self, query: str, limit: int) -> list[LiveDoc]:
        r = self._c.get(
            "https://www.federalregister.gov/api/v1/documents.json",
            params={"per_page": limit, "order": "relevance",
                    "conditions[term]": query,
                    "fields[]": ["title", "abstract", "html_url", "publication_date",
                                 "document_number", "type", "citation"]},
        )
        r.raise_for_status()
        out: list[LiveDoc] = []
        for d in r.json().get("results", []):
            body = _clean(d.get("abstract") or d.get("title") or "")
            if not body:
                continue
            num = d.get("document_number", "")
            cite = d.get("citation") or f"{d.get('type','Document')} {num}".strip()
            out.append(LiveDoc(
                id=f"fedreg-{num}",
                text=f"{d.get('title','')}. {body}".strip(),
                citation=f"Federal Register: {d.get('title','')[:80]} ({cite})".strip(),
                source_id=f"federalregister/{num}",
                source_url=d.get("html_url", "https://www.federalregister.gov/"),
                effective_date=(d.get("publication_date") or "")[:10] or "unknown",
            ))
        return out


class CourtListenerSource:
    """https://www.courtlistener.com/help/api/rest/ — token optional (raises rate limits)."""
    name = "courtlistener"

    def __init__(self, client):
        self._c = client

    def search(self, query: str, limit: int) -> list[LiveDoc]:
        headers = ({"Authorization": f"Token {settings.courtlistener_token}"}
                   if settings.courtlistener_token else {})
        r = self._c.get("https://www.courtlistener.com/api/rest/v4/search/",
                        params={"q": query, "type": "o", "order_by": "score desc"},
                        headers=headers)
        r.raise_for_status()
        out: list[LiveDoc] = []
        for item in r.json().get("results", [])[:limit]:
            text = _clean(item.get("snippet", "")) or item.get("caseName", "")
            if not text:
                continue
            cid = item.get("cluster_id") or item.get("id")
            case = item.get("caseName") or f"Opinion {cid}"
            out.append(LiveDoc(
                id=f"cl-{cid}",
                text=text,
                citation=case,
                source_id=f"courtlistener/{cid}",
                source_url=f"https://www.courtlistener.com/opinion/{cid}/",
                effective_date=(item.get("dateFiled") or "")[:10] or "unknown",
            ))
        return out


class GovInfoSource:
    """https://api.govinfo.gov — requires a free api.data.gov key (GOVINFO_API_KEY)."""
    name = "govinfo"

    def __init__(self, client):
        self._c = client

    def search(self, query: str, limit: int) -> list[LiveDoc]:
        if not settings.govinfo_api_key:
            return []
        r = self._c.post(
            "https://api.govinfo.gov/search",
            params={"api_key": settings.govinfo_api_key},
            json={"query": query, "pageSize": limit, "offsetMark": "*",
                  "resultLevel": "default"},
        )
        r.raise_for_status()
        out: list[LiveDoc] = []
        for d in r.json().get("results", [])[:limit]:
            title = d.get("title", "")
            if not title:
                continue
            pid = d.get("packageId", "")
            out.append(LiveDoc(
                id=f"govinfo-{pid}",
                text=title,
                citation=f"GovInfo: {title[:90]}",
                source_id=f"govinfo/{pid}",
                source_url=d.get("download", {}).get("pdfLink")
                           or f"https://www.govinfo.gov/app/details/{pid}",
                effective_date=(d.get("dateIssued") or "")[:10] or "unknown",
            ))
        return out


_REGISTRY = {
    "federal_register": FederalRegisterSource,
    "courtlistener": CourtListenerSource,
    "govinfo": GovInfoSource,
}


def enabled_source_names() -> list[str]:
    if not settings.live_sources_enabled:
        return []
    return [n.strip() for n in settings.live_sources.split(",")
            if n.strip() in _REGISTRY]


def get_live_sources(client) -> list[LiveSource]:
    return [_REGISTRY[name](client) for name in enabled_source_names()]
