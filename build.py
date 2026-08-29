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
GRID_COOK = "Grid_20150827000000000228_1"


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


def need_key():
    if KEY == "sample":
        raise SystemExit("인증키가 없습니다. 환경변수 DATA_GO_KR_KEY를 설정하세요 (sample 키는 5건까지만 옵니다).")


if "--fresh" in sys.argv or not os.path.exists(CACHE):
    need_key()
    print("내려받는 중…")
    json.dump({"base": fetch_all(GRID_BASE), "irdnt": fetch_all(GRID_IRDNT),
               "cook": fetch_all(GRID_COOK)},
              open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
raw = json.load(open(CACHE, encoding="utf-8"))
# 조리과정은 나중에 붙었다. 옛 캐시에는 없으니 그것만 받아 채운다 — 앞의 둘을 다시 받을 이유가 없다.
if "cook" not in raw:
    need_key()
    print("조리과정만 내려받는 중…")
    raw["cook"] = fetch_all(GRID_COOK)
    json.dump(raw, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
base, irdnt, cook = raw["base"], raw["irdnt"], raw["cook"]

# ─────────────────────────────────────────────────────────────── 재료명 정규화
PANTRY = {"물", "식용유", "소금", "설탕", "간장", "참기름", "들기름", "밀가루", "후추", "후춧가루",
          "마늘", "고춧가루", "깨", "식초", "물엿", "된장", "고추장", "맛술", "청주", "전분",
          "기름", "육수", "생강", "설탕물", "녹말가루", "올리고당", "꿀", "겨자", "소주", "미림",
          "다시마", "멸치", "국수장국", "설탕시럽", "튀김가루", "빵가루", "베이킹파우더",
          "밥", "찬밥", "쌀뜨물", "육수용멸치", "국물"}

PREFIX = ["국물용", "육수용", "손질한", "손질", "삶은", "데친", "불린", "다진", "채썬", "굵은", "고운",
          "마른", "말린", "건", "냉동", "생", "간", "썰은", "썬", "구운", "볶은"]

# 육수·국물은 사는 게 아니라 만들어 쓰는 것이다. 표기가 25종이라 낱개로 못 막는다
# (`쇠고기육수`·`쇠고기 육수`·`닭 육수`·`정수물(쇠고기육수)`…). 접두어를 떼고 나서도
# 이 말이 남아 있으면 장볼 것이 아니다 — `육수용 무`는 위 PREFIX에서 `무`로 살아남는다.
BROTH = ("육수", "국물", "장국")


def is_pantry(n):
    return n in PANTRY or any(w in n for w in BROTH)

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


def price(r):
    m = re.search(r"([\d,]+)", r.get("PC_NM") or "")
    return int(m.group(1).replace(",", "")) if m else 0


def daunting(r):
    """엄두가 안 나는 요리. 초보가 대상이면 첫 화면에 있으면 안 된다.
    난이도만으로는 꼬리곰탕(어려움)만 걸리고 곰탕(보통·120분)이 남는다.
    가격대와 시간을 같이 보면 뼈를 오래 고는 탕 · 장 담그기 · 떡이 함께 걸린다.
    쓰지 않을 뿐 데이터에서 지우는 게 아니다 — `도전` 축을 열면 그때 이 조건을 뒤집어 쓴다."""
    return r.get("LEVEL_NM") == "어려움" or (price(r) >= 20000 and minutes(r) >= 60)


# 손님 앞에서 그 자리에 해야 하는 것. 전은 눅눅해지고 구이는 질겨지고 면은 분다.
# 한 상에 여럿이면 손님이 앉아서 기다리게 된다.
FRESH_KINDS = {"부침", "구이", "밥", "만두/면류"}

# 아치에 크게 걸 대표 요리를 고르는 순서. 상의 주인공은 고기·생선 메인이고,
# 김치·나물은 곁들임이라 뒤로 간다. 숫자가 작을수록 대표에 가깝다.
HERO_RANK = {"찜": 1, "조림": 2, "구이": 3, "볶음": 4, "찌개/전골/스튜": 5, "탕": 5,
             "국": 6, "만두/면류": 7, "밥": 8, "부침": 9,
             "나물/생채/샐러드": 10, "밑반찬/김치": 11, "도시락/간식": 12}

# 사진이 한 그릇이 아니라 상차림이라 크게 걸면 무엇을 만드는 건지 안 읽힌다.
# 원형 54px에서는 문제가 없으므로 사진 자체는 남기고 대표 후보에서만 뺀다.
# (2026-08-25 대조표 육안 확인)
NO_HERO = {"된장채소수제비": "여러 그릇이 놓인 상 사진",
           "고등어양념구이": "생선구이 정식 상차림",
           "김치수제비": "수제비와 김치 두 그릇"}


def has_photo(name):
    return os.path.exists(os.path.join(HERE, "_design", "dish_%s.jpg" % name))


def hero_of(ids):
    """아치에 걸 한 장. 사진이 있고 상차림 컷이 아닌 것 중 가장 대표적인 요리."""
    cand = [i for i in ids if has_photo(meta[i]["RECIPE_NM_KO"])
            and meta[i]["RECIPE_NM_KO"] not in NO_HERO]
    if not cand:   # 전부 상차림 컷이면 그거라도 쓴다. 빈 아치보다 낫다.
        cand = [i for i in ids if has_photo(meta[i]["RECIPE_NM_KO"])]
    if not cand:
        return None
    # 순위가 같으면 조합에서 먼저 뽑힌 쪽(겹침이 가장 큰 씨앗)을 쓴다.
    return meta[min(cand, key=lambda i: (HERO_RANK.get(kind[i], 13), ids.index(i)))]["RECIPE_NM_KO"]


pool = {}
for rid, items in ing.items():
    m = meta.get(rid) or {}
    if m.get("NATION_NM") != "한식":
        continue
    buy = {n: q for n, (ty, q) in items.items() if ty != "양념" and not is_pantry(n)}
    if len(buy) >= 5:
        pool[rid] = buy

# 조리과정. 번호 순으로 세운다. STEP_TIP은 비어 있는 경우가 대부분이라 있을 때만 붙인다.
steps = defaultdict(list)
for r in sorted(cook, key=lambda r: (int(r["RECIPE_ID"]), int(r["COOKING_NO"]))):
    dc = (r.get("COOKING_DC") or "").strip()
    if dc:
        tip = (r.get("STEP_TIP") or "").strip()
        steps[int(r["RECIPE_ID"])].append({"d": dc, "t": tip} if tip else {"d": dc})

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


def fresh(rid):
    return kind[rid] in FRESH_KINDS


def greedy(cands, seed, k, max_kind, max_main, max_fresh=99):
    chosen, cur = [seed], set(pool[seed])
    kc, mc = Counter([kind[seed]]), Counter([main[seed]])
    fc = int(fresh(seed))
    while len(chosen) < k:
        best, bkey = None, None
        for rid in cands:
            if rid in chosen or kc[kind[rid]] >= max_kind or mc[main[rid]] >= max_main:
                continue
            if fresh(rid) and fc >= max_fresh:
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
        kc[kind[best]] += 1; mc[main[best]] += 1; fc += int(fresh(best))
    return chosen, cur


def variants(cands, k, max_kind, max_main, max_share, limit, max_fresh=99):
    """seed 하나가 조합 하나를 만든다. 예전에는 제일 좋은 하나만 남기고 나머지를 버렸는데,
    그 버리던 것이 곧 `다른 조합` 목록이다.

    max_share: 앞에 뽑힌 조합과 요리를 이만큼까지만 공유한다. 안 걸면 요리 하나만
    바뀐 조합이 줄줄이 나와서 다시 뽑아도 같은 화면으로 보인다.
    정렬은 살 것이 적은 순 — 화면에 나가는 숫자가 그것이라 사용자 기준과 같아야 한다."""
    ordered = sorted(cands, key=lambda r: -sum(freq[n] for n in pool[r]) / len(pool[r]))
    seen, found = set(), []
    for seed in ordered:
        ch, u = greedy(cands, seed, k, max_kind, max_main, max_fresh)
        if not ch or frozenset(ch) in seen:
            continue
        seen.add(frozenset(ch))
        apart = sum(len(pool[i]) for i in ch)
        found.append((len(u), -apart, ch, u))
    found.sort(key=lambda x: (x[0], x[1]))

    kept = []
    for buy, negapart, ch, u in found:
        if all(len(set(ch) & set(x[0])) <= max_share for x in kept):
            kept.append((ch, u, -negapart))
        if len(kept) >= limit:
            break
    return kept


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
        "id": sid, "type": stype, "title": title, "badge": badge, "hero": hero_of(ids),
        "tabLabel": tab, "people": people, "portion": portion,
        "apart": apart, "buyCount": len(union),
        "qtyCoverage": round(parsed_ok / len(union) * 100),
        "dishes": [{"name": meta[i]["RECIPE_NM_KO"], "rid": i, "kind": kind[i], "main": main[i],
                    "time": meta[i].get("COOKING_TIME"), "level": meta[i].get("LEVEL_NM"),
                    "servings": servings(meta[i]),
                    # 레시피마다 출처가 다를 수 있다. 다른 곳 레시피를 더하면 여기만 바꾸면 된다.
                    "source": "농림수산식품교육문화정보원"} for i in ids],
        "overlaps": overlaps,
        "groups": glist,
    }


# 이번 주 = 일상. 궁중음식 계열이 섞이지 않게 난이도와 시간으로 좁힌다.
weekday = [r for r in pool if meta[r].get("LEVEL_NM") == "초보환영" and minutes(meta[r]) <= 30]
# 집들이도 초보가 차린다. 엄두가 안 나는 것은 뺀다.
special = [r for r in pool if not daunting(meta[r])]

print("전체 %d개 · 이번 주 후보(초보환영·30분 이하) %d개" % (len(pool), len(weekday)))

# 축마다 조합을 여러 개 뽑는다. 하나만 두면 다음 주에 열어도 같은 화면이라 다시 열 이유가 없다.
# LIMIT: 뽑을 수 있는 전부(이번 주 22 · 집들이 39)를 다 넣으면 파일만 커진다. 12주치면 넉넉하다.
# max_fresh — 이번 주는 끼니를 따로 먹으니 그때그때 만드는 게 정상이라 안 건다.
# 집들이는 한 자리에 다 내야 해서 `그 자리에 해야 하는 것`이 셋 이상이면 손님이 기다린다.
AXES = [
    dict(type="week", cands=weekday, k=5, max_kind=1, max_main=1, max_share=2, limit=12,
         max_fresh=99, title="장 한 번으로 다섯 끼", tab="이번 주", people=2, portion=1.0,
         badge="초보환영 · 30분 이하 · 재료 겹침이 가장 많은 조합"),
    dict(type="occasion", cands=special, k=8, max_kind=1, max_main=2, max_share=3, limit=12,
         max_fresh=2, title="집들이 한 상 여덟 가지", tab="집들이", people=6, portion=0.6,
         badge="손님 상차림 · 미리 만들어 두는 것 위주"),
]

random.seed(11)
sets = []
for ax in AXES:
    vs = variants(ax["cands"], ax["k"], ax["max_kind"], ax["max_main"], ax["max_share"],
                  ax["limit"], ax["max_fresh"])
    # 무작위 평균은 축마다 하나면 된다. 조합이 달라도 후보 풀과 요리 수가 같다.
    rs = [random.sample(ax["cands"], ax["k"]) for _ in range(500)]
    ravg = round(sum(len(set().union(*[set(pool[i]) for i in x])) for x in rs) / len(rs), 1)
    for i, (ch, union, apart) in enumerate(vs, 1):
        s = build_set("%s-%d" % (ax["type"], i), ax["type"], ax["title"], ax["badge"],
                      ax["tab"], ch, union, apart, ax["people"], portion=ax["portion"])
        s["vi"], s["vn"], s["randomAvg"] = i, len(vs), ravg
        sets.append(s)

# 조리법은 실제로 쓰인 요리 것만 싣는다. 187개를 다 넣을 이유가 없다.
# 세트마다 넣으면 같은 요리가 여러 조합에 나와 그대로 중복되므로 요리명으로 한 번만 둔다.
used = {}
for s in sets:
    for d in s["dishes"]:
        used.setdefault(d["name"], d["rid"])
recipes = {n: steps[rid] for n, rid in used.items() if steps.get(rid)}

# `모든 요리` 탭 — 조합에 쓰인 요리를 한 곳에 늘어놓고 눌러서 레시피를 본다.
# 칩은 요리분류 12종을 그대로 늘어놓지 않고 다섯 묶음으로 줄인다. 칩이 열두 개면 고르는 게 일이 된다.
BUCKETS = [("국 · 찌개", {"국", "찌개/전골/스튜", "탕"}),
           ("밥 · 면", {"밥", "만두/면류", "도시락/간식"}),
           ("볶음 · 조림", {"볶음", "조림"}),
           ("찜 · 구이", {"찜", "구이"}),
           ("전 · 반찬", {"부침", "나물/생채/샐러드", "밑반찬/김치"})]


def bucket_of(k):
    for name, ks in BUCKETS:
        if k in ks:
            return name
    return "그 밖에"


catalog = []
for n, rid in sorted(used.items()):
    m = meta[rid]
    catalog.append({"name": n, "kind": kind[rid], "bucket": bucket_of(kind[rid]),
                    "time": m.get("COOKING_TIME"), "min": minutes(m), "level": m.get("LEVEL_NM"),
                    "servings": servings(m), "source": "농림수산식품교육문화정보원",
                    "rank": HERO_RANK.get(kind[rid], 13),
                    # 레시피 페이지의 재료 칸. 조합 계산에 쓰는 pool과 달리 양념·상비품까지
                    # 전부 넣는다 — 장볼 것이 아니라 만들 때 필요한 것 전부를 보여주는 자리다.
                    # v·u가 있으면 앱에서 인분을 바꿀 때 다시 계산한다.
                    # `적당량`·`약간`처럼 못 읽는 것은 v가 없고 원문 그대로 나간다.
                    "ing": [dict({"n": nm2, "q": q, "t": ty or "재료"},
                                 **(lambda p: {"v": round(p[0], 3), "u": p[1]} if p else {})(parse_qty(q)))
                            for nm2, (ty, q) in ing[rid].items()]})
buckets = [b for b, _ in BUCKETS if any(c["bucket"] == b for c in catalog)]
if any(c["bucket"] == "그 밖에" for c in catalog):
    buckets.append("그 밖에")

# 탐색 카드. 컬리 `탐색하기`처럼 분류만 늘어놓지 않고 축을 섞는다 —
# 무엇을 만드느냐(분류)뿐 아니라 얼마나 쉽고 빠른가도 고르는 이유가 된다.
cats = [{"label": "전체", "f": "all"}]
cats += [{"label": b, "f": "bucket", "v": b} for b in buckets]
cats += [{"label": "초보환영", "f": "level", "v": "초보환영"},
         {"label": "30분 안에", "f": "maxmin", "v": 30}]


def cat_match(c, cat):
    return (cat["f"] == "all"
            or (cat["f"] == "bucket" and c["bucket"] == cat["v"])
            or (cat["f"] == "level" and c["level"] == cat["v"])
            or (cat["f"] == "maxmin" and c["min"] <= cat["v"]))


# 카드마다 대표 사진을 붙인다. 사진이 있고 가장 대표적인(순위가 낮은) 요리를 쓴다.
for cat in cats:
    hit = [c for c in catalog if cat_match(c, cat) and has_photo(c["name"])
           and c["name"] not in NO_HERO]
    cat["n"] = sum(1 for c in catalog if cat_match(c, cat))
    cat["pic"] = min(hit, key=lambda c: (c["rank"], c["name"]))["name"] if hit else None

print("모든 요리 %d개 · 탐색 카드 %s"
      % (len(catalog), " / ".join("%s %d" % (c["label"], c["n"]) for c in cats)))
missing = [n for n in used if not steps.get(used[n])]
print("\n조리법 %d/%d 요리" % (len(recipes), len(used)) + ("  ※ 없음: " + " · ".join(missing) if missing else ""))
for s in sets:
    for d in s["dishes"]:
        d.pop("rid", None)

# 요리 사진 출처. 39장 중 37장이 CC BY / CC BY-SA라 표기가 의무다.
# 크레딧 파일은 _design/에 있어 저장소에 안 올라가므로, 여기서 data.json에 실어 앱이 직접 밝히게 한다.
CRED = os.path.join(HERE, "_design", "dish_credits.json")
photo_credit = {}
if os.path.exists(CRED):
    cr = json.load(open(CRED, encoding="utf-8"))
    if isinstance(cr, list):
        cr = {c["dish"]: c for c in cr}
    for n in used:
        c = cr.get(n)
        if c:
            photo_credit[n] = {"t": c["title"].replace("File:", ""), "l": c["license"], "u": c["page"]}
    print("사진 출처 %d개" % len(photo_credit))

out = {"generated": "2026-08-25", "recipes": recipes, "photos": photo_credit,
       "catalog": catalog, "cats": cats,
       "source": {"name": "농림수산식품교육문화정보원", "portal": "농림축산식품 공공데이터 포털",
                  "note": "레시피 기본정보 · 레시피 재료정보"},
       "stats": {"recipes": len(base), "korean": sum(1 for r in base if r.get("NATION_NM") == "한식"),
                 "pool": len(pool), "weekdayPool": len(weekday), "ingredients": len(freq)},
       "sets": sets}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for s in sets:
    if s["vi"] == 1:
        print("\n=== %s === 조합 %d개 · 무작위 %.1f가지"
              % (s["title"], s["vn"], s["randomAvg"]))
    print(" %2d/%d  따로 %2d → 살 것 %2d (%.0f%%) · 수량 표기 %3d%%  %s"
          % (s["vi"], s["vn"], s["apart"], s["buyCount"],
             (1 - s["buyCount"] / s["apart"]) * 100, s["qtyCoverage"],
             " · ".join(d["name"] for d in s["dishes"])))
    if s["vi"] == 1:
        for g in s["groups"]:
            print("        [%s] " % g["cat"] + " · ".join("%s %s" % (i["name"], i["qty"]) for i in g["items"]))
print("\n→ %s" % OUT)

# ──────────────────────────── app.html 템플릿에 데이터·이미지를 박아 index.html을 만든다.
# 이미지는 파일로 내보내고 index.html은 주소만 갖는다 (2026-08-25 전환).
# 전에는 전부 base64로 인라인했는데, 요리 사진에 단계 사진까지 넣으면 4MB를 넘어
# 단일 파일로는 감당이 안 된다. `아티팩트로 그대로 열린다`는 편의는 여기서 포기했다.
# 파일 이름은 d001처럼 번호로 준다 — 한글 파일명은 URL 인코딩이 얽힌다.
IMGDIR = os.path.join(HERE, "img")
os.makedirs(IMGDIR, exist_ok=True)
for f in os.listdir(IMGDIR):          # 지난 빌드의 잔재를 남기지 않는다
    os.remove(os.path.join(IMGDIR, f))


def put(src, rel):
    open(os.path.join(IMGDIR, rel), "wb").write(open(src, "rb").read())
    return "img/" + rel


TPL = os.path.join(HERE, "app.html")
if os.path.exists(TPL):
    html = open(TPL, encoding="utf-8").read()
    html = html.replace("__DATA__", json.dumps(out, ensure_ascii=False, separators=(",", ":")))

    hero = os.path.join(HERE, "_design", "hero.jpg")
    html = html.replace("__HERO__", put(hero, "hero.jpg") if os.path.exists(hero) else "")

    # 카탈로그에 있는 요리 전부. 사진이 없는 요리는 앱에서 임시 사진으로 채운다.
    photos, n = {}, 0
    for name in sorted(used):
        src = os.path.join(HERE, "_design", "dish_%s.jpg" % name)
        if os.path.exists(src):
            n += 1
            photos[name] = put(src, "d%03d.jpg" % n)
    html = html.replace("__DISHIMG__", json.dumps(photos, ensure_ascii=False, separators=(",", ":")))

    idx = os.path.join(HERE, "index.html")
    open(idx, "w", encoding="utf-8").write(html)
    tot = sum(os.path.getsize(os.path.join(IMGDIR, f)) for f in os.listdir(IMGDIR))
    print("   요리 사진 %d장 → img/ (%.0f KB)" % (len(photos), tot / 1024))
    print("→ %s  (%.0f KB)" % (idx, os.path.getsize(idx) / 1024))
