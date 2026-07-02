import{useState}from'react';
import{PREVENTION_TYPES,SKIP_TYPES,type AgentFinding}from'../../lib/types';
import s from'./FindingsPanel.module.css';
function Badge({v}:{v:number}){const p=Math.round(v*100);const c=v>=0.8?s.cHigh:v>=0.6?s.cMid:s.cLow;return<span className={`${s.badge} ${c}`}>{p}%</span>;}
function Note({f}:{f:AgentFinding}){
  const[exp,setExp]=useState(false);
  return(<article className={s.note}>
    <div className={s.noteHead}><span className={s.noteType}>{f.finding_type.replace(/_/g,' ')}</span><Badge v={f.confidence}/><span className={f.validated?s.valid:s.rej}>{f.validated?'Validated':'Rejected'}</span></div>
    <p className={s.noteSummary}>{f.summary}</p>
    {f.evidence.length>0&&<button className={s.expBtn} onClick={()=>setExp(v=>!v)} aria-expanded={exp}><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{transform:exp?'rotate(90deg)':'none',transition:'transform 150ms'}}><polyline points="9 18 15 12 9 6"/></svg>{exp?'Hide':'View'} evidence</button>}
    {exp&&<div className={s.evidence}><div className={s.evLabel}>Evidence</div>{f.evidence.map((e,i)=><div key={i} className={s.evItem}><span className={s.evDot} aria-hidden/><span>{e}</span></div>)}<div className={s.src}><span className={s.evLabel}>Agent</span><span className={s.mono}>{f.agent_name}</span></div></div>}
  </article>);
}
function Action({f}:{f:AgentFinding}){
  const labels:Record<string,string>={patrol_strategy:'Patrol',surveillance_action:'Surveillance',prevention_recommendation:'Action'};
  return(<article className={s.action}><div className={s.actTag}>{labels[f.finding_type]??'Action'}</div><p className={s.actText}>{f.summary}</p><Badge v={f.confidence}/></article>);
}
export function FindingsPanel({findings,isComplete,onExportPDF,exportingPDF}:{findings:AgentFinding[];isComplete:boolean;onExportPDF:()=>void;exportingPDF:boolean}){
  const notes=findings.filter(f=>!SKIP_TYPES.has(f.finding_type)&&f.validated);
  const actions=findings.filter(f=>PREVENTION_TYPES.has(f.finding_type)&&f.validated);
  if(!findings.length)return(<aside className={s.root} aria-label="Findings"><div className={s.hdr}><span className={s.lbl}>Intelligence</span></div><div className={s.empty}><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.25"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg><span>Awaiting investigation</span></div></aside>);
  return(<aside className={s.root} aria-label="Findings">
    {notes.length>0&&<section><div className={s.hdr}><span className={s.lbl}>Detective Notes</span><span className={s.cnt}>{notes.length}</span></div><div className={s.list}>{notes.map((f,i)=><Note key={i} f={f}/>)}</div></section>}
    {actions.length>0&&<section><div className={s.hdr}><span className={s.lbl}>Recommended Actions</span><span className={s.cnt}>{actions.length}</span></div><div className={s.list}>{actions.map((f,i)=><Action key={i} f={f}/>)}</div></section>}
    {isComplete&&<div className={s.exportWrap}><button className={s.exportBtn} onClick={onExportPDF} disabled={exportingPDF}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>{exportingPDF?'Exporting…':'Export Investigation Report'}</button></div>}
  </aside>);
}