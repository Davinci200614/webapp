import {useState} from 'react';
import {apiBaseUrl,apiRequest,errorMessage} from '../shared/api';
import type {RequestRow} from '../shared/types';
export function RequestReview({request,admin,onSaved}:{request:RequestRow;admin:boolean;onSaved:()=>Promise<void>}){
 const [note,setNote]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function act(path:string,body:object){setBusy(true);setError('');try{await apiRequest(path,{method:(path.endsWith('more-information')||path.endsWith('/retry'))?'POST':'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await onSaved();}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function download(id:number){setError('');try{const response=await fetch(`${apiBaseUrl}/api/request-documents/${id}`,{headers:{Authorization:`Bearer ${sessionStorage.getItem('webapp_api_token')||''}`}});if(!response.ok)throw new Error('Téléchargement refusé');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=`document-${id}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError(errorMessage(e))}}
 return <div style={{minWidth:230}}>{error&&<p role="alert">{error}</p>}
 <p>{request.payload.name} · {request.payload.resource_kind==='worker'?'Personnel':'Matériel'}</p>
 {request.payload.notes&&<p>{request.payload.notes}</p>}
 {request.review_state==='needs_information'&&<p>Complément demandé : {request.review_note}</p>}
 {request.allocation_state==='waiting'&&<strong>Liste prioritaire</strong>}{request.allocation&&<p>Affecté : {request.allocation.resource_name}</p>}
 {request.reviews?.map((r,i)=><small key={i}>{r.decision} · {r.note}</small>)}
 {request.notification&&<p>Notification WhatsApp : {({sent:'Acceptée par Meta',pending:'En attente',sending:'Envoi en cours',waiting_for_client:'En attente du client ou d’un modèle Meta approuvé',failed:'Échec de l’envoi'} as Record<string,string>)[request.notification.state]||request.notification.state}{admin&&['failed','waiting_for_client'].includes(request.notification.state)&&<button disabled={busy} onClick={()=>void act(`/api/requests/${request.id}/notifications/retry`,{})}>Réessayer l’envoi</button>}</p>}
 {request.documents?.map(d=><div key={d.id}><small>{d.name} · {d.assessment} · {d.note}</small>{admin&&<><button disabled={busy} onClick={()=>void download(d.id)}>Consulter la pièce</button><button disabled={busy} onClick={()=>void act(`/api/request-documents/${d.id}`,{assessment:'accepted',note})}>Pièce vérifiée</button><button disabled={busy} onClick={()=>void act(`/api/request-documents/${d.id}`,{assessment:'rejected',note})}>Pièce refusée</button></>}</div>)}
 {admin&&<><label>Motif / informations ou documents demandés<textarea value={note} maxLength={2000} onChange={e=>setNote(e.target.value)}/></label>
 {request.status==='pending_review'&&<div className="actions"><button disabled={busy} onClick={()=>void act(`/api/requests/${request.id}/status`,{status:'approved',note})}>Approuver et affecter</button><button disabled={busy||!note.trim()} onClick={()=>void act(`/api/requests/${request.id}/status`,{status:'rejected',note})}>Refuser</button><button disabled={busy||!note.trim()} onClick={()=>void act(`/api/requests/${request.id}/more-information`,{note})}>Demander un complément</button></div>}
 {request.status==='approved'&&<div className="actions"><button disabled={busy} onClick={()=>void act(`/api/requests/${request.id}/status`,{status:'completed',note})}>Terminer / libérer</button><button disabled={busy||!note.trim()} onClick={()=>void act(`/api/requests/${request.id}/status`,{status:'rejected',note})}>Annuler / libérer</button></div>}</>}
 </div>
}
