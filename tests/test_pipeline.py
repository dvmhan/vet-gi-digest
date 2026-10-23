from datetime import date

from vetdigest.compose import build_messages
from vetdigest.config import load_config
from vetdigest.kakao import TEXT_LIMIT, clip
from vetdigest.models import Article
from vetdigest.pubmed import collect, parse_pubmed_xml, score
from vetdigest.report import write_report

XML = b"""<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>40000001</PMID>
<Article><Journal><JournalIssue><PubDate><Year>2026</Year><Month>Oct</Month></PubDate></JournalIssue>
<Title>Journal of veterinary internal medicine</Title><ISOAbbreviation>J Vet Intern Med</ISOAbbreviation></Journal>
<ArticleTitle>Fecal microbiota transplantation in dogs with <i>chronic</i> enteropathy</ArticleTitle>
<Abstract><AbstractText Label="BACKGROUND">FMT is promising.</AbstractText><AbstractText Label="RESULTS">CIBDAI decreased.</AbstractText></Abstract>
<AuthorList><Author><LastName>Kim</LastName><Initials>J</Initials></Author><Author><LastName>Lee</LastName></Author></AuthorList>
<PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList></Article>
<MedlineJournalInfo><MedlineTA>J Vet Intern Med</MedlineTA></MedlineJournalInfo></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1111/jvim.1</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""


def test_parse():
    (a,) = parse_pubmed_xml(XML)
    assert a.pmid == "40000001"
    assert a.title == "Fecal microbiota transplantation in dogs with chronic enteropathy"
    assert a.abstract.startswith("BACKGROUND: FMT")
    assert a.authors == "Kim J et al."
    assert a.doi == "10.1111/jvim.1" and a.journal == "J Vet Intern Med"
    assert score(a) > 5


class FakePubMed:
    def search(self, term, days, retmax=200):
        if ("fecal microbiota" in term or "chronic enteropathy" in term) and '"Dogs"[mh]' in term:
            return ["40000001"]
        return []

    def fetch(self, pmids):
        return [a for a in parse_pubmed_xml(XML) if a.pmid in pmids]


def test_collect_tags_and_seen():
    cfg = load_config()
    res = collect(cfg, FakePubMed(), set())
    assert [a.pmid for a in res["vet_gi"]] == ["40000001"]
    assert "FMT" in res["vet_gi"][0].tags and "CIE" in res["vet_gi"][0].tags
    assert collect(cfg, FakePubMed(), {"40000001"})["vet_gi"] == []


def _art(i, sec="vet_gi"):
    a = Article(pmid=str(i), title="T" * 300, abstract="x", journal="J Vet Intern Med", journal_full="",
                pub_date="2026", authors="A", section=sec, tags=["CIE", "PLE"] if sec == "vet_gi" else [])
    a.summary = {"title_ko": "가" * 150, "kakao_line": "나" * 120, "importance": 4, "key_findings": ["결과"],
                 "study_design": "RCT", "population": "개 40두", "clinical_takeaway": "의미", "limitations": ""}
    return a


def test_messages_within_kakao_limit(tmp_path):
    secs = {"vet_gi": [_art(i) for i in range(5)], "vet_im": [_art(9, "vet_im")], "human": [_art(10, "human")]}
    msgs = build_messages(secs, {"vet_gi": "요약 " * 100}, "https://x.github.io/d", date(2026, 10, 23), 6)
    assert len(msgs) == 6
    assert msgs[0][1] == "https://x.github.io/d/daily/2026-10-23.html"
    assert msgs[4][1].endswith("#10")  # 4번째 하이라이트는 사람 논문
    assert all(len(clip(t)) <= TEXT_LIMIT for t, _, _ in msgs)
    p = write_report(tmp_path, date(2026, 10, 23), secs, {}, {"CIE": "만성 염증성 장병증"})
    assert "만성 염증성 장병증" in p.read_text() and (tmp_path / "index.html").exists()


def test_empty_day():
    msgs = build_messages({"vet_gi": [], "vet_im": [], "human": []}, {}, "", date(2026, 10, 23), 6)
    assert len(msgs) == 1 and "새로 등록된 논문이 없습니다" in msgs[0][0]
