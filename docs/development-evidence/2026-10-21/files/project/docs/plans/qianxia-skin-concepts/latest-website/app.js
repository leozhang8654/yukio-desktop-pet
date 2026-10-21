"use strict";
const states=JSON.parse(document.getElementById("state-data").textContent);
const gallery=document.getElementById("gallery"), dialog=document.getElementById("detail");
let active=0,filter="all";
for(const state of states){
 const card=document.createElement("article");card.className="card";card.dataset.changed=String(state.changed);
 card.innerHTML=`<button class="image-button stage" aria-label="查看${state.name}：${state.title}"><span class="card-number">${state.number} / 12</span><img src="${state.image}" alt="千夏${state.name}状态：${state.title}" width="280" height="304" loading="${Number(state.number)<=3?"eager":"lazy"}"><span class="zoom-mark" aria-hidden="true">↗</span></button><div class="card-info"><div class="card-heading"><h2>${state.name}</h2>${state.changed?'<span class="latest">最近调整</span>':""}</div><p class="card-subtitle">${state.title}</p><div class="card-bottom"><span class="card-id">${state.id}</span><a href="${state.image}" download="${state.number}-${state.id}.png" aria-label="下载${state.name}透明原图">原图 ↓</a></div></div>`;
 card.querySelector("button").addEventListener("click",()=>{active=states.indexOf(state);showDetail();dialog.showModal();document.body.style.overflow="hidden";});
 gallery.append(card);
}
function showDetail(){
 const s=states[active];
 document.getElementById("detail-counter").textContent=s.number+" / 12";
 document.getElementById("detail-state").textContent=s.name+" / "+s.id;
 document.getElementById("detail-title").textContent=s.title;
 document.getElementById("detail-description").textContent=s.description;
 document.getElementById("detail-motion").textContent=s.motion;
 const im=document.getElementById("detail-image");im.src=s.image;im.alt="千夏"+s.name+"状态："+s.title;
 const dl=document.getElementById("single-download");dl.href=s.image;dl.download=s.number+"-"+s.id+".png";
 document.getElementById("original").href=s.image;
}
function navigate(direction){const indexes=states.map((s,i)=>i).filter(i=>filter==="all"||states[i].changed);let position=indexes.indexOf(active);active=indexes[(position+direction+indexes.length)%indexes.length];showDetail();}
document.getElementById("previous").addEventListener("click",()=>navigate(-1));
document.getElementById("next").addEventListener("click",()=>navigate(1));
document.getElementById("close").addEventListener("click",()=>dialog.close());
dialog.addEventListener("click",e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
dialog.addEventListener("keydown",e=>{if(e.key==="ArrowRight"||e.key==="ArrowLeft"){e.preventDefault();navigate(e.key==="ArrowRight"?1:-1);}});
dialog.addEventListener("close",()=>document.body.style.overflow="");

document.querySelectorAll("[data-filter]").forEach(b=>b.addEventListener("click",()=>{filter=b.dataset.filter;document.querySelectorAll("[data-filter]").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));document.querySelectorAll(".card").forEach(c=>c.hidden=filter==="changed"&&c.dataset.changed!=="true");document.getElementById("count").textContent=(filter==="all"?states.length:states.filter(s=>s.changed).length)+" 个状态";}));
document.querySelectorAll("[data-bg]").forEach(b=>b.addEventListener("click",()=>{document.body.dataset.background=b.dataset.bg;document.querySelectorAll("[data-bg]").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));}));
document.getElementById("size").addEventListener("change",e=>document.body.dataset.size=e.target.value);


