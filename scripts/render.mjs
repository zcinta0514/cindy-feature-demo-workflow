// Offline media renderer: isolated Chromium, local assets, explicit 60fps scene API.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createHash} from 'node:crypto';
const opts=Object.fromEntries(process.argv.slice(2).reduce((pairs,v,i,a)=>{if(v.startsWith('--'))pairs.push([v.slice(2),a[i+1]]);return pairs;},[]));
const root=path.resolve(opts.project||'.');
const config=JSON.parse(await fs.readFile(path.join(root,'demo.config.json'),'utf8'));
const spec=config.videoDefaults;
if(spec.fps!==60||spec.width!==3840||spec.height!==2880)throw Error('此渲染入口要求3840×2880 / 60fps');
const entry=path.resolve(root,opts.entry||'scene/index.html'), output=path.resolve(root,opts.output||'output/silent.mp4');
const within=p=>p===root||p.startsWith(root+path.sep);
if(!within(entry)||!within(output))throw Error('入口和输出必须在本工程内');
await fs.access(entry);
try{await fs.access(output);throw Error('输出已存在，请使用新版本路径');}catch(e){if(e.code!=='ENOENT')throw e;}
await fs.mkdir(path.dirname(output),{recursive:true});
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'.browsers');
const {chromium}=createRequire(path.join(root,'package.json'))('playwright');
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff2':'font/woff2','.png':'image/png','.wav':'audio/wav'};
const server=http.createServer(async(req,res)=>{
  try{const p=await fs.realpath(path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname)));
    if(!within(p)){res.writeHead(403).end();return;}
    const bytes=await fs.readFile(p);res.writeHead(200,{'Content-Type':types[path.extname(p)]||'application/octet-stream','Cache-Control':'no-store'}).end(bytes);
  }catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin=`http://127.0.0.1:${server.address().port}`;
let browser,encoder,encoderDone,encoderFailure;const errors=[],blocked=[],missing=[];
const frames=[];let stderr='';const report={status:'pending',width:3840,height:2880,fps:60};
async function bounded(promise,label,ms=30000){
  let timer;
  try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+'超时')),ms);})]);}
  finally{clearTimeout(timer);}
}
try{
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:8/3});
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400)missing.push({url:new URL(r.url()).pathname,status:r.status()});});
  await page.route('**/*',route=>{
    const url=route.request().url();
    if(url.startsWith(origin+'/')||url.startsWith('data:')||url.startsWith('blob:'))return route.continue();
    blocked.push(url);return route.abort();
  });
  await page.goto(origin+'/'+path.relative(root,entry).split(path.sep).map(encodeURIComponent).join('/'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!window.__DEMO_EXPORT__,{},{timeout:30000});
  await bounded(page.evaluate(async()=>{await document.fonts.ready;await window.__DEMO_EXPORT__.ready;}),'页面与字体就绪');
  const count=await page.evaluate(()=>window.__DEMO_EXPORT__.frameCount);
  if(!Number.isInteger(count)||count<1||count>60*600)throw Error('frameCount须为1–36000整数');
  encoder=spawn('ffmpeg',['-v','error','-nostdin','-n','-f','image2pipe','-framerate','60','-vcodec','mjpeg','-i','pipe:0','-an','-vf','setsar=1','-c:v','libx264','-preset','fast','-crf','18','-threads','4','-pix_fmt','yuv420p','-movflags','+faststart',output],{stdio:['pipe','ignore','pipe']});
  encoder.stderr.on('data',b=>stderr=(stderr+b).slice(-4000));encoder.stdin.on('error',()=>{});
  encoderDone=new Promise((resolve,reject)=>{encoder.on('error',reject);encoder.on('close',code=>code===0?resolve():reject(Error(stderr||'FFmpeg编码失败')));});
  encoderDone.catch(e=>encoderFailure=e);
  for(let frame=0;frame<count;frame++){
    if(encoderFailure)throw encoderFailure;
    await bounded(page.evaluate(async f=>{await window.__DEMO_EXPORT__.render(f);},frame),'演员帧 '+frame);
    if(errors.length||blocked.length||missing.length)throw Error(JSON.stringify({errors,blocked,missing}));
    const pixels=await page.screenshot({type:'jpeg',quality:95,scale:'device',caret:'initial',timeout:30000});
    frames.push(createHash('sha256').update(pixels).digest('hex'));
    if(!encoder.stdin.write(pixels))await bounded(Promise.race([once(encoder.stdin,'drain'),encoderDone.then(()=>{throw Error('Encoder ended before all frames');})]),'编码输入',60000);
    if(frame===0||frame===Math.floor(count/2))await fs.writeFile(output+`.frame-${frame}.jpg`,pixels);
    if(frame%60===0)console.log(JSON.stringify({frame,total:count}));
  }
  encoder.stdin.end();await bounded(encoderDone,'编码结束',120000);
  const result=await bounded(page.evaluate(async()=>await window.__DEMO_EXPORT__.finish?.()||{}),'演员完成检查');
  if(result.complete!==true)throw Error('演员没有报告完整完成');
  if(result.assertions?.some(a=>a.passed!==true))throw Error('演员断言未通过');
  Object.assign(report,{status:'rendered',frames:count,durationSeconds:count/60,uniqueFrames:new Set(frames).size,result,errors,missing,blocked,
    sha256:createHash('sha256').update(await fs.readFile(output)).digest('hex'),scope:'仅本片离线画面渲染；尚非完整成片放行'});
  await fs.writeFile(path.join(path.dirname(output),'audio-cues.json'),JSON.stringify(result.audioCues||[],null,2)+'\n');
}catch(error){report.status='failed';report.error=String(error);if(encoder&&!encoder.killed)encoder.kill();process.exitCode=1;}
finally{
  await browser?.close();await new Promise(r=>server.close(r));
  await fs.writeFile(output+'.render.json',JSON.stringify(report,null,2)+'\n');
  if(report.status==='failed'){await fs.rm(output,{force:true});console.error(report.error);}
}
