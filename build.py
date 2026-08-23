# 보글 · BOGL° — 농정원 한식 데이터에서 "겹침이 큰 조합"을 계산해 data.json으로 굳힌다.
#
# 실행: python build.py         (캐시가 있으면 재사용, 없으면 API에서 내려받음)
#      python build.py --fresh  (다시 내려받음)
#
# 인증키는 환경변수 DATA_GO_KR_KEY. 이 API는 키를 URL 경로에 넣으므로
# data.go.kr 방식 키(/ + = 포함)는 쓸 수 없다. 농림축산식품 공공데이터 포털 키여야 한다.
import json, os, random, re, sys, urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_probe_cache.json")
OUT = os.path.join(HERE, "data.json")

_k = (os.environ.get("DATA_GO_KR_KEY") or "").strip()
KEY = _k if re.fullmatch(r"[A-Za-z0-9]+", _k) else "sample"
EP = "http://211.237.50.150:7080/openapi/%s/json/%s/%d/%d"
GRID_BASE = "Grid_20150827000000000226_1"
GRID_IRDNT = "Grid_20150827000000000227_1"


def fetch_all(grid, page=1000):
    rows, start = [], 1
    while True:
        with urllib.request.urlopen(EP % (KEY, grid, start, start + page - 1), timeout=60) as r:
            blk = json.loads(r.read().decode("utf-8"))[grid]
        if blk["result"]["code"] != "INFO-000":
            raise SystemExit("API 오류: %s" % blk["result"])
        got = blk.get("row") or []
        rows += got
        if len(rows) >= int(blk["totalCnt"]) or not got:
            return rows
        start += page


if "--fresh" in sys.argv or not os.path.exists(CACHE):
    if KEY == "sample":
        raise SystemExit("인증키가 없습니다. 환경변수 DATA_GO_KR_KEY를 설정하세요 (sample 키는 5건까지만 옵니다).")
    print("내려받는 중…")
    json.dump({"base": fetch_all(GRID_BASE), "irdnt": fetch_all(GRID_IRDNT)},
              open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
raw = json.load(open(CACHE, encoding="utf-8"))
base, irdnt = raw["base"], raw["irdnt"]

# ─────────────────────────────────────────────────────────────── 재료명 정규화
PANTRY = {"물", "식용유", "소금", "설탕", "간장", "참기름", "들기름", "밀가루", "후추", "후춧가루",
          "마늘", "고춧가루", "깨", "식초", "물엿", "된장", "고추장", "맛술", "청주", "전분",
          "기름", "육수", "생강", "설탕물", "녹말가루", "올리고당", "꿀", "겨자", "소주", "미림",
          "다시마", "멸치", "국수장국", "설탕시럽", "튀김가루", "빵가루", "베이킹파우더",
          "밥", "찬밥", "쌀뜨물", "육수용멸치", "국물"}

PREFIX = ["국물용", "손질한", "손질", "삶은", "데친", "불린", "다진", "채썬", "굵은", "고운",
          "마른", "말린", "건", "냉동", "생", "간", "썰은", "썬", "구운", "볶은"]

ALIAS = {"계란노른자": "계란", "계란흰자": "계란", "계란후라이": "계란", "달걀": "계란",
         "소고기": "쇠고기", "쇠뼈": "쇠고기", "쇠고기육수": "쇠고기",
         "칼국수면": "칼국수", "밀국수": "국수",
         "배추김치": "김치", "포기김치": "김치",
         "홍고추": "붉은고추", "적고추": "붉은고추", "풋고추": "청고추", "실파": "쪽파",
         "순창콩된장": "된장", "재래된장": "된장", "집된장": "된장",
         "진간장": "간장", "국간장": "간장", "양조간장": "간장", "맛간장": "간장",
         "고운소금": "소금", "굵은소금": "소금", "천일염": "소금"}


def split_names(s):
    """한 칸에 여러 재료가 들어있는 경우가 있다. 공백을 지우면 안 된다 —
    지우면 '식용유 소금 참기름 잣가루'가 한 덩어리가 된다."""
    s = re.sub(r"^\[[^\]]*\]", "", (s or "").strip())
    s = re.sub(r"\(.*?\)", " ", s)
    out = []
    for p in re.split(r"[·,/+]|\s{2,}", s):
        p = p.strip()
        if not p:
            continue
        toks = p.split()
        out += toks if (len(toks) >= 3 and all(len(t) <= 4 for t in toks)) else [p]
    return out


def canon(n):
    n = n.strip()
    changed = True
    while changed:
        changed = False
        for p in PREFIX:
            if n.startswith(p) and len(n) > len(p) + 1:
                n, changed = n[len(p):].strip(), True
    return ALIAS.get(re.sub(r"\s+", " ", n), re.sub(r"\s+", " ", n))


# ───────────────────────────────────────────────────────────────── 수량 정규화
# 부피는 ml로 모아서 큰술로 되돌린다. 개수 단위는 그대로 둔다.
# 고체의 부피→무게 환산은 재료마다 밀도가 달라 하지 않는다.
ML = {"컵": 200, "큰술": 15, "T": 15, "t": 5, "작은술": 5, "ml": 1, "cc": 1, "리터": 1000, "L": 1000}
G = {"g": 1, "kg": 1000, "그램": 1}
# 개수 단위는 전부 한 그룹으로 본다. 대파를 "1.5뿌리 + 0.8대"로 적으면 장을 못 본다.
COUNT = ["개", "장", "뿌리", "마리", "쪽", "모", "단", "대", "포기", "알", "톨", "줄기",
         "통", "잎", "봉", "공기", "줌", "송이", "덩어리", "자루", "판", "토막", "쪽"]
VAGUE = ["약간", "적당량", "조금", "한줌", "기호에", "취향"]


def parse_qty(s):
    """'1과1/2큰술' → (22.5, 'ml'). '3~4개' → (4, '개', 넉넉히). 못 읽으면 None."""
    s = (s or "").strip()
    if not s or any(v in s for v in VAGUE):
        return None
    s = s.replace("½", "1/2").replace("¼", "1/4").replace("⅓", "1/3")
    m = re.match(r"^\s*(\d+)\s*과\s*(\d+)\s*/\s*(\d+)\s*(.*)$", s)      # 1과1/2
    if m:
        val, unit = int(m.group(1)) + int(m.group(2)) / int(m.group(3)), m.group(4)
    else:
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)\s*(.*)$", s)  # 3~4 → 넉넉히 4
        if m:
            val, unit = max(float(m.group(1)), float(m.group(2))), m.group(3)
        else:
            m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*(.*)$", s)            # 1/2
            if m:
                val, unit = int(m.group(1)) / int(m.group(2)), m.group(3)
            else:
                m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(.*)$", s)
                if not m:
                    return None
                val, unit = float(m.group(1)), m.group(2)
    unit = unit.strip().split()[0] if unit.strip() else "개"
    unit = re.sub(r"[^\wㄱ-힣]", "", unit) or "개"
    if unit.lower() in ("kg", "g", "ml", "cc", "l"):
        unit = unit.lower()
    if unit in ML:
        return (val * ML[unit], "ml")
    if unit in G:
        return (val * G[unit], "g")
    for c in COUNT:
        if unit.startswith(c):
            return (val, c)
    return (val, unit)


import math


def fmt(val, unit):
    """장볼 양이므로 모자라지 않게 올림한다. 3.4개를 사러 갈 수는 없다."""
    if unit == "ml":
        if val >= 200:
            return "%g컵" % (math.ceil(val / 100) / 2)
        return "%g큰술" % max(1, round(val / 15))
    if unit == "g":
        if val >= 1000:
            return "%gkg" % (math.ceil(val / 100) / 10)
        return "%dg" % (math.ceil(val / 10) * 10)
    return "%d%s" % (math.ceil(val - 1e-9), unit)


def pick_qty(sums, units_seen):
    """단위가 여러 그룹으로 흩어지면 가장 자주 나온 그룹만 쓴다.
    '대파 8g + 1.5뿌리 + 0.8대'는 목록으로 못 쓴다."""
    if not sums:
        return None
    groups = {}          # 'g' / 'ml' / 개수단위 → 합
    for u, v in sums.items():
        g = u if u in ("g", "ml") else "count"
        groups.setdefault(g, {})[u] = groups.setdefault(g, {}).get(u, 0) + v
    # 가장 많이 등장한 그룹
    def hits(g):
        return sum(units_seen.get(u, 0) for u in groups[g])
    top = max(groups, key=hits)
    if top == "count":
        total = sum(groups["count"].values())
        unit = max(groups["count"], key=lambda u: units_seen.get(u, 0))
        return (fmt(total, unit), total, unit)
    total = sum(groups[top].values())
    return (fmt(total, top), total, top)


# ────────────────────────────────────────────────────────────── 마트 카테고리
CATS = [
    ("정육 · 계란", ["쇠고기", "돼지", "갈비", "삼겹", "목살", "안심", "등심", "사태", "양지", "닭", "오리",
                  "계란", "베이컨", "햄", "소시지", "정육", "우둔", "차돌"]),
    ("수산 · 건해산", ["갈치", "동태", "명태", "고등어", "조기", "오징어", "새우", "조개", "미역", "김",
                   "게", "낙지", "문어", "대구", "굴", "홍합", "바지락", "북어", "황태", "어묵", "멸치",
                   "생선", "가자미", "삼치", "꽁치", "장어", "전복", "해물", "조갯살", "쭈꾸미", "젓"]),
    ("우유 · 유제품", ["우유", "치즈", "버터", "생크림", "요구르트", "요거트", "연유"]),
    ("쌀 · 잡곡", ["쌀", "찹쌀", "보리", "현미", "팥", "녹두", "수수", "기장", "가래떡", "떡"]),
    ("라면 · 통조림", ["라면", "국수", "소면", "당면", "칼국수", "냉면", "스파게티", "통조림", "참치"]),
    ("김치 · 반찬", ["김치", "깍두기", "장아찌", "젓갈"]),
    ("장 · 양념 · 오일", ["고추장", "된장", "간장", "식초", "참기름", "들기름", "식용유", "설탕", "소금",
                     "후추", "고춧가루", "물엿", "맛술", "잣", "깨", "가루", "카레", "소스"]),
]


def category(name):
    for cat, keys in CATS:
        if any(k in name for k in keys):
            return cat
    return "채소 · 두부"


# ────────────────────────────────────────────────────────────────── 데이터 조립
meta = {int(r["RECIPE_ID"]): r for r in base}
ing = defaultdict(dict)     # rid -> {재료: (구분, 수량문자열)}
for r in irdnt:
    for nm in split_names(r.get("IRDNT_NM")):
        c = canon(nm)
        if c:
            ing[int(r["RECIPE_ID"])][c] = (r.get("IRDNT_TY_NM") or "", r.get("IRDNT_CPCTY") or "")


def minutes(r):
    m = re.match(r"(\d+)", (r.get("COOKING_TIME") or "").strip())
    return int(m.group(1)) if m else 999


def servings(r):
    m = re.match(r"(\d+)", (r.get("QNT") or "").strip())
    return int(m.group(1)) if m else 4


pool = {}
for rid, items in ing.items():
    m = meta.get(rid) or {}
    if m.get("NATION_NM") != "한식":
        continue
    buy = {n: q for n, (ty, q) in items.items() if ty != "양념" and n not in PANTRY}
    if len(buy) >= 5:
        pool[rid] = buy

kind = {r: (meta[r].get("TY_NM") or "기타") for r in pool}
main = {r: (meta[r].get("IRDNT_CODE") or "기타") for r in pool}
freq = Counter()
for s in pool.values():
    freq.update(s.keys())

VOCAB = set(freq) | {"김치", "냉면", "국수", "수제비", "만두", "부침개", "주먹밥", "덮밥",
                     "볶음밥", "죽", "잡채", "산적", "김밥", "전골", "장아찌"}
SUFFIX = ["수제비", "장아찌", "볶음밥", "비빔밥", "덮밥", "국수", "칼국수", "샐러드", "무침",
          "조림", "찌개", "전골", "볶음", "구이", "튀김", "부침", "만두", "나물", "말이",
          "김치", "찜", "국", "탕", "전", "죽", "밥", "쌈", "회"]


def nm(rid):
    return re.sub(r"\s+", "", meta[rid]["RECIPE_NM_KO"])


def dish_key(rid):
    n = nm(rid)
    for suf in SUFFIX:
        if n.endswith(suf) and len(n) > len(suf):
            return (n[:2], suf)
    return (n[:2], "")


def name_words(rid):
    n = nm(rid)
    return {w for w in VOCAB if len(w) >= 2 and w in n}


def jac(a, b):
    return len(a & b) / len(a | b)


def same_dish(a, b):
    na, nb = nm(a), nm(b)
    return (na in nb or nb in na) or dish_key(a) == dish_key(b) \
        or bool(name_words(a) & name_words(b)) or jac(set(pool[a]), set(pool[b])) >= 0.55


def greedy(cands, seed, k, max_kind, max_main):
    chosen, cur = [seed], set(pool[seed])
    kc, mc = Counter([kind[seed]]), Counter([main[seed]])
    while len(chosen) < k:
        best, bkey = None, None
        for rid in cands:
            if rid in chosen or kc[kind[rid]] >= max_kind or mc[main[rid]] >= max_main:
                continue
            if any(same_dish(rid, c) for c in chosen):
                continue
            s = set(pool[rid])
            key = (len(s - cur), -len(s))
            if bkey is None or key < bkey:
                best, bkey = rid, key
        if best is None:
            return None, None
        chosen.append(best); cur |= set(pool[best])
        kc[kind[best]] += 1; mc[main[best]] += 1
    return chosen, cur


def best_set(cands, k, max_kind, max_main):
    ordered = sorted(cands, key=lambda r: -sum(freq[n] for n in pool[r]) / len(pool[r]))
    best = None
    for seed in ordered[:120]:
        ch, u = greedy(cands, seed, k, max_kind, max_main)
        if not ch:
            continue
        apart = sum(len(pool[i]) for i in ch)
        if best is None or len(u) / apart < best[0]:
            best = (len(u) / apart, ch, u, apart)
    return best


def build_set(sid, stype, title, badge, tab, ids, union, apart, people, portion=1.0):
    """수량을 인분 기준으로 환산해 합산한다.
    portion: 요리가 많으면 한 가지를 풀로 먹지 않는다. 상차림은 0.6(여유분 20% 포함)."""
    agg = defaultdict(lambda: {"sum": defaultdict(float), "units": Counter(), "used": 0, "where": []})
    for rid in ids:
        scale = people / servings(meta[rid]) * portion
        for n, q in pool[rid].items():
            a = agg[n]
            a["used"] += 1
            a["where"].append(meta[rid]["RECIPE_NM_KO"])
            p = parse_qty(q)
            if p:
                a["sum"][p[1]] += p[0] * scale
                a["units"][p[1]] += 1

    groups = defaultdict(list)
    parsed_ok = 0
    for n, a in sorted(agg.items(), key=lambda kv: (-kv[1]["used"], kv[0])):
        got = pick_qty(a["sum"], a["units"])
        if got:
            parsed_ok += 1
            qty, val, unit = got
        else:
            qty, val, unit = "조금", None, None
        # value/unit을 같이 내보내야 앱에서 인원을 바꿀 때 다시 계산할 수 있다
        groups[category(n)].append({"name": n, "qty": qty, "value": (round(val, 3) if val else None),
                                    "unit": unit, "used": a["used"], "where": a["where"]})

    order = [c for c, _ in CATS] + ["채소 · 두부"]
    glist = [{"cat": c, "items": groups[c]} for c in dict.fromkeys(["정육 · 계란", "수산 · 건해산",
             "채소 · 두부", "김치 · 반찬", "장 · 양념 · 오일", "쌀 · 잡곡", "라면 · 통조림",
             "우유 · 유제품"]) if groups.get(c)]

    # 겹치는 재료를 하나만 뽑으면 자의적이다. 두 곳 이상에 쓰이는 것을 전부 내보낸다.
    overlaps = sorted(({"name": n, "used": a["used"], "where": a["where"]}
                       for n, a in agg.items() if a["used"] >= 2),
                      key=lambda x: (-x["used"], x["name"]))
    return {
        "id": sid, "type": stype, "title": title, "badge": badge,
        "tabLabel": tab, "people": people, "portion": portion,
        "apart": apart, "buyCount": len(union),
        "qtyCoverage": round(parsed_ok / len(union) * 100),
        "dishes": [{"name": meta[i]["RECIPE_NM_KO"], "kind": kind[i], "main": main[i],
                    "time": meta[i].get("COOKING_TIME"), "level": meta[i].get("LEVEL_NM"),
                    "servings": servings(meta[i]),
                    # 레시피마다 출처가 다를 수 있다. 다른 곳 레시피를 더하면 여기만 바꾸면 된다.
                    "source": "농림수산식품교육문화정보원"} for i in ids],
        "overlaps": overlaps,
        "groups": glist,
    }


# 이번 주 = 일상. 궁중음식 계열이 섞이지 않게 난이도와 시간으로 좁힌다.
weekday = [r for r in pool if meta[r].get("LEVEL_NM") == "초보환영" and minutes(meta[r]) <= 30]
special = list(pool)

print("전체 %d개 · 이번 주 후보(초보환영·30분 이하) %d개" % (len(pool), len(weekday)))

sets = []
b = best_set(weekday, 5, 1, 1)
sets.append(build_set("week-1", "week", "장 한 번으로 다섯 끼",
                      "초보환영 · 30분 이하 · 재료 겹침이 가장 많은 조합",
                      "이번 주", b[1], b[2], b[3], 2))
b = best_set(special, 8, 1, 2)
sets.append(build_set("occasion-1", "occasion", "집들이 한 상 여덟 가지",
                      "손님 상차림 · 미리 만들어 두는 것 위주",
                      "집들이", b[1], b[2], b[3], 6, portion=0.6))

random.seed(11)
for s in sets:
    k = len(s["dishes"])
    cands = weekday if s["type"] == "week" else special
    rs = [random.sample(cands, k) for _ in range(500)]
    s["randomAvg"] = round(sum(len(set().union(*[set(pool[i]) for i in x])) for x in rs) / len(rs), 1)

out = {"generated": "2026-08-24",
       "source": {"name": "농림수산식품교육문화정보원", "portal": "농림축산식품 공공데이터 포털",
                  "note": "레시피 기본정보 · 레시피 재료정보"},
       "stats": {"recipes": len(base), "korean": sum(1 for r in base if r.get("NATION_NM") == "한식"),
                 "pool": len(pool), "weekdayPool": len(weekday), "ingredients": len(freq)},
       "sets": sets}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for s in sets:
    print("\n=== %s ===  따로 %d → 합치면 %d (%.0f%%) · 무작위 %.1f · 수량 표기 %d%%"
          % (s["title"], s["apart"], s["buyCount"],
             (1 - s["buyCount"] / s["apart"]) * 100, s["randomAvg"], s["qtyCoverage"]))
    for d in s["dishes"]:
        print("  · %-12s %-14s %s %s" % (d["name"], d["kind"], d["time"], d["level"]))
    for g in s["groups"]:
        print("  [%s] " % g["cat"] + " · ".join("%s %s" % (i["name"], i["qty"]) for i in g["items"]))
print("\n→ %s" % OUT)

# ──────────────────────────── app.html 템플릿에 데이터·이미지를 박아 index.html을 만든다.
# 아티팩트로도 그대로 열리도록 외부 파일을 참조하지 않고 전부 인라인한다.
TPL = os.path.join(HERE, "app.html")
if os.path.exists(TPL):
    import base64
    html = open(TPL, encoding="utf-8").read()
    html = html.replace("__DATA__", json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    hero = os.path.join(HERE, "_design", "hero.jpg")
    if os.path.exists(hero):
        html = html.replace("__HERO__", "data:image/jpeg;base64," +
                            base64.b64encode(open(hero, "rb").read()).decode())
    # 요리 사진. 없는 요리는 앱에서 그릇 글리프로 남는다.
    photos = {}
    for st in out["sets"]:
        for d in st["dishes"]:
            f = os.path.join(HERE, "_design", "dish_%s.jpg" % d["name"])
            if d["name"] not in photos and os.path.exists(f):
                photos[d["name"]] = "data:image/jpeg;base64," + \
                    base64.b64encode(open(f, "rb").read()).decode()
    html = html.replace("__DISHIMG__", json.dumps(photos, ensure_ascii=False, separators=(",", ":")))
    print("   요리 사진 %d장 인라인" % len(photos))
    idx = os.path.join(HERE, "index.html")
    open(idx, "w", encoding="utf-8").write(html)
    print("→ %s  (%.0f KB)" % (idx, os.path.getsize(idx) / 1024))
