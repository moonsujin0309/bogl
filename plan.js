// 보글 · plan.js — 배치 · 매대 분류 · 재료 합산 · 유튜브 설명란 파싱.
// 브라우저에서는 build.py가 app.html에 인라인하고, node에서는 require로 읽는다 (test_plan.js).
// 화면 코드는 여기 없다. 여기 있는 것은 전부 순수 계산이다.

// ───────────────────────────────────────────── 매대 분류 (이마트몰 대분류)
const CATS = [
  ['정육 · 계란', ['쇠고기', '돼지', '갈비', '삼겹', '목살', '안심', '등심', '사태', '양지', '닭', '오리',
                 '계란', '베이컨', '햄', '소시지', '정육', '우둔', '차돌']],
  ['수산 · 건해산', ['갈치', '동태', '명태', '고등어', '조기', '오징어', '새우', '조개', '미역', '김',
                  '게', '낙지', '문어', '대구', '굴', '홍합', '바지락', '북어', '황태', '어묵', '멸치',
                  '생선', '가자미', '삼치', '꽁치', '장어', '전복', '해물', '조갯살', '쭈꾸미', '젓']],
  ['우유 · 유제품', ['우유', '치즈', '버터', '생크림', '요구르트', '요거트', '연유']],
  ['쌀 · 잡곡', ['쌀', '찹쌀', '보리', '현미', '팥', '녹두', '수수', '기장', '가래떡', '떡']],
  ['라면 · 통조림', ['라면', '국수', '소면', '당면', '칼국수', '냉면', '스파게티', '통조림', '참치']],
  ['김치 · 반찬', ['김치', '깍두기', '장아찌', '젓갈']],
  ['장 · 양념 · 오일', ['고추장', '된장', '간장', '식초', '참기름', '들기름', '식용유', '설탕', '소금',
                    '후추', '고춧가루', '물엿', '맛술', '잣', '깨', '가루', '카레', '소스']],
];
const CAT_ORDER = ['정육 · 계란', '수산 · 건해산', '채소 · 두부', '김치 · 반찬', '장 · 양념 · 오일',
                   '쌀 · 잡곡', '라면 · 통조림', '우유 · 유제품'];

function category(name){
  for(const [cat, keys] of CATS) if(keys.some(k => name.includes(k))) return cat;
  return '채소 · 두부';
}

// ───────────────────────────────────────────── 상할 때까지 며칠
// 1: 그날그날 · 7: 한 주 · 30: 오래간다. 키워드 포함이면 된다 — 사전이 아니라 장보기 횟수를 정하는 기준이다.
const SEA_LONG = ['미역', '김', '멸치', '북어', '황태', '젓', '어묵'];
const P1 = ['두부', '콩나물', '숙주', '시금치', '상추', '깻잎', '부추', '버섯', '애호박', '오이', '닭',
            '다짐', '다진', '굴', '조개', '조갯살'];
const P30 = ['무', '당근', '감자', '양파', '마늘'];
const CAT30 = ['김치 · 반찬', '장 · 양념 · 오일', '쌀 · 잡곡', '라면 · 통조림'];

function perish(name){
  const cat = category(name);
  if(cat === '수산 · 건해산') return SEA_LONG.some(k => name.includes(k)) ? 30 : 1;
  if(CAT30.includes(cat)) return 30;
  if(P1.some(k => name.includes(k))) return 1;
  if(P30.some(k => name.includes(k))) return 30;
  return 7;
}

// ───────────────────────────────────────────── 수량 (build.py parse_qty 이식 — 같은 입력에 같은 결과)
const ML = { '컵': 200, '큰술': 15, 'T': 15, 't': 5, '작은술': 5, 'ml': 1, 'cc': 1, '리터': 1000, 'L': 1000 };
const G = { 'g': 1, 'kg': 1000, '그램': 1, '근': 600 };
const COUNT = ['개', '장', '뿌리', '마리', '쪽', '모', '단', '대', '포기', '알', '톨', '줄기',
               '통', '잎', '봉지', '봉', '공기', '줌', '송이', '덩어리', '자루', '판', '토막', '묶음', '팩', '캔'];
const VAGUE = ['약간', '적당량', '조금', '한줌', '기호에', '기호껏', '취향', '적당히', '넉넉히'];
// 한글 수사는 숫자로 바꾼 뒤 기존 규칙을 탄다. `두부`의 `두`를 2로 읽지 않게 뒤에 공백이나 단위가 와야 한다.
const KNUM = { '한두': 2, '두세': 3, '다섯': 5, '여섯': 6, '한': 1, '두': 2, '세': 3, '네': 4, '반': 0.5 };
const KNUM_RE = new RegExp('^(한두|두세|다섯|여섯|한|두|세|네|반)(?=\\s|$|' +
  Object.keys(ML).concat(Object.keys(G), COUNT).filter(u => /[ㄱ-힣]/.test(u)).join('|') + ')');

function parseQty(s){
  s = String(s || '').trim();
  if(!s || VAGUE.some(v => s.includes(v))) return null;
  s = s.replace(/½/g, '1/2').replace(/¼/g, '1/4').replace(/⅓/g, '1/3').replace(KNUM_RE, (m, k) => KNUM[k]);
  let m, val, unit;
  if((m = s.match(/^\s*(\d+)\s*과\s*(\d+)\s*\/\s*(\d+)\s*(.*)$/))){ val = +m[1] + m[2] / m[3]; unit = m[4]; }
  else if((m = s.match(/^\s*(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)\s*(.*)$/))){ val = Math.max(+m[1], +m[2]); unit = m[3]; }
  else if((m = s.match(/^\s*(\d+)\s*\/\s*(\d+)\s*(.*)$/))){ val = m[1] / m[2]; unit = m[3]; }
  else if((m = s.match(/^\s*(\d+(?:\.\d+)?)\s*(.*)$/))){ val = +m[1]; unit = m[2]; }
  else return null;
  unit = unit.trim() ? unit.trim().split(/\s+/)[0] : '개';
  unit = unit.replace(/[^\wㄱ-힣]/g, '') || '개';
  if(['kg', 'g', 'ml', 'cc', 'l'].includes(unit.toLowerCase())) unit = unit.toLowerCase();
  if(unit in ML) return [val * ML[unit], 'ml'];
  if(unit in G) return [val * G[unit], 'g'];
  for(const c of COUNT) if(unit.startsWith(c)) return [val, c];
  return [val, unit];
}

// 장볼 양이라 모자라지 않게 올림한다. 3.4개를 사러 갈 수는 없다.
function fmt(v, u){
  if(v == null || !u) return '조금';
  if(u === 'ml') return v >= 200 ? (Math.ceil(v / 100) / 2) + '컵' : Math.max(1, Math.ceil(v / 15 - 1e-9)) + '큰술';
  if(u === 'g')  return v >= 1000 ? (Math.ceil(v / 100) / 10) + 'kg' : (Math.ceil(v / 10) * 10) + 'g';
  return Math.ceil(v - 1e-9) + u;
}

// 단위가 여러 그룹으로 흩어지면 가장 자주 나온 그룹만 쓴다. 개수 단위는 전부 한 그룹이다.
function pickQty(sums, seen){
  const keys = Object.keys(sums);
  if(!keys.length) return null;
  const groups = {};
  for(const u of keys){ const g = (u === 'g' || u === 'ml') ? u : 'count'; groups[g] = groups[g] || {}; groups[g][u] = (groups[g][u] || 0) + sums[u]; }
  const hits = g => Object.keys(groups[g]).reduce((a, u) => a + (seen[u] || 0), 0);
  let top = null;
  for(const g in groups) if(top === null || hits(g) > hits(top)) top = g;
  const total = Object.values(groups[top]).reduce((a, b) => a + b, 0);
  let unit = top;
  if(top === 'count'){ unit = null; for(const u in groups.count) if(unit === null || (seen[u] || 0) > (seen[unit] || 0)) unit = u; }
  return { qty: fmt(total, unit), value: Math.round(total * 1000) / 1000, unit };
}

/** 폴더 요리들의 장볼 재료를 합산한다. b인 재료만, 인분은 people/servings로 환산. */
function aggregate(dishes, people){
  const agg = new Map();
  for(const d of dishes){
    const scale = people / (d.servings || 4);
    for(const i of d.ing || []){
      if(!i.b) continue;
      let a = agg.get(i.n);
      if(!a) agg.set(i.n, a = { sum: {}, units: {}, used: 0, where: [], by: [] });
      a.used++; a.where.push(d.name);
      const has = i.v != null && i.u;
      a.by.push({ dish: d.name, v: has ? i.v * scale : null, u: has ? i.u : null, q: i.q || '조금' });   // 올림 전 원값. 헤더(살 양)만 올림한다
      if(has){ a.sum[i.u] = (a.sum[i.u] || 0) + i.v * scale; a.units[i.u] = (a.units[i.u] || 0) + 1; }
    }
  }
  const by = {};
  [...agg.entries()].sort((x, y) => (y[1].used - x[1].used) || x[0].localeCompare(y[0], 'ko')).forEach(([n, a]) => {
    const got = pickQty(a.sum, a.units) || { qty: '조금', value: null, unit: null };
    (by[category(n)] = by[category(n)] || []).push({ name: n, qty: got.qty, value: got.value, unit: got.unit, used: a.used, where: a.where, by: a.by });
  });
  const groups = CAT_ORDER.filter(c => by[c]).map(c => ({ cat: c, items: by[c] }));
  const overlaps = [...agg.entries()].filter(([, a]) => a.used >= 2)
    .map(([n, a]) => ({ name: n, used: a.used, where: a.where }))
    .sort((x, y) => (y.used - x.used) || x.name.localeCompare(y.name, 'ko'));
  return { groups, overlaps, buyCount: agg.size };
}

// ───────────────────────────────────────────── 배치
const ROLE = { '부침': 'fresh', '구이': 'fresh', '밥': 'fresh', '만두/면류': 'fresh',
               '조림': 'ahead', '찜': 'ahead', '밑반찬/김치': 'ahead',   // 나물·생채는 전날에 가면 물이 난다 (2026-09-08)
               '국': 'soup', '찌개/전골/스튜': 'soup', '탕': 'soup' };
const role = d => ROLE[d.kind] || '';
// 하루 모드 슬롯. 사용자가 고른 when(ahead·day·fresh)이 kind 판정보다 앞선다. 며칠 모드에서는 안 쓴다.
const SLOT = { ahead: 0, day: 1, fresh: 2 };
const slotOf = d => d.when in SLOT ? SLOT[d.when] : role(d) === 'ahead' ? 0 : role(d) === 'fresh' ? 2 : 1;
const minOf = d => d.min && d.min < 999 ? d.min : 0;
const buyOf = d => (d.ing || []).filter(i => i.b).map(i => i.n);
const shared = (a, b) => { const s = new Set(buyOf(b)); return buyOf(a).filter(n => s.has(n)); };
// 잔재료는 밑작업으로 알릴 값어치가 없다. 대파·마늘까지 적으면 진짜 손질거리(가지·무)가 묻힌다. 배치 점수에는 그대로 쓴다.
const MINOR = ['고추', '붉은고추', '청고추', '대파', '쪽파', '마늘', '다진마늘', '다진파', '생강', '양파', '소금', '후추'];
const major = ns => ns.filter(n => !MINOR.some(k => n.includes(k)));
// 받침이 있으면 `은`, 없으면 `는`
const neun = w => { const c = w.charCodeAt(w.length - 1) - 0xAC00; return (c >= 0 && c <= 11171 && c % 28 !== 0) ? '은' : '는'; };

// 앞쪽 날부터 하나씩 더. 7개 5일이면 2·2·1·1·1. 요리가 날보다 적으면 뒤쪽 날이 빈다.
function assign(perm, days){
  const out = []; let k = 0;
  for(let i = 0; i < days; i++){ const take = Math.ceil((perm.length - k) / (days - i)); out.push(perm.slice(k, k + take)); k += take; }
  return out;
}

// 1일에 한 번. 그 뒤로는 상하는 재료가 있는 날에 마지막 장보기로부터 너무 지났으면 한 번 더.
function tripsOf(byDay){
  const t = []; let last = 0;
  byDay.forEach((ds, i) => {
    const day = i + 1;
    const need = day === 1 || ds.some(d => buyOf(d).some(n => { const p = perish(n); return day - last > (p === 1 ? 2 : p); }));
    if(need){ t.push(day); last = day; }
  });
  return t;
}

function scoreOf(byDay){
  let s = tripsOf(byDay).length * 10;
  for(let i = 0; i + 1 < byDay.length; i++)
    if(byDay[i].some(d => role(d) === 'soup') && byDay[i + 1].some(d => role(d) === 'soup')) s += 3;
  const dayOf = []; byDay.forEach((ds, i) => ds.forEach(d => dayOf.push([d, i])));
  for(let a = 0; a < dayOf.length; a++) for(let b = a + 1; b < dayOf.length; b++)
    if(shared(dayOf[a][0], dayOf[b][0]).length) s += Math.abs(dayOf[a][1] - dayOf[b][1]);
  return s;
}

function* perms(arr){
  if(arr.length <= 1){ yield arr.slice(); return; }
  for(let i = 0; i < arr.length; i++){
    const rest = arr.slice(0, i).concat(arr.slice(i + 1));
    for(const p of perms(rest)) yield [arr[i], ...p];
  }
}
// 씨 고정 난수 — 같은 폴더면 다시 열어도 같은 배치가 나와야 한다.
function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

function* candidates(dishes){
  if(dishes.length <= 7){ yield* perms(dishes); return; }
  // ponytail: 8개 넘으면 표본 탐색. 전수는 40,320부터 체감된다
  yield dishes.slice();
  const r = rng(20260907);
  // Large playlists must not freeze the main thread. Bound pair comparisons.
  const attempts = dishes.length <= 12 ? 3000 : Math.max(1, Math.floor(80000 / (dishes.length * dishes.length)));
  for(let k = 0; k < attempts; k++){
    const p = dishes.slice();
    for(let i = p.length - 1; i > 0; i--){ const j = Math.floor(r() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
    yield p;
  }
}

/** dishes: [{name, kind, min?, when?, ing:[{n,b}]}], days: 1~7, opts: {once} — 장보기 한 번에 */
function plan(dishes, days, opts){
  opts = opts || {};
  if(days <= 1){
    const slots = [{ label: '전날', dishes: [] }, { label: '당일 아침', dishes: [] }, { label: '먹기 직전', dishes: [] }];
    for(const d of dishes) slots[slotOf(d)].dishes.push(d);
    slots.forEach(s => s.dishes.sort((a, b) => minOf(b) - minOf(a)));   // 같은 칸에서는 오래 걸리는 것부터
    const prep = [];
    for(const a of slots[0].dishes) for(const o of slots[1].dishes.concat(slots[2].dishes)){
      const sh = major(shared(a, o));
      if(sh.length) prep.push({ day: 0, text: `${sh.join('·')}${neun(sh[sh.length - 1])} 전날 손질해 두면 당일 ${o.name}에 그대로 써요` });
    }
    return { mode: 'day', slots, prep };
  }
  let best = null, bestScore = Infinity;
  for(const p of candidates(dishes)){
    const byDay = assign(p, days), s = scoreOf(byDay);
    if(s < bestScore){ best = byDay; bestScore = s; }
  }
  // 한 번에 장보면 태그만 사라진다. 점수는 그대로라 상하는 재료는 이미 앞쪽 날에 가 있다.
  const trips = opts.once ? [1] : tripsOf(best);
  const prep = [];
  for(let i = 0; i + 1 < best.length; i++){
    const ings = new Set(), names = new Set();
    for(const a of best[i]) for(const b of best[i + 1]){ const sh = major(shared(a, b)); if(sh.length){ sh.forEach(n => ings.add(n)); names.add(b.name); } }
    if(ings.size) prep.push({ day: i + 1, text: `${[...ings].join('·')} 손질할 때 내일 ${[...names].join('·')} 것도 같이` });
  }
  return { mode: 'days', days: best.map((ds, i) => ({ i: i + 1, dishes: ds, trip: trips.includes(i + 1) })), trips, prep, score: bestScore };
}

// ───────────────────────────────────────────── 유튜브 설명란
const CHAP = /^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s*[-–—:]?\s*(.+)$/;
const ING_HEAD = /재료|Ingredients|준비물/i;
const STEP_HEAD = /만드는\s*법|조리|레시피|순서|\b(?:directions|instructions|method)\b/i;

// 한 줄을 `이름 / 수량`으로 가른다. 마지막 공백(또는 :) 뒤가 수량으로 읽히면 거기서, 아니면 그 앞 칸에서 한 번 더.
function splitLine(s){
  s = s.replace(/\([^)]*\)/g, ' ').trim().replace(/^[-•·*]+\s*/, '').replace(/^\d+[.)]\s+/, '').replace(/\s+/g, ' ');
  let cut = s.length;
  for(let k = 0; k < 2; k++){
    const i = Math.max(s.lastIndexOf(' ', cut - 1), s.lastIndexOf(':', cut - 1));
    if(i <= 0) break;
    const head = s.slice(0, i).replace(/[:\s]+$/, ''), tail = s.slice(i + 1).trim();
    const p = head && parseQty(tail);
    if(p) return { n: head, q: tail, v: p[0], u: p[1], b: 1 };
    cut = i;
  }
  return { n: s, q: '', b: 1 };
}

// `돼지고기 300g, 양파 1개`처럼 한 줄에 여럿이면 나눈다. 수량이 둘 이상 읽힐 때만 — `소금, 후추 약간`은 한 줄이다.
// `1/2모`의 `/`는 분수라 자르지 않는다.
function pushLine(line, ing){
  const parts = line.replace(/(\d)\/(\d)/g, '$1\u0001$2').split(/\s*[·,\/]\s*/)
    .map(s => s.replace(/\u0001/g, '/').trim()).filter(Boolean);   // lookbehind 없이 — iOS 16.4 미만은 lookbehind에서 파싱 자체가 죽는다
  const items = parts.length >= 2 ? parts.map(splitLine) : [];
  if(items.filter(i => i.q).length >= 2){ items.forEach(i => { if(i.n) ing.push(i); }); return; }
  const it = splitLine(line);
  if(it.n) ing.push(it);
}

function parseDesc(text){
  const chapters = [], ing = [];
  let inIng = false, blank = 0;
  for(const raw of String(text || '').split(/\r?\n/)){
    const m = raw.match(CHAP);
    if(m){ chapters.push({ t: (+(m[1] || 0)) * 3600 + (+m[2]) * 60 + (+m[3]), label: m[4].trim() }); inIng = false; continue; }
    const line = raw.replace(/\([^)]*\)/g, ' ');   // `(2인분 기준)` 같은 괄호는 뗀다
    // Bilingual descriptions repeat the same recipe. Prefer the Korean ingredient list.
    if(/\bingredients\b/i.test(line) && ing.some(i => /[가-힣]/.test(i.n))){ inIng = false; continue; }
    if(/https?:\/\/|구독|좋아요|협찬|광고|문의|인스타그램|instagram|copyright/i.test(line)){ inIng = false; continue; }
    if(!inIng){
      if(ING_HEAD.test(line)){ inIng = true; blank = 0;
        const rest = line.split(/[:：]/).slice(1).join(':').trim();   // `재료 : 돼지고기 300g, 양파 1개` — 같은 줄에 달린 재료
        if(rest) pushLine(rest, ing); }
      continue;
    }
    if(!line.trim()){ if(++blank >= 2) inIng = false; continue; }
    blank = 0;
    if(STEP_HEAD.test(line)){ inIng = false; continue; }
    if(/^\s*[\[【].*[\]】]\s*:?\s*$/.test(line)) continue;   // [양념] 같은 소제목
    pushLine(line, ing);
  }
  return { ing, chapters: [...new Map(chapters.map(c => [c.t, c])).values()].sort((a, b) => a.t - b.t) };
}

function youtubeURL(text){
  const raw = String(text || '').trim(), found = raw.match(/https?:\/\/[^\s<>]+/);
  try{
    const u = new URL(found ? found[0] : raw);
    return ['https:', 'http:'].includes(u.protocol) &&
      ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtube-nocookie.com'].includes(u.hostname) ? u : null;
  }catch(e){ return null; }
}
function ytId(text){
  const u = youtubeURL(text); if(!u) return null;
  const paths = u.pathname.split('/').filter(Boolean);
  const id = u.hostname === 'youtu.be' ? paths[0] : u.pathname === '/watch' ? u.searchParams.get('v') :
    ['shorts', 'live', 'embed'].includes(paths[0]) ? paths[1] : null;
  return /^[\w-]{11}$/.test(id || '') ? id : null;
}
function ytList(text){ const u = youtubeURL(text), id = u && u.searchParams.get('list'); return /^[\w-]+$/.test(id || '') ? id : null; }

if(typeof module !== 'undefined') module.exports = { CATS, CAT_ORDER, category, perish, parseQty, fmt, pickQty, aggregate, plan, parseDesc, splitLine, ytId, ytList };
