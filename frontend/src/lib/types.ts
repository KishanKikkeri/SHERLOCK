export type EventType = 'investigation_started'|'agent_completed'|'agent_skipped'|'report_ready'|'error';
export interface WSEvent{timestamp:string;event_type:EventType;agent:string|null;message:string|null;data:{new_findings?:AgentFinding[];validated_findings?:AgentFinding[]|null;final_report?:FinalReport|null;}|null;}
export interface AgentFinding{agent_name:string;finding_type:string;summary:string;evidence:string[];confidence:number;source_entities:string[];metadata:Record<string,unknown>;validated:boolean;validation_notes:string;}
export interface FinalReport{query:string;narrative:string;findings:AgentFinding[];rejected_findings:AgentFinding[];agents_consulted:string[];}
export type InvestigationStatus='idle'|'running'|'complete'|'error';
export type AgentStatus='pending'|'running'|'complete'|'skipped';
export interface AgentStep{name:string;nodeKey:string;status:AgentStatus;message:string|null;timestamp:string|null;findings:AgentFinding[];}
export interface FeedEntry{id:string;timestamp:string;agent:string;status:'done'|'skipped'|'started'|'error';message:string;}
export interface GraphNode{id:string;label:string;type:NodeType;data:Record<string,unknown>;}
export interface GraphEdge{source:string;target:string;type:string;}
export interface GraphData{nodes:GraphNode[];edges:GraphEdge[];center:string;}
export type NodeType='Person'|'Crime'|'FIR'|'Location'|'Vehicle'|'Phone'|'BankAccount'|'Transaction';
export interface Metrics{persons:number;crimes:number;firs:number;relationships:number;repeat_offenders:number;fraud_network_size:number;suspicious_transactions:number;}
export const PREVENTION_TYPES=new Set(['patrol_strategy','surveillance_action','prevention_recommendation']);
export const SKIP_TYPES=new Set(['patrol_strategy','surveillance_action','prevention_recommendation','validation_summary']);
export const AGENT_PIPELINE:{nodeKey:string;name:string}[]=[
  {nodeKey:'chief_plan',name:'Chief Investigation Officer — Planning'},
  {nodeKey:'crime_records',name:'Crime Records Agent'},
  {nodeKey:'network_analysis',name:'Network Analysis Agent'},
  {nodeKey:'entity_resolution',name:'Entity Resolution Agent'},
  {nodeKey:'timeline_reconstruction',name:'Timeline Reconstruction Agent'},
  {nodeKey:'financial_agent',name:'Financial Intelligence Agent'},
  {nodeKey:'similar_case',name:'Similar Case Agent'},
  {nodeKey:'pattern_analysis',name:'Pattern & MO Agent'},
  {nodeKey:'forecasting_agent',name:'Forecasting Agent'},
  {nodeKey:'prevention_agent',name:'Prevention Intelligence Agent'},
  {nodeKey:'evidence_validation',name:'Evidence Validation Agent'},
  {nodeKey:'chief_synthesis',name:'Chief Investigation Officer — Synthesis'},
];
// NOTE: every `name` above must be unique and match backend/api/investigation_stream.py's
// NODE_LABELS exactly — useInvestigation.ts matches incoming events to a step by this name,
// not by nodeKey (WSEvent only carries the display name, not the LangGraph node key).