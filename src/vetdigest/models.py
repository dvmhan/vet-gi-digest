from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Article:
    pmid: str
    title: str
    abstract: str
    journal: str            # ISO 약어 (예: J Vet Intern Med)
    journal_full: str
    pub_date: str
    authors: str
    doi: str = ""
    pub_types: list[str] = field(default_factory=list)
    mesh: list[str] = field(default_factory=list)
    section: str = ""       # vet_gi | vet_im | human
    tags: list[str] = field(default_factory=list)
    score: float = 0.0
    summary: dict | None = None   # Claude 요약 결과

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

    @property
    def doi_url(self) -> str:
        return f"https://doi.org/{self.doi}" if self.doi else self.url
