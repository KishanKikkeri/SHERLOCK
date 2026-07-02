import{useCallback,useRef,useState}from'react';
import{createInvestigationSocket}from'../lib/api';
import{AGENT_PIPELINE,type AgentFinding,type AgentStep,type FeedEntry,type FinalReport,type InvestigationStatus,type WSEvent}from'../lib/types';

function buildInitialSteps():AgentStep[]{return AGENT_PIPELINE.map(a=>({name:a.name,nodeKey:a.nodeKey,status:'pending',message:null,timestamp:null,findings:[]}));}

export interface InvestigationState{status:InvestigationStatus;query:string;steps:AgentStep[];feed:FeedEntry[];allFindings:AgentFinding[];validatedFindings:AgentFinding[];finalReport:FinalReport|null;graphPersonId:number|null;graphHubPersonId:number|null;clusterData:Array<{district:string;crime_type:string;month:number;count:number}>;auditTrail:{agent:string;status:string;message:string}[];elapsedMs:number;}
export interface InvestigationActions{start:(query:string)=>void;reset:()=>void;}

const INIT:Omit<InvestigationState,'query'>={status:'idle',steps:buildInitialSteps(),feed:[],allFindings:[],validatedFindings:[],finalReport:null,graphPersonId:null,graphHubPersonId:null,clusterData:[],auditTrail:[],elapsedMs:0};

export function useInvestigation():[InvestigationState,InvestigationActions]{
  const[state,setState]=useState<InvestigationState>({...INIT,query:''});
  const wsRef=useRef<WebSocket|null>(null);
  const t0Ref=useRef<number>(0);
  const timerRef=useRef<ReturnType<typeof setInterval>|null>(null);
  const stopTimer=useCallback(()=>{if(timerRef.current){clearInterval(timerRef.current);timerRef.current=null;}},[]);

  const handleEvent=useCallback((event:WSEvent)=>{
    setState(prev=>{
      const next={...prev};
      const ts=new Date(event.timestamp).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
      if(event.event_type!=='report_ready'){
        next.feed=[...prev.feed,{id:`${event.timestamp}-${Math.random()}`,timestamp:ts,agent:event.agent??'System',status:event.event_type==='agent_skipped'?'skipped':event.event_type==='error'?'error':event.event_type==='investigation_started'?'started':'done',message:event.message??''}];
      }
      if(['agent_completed','agent_skipped'].includes(event.event_type)){
        next.auditTrail=[...prev.auditTrail,{agent:event.agent??'',status:event.event_type==='agent_skipped'?'skipped':'done',message:event.message??''}];
        next.steps=prev.steps.map(s=>s.name!==event.agent?s:{...s,status:event.event_type==='agent_skipped'?'skipped':'complete',message:event.message??null,timestamp:ts,findings:event.data?.new_findings??[]});
        const ci=next.steps.findIndex(s=>s.name===event.agent);
        if(ci>=0){const ni=next.steps.findIndex((s,i)=>i>ci&&s.status==='pending');if(ni>=0)next.steps=next.steps.map((s,i)=>i===ni?{...s,status:'running'}:s);}
      }
      if(event.event_type==='investigation_started')next.steps=next.steps.map((s,i)=>i===0?{...s,status:'running'}:s);
      const nf=event.data?.new_findings??[];
      if(nf.length){
        next.allFindings=[...prev.allFindings,...nf];
        const rf=nf.find(f=>f.finding_type==='repeat_offender_network');
        if(rf?.metadata?.repeat_offenders&&!prev.graphPersonId){const ros=rf.metadata.repeat_offenders as Array<{person_id:number}>;if(ros[0]?.person_id)next.graphPersonId=ros[0].person_id;}
        const ff=nf.find(f=>f.finding_type==='financial_network');
        if(ff?.metadata?.hub_person_id&&!prev.graphHubPersonId)next.graphHubPersonId=ff.metadata.hub_person_id as number;
        const pf=nf.find(f=>f.finding_type==='crime_pattern');
        if(pf?.metadata?.clusters)next.clusterData=pf.metadata.clusters as typeof next.clusterData;
      }
      if(event.data?.validated_findings)next.validatedFindings=event.data.validated_findings;
      if(event.event_type==='report_ready'&&event.data?.final_report){next.finalReport=event.data.final_report;next.status='complete';next.steps=next.steps.map(s=>s.status==='pending'||s.status==='running'?{...s,status:'complete'}:s);}
      if(event.event_type==='error')next.status='error';
      return next;
    });
  },[]);

  const start=useCallback((query:string)=>{
    if(wsRef.current){wsRef.current.close();wsRef.current=null;}
    stopTimer();
    setState({...INIT,steps:buildInitialSteps(),status:'running',query});
    t0Ref.current=Date.now();
    timerRef.current=setInterval(()=>setState(p=>({...p,elapsedMs:Date.now()-t0Ref.current})),100);
    wsRef.current=createInvestigationSocket(query,handleEvent,()=>{stopTimer();setState(p=>p.status==='running'?{...p,status:'error'}:p);},msg=>{stopTimer();setState(p=>({...p,status:'error',feed:[...p.feed,{id:`err-${Date.now()}`,timestamp:new Date().toLocaleTimeString(),agent:'System',status:'error',message:msg}]}));});
  },[handleEvent,stopTimer]);

  const reset=useCallback(()=>{if(wsRef.current){wsRef.current.close();wsRef.current=null;}stopTimer();setState({...INIT,steps:buildInitialSteps(),query:''});},[stopTimer]);

  return[state,{start,reset}];
}
