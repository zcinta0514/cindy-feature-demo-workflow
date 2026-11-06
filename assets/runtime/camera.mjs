// Full-target framing helpers. Inputs are logical scene coordinates, not DOM pixels.
export const ease = p => { p=Math.max(0,Math.min(1,p)); return p*p*p*(p*(p*6-15)+10); };
export function union(boxes) {
  if (!boxes.length || boxes.some(b=>![b.x,b.y,b.width,b.height].every(Number.isFinite)||b.width<0||b.height<0)) throw Error('Invalid target bounds');
  const x=Math.min(...boxes.map(b=>b.x)), y=Math.min(...boxes.map(b=>b.y));
  return {x,y,width:Math.max(...boxes.map(b=>b.x+b.width))-x,height:Math.max(...boxes.map(b=>b.y+b.height))-y};
}
export function fitTargets(boxes, viewport, {padding=32,maxScale=2.4}={}) {
  if (!(viewport.width>padding*2 && viewport.height>padding*2 && maxScale>0)) throw Error('Invalid safe viewport');
  const b=union(boxes), scale=Math.min(maxScale,(viewport.width-padding*2)/Math.max(1,b.width),(viewport.height-padding*2)/Math.max(1,b.height));
  return {scale,x:viewport.x+viewport.width/2-(b.x+b.width/2)*scale,y:viewport.y+viewport.height/2-(b.y+b.height/2)*scale};
}
export function point(p,pose){return {x:p.x*pose.scale+pose.x,y:p.y*pose.scale+pose.y};}
export function inverse(p,pose){if(!(pose.scale>0))throw Error('Invalid scale');return{x:(p.x-pose.x)/pose.scale,y:(p.y-pose.y)/pose.scale};}
export function interpolate(a,b,p){const q=ease(p);return{scale:a.scale+(b.scale-a.scale)*q,x:a.x+(b.x-a.x)*q,y:a.y+(b.y-a.y)*q};}
