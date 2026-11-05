"""검색식별 PubMed 건수 점검 (Claude 호출 없음)."""
from vetdigest.config import load_config
from vetdigest.pubmed import PubMed

cfg = load_config()
pm = PubMed()
old_sp = '(dog[tiab] OR dogs[tiab] OR canine[tiab] OR cat[tiab] OR cats[tiab] OR feline[tiab] OR "Dogs"[mh] OR "Cats"[mh])'
for k, t in cfg["vet_gi_topics"].items():
    old = pm.search(f"{t['query']} AND {old_sp}", 14, 500)
    new = pm.search(f"{t['query']} AND {cfg['species_filter']} NOT {cfg['other_species_exclude']}", 14, 500)
    print(f"::notice::14일 {k}: 이전 필터 {len(old)} → 새 필터 {len(new)}")
    dropped = [p for p in old if p not in set(new)][:8]
    if dropped:
        titles = "%0A".join(f"- {a.title[:110]}" for a in pm.fetch(dropped))
        print(f"::notice::{k} 제외된 예시:%0A{titles}")
