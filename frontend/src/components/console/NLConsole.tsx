import{useEffect,useRef,useState}from'react';
import s from'./NLConsole.module.css';
export function NLConsole({onSubmit,isRunning,lastQuery}:{onSubmit:(q:string)=>void;isRunning:boolean;lastQuery:string}){
  const[query,setQuery]=useState('');const[hIdx,setHIdx]=useState(-1);const[hist,setHist]=useState<string[]>([]);const ref=useRef<HTMLInputElement>(null);
  useEffect(()=>{if(lastQuery&&(hist.length===0||hist[0]!==lastQuery))setHist(p=>[lastQuery,...p.slice(0,19)]);},[lastQuery]);
  const submit=()=>{const q=query.trim();if(!q||isRunning)return;setHIdx(-1);onSubmit(q);setQuery('');};
  const keyDown=(e:React.KeyboardEvent<HTMLInputElement>)=>{
    if(e.key==='Enter'){submit();}
    else if(e.key==='ArrowUp'){e.preventDefault();const ni=Math.min(hIdx+1,hist.length-1);setHIdx(ni);if(hist[ni])setQuery(hist[ni]);}
    else if(e.key==='ArrowDown'){e.preventDefault();const ni=Math.max(hIdx-1,-1);setHIdx(ni);setQuery(ni===-1?'':hist[ni]);}
  };
  useEffect(()=>{const h=(e:KeyboardEvent)=>{if(e.key==='/'&&document.activeElement?.tagName!=='INPUT'){e.preventDefault();ref.current?.focus();}};window.addEventListener('keydown',h);return()=>window.removeEventListener('keydown',h);},[]);
  return(<div className={s.root} role="search"><div className={s.inner}>
    <span className={s.prompt} aria-hidden>›</span>
    <input ref={ref} className={s.input} placeholder={isRunning?'Investigation in progress…':'Ask a follow-up or start a new investigation…'} value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={keyDown} disabled={isRunning} aria-label="Investigation query" autoComplete="off" spellCheck={false}/>
    <div className={s.controls}>
      {hist.length>0&&!isRunning&&<span className={s.hint} aria-label="Arrow keys for history">↑↓</span>}
      {!isRunning&&<span className={s.hint} aria-hidden>/</span>}
      <button className={`${s.btn} ${isRunning?s.running:''}`} onClick={submit} disabled={isRunning||!query.trim()} aria-label={isRunning?'Investigating':'Run investigation'}>
        {isRunning?<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={s.spin}><path d="M12 3a9 9 0 1 0 9 9" strokeLinecap="round"/></svg>:<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>}
        <span>{isRunning?'Investigating':'Investigate'}</span>
      </button>
    </div>
  </div></div>);
}