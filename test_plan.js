// node test_plan.js — plan.js 검사. 전부 assert. 통과하면 마지막 줄에 OK.
const assert = require('assert');
const P = require('./plan.js');

const ing = (...ns) => ns.map(n => ({ n, b: 1, v: 1, u: '개' }));
const dish = (name, kind, ...ns) => ({ name, kind, servings: 2, ing: ing(...ns) });

// 하루 → 타임라인
{
  const r = P.plan([dish('조림', '조림', '무'), dish('구이', '구이', '고등어'), dish('국', '국', '두부')], 1);
  assert.strictEqual(r.mode, 'day');
  assert.deepStrictEqual(r.slots.map(s => s.dishes.map(d => d.name)), [['조림'], ['국'], ['구이']]);
  assert.deepStrictEqual(r.slots.map(s => s.label), ['전날', '당일 아침', '먹기 직전']);
}
// 나물은 전날에 안 간다(아침). when이 kind 판정보다 우선. 같은 칸은 소요시간 긴 것부터.
{
  const namul = dish('시금치나물', '나물/생채/샐러드', '시금치');
  assert.deepStrictEqual(P.plan([namul], 1).slots.map(s => s.dishes.length), [0, 1, 0]);
  const moved = Object.assign({}, dish('갈비찜', '찜', '갈비'), { when: 'fresh' });
  assert.deepStrictEqual(P.plan([moved], 1).slots.map(s => s.dishes.length), [0, 0, 1]);
  const a = Object.assign({}, dish('a', '조림', 'x'), { min: 20 }), b = Object.assign({}, dish('b', '찜', 'y'), { min: 80 });
  assert.deepStrictEqual(P.plan([a, b], 1).slots[0].dishes.map(d => d.name), ['b', 'a']);
  // 며칠 모드에서는 when을 안 본다 — 국 둘이 when:'day'여도 이웃하지 않는다
  const s1 = Object.assign({}, dish('된장국', '국', '감자'), { when: 'day' }), s2 = Object.assign({}, dish('미역국', '국', '미역'), { when: 'day' });
  const r = P.plan([s1, s2, dish('볶음', '볶음', '양파')], 3);
  const sd = r.days.filter(d => d.dishes.some(x => x.kind === '국')).map(d => d.i);
  assert.strictEqual(Math.abs(sd[0] - sd[1]), 2, 'soup days ' + sd);
}
// 장보기 한 번에 — trips=[1]. 배치는 그대로라 새우 요리는 앞쪽 날에 남는다.
{
  const ds = [dish('새우볶음', '볶음', '새우'), dish('새우전', '부침', '새우'), dish('감자조림', '조림', '감자'),
              dish('무국', '국', '무'), dish('당근밥', '밥', '당근')];
  const r = P.plan(ds, 5, { once: true });
  assert.deepStrictEqual(r.trips, [1]);
  assert.deepStrictEqual(r.days.map(d => d.trip), [true, false, false, false, false]);
  const shrimp = r.days.filter(d => d.dishes.some(x => x.name.startsWith('새우'))).map(d => d.i);
  assert.ok(Math.max(...shrimp) <= 3, 'shrimp days ' + shrimp);
}
// 전날 밑작업
{
  const r = P.plan([dish('조림', '조림', '무', '가지'), dish('국', '국', '가지')], 1);
  assert.strictEqual(r.prep.length, 1);
  assert.strictEqual(r.prep[0].day, 0);
  assert.ok(r.prep[0].text.startsWith('가지는 전날'), r.prep[0].text);
}
// 잔재료(대파·마늘)만 겹치면 밑작업이 비고, 가지가 겹치면 남는다
{
  assert.strictEqual(P.plan([dish('a', '볶음', '대파', '마늘', 'x'), dish('b', '국', '대파', '다진마늘', 'y')], 2).prep.length, 0);
  assert.strictEqual(P.plan([dish('조림', '조림', '대파'), dish('국', '국', '대파')], 1).prep.length, 0);
  // 잔재료는 밑작업에서만 빠진다. 배치 점수에는 남아 대파를 같이 쓰는 둘이 이웃한 날에 온다.
  {
    const r = P.plan([dish('a', '볶음', '대파', 'p'), dish('b', '찜', 'q'), dish('c', '조림', 'r'), dish('d', '구이', '대파', 's')], 4);
    const day = n => r.days.findIndex(d => d.dishes.some(x => x.name === n));
    assert.strictEqual(Math.abs(day('a') - day('d')), 1, JSON.stringify(r.days.map(d => d.dishes.map(x => x.name))));
    assert.strictEqual(r.prep.length, 0);
  }
  const r = P.plan([dish('a', '볶음', '가지', '대파'), dish('b', '국', '가지', '마늘')], 2);
  assert.strictEqual(r.prep.length, 1);
  assert.ok(/^가지 손질할 때/.test(r.prep[0].text), r.prep[0].text);
}
// 국 2 + 볶음 2 + 구이 1, 5일 → 국이 이웃하지 않는다
{
  const r = P.plan([dish('된장국', '국', '감자'), dish('미역국', '국', '미역'), dish('볶음1', '볶음', '양파'),
                    dish('볶음2', '볶음', '당근'), dish('구이', '구이', '김')], 5);
  assert.strictEqual(r.mode, 'days');
  const soupDays = r.days.filter(d => d.dishes.some(x => x.kind === '국')).map(d => d.i);
  assert.strictEqual(soupDays.length, 2);
  assert.ok(Math.abs(soupDays[0] - soupDays[1]) >= 2, 'soup days: ' + soupDays);
  assert.deepStrictEqual(r.days.map(d => d.dishes.length), [1, 1, 1, 1, 1]);
}
// 새우 요리 하나 + 오래가는 것 4개 → 새우 요리가 1~3일, 장보기 한 번
{
  const r = P.plan([dish('감자조림', '조림', '감자'), dish('양파볶음', '볶음', '양파'), dish('새우볶음', '볶음', '새우'),
                    dish('무국', '국', '무'), dish('당근밥', '밥', '당근')], 5);
  const shrimp = r.days.find(d => d.dishes.some(x => x.name === '새우볶음')).i;
  assert.ok(shrimp <= 3, 'shrimp day ' + shrimp);
  assert.deepStrictEqual(r.trips, [1]);
}
// 새우 요리 2개 + 오래가는 것 3개 → 장보기 2번 이하
{
  const r = P.plan([dish('새우볶음', '볶음', '새우'), dish('새우전', '부침', '새우'), dish('감자조림', '조림', '감자'),
                    dish('무국', '국', '무'), dish('당근밥', '밥', '당근')], 5);
  assert.ok(r.trips.length <= 2, 'trips ' + r.trips);
}
// 고르게 나눈다 — 7개 5일 = 2·2·1·1·1, 3개 5일 = 1·1·1·0·0
{
  const seven = Array.from({ length: 7 }, (_, i) => dish('d' + i, '볶음', 'x' + i));
  assert.deepStrictEqual(P.plan(seven, 5).days.map(d => d.dishes.length), [2, 2, 1, 1, 1]);
  assert.deepStrictEqual(P.plan(seven.slice(0, 3), 5).days.map(d => d.dishes.length), [1, 1, 1, 0, 0]);
}
// 겹치는 재료는 이웃한 날 + 밑작업 한 줄
{
  const r = P.plan([dish('a', '볶음', '가지', 'x'), dish('b', '국', 'y'), dish('c', '찜', 'z'), dish('d', '볶음', '가지', 'w')], 4);
  const da = r.days.find(d => d.dishes.some(x => x.name === 'a')).i, dd = r.days.find(d => d.dishes.some(x => x.name === 'd')).i;
  assert.strictEqual(Math.abs(da - dd), 1);
  assert.strictEqual(r.prep.length, 1);
  assert.ok(/가지 손질할 때 내일 [ad] 것도 같이/.test(r.prep[0].text), r.prep[0].text);
}
// 8개 이상 — 표본 탐색이 끝나고 결정적이다
{
  const nine = Array.from({ length: 9 }, (_, i) => dish('d' + i, i % 3 ? '볶음' : '국', 'x' + i));
  const a = P.plan(nine, 5), b = P.plan(nine, 5);
  assert.deepStrictEqual(a.days.map(d => d.dishes.map(x => x.name)), b.days.map(d => d.dishes.map(x => x.name)));
  assert.strictEqual(a.days.reduce((s, d) => s + d.dishes.length, 0), 9);
}
// perish
assert.strictEqual(P.perish('새우'), 1);
assert.strictEqual(P.perish('미역'), 30);
assert.strictEqual(P.perish('두부'), 1);
assert.strictEqual(P.perish('양파'), 30);
assert.strictEqual(P.perish('가지'), 7);
assert.strictEqual(P.perish('쇠고기'), 7);
assert.strictEqual(P.perish('김치'), 30);

// 설명란
{
  const r = P.parseDesc(`맛있는 김치찌개
0:00 인트로
1:20 재료 손질
12:05 - 끓이기

[재료]
돼지고기 300g
대파 1대
- 간장 2큰술

[만드는 법]
1. 고기를 볶는다`);
  assert.strictEqual(r.chapters.length, 3);
  assert.deepStrictEqual(r.chapters.map(c => c.t), [0, 80, 725]);
  assert.strictEqual(r.chapters[2].label, '끓이기');
  assert.deepStrictEqual(r.ing.map(i => [i.n, i.v, i.u]), [['돼지고기', 300, 'g'], ['대파', 1, '대'], ['간장', 30, 'ml']]);
  assert.ok(r.ing.every(i => i.b === 1));
  assert.deepStrictEqual(P.parseDesc('그냥 설명').ing, []);
  assert.deepStrictEqual(P.parseDesc('재료: 소면 1 봉').ing.map(i => [i.n, i.v, i.u]), [['소면', 1, '봉']]);   // 헤더 줄에 달린 재료도 읽는다
  assert.deepStrictEqual(P.parseDesc('재료\n다진마늘 1 큰술\n두부:1모').ing.map(i => [i.n, i.v, i.u]), [['다진마늘', 15, 'ml'], ['두부', 1, '모']]);
}
// 수량 — 한글 수사 · 근 · 새 단위 · 모호한 말
assert.deepStrictEqual(P.parseQty('한 근'), [600, 'g']);
assert.deepStrictEqual(P.parseQty('반 모'), [0.5, '모']);
assert.deepStrictEqual(P.parseQty('두세 개'), [3, '개']);
assert.deepStrictEqual(P.parseQty('한두개'), [2, '개']);
assert.deepStrictEqual(P.parseQty('세컵'), [600, 'ml']);
assert.deepStrictEqual(P.parseQty('1묶음'), [1, '묶음']);
assert.deepStrictEqual(P.parseQty('2팩'), [2, '팩']);
assert.strictEqual(P.parseQty('적당히'), null);
assert.strictEqual(P.parseQty('넉넉히'), null);
assert.strictEqual(P.parseQty('두부'), null);       // `두`를 2로 읽지 않는다
// 설명란 — 가운뎃점·쉼표 한 줄, `재료 : …` 한 줄, 괄호, 분수의 `/`는 안 자른다
assert.deepStrictEqual(P.parseDesc('재료\n돼지고기 300g · 양파 1개 · 두부 1/2모').ing.map(i => [i.n, i.v, i.u]),
  [['돼지고기', 300, 'g'], ['양파', 1, '개'], ['두부', 0.5, '모']]);
assert.deepStrictEqual(P.parseDesc('재료 : 돼지고기 300g, 양파 1개').ing.map(i => [i.n, i.v, i.u]), [['돼지고기', 300, 'g'], ['양파', 1, '개']]);
assert.deepStrictEqual(P.parseDesc('재료 (2인분 기준)\n소금, 후추 약간\n순두부 한 모').ing.map(i => [i.n, i.v, i.u]),
  [['소금, 후추 약간', undefined, undefined], ['순두부', 1, '모']]);   // 모호한 양은 이름에 남는다(기존 규칙)
assert.deepStrictEqual(P.splitLine('대파 1대(흰 부분)'), { n: '대파', q: '1대', v: 1, u: '대', b: 1 });
assert.deepStrictEqual(P.parseQty('1과1/2큰술'), [22.5, 'ml']);
// 장볼 양은 올림 — 20ml를 1큰술(15ml)로 내보내면 모자란다
assert.strictEqual(P.fmt(20, 'ml'), '2큰술'); assert.strictEqual(P.fmt(15, 'ml'), '1큰술'); assert.strictEqual(P.fmt(5, 'ml'), '1큰술');
assert.deepStrictEqual(P.parseQty('3~4개'), [4, '개']);
assert.strictEqual(P.parseQty('적당량'), null);
assert.deepStrictEqual(P.parseQty('200g'), [200, 'g']);
assert.deepStrictEqual(P.parseQty('1/2모'), [0.5, '모']);
assert.deepStrictEqual(P.parseQty('2'), [2, '개']);
assert.strictEqual(P.fmt(3.4, '개'), '4개');
assert.strictEqual(P.fmt(230, 'ml'), '1.5컵');
assert.strictEqual(P.fmt(1234, 'g'), '1.3kg');

// URL
assert.strictEqual(P.ytId('https://youtu.be/dQw4w9WgXcQ?t=3'), 'dQw4w9WgXcQ');
assert.strictEqual(P.ytId('https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx'), 'dQw4w9WgXcQ');
assert.strictEqual(P.ytId('https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
assert.strictEqual(P.ytId('https://youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
assert.strictEqual(P.ytId('https://www.youtube.com/live/dQw4w9WgXcQ?si=1'), 'dQw4w9WgXcQ');
assert.strictEqual(P.ytId('https://example.com/'), null);
assert.strictEqual(P.ytList('https://www.youtube.com/playlist?list=PLabc_123-x'), 'PLabc_123-x');
assert.strictEqual(P.ytList('https://youtu.be/dQw4w9WgXcQ'), null);

// 합산 — 같은 재료 두 요리 → used 2, 수량 합산 + 인분 환산
{
  const a = { name: 'A', servings: 2, ing: [{ n: '대파', v: 1, u: '대', b: 1 }, { n: '소금', v: 5, u: 'ml' }] };
  const b = { name: 'B', servings: 4, ing: [{ n: '대파', v: 2, u: '대', b: 1 }, { n: '새우', v: 200, u: 'g', b: 1 }] };
  const r = P.aggregate([a, b], 4);
  assert.strictEqual(r.buyCount, 2);            // 소금은 b가 없어 빠진다
  const pa = r.groups.flatMap(g => g.items).find(i => i.name === '대파');
  assert.strictEqual(pa.used, 2);
  assert.strictEqual(pa.value, 4);               // 1×(4/2) + 2×(4/4)
  assert.strictEqual(pa.qty, '4대');
  assert.deepStrictEqual(r.groups.map(g => g.cat), ['수산 · 건해산', '채소 · 두부']);
  assert.deepStrictEqual(r.overlaps, [{ name: '대파', used: 2, where: ['A', 'B'] }]);
  assert.deepStrictEqual(pa.by, [{ dish: 'A', v: 2, u: '대', q: '조금' }, { dish: 'B', v: 2, u: '대', q: '조금' }]);   // 요리별 환산량
  assert.deepStrictEqual(r.groups[0].items[0].by, [{ dish: 'B', v: 200, u: 'g', q: '조금' }]);
  // 요리별은 올림 전 원값이라 합이 헤더(올림)와 다를 수 있다 — 12g+13g → 헤더 30g
  { const x = P.aggregate([{ name: 'A', servings: 2, ing: [{ n: '무', v: 12, u: 'g', b: 1 }] }, { name: 'B', servings: 2, ing: [{ n: '무', v: 13, u: 'g', b: 1 }] }], 2).groups[0].items[0];
    assert.strictEqual(x.qty, '30g'); assert.deepStrictEqual(x.by.map(b => b.v), [12, 13]); }
  const shrimp = r.groups[0].items[0];
  assert.strictEqual(shrimp.qty, '200g');
}
console.log('OK — plan.js 검사 전부 통과');
