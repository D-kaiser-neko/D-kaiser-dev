let songs=[],lrcLines=[],curIdx=-1,curPg=1,curKw='',curSrc='muguang',total=0;
const au=document.getElementById('au'),fpAu=document.getElementById('fpAu');

function toast(m){let t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000);}
function setSrc(s){curSrc=s;document.getElementById('srcMg').className=s==='muguang'?'active':'';document.getElementById('srcHi').className=s==='hi'?'active':'';}

function doSearch(pg=1){
  let kw=document.getElementById('kw').value.trim();
  if(!kw&&pg===1)return;
  if(pg===1)curKw=kw;
  curPg=pg;
  document.getElementById('pgI').textContent=`第 ${pg} 页 · 搜索中...`;
  fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:curKw,source:curSrc,page:pg})})
  .then(r=>r.json()).then(d=>{
    songs=d.songs||[];total=d.total||0;render();
    document.getElementById('pgI').textContent=`第 ${pg} 页 · ${total?Math.ceil(total/20)+'页 ':''}${songs.length} 首`;
    document.getElementById('prevB').disabled=pg<=1;
    document.getElementById('nextB').disabled=songs.length<20;
  });
}
function chgPg(d){doSearch(curPg+d);}

function render(){
  let el=document.getElementById('list');el.innerHTML='';
  songs.forEach((s,i)=>{
    let fl=(s.minfo||[]).some(m=>m.format==='flac');
    let tg=fl?'<span class="tg tg-f">FLAC</span>':'<span class="tg tg-m">MP3</span>';
    let dur=s.duration||0;let mn=Math.floor(dur/60),sc=dur%60;
    el.innerHTML+=`<div class="si"><input type="checkbox" data-i="${i}"><img class="sc" src="${esc(s.pic_url||'')}" onerror="this.style.display='none'"><div class="sf"><div class="sn">${esc(s.name)}${tg}</div><div class="sa">${esc(s.artist)} · ${mn}:${String(sc).padStart(2,'0')}</div></div><button class="bs bp" onclick="event.stopPropagation();preview(${i})">▶</button><button class="bs bd" onclick="event.stopPropagation();dlOne(${i})">⬇</button></div>`;
  });
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function togAll(){let c=[...document.querySelectorAll('.si input[type=checkbox]')];let a=c.every(x=>x.checked);c.forEach(x=>x.checked=!a);}
function dlSel(){let ids=[...document.querySelectorAll('.si input:checked')].map(c=>+c.dataset.i);if(!ids.length)return toast('请先勾选');
  fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:ids,source:curSrc})}).then(()=>toast(`已加入 ${ids.length} 首`));}
function dlOne(i){fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:[i],source:curSrc})}).then(()=>toast('已加入'));}

function preview(i){
  curIdx=i;let s=songs[i];
  document.getElementById('pbT').textContent=s.name;
  document.getElementById('pbS').textContent=s.artist;
  document.getElementById('pbC').src=s.pic_url||'';
  document.getElementById('pBar').classList.add('active');
  fetch('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,source:curSrc})})
  .then(r=>r.json()).then(d=>{if(d.url){au.src=d.url;au.play();}else{document.getElementById('pbS').textContent='无预览资源';}});
  fetch('/api/lyric',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,source:curSrc})})
  .then(r=>r.json()).then(d=>{lrcLines=d.lrc?parseLrc(d.lrc):[];});
}

/* ★ 修复: 兼容 [mm:ss] / [mm:ss.xx] / [mm:ss.xxx] */
function parseLrc(t){
  return t.split('\n').map(l=>{
    let m=l.match(/^\[(\d+):(\d+)(?:\.(\d+))?\](.*)$/);
    if(m){
      let sec=parseInt(m[2],10);
      if(m[3])sec+=parseInt(m[3],10)/Math.pow(10,m[3].length);
      return{time:parseInt(m[1],10)*60+sec,text:m[4]};
    }
    return null;
  }).filter(Boolean).sort((a,b)=>a.time-b.time);
}

function openFp(){
  if(curIdx<0)return;let s=songs[curIdx];
  document.getElementById('fpT').textContent=s.name;
  document.getElementById('fpA').textContent=s.artist;
  document.getElementById('fpC').src=s.pic_url||'';
  if(fpAu.src!==au.src)fpAu.src=au.src;
  fpAu.currentTime=au.currentTime;fpAu.play().catch(()=>{});au.pause();
  let box=document.getElementById('fpL');box.innerHTML='';
  lrcLines.forEach(l=>{let d=document.createElement('div');d.className='fp-li';d.textContent=l.text||'♪';box.appendChild(d);});
  document.getElementById('fp').classList.add('active');
}
function closeFp(){document.getElementById('fp').classList.remove('active');au.currentTime=fpAu.currentTime;au.play().catch(()=>{});fpAu.pause();}

fpAu.addEventListener('timeupdate',()=>{
  if(!lrcLines.length)return;let t=fpAu.currentTime,ai=0;
  for(let i=lrcLines.length-1;i>=0;i--){if(lrcLines[i].time<=t){ai=i;break;}}
  document.querySelectorAll('.fp-li').forEach((el,i)=>{
    if(i===ai){el.classList.add('active');el.scrollIntoView({behavior:'smooth',block:'center'});}
    else{el.classList.remove('active');}
  });
});
fpAu.addEventListener('ended',()=>{if(curIdx<songs.length-1){preview(curIdx+1);setTimeout(openFp,300);}});

function toggleDp(){document.getElementById('dp').classList.toggle('active');refreshDp();}
function refreshDp(){
  fetch('/api/dl-status').then(r=>r.json()).then(d=>{
    let h='<div class="dp-t">计划中 ('+d.pending.length+')</div>';
    if(!d.pending.length)h+='<div style="font-size:11px;color:var(--sub);padding:6px;">暂无任务</div>';
    d.pending.forEach(t=>{h+=`<div class="di"><div class="di-n">${esc(t.name)} - ${esc(t.artist)}</div><div class="di-s">${t.status}</div><div class="di-d" onclick="delP(${t.id})">✕</div></div>`;});
    h+='<div class="dp-t">已完成 ('+d.completed.length+')</div>';
    if(!d.completed.length)h+='<div style="font-size:11px;color:var(--sub);padding:6px;">暂无记录</div>';
    d.completed.forEach(t=>{h+=`<div class="di"><div class="di-n">${esc(t.name)} - ${esc(t.artist)}</div><div class="di-s" style="color:${t.status==='成功'?'var(--grn)':'#e74c3c'}">${t.status}</div></div>`;});
    if(d.completed.length)h+='<button class="dp-clr" onclick="clrDone()">清空已完成</button>';
    document.getElementById('dpB').innerHTML=h;
    let b=document.getElementById('dlB');
    if(d.pending.length>0){b.style.display='flex';b.textContent=d.pending.length;}else{b.style.display='none';}
  });
}
function delP(id){fetch('/api/dl-remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}).then(()=>refreshDp());}
function clrDone(){fetch('/api/dl-clear',{method:'POST'}).then(()=>refreshDp());}
setInterval(refreshDp,2000);

function saveCk(){let c=document.getElementById('ckIn').value.trim();if(!c)return;
  fetch('/api/cookie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookie:c})}).then(()=>toast('Cookie 已保存'));}

let es=null;
function connectLogs(){
  if(es)es.close();
  es=new EventSource('/api/logs-stream');
  es.onmessage=function(e){
    let el=document.getElementById('logs');
    let d=document.createElement('div');d.textContent=e.data;el.appendChild(d);
    el.scrollTop=el.scrollHeight;
    while(el.children.length>200)el.removeChild(el.firstChild);
  };
  es.onerror=function(){setTimeout(connectLogs,3000);};
}
connectLogs();