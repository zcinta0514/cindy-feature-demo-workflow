/* Case-specific centered English layout; shared brand resources, durations and easing retained. */
/* Cindy shared motion v1.0.0. Local GSAP required. No network/timers. */
(function (global) {
  'use strict';
  const preset = Object.freeze({
    version: '1.0.0', width: 1920, height: 1080, fps: 60,
    cursor: {width: 22, height: 30, hotspot: [3, 2]},
    move: {duration: .55, ease: 'power2.inOut'},
    camera: {duration: .8, ease: 'power2.inOut'},
    click: {down: .07, up: .13, scale: .88},
    input: {secondsPerCharacter: .055, punctuationHold: .09, readHold: .65},
    intro: {duration: 3.2, arrival: .75, settleAt: 2.4, settleDuration: .8},
    outro: {duration: 3.4, exit: .42, arrivalOffset: .45, textOffset: .85}
  });
  function create(scope, config) {
    const c = Object.assign({duration: 14, introStart: 0, feature: '功能名称', closing: '符合本期能力的收尾文案'}, config);
    if (!(c.duration >= 7) || (c.introStart !== null && (c.introStart < 0 || c.introStart + 3.2 > c.duration - 3.4))) throw Error('片长或片头位置不合法');
    const $ = selector => { const el = scope.querySelector(selector); if (!el) throw Error('缺少模板节点 ' + selector); return el; };
    const tl = gsap.timeline({paused: true});
    const typing = [], effects = [];
    $('.brand-feature').textContent = c.feature;
    $('.brand-closing').textContent = c.closing;
    const pieces = [
      {el: $('.brand-icon'), hero: {x:610,y:393,scale:1}, outroHero:{x:610,y:359,scale:1}, header:{x:288,y:27,scale:58/180}},
      {el: $('.brand-wordmark'), hero: {x:840,y:404,scale:1}, outroHero:{x:840,y:370,scale:1}, header:{x:363,y:31.9,scale:147/470}},
      {el: $('.brand-feature'), hero: {x:(1920-$('.brand-feature').offsetWidth)/2,y:628,scale:1}, outroHero:{x:(1920-$('.brand-feature').offsetWidth)/2,y:594,scale:1}, header:{x:545,y:36.5,scale:30/44}}
    ];
    const out = c.duration - preset.outro.duration;
    pieces.forEach((p,i) => {
      if (c.introStart === null) {
        tl.set(p.el, Object.assign({},p.header,{opacity:1}),0);
      } else {
        tl.set(p.el, Object.assign({},p.header,{opacity:c.introStart > 0 ? 1 : 0}),0);
        tl.fromTo(p.el,Object.assign({},p.hero,{y:p.hero.y+18,opacity:i===0?1:0}),Object.assign({},p.hero,{opacity:1,duration:.75,ease:'power3.out',immediateRender:false}),c.introStart+(i===0?0:.15+i*.1));
        tl.fromTo(p.el,Object.assign({},p.hero,{opacity:1}),Object.assign({},p.header,{opacity:1,duration:.8,ease:'power3.inOut',immediateRender:false}),c.introStart+2.4);
      }
      tl.fromTo(p.el,Object.assign({},p.header,{opacity:1}),Object.assign({},p.header,{y:p.header.y-8,opacity:0,duration:.42,ease:'power2.inOut',immediateRender:false}),out);
      tl.fromTo(p.el,Object.assign({},p.outroHero,{y:p.outroHero.y+18,opacity:0}),Object.assign({},p.outroHero,{opacity:1,duration:.70,ease:'power3.out',immediateRender:false}),out+.45+i*.08);
    });
    tl.fromTo($('.brand-closing'),{y:12,opacity:0},{y:0,opacity:1,duration:.65,ease:'power3.out',immediateRender:false},out+.85);
    const body = $('.content-stage');
    gsap.set(body,{opacity:c.introStart===0?0:1,y:c.introStart===0?12:0,scale:c.introStart===0?.985:1});
    gsap.set($('.cursor-shape'),{scale:1});
    // Complete handoff: body exits .3s before header, matching approved source.
    tl.fromTo(body,{opacity:c.introStart===0?0:1,y:c.introStart===0?12:0,scale:c.introStart===0?.985:1},{opacity:1,y:0,scale:1,duration:.65,ease:'power3.out',immediateRender:false},c.introStart===0?3.2:0);
    if (c.introStart !== null && c.introStart > 0) {
      tl.to(body,{opacity:0,duration:.35,ease:'power2.inOut'},c.introStart);
      tl.to(body,{opacity:1,duration:.65,ease:'power3.out'},c.introStart+3.2);
    }
    tl.to(body,{opacity:0,y:14,scale:.985,duration:.65,ease:'power2.inOut'},out-.3);
    // Background keeps a continuous global phase; never resets at outro.
    tl.fromTo($('.mesh'),{'--hf-x1':'12%','--hf-y1':'22%','--hf-x2':'84%','--hf-y2':'20%','--hf-x3':'78%','--hf-y3':'90%','--hf-x4':'22%','--hf-y4':'87%'},{'--hf-x1':'22%','--hf-y1':'12%','--hf-x2':'91%','--hf-y2':'33%','--hf-x3':'66%','--hf-y3':'96%','--hf-x4':'12%','--hf-y4':'74%',duration:Math.max(.1,c.duration-4),ease:'sine.inOut'},0);
    tl.to({}, {duration:.001}, c.duration-.001);
    function move(x,y,at,options) {
      const o=Object.assign({},preset.move,options);
      tl.to($('.demo-cursor'),{x:x-3,y:y-2,duration:o.duration,ease:o.ease},at); return api;
    }
    function moveTo(selector,at,options) {
      const rect=$(selector).getBoundingClientRect(), world=$('.camera-world').getBoundingClientRect();
      const sx=$('.camera-world').offsetWidth/world.width, sy=$('.camera-world').offsetHeight/world.height;
      return move((rect.left+rect.width/2-world.left)*sx,(rect.top+rect.height/2-world.top)*sy,at,options);
    }
    function click(at) {
      tl.to($('.cursor-shape'),{scale:preset.click.scale,duration:.07,ease:'power2.out'},at);
      tl.to($('.cursor-shape'),{scale:1,duration:.13,ease:'power2.out'},at+.07);return api;
    }
    function camera(view,at,options) {
      tl.to($('.camera-world'),Object.assign({},preset.camera,view,options),at);return api;
    }
    function type(selector,text,at,options) {
      const o=Object.assign({},preset.input,options), el=$(selector);
      const chars=Array.from(new Intl.Segmenter('zh',{granularity:'grapheme'}).segment(text),s=>s.segment);
      let t=at;const ends=chars.map(ch=>{t+=o.secondsPerCharacter+(/[，。！？；,.!?;]/u.test(ch)?o.punctuationHold:0);return t;});
      typing.push({el,chars,ends,at,end:t,readUntil:t+o.readHold});return {end:t,readUntil:t+o.readHold};
    }
    function effect(fn) {effects.push(fn);return api;}
    function render(time) {
      if(time<=0){
        pieces.forEach((p,i)=>gsap.set(p.el,c.introStart===0?Object.assign({},p.hero,{y:p.hero.y+18,opacity:i===0?1:0}):Object.assign({},p.header,{opacity:1})));
        gsap.set(body,{opacity:c.introStart===0?0:1,y:c.introStart===0?12:0,scale:c.introStart===0?.985:1});
        gsap.set($('.brand-closing'),{opacity:0,y:12});
      }
      typing.forEach(item=>{let n=0;while(n<item.ends.length&&time>=item.ends[n])n++;const value=item.chars.slice(0,n).join('');if(item.el.matches('input,textarea'))item.el.value=value;else item.el.textContent=value;});
      effects.forEach(fn=>fn(time));
    }
    function seek(time) {tl.seek(Math.max(0,Math.min(c.duration,time)),true);render(time);}
    const api={timeline:tl,config:c,preset,move,moveTo,click,camera,type,effect,render,seek};return api;
  }
  global.CindyMotion={preset,create};
})(window);
