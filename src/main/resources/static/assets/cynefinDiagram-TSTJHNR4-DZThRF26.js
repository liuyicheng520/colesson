import{p as gt}from"./chunk-JWPE2WC7-B_yTw_lU.js";import{s as $t,g as bt,p as wt,o as Ct,a as Dt,b as vt,_ as s,l as X,F as kt,e as Tt,q as At,B as Q,z as Z,D as Bt,W as rt}from"./mermaid.core-CU6ljMbI.js";import{p as St}from"./cynefin-VYW2F7L2-CGgffmHc.js";import"./index-B9FbLEYC.js";import"./vendor-Dsm72HpX.js";import"./element-plus-BsXsclFA.js";import"./timer-DWAvo6M8.js";var st=s(()=>({domains:new Map,transitions:[]}),"createDefaultData"),H=st(),Mt=s(()=>H.domains,"getDomains"),zt=s(()=>H.transitions,"getTransitions"),Lt=s(t=>{var e;if(t)for(const n of t){const o=n.domain,c=((e=n.items)!=null?e:[]).map(f=>({label:f.label}));H.domains.set(o,{name:o,items:c})}},"setDomains"),Nt=s(t=>{t&&(H.transitions=t.filter(e=>e.from===e.to?(X.warn(`Cynefin: self-loop transition on domain "${e.from}" is not meaningful and will be skipped.`),!1):!0).map(e=>({from:e.from,to:e.to,label:e.label||void 0})))},"setTransitions"),Pt=s(()=>Q({...Bt.cynefin,...Z().cynefin}),"getConfig"),Wt=s(()=>{At(),H=st()},"clear"),Y={getDomains:Mt,getTransitions:zt,setDomains:Lt,setTransitions:Nt,getConfig:Pt,clear:Wt,setAccTitle:vt,getAccTitle:Dt,setDiagramTitle:Ct,getDiagramTitle:wt,getAccDescription:bt,setAccDescription:$t},It=s(t=>{gt(t,Y),Y.setDomains(t.domains),Y.setTransitions(t.transitions)},"populate"),Ft={parse:s(async t=>{const e=await St("cynefin",t);X.debug(e),It(e)},"parse")};function E(t){let e=t+1831565813|0;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}s(E,"seededRandom");function it(t){let e=0;for(let n=0;n<t.length;n++){const o=t.charCodeAt(n);e=(e<<5)-e+o,e|=0}return e}s(it,"hashString");function ct(t,e){return typeof t=="number"&&Number.isFinite(t)&&t!==0?t:it(e)}s(ct,"resolveSeed");function lt(t,e,n,o){const c=t/2,f=o!=null?o:t*.015,D=7,I=e/D,d=[];for(let a=0;a<=D;a++){const p=E(n+a*17)*f*2-f;d.push({x:c+p,y:a*I})}let v=`M${d[0].x},${d[0].y}`;for(let a=0;a<d.length-1;a++){const p=d[a],i=d[a+1],m=(p.y+i.y)/2,b=a%2===0?1:-1,h=f*1.5*b*E(n+a*31+7),F=p.x+h,R=m,_=i.x-h;v+=` C${F},${R} ${_},${m} ${i.x},${i.y}`}return v}s(lt,"generateFoldPath");function ft(t,e,n,o){const c=e/2,f=o!=null?o:e*.015,D=7,I=t/D,d=[];for(let a=0;a<=D;a++){const p=E(n+a*23)*f*2-f;d.push({x:a*I,y:c+p})}let v=`M${d[0].x},${d[0].y}`;for(let a=0;a<d.length-1;a++){const p=d[a],i=d[a+1],m=(p.x+i.x)/2,b=a%2===0?1:-1,h=f*1.5*b*E(n+a*37+11),F=m,R=p.y+h,_=m,z=i.y-h;v+=` C${F},${R} ${_},${z} ${i.x},${i.y}`}return v}s(ft,"generateHorizontalBoundary");function dt(t,e){const n=t/2,o=e*.5,c=e,f=t*.03;return[`M${n},${o}`,`C${n+f},${o+(c-o)*.2}`,`${n-f*1.5},${o+(c-o)*.55}`,`${n+f*.5},${o+(c-o)*.75}`,`C${n-f},${o+(c-o)*.85}`,`${n+f*.3},${o+(c-o)*.95}`,`${n},${c}`].join(" ")}s(dt,"generateCliffPath");function mt(t,e,n,o){return[`M${t-n},${e}`,`A${n},${o} 0 1,1 ${t+n},${e}`,`A${n},${o} 0 1,1 ${t-n},${e}`,"Z"].join(" ")}s(mt,"generateConfusionPath");var at={complex:{model:"Probe → Sense → Respond",practice:"Emergent Practices"},complicated:{model:"Sense → Analyse → Respond",practice:"Good Practices"},clear:{model:"Sense → Categorise → Respond",practice:"Best Practices"},chaotic:{model:"Act → Sense → Respond",practice:"Novel Practices"},confusion:{model:"",practice:"Disorder"}},Rt=s((t,e)=>{const n=t/2,o=e/2;return{complex:{cx:n/2,cy:o/2,x:0,y:0,w:n,h:o},complicated:{cx:n+n/2,cy:o/2,x:n,y:0,w:n,h:o},chaotic:{cx:n/2,cy:o+o/2,x:0,y:o,w:n,h:o},clear:{cx:n+n/2,cy:o+o/2,x:n,y:o,w:n,h:o},confusion:{cx:n,cy:o,x:n*.7,y:o*.7,w:n*.6,h:o*.6}}},"getDomainLayouts"),_t=s(()=>{const t=rt(),e=Z();return Q(t,e.themeVariables).cynefin},"getCynefinDomainColors"),U=3,Vt=s((t,e,n,o)=>{var et;const c=o.db,f=c.getDomains(),D=c.getTransitions(),I=c.getDiagramTitle(),d=c.getAccTitle(),v=c.getAccDescription(),a=c.getConfig(),p=_t();X.debug("Rendering Cynefin diagram");const i=a.width,m=a.height,b=a.padding,h=a.showDomainDescriptions,F=a.boundaryAmplitude,R=i+b*2,_=m+b*2,z={complex:p.complexBg,complicated:p.complicatedBg,clear:p.clearBg,chaotic:p.chaoticBg,confusion:p.confusionBg},k=kt(e);Tt(k,_,R,(et=a.useMaxWidth)!=null?et:!0),k.attr("viewBox",`0 0 ${R} ${_}`),d&&k.append("title").text(d),v&&k.append("desc").text(v);const T=k.append("g").attr("transform",`translate(${b}, ${b})`),V=Rt(i,m),J=ct(a.seed,e),pt=T.append("g").attr("class","cynefin-backgrounds"),j=["complex","complicated","chaotic","clear"];for(const l of j){const r=V[l];pt.append("rect").attr("class","cynefinDomain").attr("x",r.x).attr("y",r.y).attr("width",r.w).attr("height",r.h).attr("fill",z[l]).attr("fill-opacity",.4).attr("stroke","none")}const q=T.append("g").attr("class","cynefin-boundaries");q.append("path").attr("class","cynefinBoundary").attr("d",lt(i,m,J,F)).attr("fill","none"),q.append("path").attr("class","cynefinBoundary").attr("d",ft(i,m,J+100,F)).attr("fill","none"),q.append("path").attr("class","cynefinCliff").attr("d",dt(i,m)).attr("fill","none");const yt=i*.15,ut=m*.15;T.append("path").attr("class","cynefinConfusion").attr("d",mt(i/2,m/2,yt,ut)).attr("fill",z.confusion).attr("fill-opacity",.5);const K=T.append("g").attr("class","cynefin-labels");for(const l of j){const r=V[l];K.append("text").attr("class","cynefinDomainLabel").attr("x",r.cx).attr("y",h?r.cy-30:r.cy).attr("text-anchor","middle").attr("dominant-baseline","middle").text(l.charAt(0).toUpperCase()+l.slice(1))}if(K.append("text").attr("class","cynefinDomainLabel").attr("x",i/2).attr("y",h?m/2-10:m/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text("Confusion"),h){const l=T.append("g").attr("class","cynefin-subtitles");for(const r of j){const u=V[r],y=at[r];l.append("text").attr("class","cynefinSubtitle").attr("x",u.cx).attr("y",u.cy-10).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.model),l.append("text").attr("class","cynefinSubtitle").attr("x",u.cx).attr("y",u.cy+5).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.practice)}l.append("text").attr("class","cynefinSubtitle").attr("x",i/2).attr("y",m/2+8).attr("text-anchor","middle").attr("dominant-baseline","middle").text(at.confusion.practice)}const O=T.append("g").attr("class","cynefin-items"),A=26,tt=10,ht=["complex","complicated","chaotic","clear","confusion"];for(const l of ht){const r=f.get(l);if(!r||r.items.length===0)continue;const u=V[l],y=l==="confusion";let L=r.items,N=0;y&&r.items.length>U&&(N=r.items.length-U,L=r.items.slice(0,U));let B;if(y){const g=h?22:14;B=u.cy+g}else B=u.cy+(h?25:15);if([...L].forEach((g,S)=>{const w=B+S*(A+4),M=O.append("g"),P=M.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",A/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(g.label);let $=g.label.length*7;const x=P.node();if(x&&typeof x.getBBox=="function"){const G=x.getBBox();G.width>0&&($=G.width)}const C=$+tt*2,W=u.cx-C/2;M.attr("transform",`translate(${W}, ${w})`),M.insert("rect","text").attr("class","cynefinItem").attr("x",0).attr("y",0).attr("width",C).attr("height",A).attr("rx",4).attr("ry",4).attr("fill",z[l]).attr("fill-opacity",.95),P.attr("x",C/2).attr("y",A/2)}),N>0){const g=B+L.length*(A+4),S=`+${N} more`,w=O.append("g"),M=w.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",A/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(S);let P=S.length*7;const $=M.node();if($&&typeof $.getBBox=="function"){const W=$.getBBox();W.width>0&&(P=W.width)}const x=P+tt*2,C=u.cx-x/2;w.attr("transform",`translate(${C}, ${g})`),w.insert("rect","text").attr("class","cynefinItemOverflow").attr("x",0).attr("y",0).attr("width",x).attr("height",A).attr("rx",4).attr("ry",4).attr("fill",z[l]).attr("fill-opacity",.6),M.attr("x",x/2).attr("y",A/2)}}if(D.length>0){const l=k.select("defs").empty()?k.append("defs"):k.select("defs"),r=`cynefin-arrow-${e}`;l.append("marker").attr("id",r).attr("viewBox","0 0 10 10").attr("refX",9).attr("refY",5).attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto-start-reverse").append("path").attr("d","M 0 0 L 10 5 L 0 10 z").attr("class","cynefinArrowHead");const u=T.append("g").attr("class","cynefin-arrows");D.forEach(y=>{const L=V[y.from],N=V[y.to];if(!L||!N)return;if(y.from===y.to){X.warn(`Cynefin renderer: skipping self-loop on domain "${y.from}"`);return}const B=L.cx,g=L.cy,S=N.cx,w=N.cy,M=(B+S)/2,P=(g+w)/2,$=S-B,x=w-g,C=Math.sqrt($*$+x*x),W=C*.15,G=-x/C,xt=$/C,nt=M+G*W,ot=P+xt*W;u.append("path").attr("class","cynefinArrowLine").attr("d",`M${B},${g} Q${nt},${ot} ${S},${w}`).attr("fill","none").attr("marker-end",`url(#${r})`),y.label&&u.append("text").attr("class","cynefinArrowLabel").attr("x",nt).attr("y",ot-6).attr("text-anchor","middle").attr("dominant-baseline","auto").text(y.label)})}I&&T.append("text").attr("class","cynefinTitle").attr("x",i/2).attr("y",-b/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text(I)},"draw"),Et={draw:Vt},Ht=s(()=>{const t=rt(),e=Z();return Q(t,e.themeVariables).cynefin},"getCynefinTheme"),Gt=s(()=>{const t=Ht();return`
	.cynefinDomain {
		stroke: none;
	}
	.cynefinDomainLabel {
		font-size: ${t.domainFontSize}px;
		font-weight: bold;
		fill: ${t.labelColor};
	}
	.cynefinSubtitle {
		font-size: ${t.itemFontSize-1}px;
		fill: ${t.textColor};
		font-style: italic;
	}
	.cynefinItem {
		fill-opacity: 0.95;
		stroke: ${t.boundaryColor};
		stroke-width: 1;
	}
	.cynefinItemText {
		font-size: ${t.itemFontSize}px;
		fill: ${t.textColor};
	}
	.cynefinItemOverflow {
		fill-opacity: 0.6;
		stroke: ${t.boundaryColor};
		stroke-width: 1;
		stroke-dasharray: 3 2;
	}
	.cynefinBoundary {
		stroke: ${t.boundaryColor};
		stroke-width: ${t.boundaryWidth};
		stroke-dasharray: 6 3;
	}
	.cynefinCliff {
		stroke: ${t.cliffColor};
		stroke-width: ${t.cliffWidth};
	}
	.cynefinConfusion {
		stroke: ${t.boundaryColor};
		stroke-width: 1.5;
		stroke-dasharray: 4 2;
	}
	.cynefinArrowLine {
		stroke: ${t.arrowColor};
		stroke-width: ${t.arrowWidth};
		fill: none;
	}
	.cynefinArrowHead {
		fill: ${t.arrowColor};
		stroke: none;
	}
	.cynefinArrowLabel {
		font-size: ${t.itemFontSize-1}px;
		fill: ${t.textColor};
	}
	.cynefinTitle {
		font-size: ${t.domainFontSize+2}px;
		font-weight: bold;
		fill: ${t.labelColor};
	}
	`},"styles"),Yt=Gt,Kt={parser:Ft,db:Y,renderer:Et,styles:Yt};export{Kt as diagram};
