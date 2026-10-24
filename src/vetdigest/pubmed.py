"""PubMed E-utilities 검색 및 파싱."""
from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET

import requests

from .config import journal_clause
from .models import Article

log = logging.getLogger(__name__)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# 정정/논평 등 연구 내용이 아닌 출판 유형 제외
NON_RESEARCH = '("Published Erratum"[pt] OR "Comment"[pt] OR "Retraction of Publication"[pt] OR "Editorial"[pt] OR "News"[pt])'

# 근거 수준 가중치 (랭킹용)
PUB_TYPE_WEIGHT = {
    "Practice Guideline": 5,
    "Guideline": 5,
    "Consensus Development Conference": 5,
    "Meta-Analysis": 4.5,
    "Systematic Review": 4.5,
    "Randomized Controlled Trial": 4,
    "Clinical Trial": 3,
    "Multicenter Study": 2.5,
    "Comparative Study": 1.5,
    "Review": 1.5,
    "Case Reports": -1,
    "Letter": -1,
}
TOP_JOURNALS = {
    "J Vet Intern Med": 2.0, "J Am Vet Med Assoc": 1.0, "J Small Anim Pract": 1.0,
    "Vet J": 1.0, "J Feline Med Surg": 1.0,
    "Gastroenterology": 2.0, "Gut": 2.0, "Lancet Gastroenterol Hepatol": 2.0,
    "N Engl J Med": 2.5, "Lancet": 2.5, "Nat Med": 2.0, "J Crohns Colitis": 1.5,
}


class PubMed:
    def __init__(self, session: requests.Session | None = None):
        self.s = session or requests.Session()
        self.base = {"tool": "vet-gi-digest", "email": os.environ.get("NCBI_EMAIL", "")}
        if key := os.environ.get("NCBI_API_KEY"):
            self.base["api_key"] = key
        # API 키 없으면 초당 3회 제한
        self.delay = 0.12 if "api_key" in self.base else 0.4

    def _get(self, endpoint: str, params: dict) -> requests.Response:
        for attempt in range(4):
            time.sleep(self.delay)
            r = self.s.get(f"{EUTILS}/{endpoint}", params={**self.base, **params}, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r
        r.raise_for_status()
        return r

    def search(self, term: str, days: int, retmax: int = 200) -> list[str]:
        r = self._get("esearch.fcgi", {
            "db": "pubmed", "term": f"({term}) NOT {NON_RESEARCH}",
            "datetype": "edat", "reldate": days, "retmax": retmax,
            "retmode": "json", "sort": "pub_date",
        })
        return r.json()["esearchresult"].get("idlist", [])

    def fetch(self, pmids: list[str]) -> list[Article]:
        out: list[Article] = []
        for i in range(0, len(pmids), 100):
            r = self._get("efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids[i:i + 100]), "retmode": "xml"})
            out.extend(parse_pubmed_xml(r.content))
        return out


def _text(el: ET.Element | None) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_pubmed_xml(xml: bytes) -> list[Article]:
    root = ET.fromstring(xml)
    arts = []
    for pa in root.iter("PubmedArticle"):
        mc = pa.find("MedlineCitation")
        art = mc.find("Article")
        parts = []
        for ab in art.findall("Abstract/AbstractText"):
            label = ab.get("Label")
            parts.append(f"{label}: {_text(ab)}" if label else _text(ab))
        authors = art.findall("AuthorList/Author")
        first = authors[0] if authors else None
        if first is not None:
            name = first.findtext("LastName") or first.findtext("CollectiveName") or ""
            if ini := first.findtext("Initials"):
                name += f" {ini}"
            author_str = name + (" et al." if len(authors) > 1 else "")
        else:
            author_str = ""
        pd = art.find("Journal/JournalIssue/PubDate")
        pub_date = " ".join(x for x in [pd.findtext("Year"), pd.findtext("Month")] if x) if pd is not None else ""
        if not pub_date and pd is not None:
            pub_date = pd.findtext("MedlineDate") or ""
        doi = next((i.text or "" for i in pa.findall("PubmedData/ArticleIdList/ArticleId") if i.get("IdType") == "doi"), "")
        arts.append(Article(
            pmid=mc.findtext("PMID"),
            title=_text(art.find("ArticleTitle")),
            abstract="\n".join(parts),
            journal=mc.findtext("MedlineJournalInfo/MedlineTA") or art.findtext("Journal/ISOAbbreviation") or "",
            journal_full=art.findtext("Journal/Title") or "",
            pub_date=pub_date,
            authors=author_str,
            doi=doi,
            pub_types=[_text(p) for p in art.findall("PublicationTypeList/PublicationType")],
            mesh=[_text(m.find("DescriptorName")) for m in mc.findall("MeshHeadingList/MeshHeading")],
        ))
    return arts


def score(a: Article) -> float:
    s = max([PUB_TYPE_WEIGHT.get(t, 0) for t in a.pub_types] or [0])
    s += TOP_JOURNALS.get(a.journal, 0)
    s += 1.0 if len(a.abstract) > 400 else (-2.0 if not a.abstract else 0)
    s += 0.5 * (len(a.tags) - 1) if a.tags else 0
    return s


def collect(cfg: dict, pm: PubMed, seen: set[str]) -> dict[str, list[Article]]:
    """세 섹션(vet_gi / vet_im / human)의 신규 논문을 수집·랭킹."""
    days = cfg["lookback_days"]
    vj = cfg["vet_journals"]
    all_vet = journal_clause(vj["core"] + vj["extended"])
    core = journal_clause(vj["core"])

    # 1) 수의 소화기 심층: 주제별 검색 → 태그 부여
    #    논문 수가 적어 저널 제한 없이 검색하고, 목록 밖 저널은 랭킹에서 감점
    gi_tags: dict[str, list[str]] = {}
    for key, t in cfg["vet_gi_topics"].items():
        term = f"{t['query']} AND {cfg['species_filter']}"
        if not cfg.get("vet_gi_all_journals", True):
            term += f" AND {all_vet}"
        for pmid in pm.search(term, days):
            gi_tags.setdefault(pmid, []).append(key)
    # 'GI'(기타)는 다른 주제로 이미 잡혔으면 생략
    for tags in gi_tags.values():
        if len(tags) > 1 and "GI" in tags:
            tags.remove("GI")

    # 2) 수의 내과 일반: 핵심 저널 – 비내과 주제 – 소화기 중복
    im_ids = [p for p in pm.search(f"{core} NOT {cfg['vet_im_exclude']}", days) if p not in gi_tags]

    # 3) 사람 IBD/크론병/FMT
    hu_ids = pm.search(
        f"{cfg['human_topics']} AND {journal_clause(cfg['human_journals'])} NOT {cfg['human_exclude']}", days)

    listed = set(vj["core"] + vj["extended"])
    sections = {"vet_gi": list(gi_tags), "vet_im": im_ids, "human": hu_ids}
    result: dict[str, list[Article]] = {}
    for sec, ids in sections.items():
        ids = [p for p in dict.fromkeys(ids) if p not in seen]
        arts = pm.fetch(ids) if ids else []
        for a in arts:
            a.section = sec
            a.tags = gi_tags.get(a.pmid, []) if sec == "vet_gi" else []
            a.score = score(a)
            if sec == "vet_gi" and a.journal not in listed:
                a.score -= 1.5
        arts = [a for a in arts if a.abstract or a.score > 2]
        arts.sort(key=lambda a: a.score, reverse=True)
        result[sec] = arts[: cfg["limits"][sec]]
        log.info("%s: %d건 검색, %d건 선정", sec, len(ids), len(result[sec]))
    return result
