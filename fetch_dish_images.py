# 요리 사진을 위키미디어 공용에서 받아 원형 썸네일로 저장한다.
# 재료는 아이콘이지만 요리는 눈으로 고르는 대상이라 사진이 있어야 한다.
#
# 결과: _design/dish_<요리이름>.jpg  +  _dish_sheet.png (눈으로 확인용)
# 검색이 엉뚱한 걸 물어오는 일이 잦으니 반드시 대조표를 보고 판단할 것.
import io, json, os, re, time, urllib.parse, urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_design")
UA = {"User-Agent": "BoglMockup/0.1 (https://github.com/moonsujin0309/bogl; moonopmd@gmail.com) Python-urllib"}
PAUSE = 2.0
API = "https://commons.wikimedia.org/w/api.php"
SIZE = 220

# (요리이름, [검색어들], [제목에 반드시 들어가야 할 낱말])
JOBS = [
    ("양파전",        ["Yangpa-jeon", "Onion pancake Korean", "Buchimgae"],        ["jeon", "pancake", "buchim"]),
    ("북어국",        ["Bugeo-guk", "Bugeotguk", "Dried pollock soup"],            ["bugeo", "pollock", "guk"]),
    ("두부두루치기",   ["Dubu-duruchigi", "Duruchigi", "Tofu stir fry Korean"],     ["duruchigi", "dubu", "tofu"]),
    ("된장찌개",       ["Doenjang-jjigae"],                                        ["doenjang"]),
    ("된장채소수제비",  ["Sujebi", "Sujaebi"],                                      ["sujebi", "sujaebi"]),
    ("동태찌개",       ["Dongtae-jjigae", "Saengtae-jjigae", "Pollock stew"],       ["dongtae", "saengtae", "jjigae"]),
    ("갈치조림",       ["Galchi-jorim", "Braised cutlassfish"],                     ["galchi", "cutlass"]),
    ("돼지갈비찜",     ["Dwaeji-galbi-jjim", "Galbi-jjim"],                         ["galbi"]),
    ("나박김치",       ["Nabak-kimchi", "Mul-kimchi"],                              ["nabak", "kimchi"]),
    ("계란말이주먹밥",  ["Gyeran-mari", "Jumeok-bap", "Korean rice ball"],           ["gyeran", "jumeok", "rice ball"]),
]
BAD = ["map", "diagram", "logo", "chart", "portrait", "performing", "signboard", "restaurant exterior"]


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


credits, cells = [], []
for name, terms, must in JOBS:
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
            path = os.path.join(OUT, "dish_%s.jpg" % name)
            square(img, SIZE).save(path, "JPEG", quality=80, optimize=True)
            print("%-14s %5.1f KB  %s  [%s]" % (name, os.path.getsize(path) / 1024,
                                                c["title"][5:45], c["license"]))
            credits.append({"dish": name, "title": c["title"], "license": c["license"], "page": c["page"]})
            cells.append((name, Image.open(path)))
            done = True
            break
    if not done:
        print("FAIL %-14s (아이콘으로 남는다)" % name)

if cells:
    cols = 5
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 152 + 8, rows * 152 + 8), (24, 24, 24))
    for i, (nm, im) in enumerate(cells):
        sheet.paste(im.resize((144, 144)), (8 + (i % cols) * 152, 8 + (i // cols) * 152))
    sheet.save(os.path.join(HERE, "_dish_sheet.png"))

json.dump(credits, open(os.path.join(OUT, "dish_credits.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n대조표: _dish_sheet.png · 출처: _design/dish_credits.json")
