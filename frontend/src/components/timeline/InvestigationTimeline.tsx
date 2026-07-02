import type{AgentStep}from'../../lib/types';
import s from'./InvestigationTimeline.module.css';
const PendingIcon=()=><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="9"/></svg>;
const RunningIcon=()=><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={s.spin}><path d="M12 3a9 9 0 1 0 9 9" strokeLinecap="round"/></svg>;
const DoneIcon=()=><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
const SkipIcon=()=><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="9" strokeDasharray="2 4"/></svg>;
function fmt(ms:number){return ms<1000?`${ms}ms`:`${(ms/1000).toFixed(1)}s`;}
export function InvestigationTimeline({steps,elapsedMs}:{steps:AgentStep[];elapsedMs:number}){
  const done=steps.filter(s=>s.status==='complete').length;
  return(<aside className={s.root} aria-label="Investigation timeline">
    <div className={s.header}><span className={s.label}>Investigation</span>{elapsedMs>0&&<span className={s.elapsed}>{fmt(elapsedMs)}</span>}</div>
    <div className={s.progress} role="progressbar" aria-valuenow={done} aria-valuemax={steps.length}><div className={s.fill} style={{width:`${(done/steps.length)*100}%`}}/></div>
    <nav className={s.steps}>
      {steps.map((step,i)=>(
        <div key={step.nodeKey} className={`${s.step} ${s[step.status]}`} aria-current={step.status==='running'?'step':undefined}>
          {i<steps.length-1&&<div className={`${s.connector} ${step.status==='complete'?s.connFilled:''}`} aria-hidden/>}
          <div className={s.icon} aria-hidden>{step.status==='pending'?<PendingIcon/>:step.status==='running'?<RunningIcon/>:step.status==='complete'?<DoneIcon/>:<SkipIcon/>}</div>
          <div className={s.content}>
            <span className={s.name}>{step.name}</span>
            {step.status==='running'&&<span className={s.runningText}>Analysing<span className={s.dots}><span>.</span><span>.</span><span>.</span></span></span>}
            {step.status==='complete'&&step.message&&<span className={s.msg}>{step.message.replace(/^[^:]+:\s*/,'').slice(0,60)}</span>}
            {step.status==='skipped'&&<span className={s.skip}>Not required</span>}
          </div>
        </div>
      ))}
    </nav>
  </aside>);
}