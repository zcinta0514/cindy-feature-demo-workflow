// Render the approved HTML itself, without rebuilding its UI or camera.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import assert from 'node:assert/strict';

const options={};for(let i=2;i<process.argv.length;i++){const v=process.argv[i];if(v.startsWith('--'))options[v.slice(2)]=(!process.argv[i+1]||process.argv[i+1].startsWith('--'))?true:process.argv[++i];}
const project=path.resolve(options.project||'.'),entry=path.resolve(options.entry||path.join(project,'production-library/previews/original-workflow-4x3-v6/index.html'));
const output=path.resolve(options.output||path.join(project,'output/plan-4x3'));
const compare=options.compare&&path.resolve(options.compare),render=!!options.render;
const req=createRequire(path.join(project,'package.json'));
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(project,'.browsers');
const {chromium}=req('playwright');
const sha=b=>createHash('sha256').update(b).digest('hex');
await fs.mkdir(output,{recursive:true});
const receipt=path.join(output,'replay.json');
try{await fs.access(receipt);throw Error('输出目录已有验收记录，请换目录');}catch(e){if(e.code!=='ENOENT')throw e;}
const servers=[];const contexts=[];
const browserArgs=['--hide-scrollbars','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows','--force-color-profile=srgb'];
// CPU compositing makes the 1440px comparison insensitive to transient GPU raster caches.
// Production retains the normal compositor, as used for the shipped 4K reference.
if(!render)browserArgs.push('--run-all-compositor-stages-before-draw','--disable-gpu');
const browser=await chromium.launch({channel:'chromium',headless:true,args:browserArgs});
const mimes={'.html':'text/html; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff2':'font/woff2','.woff':'font/woff','.png':'image/png','.jpg':'image/jpeg','.wav':'audio/wav','.m4a':'audio/mp4'};
async function server(file){
 const root=path.dirname(file),s=http.createServer(async(req,res)=>{try{const n=decodeURIComponent(new URL(req.url,'http://localhost').pathname);const p=path.resolve(root,'.'+n);if(!p.startsWith(root+path.sep))throw Error('path');const b=await fs.readFile(p);res.writeHead(200,{'Content-Type':mimes[path.extname(p)]||'application/octet-stream'});res.end(b);}catch{res.writeHead(404);res.end();}});
 await new Promise(r=>s.listen(0,'127.0.0.1',r));servers.push(s);return `http://127.0.0.1:${s.address().port}/${path.basename(file)}`;
}
async function prepare(file){
 const url=await server(file),origin=new URL(url).origin;
 const ctx=await browser.newContext({viewport:{width:1440,height:1080},deviceScaleFactor:render?8/3:1,locale:'en-US',timezoneId:'UTC',colorScheme:'light'});contexts.push(ctx);
 const errors=[],failed=[];await ctx.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push(r.url());});
 await page.clock.install({time:new Date('2026-11-06T00:00:00Z')});
 await page.addInitScript(()=>{let seed=123456;Math.random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);});
 await page.goto(url,{waitUntil:'load'});await page.waitForFunction(()=>window.__visualPreview?.ready,{},{timeout:60000});
 await page.evaluate(()=>document.fonts.ready);
 await page.addStyleTag({content:'.review-toolbar{display:none!important}html,body{margin:0;width:1440px!important;height:1080px!important;overflow:hidden!important}#screen{width:1440px!important;height:1080px!important;max-width:none!important;margin:0!important}*{caret-animation:manual!important}'});
 await page.clock.pauseAt(new Date('2026-11-06T00:01:00Z'));
 await page.evaluate(()=>{
   window.__portableFrame=0;window.__portableCues=[];window.__portableAnimations=new Map();
   document.addEventListener('keydown',e=>{if(e.key.length===1&&e.target.closest('.ProseMirror,textarea'))__portableCues.push({kind:'key',frame:__portableFrame,time:__portableFrame/60});},true);
   document.addEventListener('pointerup',e=>{if(e.target.closest('#root'))__portableCues.push({kind:'click',frame:__portableFrame,time:__portableFrame/60});},true);
   window.__visualPreview.play();
 });
 return {page,errors,failed};
}
async function step(item,f){
 await item.page.evaluate(f=>window.__portableFrame=f,f);
 await item.page.clock.runFor(Math.round((f+1)*1000/60)-Math.round(f*1000/60));
 return item.page.evaluate(async()=>{
   for(let i=0;i<8;i++)await new Promise(resolve=>{const c=new MessageChannel();c.port1.onmessage=()=>{c.port1.close();c.port2.close();resolve();};c.port2.postMessage(0);});
   const now=performance.now();for(const a of document.getAnimations()){let start=__portableAnimations.get(a);if(start===undefined){start=now;__portableAnimations.set(a,start);a.pause();}a.currentTime=Math.max(0,now-start);}
   const v=__visualPreview.getState(),s=v.state,c=document.querySelector('.preview-cursor')?.getBoundingClientRect();
   return {index:s.index,key:s.key,complete:s.complete,error:s.error,playing:v.playing,time:v.time,exit:v.exit,pose:v.camera?.pose,cursor:c?{x:c.x,y:c.y,right:c.right,bottom:c.bottom}:null};
 });
}
let encoder,encodeDone;let stderr='';
try{
 const primary=await prepare(entry),reference=compare?await prepare(compare):null;
 const result={version:2,entry:'plan-4x3',browser:browser.version(),platform:process.platform,arch:process.arch,fps:60,width:render?3840:1440,height:render?2880:1080,mode:render?'full-render':'full-replay',comparison:compare?'source-vs-restored':'not-requested',samples:[],transitions:[],frames:0,errors:[],checks:{},subjectiveViewing:'not-performed',audioListening:'not-performed'};
 if(render){
  const video=path.join(output,'silent-master.mp4');
  encoder=spawn('ffmpeg',['-n','-v','error','-f','image2pipe','-framerate','60','-vcodec','mjpeg','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-vf','setsar=1','-movflags','+faststart',video],{stdio:['pipe','ignore','pipe']});
  encoder.stderr.on('data',b=>stderr+=b);encoder.stdin.on('error',()=>{});
  encodeDone=new Promise((resolve,reject)=>{encoder.on('error',reject);encoder.on('close',c=>c===0?resolve():reject(Error(stderr)));});encodeDone.catch(()=>{});
 }
 let previous=-100,last,seen=new Set();
 const maxFrames=Number(options['max-frames']||18000);
 for(let f=0;f<maxFrames;f++){
  const s=await step(primary,f);last=s;if(s.error)throw Error(s.error);
  const other=reference?await step(reference,f):null;
  if(other){assert.equal(s.index,other.index,'操作时间线不一致，frame='+f);assert.equal(s.key,other.key);assert.equal(s.complete,other.complete);}
  const changed=s.index!==previous;
  if(changed){result.transitions.push({frame:f,...s});previous=s.index;}
  const sample=(changed||f%600===0||f===120||(!s.playing&&s.complete));
  if(sample){
   // Flush the compositing surface at the same frozen time before measuring it.
   if(reference){await primary.page.screenshot({type:'png',caret:'initial'});await reference.page.screenshot({type:'png',caret:'initial'});}
   const png=await primary.page.screenshot({type:'png',caret:'initial'}),sample={frame:f,index:s.index,key:s.key,sha256:sha(png),pose:s.pose,referencePose:other?.pose};
   await fs.writeFile(path.join(output,`frame-${String(f).padStart(5,'0')}.png`),png);
   if(reference){const ref=await reference.page.screenshot({type:'png',caret:'initial'});sample.referenceSha256=sha(ref);sample.identical=sample.sha256===sample.referenceSha256;
    if(!sample.identical){
     sample.pixelDifference=await primary.page.evaluate(async({a,b})=>{
      const decode=async v=>createImageBitmap(await (await fetch('data:image/png;base64,'+v)).blob());
      const ia=await decode(a),ib=await decode(b),canvas=new OffscreenCanvas(ia.width,ia.height),ctx=canvas.getContext('2d');
      ctx.drawImage(ia,0,0);const x=ctx.getImageData(0,0,ia.width,ia.height).data;ctx.clearRect(0,0,ia.width,ia.height);ctx.drawImage(ib,0,0);const y=ctx.getImageData(0,0,ib.width,ib.height).data;
      let changed=0,max=0,sum=0;for(let i=0;i<x.length;i+=4){let pixel=0;for(let c=0;c<3;c++){const d=Math.abs(x[i+c]-y[i+c]);sum+=d;max=Math.max(max,d);pixel=Math.max(pixel,d);}if(pixel)changed++;}
      return {changedPixels:changed,changedRatio:changed/(ia.width*ia.height),maxChannelDelta:max,meanChannelDelta:sum/(ia.width*ia.height*3)};
     },{a:png.toString('base64'),b:ref.toString('base64')});
     const d=sample.pixelDifference;sample.withinTolerance=d.maxChannelDelta<=8&&d.changedRatio<=.0001&&d.meanChannelDelta<=.001;
     await fs.writeFile(path.join(output,`reference-${f}.png`),ref);
     if(!sample.withinTolerance){await fs.writeFile(path.join(output,'failed-sample.json'),JSON.stringify(sample,null,2));throw Error('像素差异超过抗锯齿容差，frame='+f+' '+JSON.stringify(d));}
    }
    const texts=await Promise.all([primary.page,reference.page].map(p=>p.locator('#root').innerText()));assert.equal(texts[0],texts[1],'原生组件文字不同');
   }
   result.samples.push(sample);
  }
  if(render){const jpg=await primary.page.screenshot({type:'jpeg',quality:95,caret:'initial',scale:'device'});seen.add(sha(jpg));if(!encoder.stdin.write(jpg))await once(encoder.stdin,'drain');}
  result.frames=f+1;
  if(f%300===0){console.log(JSON.stringify({frame:f,index:s.index,key:s.key,time:s.time}));await fs.writeFile(path.join(output,'progress.json'),JSON.stringify({frame:f,...s}));}
  if(primary.errors.length||primary.failed.length)throw Error(JSON.stringify({errors:primary.errors,failed:primary.failed}));
  if(!s.playing&&s.complete)break;
 }
 assert(last.complete&&!last.playing,'重演未完成');
 if(encoder){encoder.stdin.end();await encodeDone;}
 const cues=await primary.page.evaluate(()=>window.__portableCues);await fs.writeFile(path.join(output,'audio-cues.json'),JSON.stringify(cues,null,2));
 result.last=last;result.uniqueFrames=seen.size;result.audioCues=cues.length;result.checks.complete=true;result.checks.resourceErrors=primary.failed;result.checks.pageErrors=primary.errors;result.checks.allSamplePixelsIdentical=reference?result.samples.every(x=>x.identical):null;result.checks.allSamplesWithinTolerance=reference?result.samples.every(x=>x.identical||x.withinTolerance):null;result.pixelTolerance={maxChannelDelta:8,maxChangedRatio:.0001,maxMeanChannelDelta:.001,reason:'容许极小面积的浏览器合成/边缘抗锯齿差异；每帧操作状态与抽查可见文字仍须完全一致。不是逐像素无差别保证。'};
 result.duration=result.frames/60;result.status='passed';
 await fs.writeFile(receipt,JSON.stringify(result,null,2));console.log(JSON.stringify({status:'passed',frames:result.frames,duration:result.duration,samples:result.samples.length,comparison:result.checks.allSamplePixelsIdentical}));
}catch(e){encoder?.kill();await fs.writeFile(path.join(output,'failure.json'),JSON.stringify({error:e.stack,ffmpeg:stderr},null,2));throw e;}
finally{await browser.close();await Promise.all(servers.map(s=>new Promise(r=>s.close(r))));}
