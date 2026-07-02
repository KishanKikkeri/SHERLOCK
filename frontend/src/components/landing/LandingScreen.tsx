import{useEffect,useRef,useState}from'react';
import s from'./LandingScreen.module.css';
const SUGGESTED=['Show repeat burglary offenders operating in Mysuru during festival seasons and identify future hotspots','Trace the financial network linked to fraud cases and identify suspicious money movement patterns','Find hidden relationships between repeat offenders and identify potential organized crime groups'];
export function LandingScreen({onSubmit}:{onSubmit:(q:string)=>void}){
  const[query,setQuery]=useState('');const[focused,setFocused]=useState(false);const ref=useRef<HTMLInputElement>(null);
  useEffect(()=>{setTimeout(()=>ref.current?.focus(),100);},[]);
  const submit=()=>{const q=query.trim();if(q)onSubmit(q);};
  const keyDown=(e:React.KeyboardEvent)=>{if(e.key==='Enter')submit();};
  return(<div className={s.root}><div className={s.grid} aria-hidden/>
    <div className={s.center}>
      <div className={s.brand}>
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden><rect width="28" height="28" rx="6" fill="#38BDF8" fillOpacity="0.12"/><path d="M7 10h14M7 14h9M7 18h11" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round"/><circle cx="21" cy="18" r="4" stroke="#38BDF8" strokeWidth="1.5"/><path d="M24 21l2.5 2.5" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round"/></svg>
        <h1 className={s.wordmark}>SHERLOCK</h1>
      </div>
      <p className={s.tagline}>AI Crime Intelligence Command Center</p>
      <div className={`${s.inputWrap} ${focused?s.focused:''}`}>
        <svg className={s.icon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input ref={ref} className={s.input} placeholder="Ask any investigation question..." value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={keyDown} onFocus={()=>setFocused(true)} onBlur={()=>setFocused(false)} aria-label="Investigation query" autoComplete="off" spellCheck={false}/>
        <button className={s.btn} onClick={submit} disabled={!query.trim()}>Investigate</button>
      </div>
      <div className={s.suggestions}>
        <span className={s.suggestLabel}>Suggested</span>
        {SUGGESTED.map((q,i)=><button key={i} className={s.suggest} onClick={()=>onSubmit(q)}><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><polyline points="9 18 15 12 9 6"/></svg><span>{q.length>70?q.slice(0,70)+'…':q}</span></button>)}
      </div>
    </div>
    <footer className={s.footer}><span className={s.badge}><span className={s.dot} aria-hidden/>All findings evidence-backed and validated</span></footer>
  </div>);
}