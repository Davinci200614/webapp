import {useState, type FormEvent} from 'react';
import {apiRequest, errorMessage} from '../shared/api';
import type {RequestRow} from '../shared/types';

export function Apply(){
 const [id,setId]=useState(sessionStorage.getItem('application_id')||'');
 const [code,setCode]=useState(sessionStorage.getItem('application_code')||'');
 const [item,setItem]=useState<RequestRow|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const [kind,setKind]=useState('machine'),[files,setFiles]=useState<File[]>([]);
 const headers={'X-Request-Token':code};
 async function load(requestId=id,token=code){const data=await apiRequest<RequestRow>(`/api/applications/${requestId}`,{headers:{'X-Request-Token':token}});setItem(data);sessionStorage.setItem('application_id',requestId);sessionStorage.setItem('application_code',token);}
 async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();setBusy(true);setError('');try{const form=new FormData(event.currentTarget);const payload=Object.fromEntries(form.entries());const result=await apiRequest<{id:number;tracking_code:string}>('/api/applications',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,whatsapp_updates:form.get('whatsapp_updates')==='on',area_hectares:form.get('area_hectares')?Number(form.get('area_hectares')):null})});setId(String(result.id));setCode(result.tracking_code);await load(String(result.id),result.tracking_code);setMessage('Demande envoyée. Conservez votre numéro et votre code privé.');}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function upload(){setBusy(true);setError('');try{for(const file of files){if(file.size>5*1024*1024)throw new Error('Chaque document doit faire au maximum 5 Mo.');await apiRequest(`/api/applications/${id}/documents`,{method:'POST',headers:{...headers,'X-Filename':encodeURIComponent(file.name),'Content-Type':file.type},body:file});setFiles(current=>current.filter(pending=>pending!==file));}setFiles([]);await load();setMessage('Documents envoyés. Ajoutez un complément pour soumettre votre réponse à l’administrateur.');}catch(e){setError(errorMessage(e));await load().catch(()=>{})}finally{setBusy(false)}}
 async function removeDocument(documentId:number){setBusy(true);setError('');try{await apiRequest(`/api/applications/${id}/documents/${documentId}`,{method:'DELETE',headers});await load();}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function supplement(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;setBusy(true);setError('');try{await apiRequest(`/api/applications/${id}/information`,{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({information:new FormData(form).get('information')})});form.reset();await load();setMessage('Complément envoyé pour examen.');}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 return <section className="panel padded"><h2>Demande en ligne</h2><p>Demandez du matériel ou du personnel sans WhatsApp. L’administrateur examine votre dossier avant toute affectation.</p>{error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
 {!item&&<form className="field-grid" onSubmit={create}>
 <label>Nom complet<input name="name" required maxLength={120}/></label><label>Téléphone<input name="phone" required pattern="\+?[0-9]{8,15}" placeholder="+212600000000"/></label>
 <label>Besoin<select name="resource_kind" value={kind} onChange={e=>setKind(e.target.value)}><option value="machine">Matériel / tracteur</option><option value="worker">Personnel</option></select></label>
 {kind==='machine'&&<label>Type de matériel<input name="machine_type" required maxLength={120} placeholder="Tracteur"/></label>}
 <label>Travail / compétence recherchée<input name="operation" required maxLength={120} placeholder="Labour"/></label><label>Localité<input name="location" required maxLength={160}/></label>
 <label>Date souhaitée<input name="preferred_date" type="date" required/></label><label>Surface (ha)<input name="area_hectares" type="number" min="0.01" step="any"/></label>
 <label>Urgence<select name="urgency_level"><option value="normal">Normale</option><option value="urgent">Urgente</option><option value="critical">Critique</option></select></label>
 <label className="check"><input name="whatsapp_updates" type="checkbox" defaultChecked/>Recevoir sur WhatsApp la liste initiale et les demandes de pièces de l’administrateur.</label><label>Informations complémentaires<textarea name="notes" maxLength={3000}/></label><button disabled={busy}>Envoyer la demande</button></form>}
 <hr/><h2>Suivre ma demande</h2><p>Gardez ce code privé : il permet d’accéder au dossier et d’envoyer des documents. Conservez-le pour retrouver votre demande sur un autre appareil.</p>
 <form className="field-grid" onSubmit={e=>{e.preventDefault();setError('');setBusy(true);void load().catch(e=>setError(errorMessage(e))).finally(()=>setBusy(false))}}><label>Numéro de demande<input required type="number" min="1" value={id} onChange={e=>{setId(e.target.value);setItem(null)}}/></label><label>Code privé<input required autoComplete="off" value={code} onChange={e=>{setCode(e.target.value);setItem(null)}}/></label><button disabled={busy}>Consulter / actualiser</button></form>
 {item&&<><h3>Demande #{item.id}</h3><p>Statut : {item.status==='approved'?'Approuvée':item.status==='rejected'?'Refusée':item.status==='completed'?'Terminée':item.review_state==='needs_information'?'Complément demandé':'En cours d’examen'}</p>
 {item.allocation_state==='waiting'&&<p>Votre demande approuvée est sur la liste prioritaire. Aucun matériel ou personnel compatible n’est disponible actuellement.</p>}
 {item.allocation&&<p>Affectation : {item.allocation.resource_name}. La coopérative coordonnera l’intervention avec vous.</p>}
 {item.reviews?.map((r,i)=><p key={i}>{r.created_at} · {r.decision} : {r.note||'Décision enregistrée'}</p>)}
 <h3>Documents justificatifs</h3>{item.document_checklist&&<p dir="auto" style={{whiteSpace:'pre-wrap'}}>{item.document_checklist}</p>}<p>PDF, JPEG ou PNG · 5 Mo par fichier · 10 fichiers maximum. Les pièces et leurs noms sont transmis à l’administrateur. Leur contenu n’est pas analysé par l’IA ; seul l’administrateur examine leur authenticité.</p>
 <ul>{item.documents?.map(d=><li key={d.id}>{d.name} · {d.assessment} {d.note}{item.status==='pending_review'&&d.assessment!=='accepted'&&<button disabled={busy} onClick={()=>void removeDocument(d.id)}>Retirer / remplacer</button>}</li>)}</ul>
 {item.status==='pending_review'&&<><label>Ajouter des documents<input type="file" multiple accept=".pdf,.png,.jpg,.jpeg" onChange={e=>setFiles(Array.from(e.target.files||[]))}/></label><button type="button" disabled={busy||!files.length} onClick={()=>void upload()}>Envoyer les documents</button>
 <form className="field-grid" onSubmit={supplement}><label>Répondre / compléter le dossier<textarea name="information" required maxLength={3000}/></label><button disabled={busy}>Soumettre le complément</button></form></>}
 <button onClick={()=>{setItem(null);setId('');setCode('');setMessage('');sessionStorage.removeItem('application_id');sessionStorage.removeItem('application_code')}}>Nouvelle demande</button></>}
 </section>
}
