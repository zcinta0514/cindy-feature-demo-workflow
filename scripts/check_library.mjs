// Offline loading smoke checks; this is not full-film acceptance.
import fs from 'node:fs/promises';import path from 'node:path';import http from 'node:http';import {createRequire} from 'node:module';
const project=path.resolve(process.argv[2]),root=path.join(project,'production-library');
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(project,'.browsers');
const {chromium}=createRequire(path.join(project,'package.json'))('playwright');
const catalog=JSON.parse(await fs.readFile(path.join(root,'catalog.json')));
const browser=await chromium.launch({channel:'chromium',headless:true});const results=[];
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2','.woff':'font/woff','.wav':'audio/wav','.m4a':'audio/mp4'};
const playback=process.argv.includes('--playback');
try{for(const item of catalog.cases){
 if(playback&&!item.id.startsWith('collaboration-'))continue;
 const base=path.dirname(path.join(root,item.entry));
 const server=http.createServer(async(req,res)=>{try{const sub=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(sub==='/favicon.ico'){res.writeHead(204);res.end();return;}const file=path.resolve(base,'.'+sub);if(!file.startsWith(base+path.sep))throw Error('outside root');res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});res.end(await fs.readFile(file));}catch{res.statusCode=404;res.end('not found');}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin=`http://127.0.0.1:${server.address().port}`;
 const ctx=await browser.newContext({viewport:{width:1440,height:1080},locale:item.language==='zh-CN'?'zh-CN':'en-US'});const errors=[],missing=[],blocked=[];
 await ctx.route('**/*',route=>{if(new URL(route.request().url()).origin===origin)return route.continue();blocked.push(route.request().url());return route.abort();});
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)missing.push(new URL(r.url()).pathname);});
 if(playback)await page.clock.install({time:new Date('2026-11-06T00:00:00Z')});
 let ready=false,reason;
 try{await page.goto(origin+'/'+path.basename(item.entry),{waitUntil:'load'});await page.waitForFunction(id=>/^(plan|collaboration|visuals)/.test(id)?window.__visualPreview?.ready:window.__iosDemo?.ready||window.__uiPage?.ready||window.__p54?.store||window.__showcase?.ready,item.id,{timeout:20000});await page.evaluate(()=>document.fonts.ready);ready=true;}catch(e){reason=e.message;}
 let replay;
 if(playback&&ready){
  await page.clock.pauseAt(new Date('2026-11-06T00:01:00Z'));await page.evaluate(()=>window.__visualPreview.play());
  for(let i=0;i<3600;i++){await page.clock.runFor(100);replay=await page.evaluate(()=>{const v=window.__visualPreview.getState();return{index:v.state.index,complete:v.state.complete,error:v.state.error,playing:v.playing,time:v.time};});if(replay.error||(!replay.playing&&replay.complete))break;}
  if(replay.error||!replay.complete)errors.push('回放失败：'+JSON.stringify(replay));
 }
 const screenshot=path.join(project,'evidence','library-'+item.id+'.png');await page.screenshot({path:screenshot});
 const state=await page.evaluate(()=>({textLength:document.body.innerText.length,preview:!!window.__preview,visual:!!window.__visualPreview,ios:!!window.__iosDemo,host:!!window.__p54}));
 results.push({id:item.id,ready,errors,missing,blocked,state,reason,replay,status:ready&&!errors.length&&!missing.length&&!blocked.length?'passed':'failed',scope:playback?'full interactive playback; not encoded-film or subjective acceptance':'load/fonts/local-resources only; not full replay or subjective acceptance'});
 console.log(JSON.stringify(results.at(-1)));await ctx.close();await new Promise(r=>server.close(r));
 }}finally{await browser.close();}
await fs.writeFile(path.join(project,'evidence',playback?'collaboration-playback.json':'library-load.json'),JSON.stringify(results,null,2));if(results.some(r=>r.status!=='passed'))process.exitCode=1;
