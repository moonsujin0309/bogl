# 요리 사진을 위키미디어 공용에서 받아 원형 썸네일로 저장한다.
# 재료는 아이콘이지만 요리는 눈으로 고르는 대상이라 사진이 있어야 한다.
#
# 결과: _design/dish_<요리이름>.jpg  +  _dish_sheet.png (눈으로 확인용)
# 검색이 엉뚱한 걸 물어오는 일이 잦으니 반드시 대조표를 보고 판단할 것.
#
# 한글 이름으로 검색하면 42개 중 8개만 잡히고 그중 하나는 엉뚱한 사진이었다(2026-08-24 실측).
# 그래서 요리마다 로마자 검색어와 "제목에 반드시 있어야 할 낱말"을 손으로 준다.
# 농정원 API에는 이미지가 없다 — Grid 229 이후는 전부 "해당하는 서비스를 찾을 수 없습니다".
#
# 실행: python fetch_dish_images.py          (이미 있는 파일은 건너뛴다)
#      python fetch_dish_images.py --all    (전부 다시 받는다)
import io, json, os, sys, time, urllib.parse, urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_design")
UA = {"User-Agent": "BoglMockup/0.1 (https://github.com/moonsujin0309/bogl; moonopmd@gmail.com) Python-urllib"}
PAUSE = 3.5
API = "https://commons.wikimedia.org/w/api.php"
# 앱에서 원은 46px로 그려진다. 3배 화면을 쳐도 138px면 충분하다.
# 220으로 두면 35장이 index.html을 753KB까지 밀어올린다 — 눈에 보이지도 않는 화소값이다.
SIZE = 150
# 아치는 화면에서 323px로 그려진다. 150px을 걸면 2.1배로 늘어나 뿌옇다.
# 대표로 쓰이는 요리만 크게 둔다 — 전부 키우면 index.html이 1MB를 넘는다.
# 480·품질78로 두니 열 장이 index.html을 1,034KB까지 밀어올렸다. 아치는 323px이라
# 400이면 1.24배로 충분히 선명하고, 사진은 압축을 조금 더 먹여도 티가 안 난다.
HERO_SIZE = 400
QUALITY = 78
HERO_QUALITY = 66
REDO = "--all" in sys.argv

# 어떤 요리가 대표인지는 build.py가 정해 data.json의 sets[].hero에 적는다.
# 여기서 그걸 읽어 그 요리만 큰 크기로 맞춘다. 없으면 전부 SIZE.
HEROES = set()
_dj = os.path.join(HERE, "data.json")
if os.path.exists(_dj):
    HEROES = {s["hero"] for s in json.load(open(_dj, encoding="utf-8"))["sets"] if s.get("hero")}


def target(name):
    return (HERO_SIZE, HERO_QUALITY) if name in HEROES else (SIZE, QUALITY)

# (요리이름, [검색어들], [제목에 반드시 들어가야 할 낱말])
# must는 좁게 준다. 넓게 주면 "Banchans.jpg" 같은 모둠 사진이 호박무침 자리에 들어온다.
JOBS = [
    ("양파전",            ["Yangpa-jeon", "Onion pancake Korean", "Buchimgae"],   ["jeon", "pancake", "buchim"]),
    ("북어국",            ["Bugeo-guk", "Bugeotguk", "Dried pollock soup"],       ["bugeo", "pollock", "guk"]),
    ("두부두루치기",       ["Dubu-duruchigi", "Duruchigi", "Tofu stir fry Korean"], ["duruchigi", "dubu", "tofu"]),
    ("된장찌개",           ["Doenjang-jjigae"],                                   ["doenjang"]),
    ("된장채소수제비",      ["Sujebi", "Sujaebi"],                                 ["sujebi", "sujaebi"]),
    ("동태찌개",           ["Dongtae-jjigae", "Saengtae-jjigae", "Pollock stew"],  ["dongtae", "saengtae", "jjigae"]),
    ("갈치조림",           ["Galchi-jorim", "Braised cutlassfish"],                ["galchi", "cutlass"]),
    ("돼지갈비찜",         ["Dwaeji-galbi-jjim", "Galbi-jjim"],                    ["galbi"]),
    ("나박김치",           ["Nabak-kimchi", "Mul-kimchi"],                         ["nabak", "kimchi"]),
    ("계란말이주먹밥",      ["Gyeran-mari", "Jumeok-bap", "Korean rice ball"],      ["gyeran", "jumeok", "rice ball"]),

    # ── 아래는 2026-08-24에 더한 것 ──────────────────────────────
    ("가지쇠고기볶음",      ["Gaji-bokkeum", "Gaji namul"],                        ["gaji"]),
    ("고등어양념구이",      ["Godeungeo-gui", "Grilled mackerel Korean"],           ["godeungeo", "mackerel"]),
    ("김치두부쌈",         ["Dubu-kimchi", "Tofu kimchi"],                         ["dubu-kimchi", "dubukimchi"]),
    ("김치볶음밥",         ["Kimchi-bokkeum-bap", "Kimchi fried rice"],            ["bokkeum-bap", "fried rice"]),
    ("김치수제비",         ["Kimchi-sujebi"],                                      ["sujebi"]),
    ("깻잎말이김치",       ["Kkaennip-kimchi", "Perilla leaf kimchi"],             ["kkaennip", "perilla"]),
    ("닭가슴살해파리샐러드", ["Haepari-naengchae", "Jellyfish salad Korean"],        ["haepari", "jellyfish"]),
    ("닭꼬치구이",         ["Dak-kkochi", "Dakkochi", "Korean chicken skewer"],    ["kkochi", "skewer"]),
    ("두부알찜",           ["Dubu-jjim", "Gyeran-jjim"],                          ["dubu-jjim", "jjim"]),
    ("맑은대구탕",         ["Daegu-tang", "Daegutang", "Codfish soup Korean"],     ["daegu-tang", "daegutang"]),
    ("매운가지볶음",       ["Gaji-bokkeum"],                                       ["gaji"]),
    ("부추잡채",          ["Buchu-japchae"],                                       ["buchu"]),
    ("사골우거지탕",       ["Ugeoji-guk", "Ugeojitang", "Ugeoji"],                 ["ugeoji"]),
    ("쇠고기완자찜",       ["Wanja-jeon", "Gogi-wanja", "Wanja"],                  ["wanja"]),
    ("순대볶음",          ["Sundae-bokkeum"],                                      ["sundae"]),
    ("양송이버섯죽",       ["Beoseot-juk", "Yangsongi"],                           ["beoseot", "yangsongi"]),
    ("열무김치냉면",       ["Yeolmu-naengmyeon", "Naengmyeon"],                    ["naengmyeon"]),
    ("잔치국수",          ["Janchi-guksu"],                                        ["janchi"]),
    ("제육겨자쌈",         ["Jeyuk-bokkeum", "Jeyuk"],                             ["jeyuk"]),
    ("조기찜",            ["Jogi-jjim", "Jogijjim"],                              ["jogi"]),
    ("청국장찌개",         ["Cheonggukjang-jjigae", "Cheonggukjang"],              ["cheonggukjang"]),
    ("콩나물국밥",         ["Kongnamul-gukbap"],                                    ["kongnamul"]),
    ("콩나물잡채",         ["Japchae"],                                            ["japchae"]),
    ("호박양파국",         ["Aehobak-guk", "Hobak-guk"],                           ["hobak"]),
    ("호박무침",          ["Hobak-namul", "Aehobak-bokkeum", "Aehobak-namul"],     ["hobak"]),
    ("콩나물무밥",         ["Kongnamul-bap", "Kongnamulbap"],                      ["kongnamul-bap", "kongnamulbap"]),
    ("오징어찌개",         ["Ojingeo-jjigae", "Ojingeo-guk"],                      ["ojingeo"]),
    ("오징어볶음과소면",    ["Ojingeo-bokkeum"],                                    ["ojingeo-bokkeum"]),
    ("모듬전",            ["Modeum-jeon", "Jeon Korean platter"],                 ["modeum"]),
    ("생태국",            ["Saengtae-guk", "Saengtaeguk"],                        ["saengtae"]),
    ("알탕",              ["Altang", "Al-tang"],                                  ["altang", "al-tang"]),
    ("버섯두부찌개",       ["Beoseot-jjigae", "Dubu-jjigae"],                      ["beoseot-jjigae", "dubu-jjigae"]),
    ("명란젓찌개",         ["Myeongnan-jjigae"],                                    ["myeongnan-jjigae"]),
    ("찬밥지짐이",         ["Bap-jeon", "Bapjeon"],                                ["bap-jeon", "bapjeon"]),
]

# 검색이 물어온 사진이 다른 요리라 뺐다 (2026-08-24 대조표 육안 확인).
# 다시 넣지 마라 — 같은 검색어면 같은 사진이 또 온다. 남의 요리 사진을 붙이느니 그릇 글리프가 낫다.
REJECTED = {
    "김치적":        "Seop sanjeok(섭산적) — 고기 산적이다. 김치전으로도 못 대신한다(적은 꼬치)",
    "두부채소냉채":   "Miyeok-naengchae — 미역냉채라 두부가 없다",
    "호박무침":      "Hobak-goji — 말린 호박고지라 무침이 아니다. BAD에 goji를 넣고 다시 찾는다",
    "콩나물무밥":    "Jeonju-bibim-bap — 전주비빔밥 상차림이다. must를 kongnamul-bap으로 좁혀 다시 찾는다",
    "오징어볶음과소면": "Ojingeo-chae-bokkeum — 마른 오징어채라 생물 볶음과 다르다. BAD에 chae-bokkeum",
    "골뱅이볶음":    "Golbaengi-muchim — 차가운 무침이라 볶음과 다르다. 공용에 볶음 사진이 없다",
    "해물밥전":      "Haemul-pajeon밖에 없다 — 파전은 밥전이 아니다",
    "채소국수":      "이름이 일반적이다. Bibim-guksu는 다른 요리다",
    "별미밥":        "이름이 일반적이라 검색어를 만들 수 없다",
}

# 같은 요리라 사진을 나눠 쓴다. build.py의 same_dish()가 이미 한 요리로 보는 것들이다.
# 없는 사진을 만들어 붙이는 게 아니라, 있는 사진을 정직하게 돌려 쓰는 것이다.
SAME = {
    "갈치무조림": "갈치조림",
    "버섯청국장찌개": "청국장찌개",
}

# 이름이 너무 일반적이거나(별미밥·채소국수) 그 요리의 사진이 공용에 없어서 비워 둔다.
# 앱에서는 그릇 글리프로 남는다 — 다른 요리 사진을 갖다 붙이는 것보다 낫다.
BAD = ["map", "diagram", "logo", "chart", "portrait", "performing", "signboard",
       "restaurant exterior", "banchan", "menu", "poster",
       "goji",           # 호박고지 — 말린 재료지 요리가 아니다
       "chae-bokkeum"]   # 오징어채볶음 — 마른 채라 생물 볶음과 다르다


def search(term, limit=8):
    q = urllib.parse.urlencode({
        "action": "query", "generator": "search", "gsrsearch": term,
        "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": "900", "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(API + "?" + q, headers=UA), timeout=30) as r:
        data = json.load(r)
    time.sleep(PAUSE)
    out = []
    for p in sorted((data.get("query") or {}).get("pages", {}).values(),
                    key=lambda x: x.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        url = ii.get("thumburl") or ii.get("url")
        if not url or not url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
            continue
        out.append({"title": p.get("title", ""), "url": url,
                    "license": (ii.get("extmetadata") or {}).get("LicenseShortName", {}).get("value", "?"),
                    "page": ii.get("descriptionurl", "")})
    return out


def grab(url, tries=3):
    last = None
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                img = Image.open(io.BytesIO(r.read())).convert("RGB")
            time.sleep(PAUSE)
            return img
        except Exception as e:
            last = e
            time.sleep(PAUSE * (a + 2))
    raise last


def square(img, n):
    w, h = img.size
    s = max(n / w, n / h)
    img = img.resize((int(w * s + .5), int(h * s + .5)), Image.LANCZOS)
    W, H = img.size
    return img.crop(((W - n) // 2, (H - n) // 2, (W - n) // 2 + n, (H - n) // 2 + n))


# 파일 크기를 설정과 맞춘다. 대표 요리는 HERO_SIZE, 나머지는 SIZE.
# 다시 받지 않고 줄이기만 하므로 검색 결과가 달라질 걱정이 없다.
shrunk = 0
for f in sorted(os.listdir(OUT)):
    if not (f.startswith("dish_") and f.endswith(".jpg")):
        continue
    fp = os.path.join(OUT, f)
    nm = f[5:-4]
    im = Image.open(fp)
    tsize, tq = target(nm)
    if im.width > tsize:
        square(im.convert("RGB"), tsize).save(fp, "JPEG", quality=tq, optimize=True)
        shrunk += 1
if shrunk:
    print("이미 있던 사진 %d장을 설정 크기로 줄였다" % shrunk)

CREDITS = os.path.join(OUT, "dish_credits.json")
credits = {}
if os.path.exists(CREDITS):
    old = json.load(open(CREDITS, encoding="utf-8"))
    credits = {c["dish"]: c for c in old} if isinstance(old, list) else old

fail = []
for name, terms, must in JOBS:
    path = os.path.join(OUT, "dish_%s.jpg" % name)
    if os.path.exists(path) and not REDO:
        print("%-16s 있음, 건너뜀" % name)
        continue
    done = False
    for term in terms:
        if done:
            break
        for c in search(term):
            t = c["title"].lower()
            if not any(k in t for k in must) or any(b in t for b in BAD):
                continue
            try:
                img = grab(c["url"])
            except Exception as e:
                print("  skip", c["title"][:40], type(e).__name__)
                continue
            _s, _q = target(name)
            square(img, _s).save(path, "JPEG", quality=_q, optimize=True)
            print("%-16s %5.1f KB  %s  [%s]" % (name, os.path.getsize(path) / 1024,
                                                c["title"][5:45], c["license"]))
            credits[name] = {"dish": name, "title": c["title"],
                             "license": c["license"], "page": c["page"]}
            done = True
            break
    if not done:
        fail.append(name)
        print("FAIL %-16s (그릇 글리프로 남는다)" % name)

# 같은 요리끼리 사진을 나눠 쓴다. 출처도 함께 물려준다.
for name, src in SAME.items():
    sp = os.path.join(OUT, "dish_%s.jpg" % src)
    if os.path.exists(sp):
        open(os.path.join(OUT, "dish_%s.jpg" % name), "wb").write(open(sp, "rb").read())
        if src in credits:
            credits[name] = dict(credits[src], dish=name, same_as=src)
        print("%-16s ← %s 사진 재사용" % (name, src))

# 대조표. 검색이 엉뚱한 걸 물어오므로 이걸 눈으로 보고 판단해야 한다.
cells = []
for name, _, _ in JOBS:
    p = os.path.join(OUT, "dish_%s.jpg" % name)
    if os.path.exists(p):
        cells.append((name, Image.open(p)))
if cells:
    cols = 7
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 152 + 8, rows * 152 + 8), (24, 24, 24))
    for i, (nm, im) in enumerate(cells):
        sheet.paste(im.resize((144, 144)), (8 + (i % cols) * 152, 8 + (i // cols) * 152))
    sheet.save(os.path.join(HERE, "_dish_sheet.png"))
    print("\n대조표 %d장 → _dish_sheet.png  (왼→오, 위→아래 순서는 아래 목록과 같다)" % len(cells))
    for i in range(0, len(cells), cols):
        print("  " + " · ".join(nm for nm, _ in cells[i:i + cols]))

json.dump(credits, open(CREDITS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n못 찾음 %d개: %s" % (len(fail), " · ".join(fail) or "없음"))
print("출처: _design/dish_credits.json")

# ── 대표 요리만 큰 크기로 맞춘다 ──────────────────────────────
# 검색을 다시 돌리지 않는다. dish_credits.json에 박아둔 그 파일을 제목으로 집어 다시 받는다.
# 검색은 결과가 흔들려서, 눈으로 통과시킨 사진이 다른 것으로 바뀔 수 있다.
def by_title(title):
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo",
                                "iiprop": "url", "iiurlwidth": "1000", "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(API + "?" + q, headers=UA), timeout=30) as r:
        data = json.load(r)
    time.sleep(PAUSE)
    for pg in ((data.get("query") or {}).get("pages") or {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        return ii.get("thumburl") or ii.get("url")
    return None


big = 0
for name in sorted(HEROES):
    fp = os.path.join(OUT, "dish_%s.jpg" % name)
    if not os.path.exists(fp) or Image.open(fp).width >= HERO_SIZE:
        continue
    c = credits.get(name)
    if not c:
        print("대표 %-14s 출처 기록이 없어 건너뜀" % name)
        continue
    try:
        u = by_title(c["title"])
        img = grab(u) if u else None
    except Exception as e:
        print("대표 %-14s 실패 %s" % (name, type(e).__name__))
        continue
    if img:
        square(img, HERO_SIZE).save(fp, "JPEG", quality=HERO_QUALITY, optimize=True)
        print("대표 %-14s %dpx  %5.1f KB" % (name, HERO_SIZE, os.path.getsize(fp) / 1024))
        big += 1
print("대표 %d종 중 %d장을 %dpx로 올렸다" % (len(HEROES), big, HERO_SIZE))
