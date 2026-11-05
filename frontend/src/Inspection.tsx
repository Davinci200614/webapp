import {useEffect,useState} from 'react';
import './inspection.css';
import {apiRequest} from './shared/api';

type ChatMessage={id:string;farmer_phone:string;kind:string;text:string|null;reply:string|null;status:string;error:string|null;error_code:string|null;route:string|null;duration_ms:number|null;created_at:string};
type Snapshot={database_path:string;schema_version:number;counts:Record<string,number>;messages:ChatMessage[];drafts:unknown[];listings:unknown[];machines:unknown[];requests:unknown[];catalog:unknown[]};
export function Inspection(){
 const [data,setData]=useState<Snapshot|null>(null),[error,setError]=useState(''),[phone,setPhone]=useState(''),[filter,setFilter]=useState(''),[tab,setTab]=useState<'messages'|'drafts'|'listings'|'machines'|'requests'|'catalog'>('messages');
 async function load(){try{setData(await apiRequest<Snapshot>('/api/debug/snapshot'+(filter?'?phone='+encodeURIComponent(filter):'')));setError('')}catch(e){setError(String(e))}}
 useEffect(()=>{load();const timer=setInterval(load,5000);return()=>clearInterval(timer)},[filter]);
 return <section className="inspection"><a href="/">← Dashboard</a><header><div><h1>WhatsApp → database inspector</h1><p>Live local view · refreshes every 5 seconds</p></div><button onClick={load}>Refresh now</button></header>
 <InboxPanel/>
 <p className="inspection-note">An incoming message is stored before understanding. A draft is unfinished. A published listing or saved request appears only after confirmation. “processed” means the reply was handled; check the model error column too.</p>
 {error&&<p role="alert" className="inspection-error">{error}</p>}
 {data&&<><p><strong>Actual SQLite file:</strong> <code>{data.database_path}</code> · schema {data.schema_version}</p><div className="inspection-counts">{Object.entries(data.counts).map(([name,count])=><div key={name}><span>{name}</span><strong>{count}</strong></div>)}</div>
 <form onSubmit={e=>{e.preventDefault();setFilter(phone.trim())}}><label>Filter messages and drafts by exact sender <input value={phone} onChange={e=>setPhone(e.target.value)} placeholder="212…"/></label><button type="submit">Apply</button><button type="button" onClick={()=>{setPhone('');setFilter('')}}>All senders</button></form>
 <nav aria-label="Database tables">{(['messages','drafts','listings','machines','requests','catalog'] as const).map(name=><button key={name} aria-pressed={tab===name} onClick={()=>setTab(name)}>{name}</button>)}</nav>
 {tab==='messages'?<div className="inspection-table"><table><thead><tr><th>Time / sender</th><th>Incoming → reply</th><th>Persistence / understanding</th></tr></thead><tbody>{data.messages.map(message=><tr key={message.id}><td>{message.created_at}<br/><b>{message.farmer_phone}</b><small>{message.kind} · {message.id}</small></td><td><div dir="auto">{message.text||'—'}</div><blockquote dir="auto">{message.reply||'No stored reply yet'}</blockquote></td><td><b>{message.status}</b><p>{message.route||'No v2 audit (older message)'} {message.duration_ms!=null&&`· ${Math.round(message.duration_ms)} ms`}</p>{(message.error_code||message.error)&&<strong className="inspection-error">{message.error_code||message.error}</strong>}</td></tr>)}</tbody></table>{!data.messages.length&&<p>No matching stored messages yet. Send a WhatsApp message and refresh.</p>}</div>:<><p>{tab==='listings'||tab==='machines'?'is_demo: 1 marks fictional demo data. Demo contacts are not real.':''}</p>{data[tab].length?data[tab].map((row,index)=><pre key={index} dir="auto">{JSON.stringify(row,null,2)}</pre>):<p>No records in this view yet.</p>}</>}
 </>}
 </section>;
}


type InboxRow={id:string;state:string;attempts:number;error:string|null;created_at:string};
function InboxPanel(){
 const [rows,setRows]=useState<InboxRow[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){try{setRows(await apiRequest<InboxRow[]>('/api/debug/inbox'));setError('')}catch(e){setError(String(e))}}
 useEffect(()=>{void load();const timer=setInterval(()=>void load(),5000);return()=>clearInterval(timer)},[]);
 async function retry(id:string){setBusy(true);try{await apiRequest(`/api/debug/inbox/${encodeURIComponent(id)}/retry`,{method:'POST'});await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <details><summary>File de traitement WhatsApp ({rows.filter(r=>r.state==='failed').length} échecs)</summary>{error&&<p role="alert">{error}</p>}<div className="table-wrap"><table><thead><tr><th>Message</th><th>État</th><th>Essais</th><th>Erreur</th><th>Action</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.id}</td><td>{r.state}</td><td>{r.attempts}</td><td>{r.error||'—'}</td><td>{r.state==='failed'&&<button disabled={busy} onClick={()=>void retry(r.id)}>Réessayer</button>}</td></tr>)}</tbody></table></div></details>
}
