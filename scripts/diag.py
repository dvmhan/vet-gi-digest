"""검색식별 PubMed 건수 점검 (Claude 호출 없음)."""
from vetdigest.config import journal_clause, load_config
from vetdigest.pubmed import PubMed

cfg = load_config()
pm = PubMed()
vj = cfg["vet_journals"]
allv = journal_clause(vj["core"] + vj["extended"])
for days in (3, 30):
    for k, t in cfg["vet_gi_topics"].items():
        n_all = len(pm.search(f"{t['query']} AND {cfg['species_filter']}", days, 500))
        n_j = len(pm.search(f"{t['query']} AND {cfg['species_filter']} AND {allv}", days, 500))
        print(f"::notice::{days}일 {k}: 전체 {n_all} / 저널필터 {n_j}")
