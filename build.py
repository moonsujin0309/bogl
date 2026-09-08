# 보글 · BOGL° — 농정원 한식 데이터를 정규화해 `모든 요리` 카탈로그(data.json)로 굳히고 index.html을 만든다.
#
# 2026-09-07 정의 전환 뒤의 build.py다. 조합 계산은 없다 — 무엇을 먹을지는 사람이 고르고,
# 언제 먹고 뭘 살지는 브라우저의 plan.js가 계산한다. 여기서 하는 일은 셋뿐이다.
#   1. catalog.txt에 적힌 요리를 농정원 데이터에서 찾아 재료·수량·조리과정을 정규화한다
#   2. data.json으로 굳힌다 ({generated, source, stats, catalog, photos})
#   3. app.html의 __DATA__ · __PLAN__ · __YTKEY__ · __DISHIMG__ · __HERO__ 를 채워 index.html을 만든다
#
# 실행: python build.py         (캐시가 있으면 재사용, 없으면 API에서 내려받음)
#      python build.py --fresh  (다시 내려받음)
#
# 인증키는 환경변수 DATA_GO_KR_KEY. 이 API는 키를 URL 경로에 넣으므로
# data.go.kr 방식 키(/ + = 포함)는 쓸 수 없다. 농림축산식품 공공데이터 포털 키여야 한다.
# 유튜브 키는 환경변수 YOUTUBE_KEY. 없으면 빈 문자열로 들어가고 앱은 링크+직접 입력만 된다. 파일에 박지 마라.
import json, os, re, sys, urllib.request
from collections import defaultdict

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
# 부피는 ml로 모은다. 개수 단위는 그대로 둔다. 고체의 부피→무게 환산은 재료마다 밀도가 달라 하지 않는다.
# plan.js의 parseQty와 같은 규칙이어야 한다 — 사용자가 직접 적은 재료도 같은 눈으로 읽는다.
ML = {"컵": 200, "큰술": 15, "T": 15, "t": 5, "작은술": 5, "ml": 1, "cc": 1, "리터": 1000, "L": 1000}
G = {"g": 1, "kg": 1000, "그램": 1, "근": 600}
# 개수 단위는 전부 한 그룹으로 본다. 대파를 "1.5뿌리 + 0.8대"로 적으면 장을 못 본다.
COUNT = ["개", "장", "뿌리", "마리", "쪽", "모", "단", "대", "포기", "알", "톨", "줄기",
         "통", "잎", "봉지", "봉", "공기", "줌", "송이", "덩어리", "자루", "판", "토막", "묶음", "팩", "캔"]
VAGUE = ["약간", "적당량", "조금", "한줌", "기호에", "기호껏", "취향", "적당히", "넉넉히"]
# 한글 수사 → 숫자. 뒤에 공백이나 단위가 와야 한다 (`두부`의 `두`가 아니다). plan.js KNUM_RE와 같다.
KNUM = {"한두": 2, "두세": 3, "다섯": 5, "여섯": 6, "한": 1, "두": 2, "세": 3, "네": 4, "반": 0.5}
KNUM_RE = re.compile("^(한두|두세|다섯|여섯|한|두|세|네|반)(?=\\s|$|" +
                     "|".join(u for u in list(ML) + list(G) + COUNT if re.search(r"[ㄱ-힣]", u)) + ")")


def parse_qty(s):
    """'1과1/2큰술' → (22.5, 'ml'). '3~4개' → (4, '개', 넉넉히). 못 읽으면 None."""
    s = (s or "").strip()
    if not s or any(v in s for v in VAGUE):
        return None
    s = s.replace("½", "1/2").replace("¼", "1/4").replace("⅓", "1/3")
    s = KNUM_RE.sub(lambda m: str(KNUM[m.group(1)]), s)
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


# ────────────────────────────────────────────────────────────────── 데이터 조립
meta = {int(r["RECIPE_ID"]): r for r in base}
by_name = {r["RECIPE_NM_KO"]: int(r["RECIPE_ID"]) for r in base}
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


# 조리과정. 번호 순으로 세운다. STEP_TIP은 비어 있는 경우가 대부분이라 있을 때만 붙인다.
steps = defaultdict(list)
for r in sorted(cook, key=lambda r: (int(r["RECIPE_ID"]), int(r["COOKING_NO"]))):
    dc = (r.get("COOKING_DC") or "").strip()
    if dc:
        tip = (r.get("STEP_TIP") or "").strip()
        steps[int(r["RECIPE_ID"])].append({"d": dc, "t": tip} if tip else {"d": dc})


def has_photo(name):
    return os.path.exists(os.path.join(HERE, "_design", "dish_%s.jpg" % name))


# `모든 요리` 목록의 진실 소스는 catalog.txt다. 한 줄에 요리 하나, 농정원 RECIPE_NM_KO 그대로.
names = [l.strip() for l in open(os.path.join(HERE, "catalog.txt"), encoding="utf-8") if l.strip()]
lost = [n for n in names if n not in by_name]
if lost:
    raise SystemExit("catalog.txt에 있는데 농정원 데이터에 없는 요리: " + " · ".join(lost))


def ing_row(n, ty, q):
    # 레시피 페이지의 재료 칸. 양념·상비품까지 전부 — 만들 때 필요한 것 전부를 보여주는 자리다.
    # b: 장볼 것(양념이 아니고 상비품도 아닌 것). v·u가 있으면 앱에서 인분을 바꿀 때 다시 계산한다.
    row = {"n": n, "q": q, "t": ty or "재료"}
    p = parse_qty(q)
    if p:
        row["v"], row["u"] = round(p[0], 3), p[1]
    if ty != "양념" and not is_pantry(n):
        row["b"] = 1
    return row


# 매운 요리 — 재료 이름으로 본다. 홈 탐색 칩 `안 매워요`가 spicy 없는 것만 남긴다.
SPICY = ("고춧가루", "고추장", "청양", "매운", "불닭")

catalog = []
for n in names:
    rid = by_name[n]
    m = meta[rid]
    rows = [ing_row(nm2, ty, q) for nm2, (ty, q) in ing[rid].items()]
    c = {"name": n, "kind": m.get("TY_NM") or "기타",
         "time": m.get("COOKING_TIME"), "min": minutes(m), "level": m.get("LEVEL_NM"),
         "servings": servings(m),
         # 출처는 레시피마다 붙인다. 다른 곳 레시피를 더하면 이 줄만 바꾼다.
         "source": "농림수산식품교육문화정보원",
         "ing": rows, "steps": steps.get(rid, [])}
    if any(k in r["n"] for r in rows for k in SPICY):
        c["spicy"] = 1
    catalog.append(c)

no_steps = [c["name"] for c in catalog if not c["steps"]]
print("요리 %d개 · 장볼 재료 평균 %.1f가지 · 조리법 %d개 · 매운 요리 %d개"
      % (len(catalog), sum(sum(1 for i in c["ing"] if i.get("b")) for c in catalog) / len(catalog),
         len(catalog) - len(no_steps), sum(1 for c in catalog if c.get("spicy")))
      + ("  ※ 조리법 없음: " + " · ".join(no_steps) if no_steps else ""))

# 요리 사진 출처. 대부분 CC BY / CC BY-SA라 표기가 의무다.
# 크레딧 파일은 _design/에 있어 저장소에 안 올라가므로, 여기서 data.json에 실어 앱이 직접 밝히게 한다.
CRED = os.path.join(HERE, "_design", "dish_credits.json")
photo_credit = {}
if os.path.exists(CRED):
    cr = json.load(open(CRED, encoding="utf-8"))
    if isinstance(cr, list):
        cr = {c["dish"]: c for c in cr}
    for n in names:
        c = cr.get(n)
        if c:
            photo_credit[n] = {"t": c["title"].replace("File:", ""), "l": c["license"], "u": c["page"]}
    print("사진 출처 %d개" % len(photo_credit))

out = {"generated": "2026-09-07", "photos": photo_credit, "catalog": catalog,
       "source": {"name": "농림수산식품교육문화정보원", "portal": "농림축산식품 공공데이터 포털",
                  "note": "레시피 기본정보 · 레시피 재료정보 · 레시피 과정정보"},
       "stats": {"recipes": len(base), "korean": sum(1 for r in base if r.get("NATION_NM") == "한식"),
                 "catalog": len(catalog)}}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("→ %s" % OUT)

# ──────────────────────────── app.html 템플릿에 데이터·계산·이미지를 박아 index.html을 만든다.
# 이미지는 파일로 내보내고 index.html은 주소만 갖는다 (2026-08-25 전환).
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
    html = html.replace("__PLAN__", open(os.path.join(HERE, "plan.js"), encoding="utf-8").read())
    # 유튜브 키는 환경변수에서만. 빌드 결과(index.html)에는 들어가지만 저장소의 소스에는 없다.
    html = html.replace("__YTKEY__", (os.environ.get("YOUTUBE_KEY") or "").strip())

    hero = os.path.join(HERE, "_design", "hero.jpg")
    html = html.replace("__HERO__", put(hero, "hero.jpg") if os.path.exists(hero) else "")

    photos, n = {}, 0
    for name in sorted(names):
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
