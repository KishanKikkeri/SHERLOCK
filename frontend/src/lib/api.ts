import type{GraphData,Metrics,FinalReport,WSEvent}from'./types';
const BASE=import.meta.env.VITE_API_URL??'http://localhost:8000';
const WS_BASE=BASE.replace(/^http/,'ws');
export async function fetchMetrics():Promise<Metrics>{const r=await fetch(`${BASE}/metrics`);return r.json();}
export async function fetchSubgraph(personId:number,hops=1):Promise<GraphData>{const r=await fetch(`${BASE}/graph/${personId}?hops=${hops}`);return r.json();}
export async function exportPDF(finalReport:FinalReport,auditTrail:{agent:string;status:string;message:string}[],caseId:string):Promise<Blob>{
  const r=await fetch(`${BASE}/export/pdf`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({final_report:finalReport,audit_trail:auditTrail,case_id:caseId})});
  return r.blob();
}
export function downloadBlob(blob:Blob,filename:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url);}
export function createInvestigationSocket(query:string,onEvent:(e:WSEvent)=>void,onClose:()=>void,onError:(m:string)=>void):WebSocket{
  const ws=new WebSocket(`${WS_BASE}/ws/investigate`);
  ws.onopen=()=>ws.send(JSON.stringify({query}));
  ws.onmessage=(msg)=>{try{onEvent(JSON.parse(msg.data));}catch(e){onError(`Parse error: ${e}`);}};
  ws.onclose=()=>onClose();
  ws.onerror=()=>{onError('WebSocket error — is the SHERLOCK backend running on port 8000?');onClose();};
  return ws;
}