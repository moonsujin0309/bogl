// Foreground browser regression run; server and browser always close in finally.
// NODE_PATH can point to the desktop's bundled playwright. No app dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const root = __dirname;
const fixture = {id:'abcdefghijk', snippet:{title:'테스트 두부조림',channelTitle:'테스트 주방',description:'재료\n두부 1모\n양파 1개\n간장 2큰술\n\n00:00 재료 준비\n01:00 볶기\n02:30 완성'}};
const mockPlayer = `window.YT={Player:class {constructor(id,options){this.el=document.getElementById(id);this.options=options;this.time=Number(new URL(this.el.src).searchParams.get('start'))||0;this.state=2;window.testPlayer=this;setTimeout(()=>options.events.onReady({target:this}),10);} getIframe(){return this.el} getCurrentTime(){return this.time} getPlayerState(){return this.state} seekTo(t){this.time=t} playVideo(){this.state=1;this.options.events.onStateChange({data:1,target:this})} pauseVideo(){this.state=2;this.options.events.onStateChange({data:2,target:this})} destroy(){this.el.remove()} }};window.onYouTubeIframeAPIReady();`;
const server = http.createServer((req,res) => {
  const relative = decodeURIComponent(new URL(req.url,'http://localhost').pathname).slice(1) || 'index.html';
  const file = path.resolve(root,relative);
  if(!file.startsWith(root + path.sep)){res.writeHead(403);return res.end();}
  try{ const content = fs.readFileSync(file); const ext = path.extname(file);
    res.setHeader('Content-Type',({'.html':'text/html; charset=utf-8','.js':'application/javascript','.png':'image/png','.jpg':'image/jpeg','.webmanifest':'application/manifest+json'})[ext] || 'text/plain');res.end(content);
  }catch(e){res.writeHead(404);res.end();}
});
let browser;
const watchdog = setTimeout(() => { console.error('FAIL: browser tests exceeded 90 seconds'); process.exit(1); },90000);
(async () => {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  browser = await chromium.launch({headless:true,channel:'msedge'});
  const context = await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1});
  const page = await context.newPage(), errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://www.googleapis.com/youtube/v3/**',route=>route.fulfill({json:{items:[fixture]}}));
  await page.route('https://www.youtube.com/iframe_api',route=>route.fulfill({contentType:'application/javascript',body:mockPlayer}));
  await page.route('https://www.youtube-nocookie.com/**',route=>route.fulfill({contentType:'text/html',body:'<body style="margin:0;background:#171614;color:#eee;display:grid;place-items:center;height:100vh;font:16px sans-serif">YouTube · 테스트 플레이어</body>'}));
  const base=`http://127.0.0.1:${server.address().port}/`;
  await page.goto(base); await page.locator('#ytbtn').waitFor();
  assert.equal(await page.evaluate(()=>fmtR(5,'ml')),'1작은술');
  assert.equal(await page.evaluate(()=>fmtR(0.25,'모')),'0.25모');
  assert.equal(await page.locator('#finder').isVisible(),true,'new visitors start by finding a dish');
  assert.equal(await page.locator('#mp').isVisible(),false,'no plan before a recipe');
  assert.equal(await page.locator('#findgo .youtube-mark').count(),1);
  assert.equal(await page.locator('#dishideas a').count(),6);
  assert.equal(await page.locator('#dishideas .menu-photo').count(),6);
  await page.waitForFunction(()=>[...document.querySelectorAll('#dishideas .menu-photo')].filter(i=>i.loading==='eager').every(i=>i.complete&&i.naturalWidth>0));
  assert.equal(await page.evaluate(()=>new Set([...document.querySelectorAll('#dishideas .menu-photo')].map(i=>i.src)).size),6,'six distinct food photos, no repeated drawing');
  assert.equal(await page.locator('[data-dish-search="알리오 올리오 파스타"]').count(),1);
  assert.ok(await page.evaluate(()=>document.getElementById('dishideas').getBoundingClientRect().top<document.getElementById('findquery').getBoundingClientRect().top),'concrete menu choices come before open search');
  for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`discovery no overflow at ${width}`);}
  assert.ok(await page.evaluate(()=>document.getElementById('homehero').getBoundingClientRect().right<=document.getElementById('finder').getBoundingClientRect().left+1),'desktop title sits beside menu');
  await page.click('#previewtoggle');
  assert.ok(await page.evaluate(()=>document.querySelector('.app').getBoundingClientRect().width<=391),'local mobile preview uses 390px app container');
  assert.ok(await page.evaluate(()=>document.getElementById('homehero').getBoundingClientRect().bottom<=document.getElementById('finder').getBoundingClientRect().top+1),'preview uses actual mobile stacking');
  await page.click('#previewtoggle');
  if(process.env.BOGL_QA_DIR){fs.mkdirSync(process.env.BOGL_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BOGL_QA_DIR,'discover-desktop.png'),fullPage:true});}
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>[...document.querySelectorAll('#dishideas .menu-photo')].filter(i=>i.getBoundingClientRect().top<innerHeight).every(i=>i.complete&&i.naturalWidth>0));
  if(process.env.BOGL_QA_DIR) await page.screenshot({path:path.join(process.env.BOGL_QA_DIR,'discover-mobile-first.png'),fullPage:false});
  if(process.env.BOGL_QA_DIR){fs.mkdirSync(process.env.BOGL_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BOGL_QA_DIR,'discover-mobile.png'),fullPage:true});}
  assert.ok(await page.evaluate(()=>document.querySelector('#dishideas .menu-photo').getBoundingClientRect().bottom<innerHeight),'first food photo fully visible without scrolling on mobile');
  await page.click('#findprefs summary');await page.click('[data-value="간단하게"]');await page.click('[data-value="한 그릇"]');
  await page.fill('#findquery','두부 & 계란');
  assert.equal(await page.locator('#findterms').inputValue(),'두부 & 계란 레시피 간단하게 한 그릇');
  assert.match(await page.locator('#dishideas a').first().getAttribute('href'),/search_query=/);
  await context.route('https://www.youtube.com/results?**',route=>route.fulfill({contentType:'text/html',body:'Search destination test'}));
  const popupPromise=context.waitForEvent('page');await page.locator('#findquery').press('Enter');const popup=await popupPromise;await popup.waitForLoadState();
  assert.equal(new URL(popup.url()).searchParams.get('search_query'),'두부 & 계란 레시피 간단하게 한 그릇');await popup.close();
  await page.reload();assert.equal(await page.locator('#prefsummary').textContent(),'간단하게 · 한 그릇');
  assert.match(await page.locator('#findreturntext').textContent(),/링크 복사/);
  await page.click('#findprefs summary');await page.click('#prefreset');assert.equal(await page.locator('#findterms').inputValue(),'요리 레시피');
  await page.click('[data-cuisine="양식"]');assert.equal(await page.locator('[data-dish-search="김치찌개"]').count(),0);
  const menuPopupPromise=context.waitForEvent('page');await page.click('[data-dish-search="알리오 올리오 파스타"]');const menuPopup=await menuPopupPromise;await menuPopup.waitForLoadState();
  assert.equal(new URL(menuPopup.url()).searchParams.get('search_query'),'알리오 올리오 파스타 레시피');await menuPopup.close();
  await page.reload();assert.equal(await page.locator('[data-cuisine="양식"]').getAttribute('aria-pressed'),'true');
  await page.click('[data-cuisine="골고루"]');
  await page.click('[data-mode="video"]');assert.equal(await page.locator('.library-empty h2').textContent(),'아직 담은 영상이 없어요');
  await page.click('#emptyaction');await page.click('#cataloglink'); assert.equal(await page.locator('#grid .card').count(),74);
  await page.click('#ytbtn'); await page.fill('#lku','https://example.com/watch?v=abcdefghijk');await page.click('#lkgo');
  assert.match(await page.locator('#linkerror').textContent(),/유튜브/);
  await page.fill('#lku','https://youtube.com/watch?v=abcdefghijk&list=PLexample');await page.click('#lkgo');
  await page.locator('#yfgo').waitFor();
  assert.equal(await page.locator('#yfi').inputValue(),'두부 1모\n양파 1개\n간장 2큰술');
  await page.click('#yfgo'); await page.waitForFunction(()=>document.getElementById('back10')?.disabled===false);
  assert.equal(await page.locator('#recipe.on').count(),1); assert.equal(await page.locator('#ytf').count(),1);
  await page.evaluate(()=>window.originalFrame=document.getElementById('ytf'));
  await page.click('[data-ingredient="0"]');
  assert.equal(await page.locator('[data-ingredient="0"]').getAttribute('aria-pressed'),'true');
  await page.click('#servp'); assert.equal(await page.locator('#servn').textContent(),'3인분');
  await page.click('#rseg [data-t="step"]'); await page.click('.ch[data-t="60"]');
  assert.equal(await page.evaluate(()=>testPlayer.getCurrentTime()),60);
  await page.click('#back10'); assert.equal(await page.evaluate(()=>testPlayer.getCurrentTime()),50);
  await page.click('#rseg [data-t="ing"]');
  assert.equal(await page.evaluate(()=>originalFrame===document.getElementById('ytf')),true,'tab changes must retain player');
  await page.click('#rback'); assert.equal(await page.locator('#ytf').count(),0,'leaving recipe destroys player');
  assert.equal(await page.locator('#resume').isVisible(),true);
  await page.reload(); await page.click('#resume'); await page.waitForFunction(()=>window.testPlayer);
  assert.equal(await page.evaluate(()=>testPlayer.getCurrentTime()),50);
  assert.equal(await page.locator('[data-ingredient="0"]').getAttribute('aria-pressed'),'true');
  await page.click('#redit'); await page.fill('#yfi','');await page.click('#yfgo');
  await page.click('#recipeplan'); assert.match(await page.locator('#missing').textContent(),/재료 미입력 영상 1개/);
  await page.click('#back'); await page.click('#pback');
  await page.click('#ytbtn'); await page.fill('#lku','https://youtu.be/abcdefghijk'); await page.click('#lkgo');
  assert.equal(await page.locator('#recipe.on').count(),1,'duplicate opens existing video');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('bogl.folders'))[0].dishes.length),1);
  await page.click('#finishcook'); assert.equal(await page.locator('#resume').isVisible(),false);
  await page.click('#ytbtn'); await page.keyboard.press('Escape'); assert.equal(await page.locator('#sheet').isVisible(),false);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'ytbtn');
  // Keyboard loop stays inside modal and body regains scroll after closing.
  await page.click('#ytbtn'); await page.keyboard.press('Shift+Tab');
  assert.equal(await page.evaluate(()=>document.getElementById('sheetbox').contains(document.activeElement)),true);
  await page.keyboard.press('Escape'); assert.equal(await page.evaluate(()=>document.querySelector('.app').inert),false);
  // No-key path still stores video before ingredients, metadata and chapter inputs are optional.
  await page.route(base,async route=>{const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/const YTKEY = '[^']*';/,"const YTKEY = '';"); await route.fulfill({contentType:'text/html; charset=utf-8',body:html});});
  await page.goto(base);await page.click('#ytbtn');await page.fill('#lku','https://youtu.be/zyxwvutsrqp');await page.click('#lkgo');
  await page.locator('#yfgo').waitFor(); await page.click('#yfgo');
  assert.equal(await page.locator('#rtitle').textContent(),'저장한 영상');
  await page.click('#redit');await page.fill('#yfdesc','재료\n달걀 2개\n소금 1g\n00:00 준비\n00:45 익히기');await page.click('#yfparse');await page.click('#yfgo');
  assert.equal(await page.locator('[data-ingredient]').count(),2);
  await page.click('#rseg [data-t="step"]');assert.equal(await page.locator('.ch').count(),2);
  // Save screenshots of actual app DOM with explicitly mocked test media.
  const out=process.env.BOGL_QA_DIR;
  if(out){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'recipe-mobile.png'),fullPage:true});}
  await page.click('#rback');
  for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`no overflow at ${width}`);}
  await page.setViewportSize({width:390,height:844});
  if(out) await page.screenshot({path:path.join(out,'library-mobile.png'),fullPage:true});
  // Reviewer regressions: duplicated videos share edited recipe, not readiness checks.
  await page.evaluate(()=>{const fs=JSON.parse(localStorage.getItem('bogl.folders'));const copy=JSON.parse(JSON.stringify(fs[0]));copy.id='duplicate-plan';fs.push(copy);localStorage.setItem('bogl.folders',JSON.stringify(fs));});
  await page.reload();await page.locator('[data-vid="zyxwvutsrqp"] [data-a="video"]').first().click();
  await page.click('#rseg [data-t="ing"]');await page.click('[data-ingredient="0"]');await page.click('#redit');await page.fill('#yfi','새 재료 1개');await page.click('#yfgo');
  assert.equal(await page.locator('[data-ingredient="0"]').getAttribute('aria-pressed'),'false');
  const copies=await page.evaluate(()=>JSON.parse(localStorage.getItem('bogl.folders')).flatMap(f=>f.dishes).filter(d=>d.vid==='zyxwvutsrqp'));
  assert.equal(copies.length,2);assert.ok(copies.every(d=>d.ing.length===1&&d.ing[0].n==='새 재료'));
  await page.click('#rback');await page.locator('[data-mode="discover"]').first().click();await page.click('#cataloglink');await page.locator('#grid .th').first().click();await page.click('#rseg [data-t="step"]');
  for(let i=0;i<30;i++){if(!await page.locator('#snext').isVisible())break;await page.click('#snext');}
  assert.equal(await page.locator('#home.on').count(),1);assert.equal(await page.locator('#resume').isVisible(),false);
  // Failed playlist import must not leave an empty folder; successful import creates one.
  await page.unroute(base);await page.route('https://www.googleapis.com/youtube/v3/**',route=>route.fulfill({status:403,json:{error:{code:403}}}));await page.goto(base);
  const before=await page.evaluate(()=>JSON.parse(localStorage.getItem('bogl.folders')).length);
  await page.click('#ytbtn');await page.fill('#lku','https://youtube.com/playlist?list=PLtest');await page.click('#lkgo');
  await page.waitForFunction(()=>document.getElementById('linkerror').textContent.includes('읽지 못'));
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('bogl.folders')).length),before);
  await page.route('https://www.googleapis.com/youtube/v3/**',route=>{const endpoint=new URL(route.request().url()).pathname;
    route.fulfill({json:{items:endpoint.endsWith('playlistItems')?[{snippet:{...fixture.snippet,resourceId:{videoId:'playlist123'},videoOwnerChannelTitle:'테스트 주방'}}]:[{snippet:{title:'테스트 재생목록'}}]}});});
  await page.click('#lkgo');await page.waitForFunction(()=>document.getElementById('home').classList.contains('on')&&!document.getElementById('sheet').classList.contains('on'));
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('bogl.folders')).length),before+1);
  await page.evaluate(()=>{const fs=JSON.parse(localStorage.getItem('bogl.folders'));fs[0].dishes.push({vid:'expired1234',name:'만료된 API 제목',ing:[{n:'API 재료'}],chapters:[{t:0,label:'시작'}],at:Date.now()-31*86400000});localStorage.setItem('bogl.folders',JSON.stringify(fs));});
  await page.reload();
  const stale=await page.evaluate(()=>JSON.parse(localStorage.getItem('bogl.folders'))[0].dishes.find(d=>d.vid==='expired1234'));
  assert.equal(stale.name,'저장한 영상');assert.equal(stale.ing.length,0);assert.equal(stale.chapters.length,0);
  assert.deepEqual(errors,[]);
  console.log('OK — browser flows: import, optional ingredients, playlist-video choice, checklist, servings, persistent player, chapter seek, rewind, reload resume, missing ingredients, deduplication, completion, dialog keyboard, no-key import, description parsing, 4 viewport widths; no page errors.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{clearTimeout(watchdog);if(browser)await browser.close();server.close();});
