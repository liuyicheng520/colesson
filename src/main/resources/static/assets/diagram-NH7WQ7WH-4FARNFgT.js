import{p as $}from"./chunk-JWPE2WC7-B3fqyrBO.js";import{_ as u,B as b,F as C,e as S,l as w,b as D,a as T,o as z,p as F,g as P,s as E,z as A,D as W,q as _}from"./mermaid.core-BesLrdQV.js";import{p as N}from"./cynefin-VYW2F7L2-CTHl-xfT.js";import"./index-XFAYuViF.js";import"./vendor-Dsm72HpX.js";import"./element-plus-BsXsclFA.js";import"./timer-DWAvo6M8.js";var L=W.packet,m,v=(m=class{constructor(){this.packet=[],this.setAccTitle=D,this.getAccTitle=T,this.setDiagramTitle=z,this.getDiagramTitle=F,this.getAccDescription=P,this.setAccDescription=E}getConfig(){const t=b({...L,...A().packet});return t.showBits&&(t.paddingY+=10),t}getPacket(){return this.packet}pushWord(t){t.length>0&&this.packet.push(t)}clear(){_(),this.packet=[]}},u(m,"PacketDB"),m),M=1e4,Y=u((e,t)=>{$(e,t);let s=-1,r=[],l=1;const{bitsPerRow:c}=t.getConfig();for(let{start:a,end:o,bits:n,label:d}of e.blocks){if(a!==void 0&&o!==void 0&&o<a)throw new Error(`Packet block ${a} - ${o} is invalid. End must be greater than start.`);if(a!=null||(a=s+1),a!==s+1)throw new Error(`Packet block ${a} - ${o!=null?o:a} is not contiguous. It should start from ${s+1}.`);if(n===0)throw new Error(`Packet block ${a} is invalid. Cannot have a zero bit field.`);for(o!=null||(o=a+(n!=null?n:1)-1),n!=null||(n=o-a+1),s=o,w.debug(`Packet block ${a} - ${s} with label ${d}`);r.length<=c+1&&t.getPacket().length<M;){const[p,i]=I({start:a,end:o,bits:n,label:d},l,c);if(r.push(p),p.end+1===l*c&&(t.pushWord(r),r=[],l++),!i)break;({start:a,end:o,bits:n,label:d}=i)}}t.pushWord(r)},"populate"),I=u((e,t,s)=>{if(e.start===void 0)throw new Error("start should have been set during first phase");if(e.end===void 0)throw new Error("end should have been set during first phase");if(e.start>e.end)throw new Error(`Block start ${e.start} is greater than block end ${e.end}.`);if(e.end+1<=t*s)return[e,void 0];const r=t*s-1,l=t*s;return[{start:e.start,end:r,label:e.label,bits:r-e.start},{start:l,end:e.end,label:e.label,bits:e.end-l}]},"getNextFittingBlock"),x={parser:{yy:void 0},parse:u(async e=>{var r;const t=await N("packet",e),s=(r=x.parser)==null?void 0:r.yy;if(!(s instanceof v))throw new Error("parser.parser?.yy was not a PacketDB. This is due to a bug within Mermaid, please report this issue at https://github.com/mermaid-js/mermaid/issues.");w.debug(t),Y(t,s)},"parse")},O=u((e,t,s,r)=>{const l=r.db,c=l.getConfig(),{rowHeight:a,paddingY:o,bitWidth:n,bitsPerRow:d}=c,p=l.getPacket(),i=l.getDiagramTitle(),h=a+o,g=h*(p.length+1)-(i?0:a),k=n*d+2,f=C(t);f.attr("viewBox",`0 0 ${k} ${g}`),S(f,g,k,c.useMaxWidth);for(const[y,B]of p.entries())j(f,B,y,c);f.append("text").text(i).attr("x",k/2).attr("y",g-h/2).attr("dominant-baseline","middle").attr("text-anchor","middle").attr("class","packetTitle")},"draw"),j=u((e,t,s,{rowHeight:r,paddingX:l,paddingY:c,bitWidth:a,bitsPerRow:o,showBits:n})=>{const d=e.append("g"),p=s*(r+c)+c;for(const i of t){const h=i.start%o*a+1,g=(i.end-i.start+1)*a-l;if(d.append("rect").attr("x",h).attr("y",p).attr("width",g).attr("height",r).attr("class","packetBlock"),d.append("text").attr("x",h+g/2).attr("y",p+r/2).attr("class","packetLabel").attr("dominant-baseline","middle").attr("text-anchor","middle").text(i.label),!n)continue;const k=i.end===i.start,f=p-2;d.append("text").attr("x",h+(k?g/2:0)).attr("y",f).attr("class","packetByte start").attr("dominant-baseline","auto").attr("text-anchor",k?"middle":"start").text(i.start),k||d.append("text").attr("x",h+g).attr("y",f).attr("class","packetByte end").attr("dominant-baseline","auto").attr("text-anchor","end").text(i.end)}},"drawWord"),q={draw:O},G={byteFontSize:"10px",startByteColor:"black",endByteColor:"black",labelColor:"black",labelFontSize:"12px",titleColor:"black",titleFontSize:"14px",blockStrokeColor:"black",blockStrokeWidth:"1",blockFillColor:"#efefef"},H=u(({packet:e}={})=>{const t=b(G,e);return`
	.packetByte {
		font-size: ${t.byteFontSize};
	}
	.packetByte.start {
		fill: ${t.startByteColor};
	}
	.packetByte.end {
		fill: ${t.endByteColor};
	}
	.packetLabel {
		fill: ${t.labelColor};
		font-size: ${t.labelFontSize};
	}
	.packetTitle {
		fill: ${t.titleColor};
		font-size: ${t.titleFontSize};
	}
	.packetBlock {
		stroke: ${t.blockStrokeColor};
		stroke-width: ${t.blockStrokeWidth};
		fill: ${t.blockFillColor};
	}
	`},"styles"),Z={parser:x,get db(){return new v},renderer:q,styles:H};export{Z as diagram};
