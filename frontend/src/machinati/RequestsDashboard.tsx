import { useEffect, useState } from 'react';
import {
  Tractor,
  LayoutDashboard,
  CalendarDays,
  Users,
  MessageCircle,
  RefreshCw,
  CheckCircle2,
  ShieldCheck,
  Clock,
  Search,
} from 'lucide-react';
import {RequestReview} from './RequestReview';
import { apiRequest, errorMessage } from '../shared/api';
import type { MachineRow, RequestRow } from '../shared/types';

type DashboardView = 'requests' | 'machines';

const statusText: Record<string, string> = {
  draft: 'Brouillon',
  pending_review: 'À examiner',
  approved: 'Approuvée',
  rejected: 'Refusée',
  completed: 'Terminée',
};

export function RequestsDashboard({admin=false}:{admin?:boolean}) {
  const [items, setItems] = useState<RequestRow[]>([]);
  const [machines, setMachines] = useState<MachineRow[]>([]);
  const [errors, setErrors] = useState({ requests: '', machines: '' });
  const [view, setView] = useState<DashboardView>('requests');
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [reviewer, setReviewer] = useState('');
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    const [requestResult, machineResult] = await Promise.allSettled([
      apiRequest<RequestRow[]>('/api/requests'),
      apiRequest<MachineRow[]>('/api/machines'),
    ]);

    if (requestResult.status === 'fulfilled') {
      setItems(requestResult.value);
      setErrors(current => ({ ...current, requests: '' }));
    } else {
      setErrors(current => ({ ...current, requests: errorMessage(requestResult.reason) }));
    }

    if (machineResult.status === 'fulfilled') {
      setMachines(machineResult.value);
      setErrors(current => ({ ...current, machines: '' }));
    } else {
      setErrors(current => ({ ...current, machines: errorMessage(machineResult.reason) }));
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, []);

  async function verifyUrgency(id: number) {
    if (!reviewer.trim()) {
      setErrors(current => ({ ...current, requests: 'Saisissez le nom du vérificateur.' }));
      return;
    }
    setBusy(id);
    try {
      await apiRequest(`/api/requests/${id}/urgency-verification`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: reviewer.trim() }),
      });
      await load();
    } catch (error) {
      setErrors(current => ({ ...current, requests: errorMessage(error) }));
    } finally {
      setBusy(null);
    }
  }

  const visibleRequests = items.filter(request =>
    (filter === 'all' || request.status === filter || (filter === 'waiting' && request.allocation_state === 'waiting') || (filter === 'needs_information' && request.review_state === 'needs_information')) &&
    `${request.farmer_phone} ${JSON.stringify(request.payload)}`.toLowerCase().includes(search.toLowerCase()),
  );
  const pendingRequests = visibleRequests.filter(request => request.status === 'pending_review');
  const [priorityLeader, nextPriority] = pendingRequests;
  const scoreDifference = priorityLeader && nextPriority
    ? priorityLeader.priority_score - nextPriority.priority_score
    : null;
  const visibleMachines = machines.filter(machine =>
    `${machine.name} ${machine.machine_type} ${machine.location || ''}`.toLowerCase().includes(search.toLowerCase()),
  );
  const pending = items.filter(request => request.status === 'pending_review').length;
  const approved = items.filter(request => request.status === 'approved').length;
  const availableMachines = machines.filter(machine => Boolean(machine.available) && !machine.reserved_for_own_use && !machine.is_allocated).length;
  const machineLocations = new Set(machines.map(machine => machine.location).filter(Boolean)).size;

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="logo">✳</span>
          <span>MACHINATI<small>Gestion coopérative</small></span>
        </div>
        <div className="nav">
          <button className={view === 'requests' ? 'active' : ''} onClick={() => setView('requests')}>
            <LayoutDashboard size={19} /> Demandes
          </button>
          <div><a href="/cooperative#planning"><CalendarDays size={19} /> Planning</a></div>
          <button className={view === 'machines' ? 'active' : ''} onClick={() => setView('machines')}>
            <Tractor size={19} /> Matériel
          </button>
          <div><Users size={19} /> Agriculteurs <small>Bientôt</small></div>
          <div><MessageCircle size={19} /> WhatsApp <small>Connecteur</small></div>
        </div>
        <div className="sidefoot"><a href="/machines">Gérer le matériel</a><br/><a href="/employment">Espace emploi</a></div>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">ESPACE COOPÉRATIVE</p>
            <h1>{view === 'requests' ? 'Demandes de matériel' : 'Parc matériel'}</h1>
            <p className="muted">
              {view === 'requests' ? 'Suivez les demandes web et WhatsApp' : 'Consultez le matériel enregistré dans la coopérative'}
            </p>
          </div>
          <button className="refresh" onClick={() => void load()}>
            <RefreshCw size={16} /> Actualiser
          </button>
        </header>

        {view === 'requests' ? (
          <>
            <section className="metrics">
              <article><div className="metricicon mint"><MessageCircle size={20} /></div><div><span>Demandes reçues</span><strong>{items.length}</strong></div></article>
              <article><div className="metricicon amber"><Clock size={20} /></div><div><span>À examiner</span><strong>{pending}</strong></div></article>
              <article><div className="metricicon blue"><CheckCircle2 size={20} /></div><div><span>Approuvées</span><strong>{approved}</strong></div></article>
            </section>

            <section className="panel">
              <div className="paneltop">
                <div><h2>Toutes les demandes</h2>{admin&&<button onClick={()=>{void apiRequest('/api/requests/dispatch',{method:'POST'}).then(load).catch(e=>setErrors(current=>({...current,requests:errorMessage(e)})))}}>Réaffecter la liste prioritaire</button>}<p className="muted">Validation des dossiers · affectation des ressources · liste prioritaire.</p></div>
                <div className="controls">
                  <label className="reviewer-input">Vérifié par <input maxLength={80} placeholder="Nom du vérificateur" value={reviewer} onChange={event => setReviewer(event.target.value)} /></label>
                  <label className="search"><Search size={16} /><input placeholder="Rechercher..." value={search} onChange={event => setSearch(event.target.value)} /></label>
                  <select value={filter} onChange={event => setFilter(event.target.value)}>
                    <option value="all">Tous les statuts</option><option value="waiting">Liste prioritaire</option><option value="needs_information">Complément demandé</option>
                    {Object.entries(statusText).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </div>
              </div>
              {errors.requests && <div className="error">{errors.requests} — Vérifiez la connexion au backend FastAPI.</div>}
              {priorityLeader && nextPriority && (
                <div className="paneltop" aria-live="polite">
                  <div>
                    <h2>Comparaison des priorités à examiner</h2>
                    <p className="muted">
                      {priorityLeader.payload.location || 'Localité à confirmer'} ({priorityLeader.priority_score} pts)
                      {' · '}
                      {nextPriority.payload.location || 'Localité à confirmer'} ({nextPriority.priority_score} pts)
                    </p>
                    <p className="muted">
                      {scoreDifference && scoreDifference > 0
                        ? `La première demande a ${scoreDifference} points de priorité en plus. `
                        : scoreDifference === 0
                          ? 'Score égal; le classement secondaire départage les demandes. '
                          : 'Le score demande une vérification du classement. '}
                      {priorityLeader.priority_reason}
                    </p>
                  </div>
                </div>
              )}
              <div className="tablewrap">
                <table>
                  <thead><tr><th>AGRICULTEUR</th><th>MACHINE / OPÉRATION</th><th>SURFACE</th><th>LOCALITÉ</th><th>DATE SOUHAITÉE</th><th>ADÉQUATION MATÉRIEL</th><th>URGENCE</th><th>PRIORITÉ</th><th>STATUT</th><th>ACTIONS</th></tr></thead>
                  <tbody>
                    {visibleRequests.map(request => (
                      <tr key={request.id}>
                        <td><div className="phone"><span className="avatar">{request.farmer_phone.slice(-2)}</span>{request.farmer_phone}</div></td>
                        <td><b>{request.payload.machine_type || 'Non précisé'}</b><small>{request.payload.operation || '—'}</small></td>
                        <td>{request.payload.area_hectares ?? '—'} ha</td>
                        <td>{request.payload.location || '—'}</td>
                        <td>{request.payload.preferred_date || request.payload.preferred_date_text || '—'}</td>
                        <td>
                          <div className="machine-fit">
                            <span className={`machine-fit-badge ${{local:'match','transport-review':'transport_review','date-review':'date_review',unavailable:'unavailable',not_specified:'not_specified'}[request.machine_fit]}`}>
                              {request.machine_fit === 'local' ? 'Machine fit' : request.machine_fit === 'transport-review' ? 'Transport à vérifier' : request.machine_fit === 'date-review' ? 'Date à vérifier' : request.machine_fit === 'unavailable' ? 'Non disponible' : 'À préciser'}
                            </span>
                            <small>{request.machine_fit_reason}</small>
                            {request.matching_machines.map(machine => (
                              <small key={machine.id}>{machine.name} · {machine.location || 'Localité à confirmer'}{machine.compatibility_notes ? ` · ${machine.compatibility_notes}` : ''}</small>
                            ))}
                          </div>
                        </td>
                        <td>
                          <div className="urgency-review">
                            <span className={`urgency-badge ${request.payload.urgency_level || 'unknown'}`}>
                              {request.payload.urgency_level === 'critical' ? 'Critique' : request.payload.urgency_level === 'urgent' ? 'Urgente' : request.payload.urgency_level === 'normal' ? 'Normale / flexible' : 'À préciser'}
                            </span>
                            {request.payload.urgency_reason && <small>{request.payload.urgency_reason}</small>}
                            {request.payload.urgency_level && ['urgent', 'critical'].includes(request.payload.urgency_level) && admin && request.status === 'pending_review' && (
                              request.payload.verified_by ? (
                                <small className="verified-by"><ShieldCheck size={13} /> Validée par {request.payload.verified_by}</small>
                              ) : (
                                <button className="verify-urgency" disabled={busy === request.id || !reviewer.trim()} onClick={() => void verifyUrgency(request.id)}>
                                  <ShieldCheck size={14} /> Valider l'urgence
                                </button>
                              )
                            )}
                          </div>
                        </td>
                        <td><strong className="priority-score">{request.priority_score}</strong><small>{request.priority_reason}</small></td>
                        <td><span className={`status ${request.status}`}>{statusText[request.status] || request.status}</span></td>
                        <td>
                          <RequestReview request={request} admin={admin} onSaved={load}/>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!visibleRequests.length && <div className="empty"><Tractor size={36} /><h3>Aucune demande à afficher</h3><p>Les demandes web et WhatsApp apparaîtront ici après réception.</p></div>}
              </div>
            </section>
          </>
        ) : (
          <>
            <section className="metrics">
              <article><div className="metricicon mint"><Tractor size={20} /></div><div><span>Matériels enregistrés</span><strong>{machines.length}</strong></div></article>
              <article><div className="metricicon amber"><CheckCircle2 size={20} /></div><div><span>Disponibles</span><strong>{availableMachines}</strong></div></article>
              <article><div className="metricicon blue"><Users size={20} /></div><div><span>Localités</span><strong>{machineLocations}</strong></div></article>
            </section>

            <section className="panel">
              <div className="paneltop">
                <div><h2>Matériel de la coopérative</h2><p className="muted">Disponibilité illustrative · tarifs horaires indicatifs</p></div>
                <label className="search"><Search size={16} /><input placeholder="Rechercher..." value={search} onChange={event => setSearch(event.target.value)} /></label>
              </div>
              {errors.machines && <div className="error">{errors.machines} — Vérifiez la connexion au backend FastAPI.</div>}
              <div className="tablewrap">
                <table>
                  <thead><tr><th>MATÉRIEL</th><th>TYPE</th><th>LOCALITÉ</th><th>PROPRIÉTAIRE</th><th>USAGE PROPRE</th><th>FENÊTRE DE DISPONIBILITÉ</th><th>NOTES</th><th>TARIF HORAIRE</th><th>DISPONIBILITÉ</th></tr></thead>
                  <tbody>
                    {visibleMachines.map(machine => (
                      <tr key={machine.id}>
                        <td><b>{machine.name}</b></td>
                        <td>{machine.machine_type}</td>
                        <td>{machine.location || '—'}</td>
                        <td>{machine.owner_type === 'partner' ? 'Partenaire' : 'Coopérative'}</td>
                        <td>{machine.reserved_for_own_use ? 'Réservé' : 'Non réservé'}</td>
                        <td>{machine.available_from || machine.available_to ? `${machine.available_from || '…'} → ${machine.available_to || '…'}` : 'À confirmer'}</td>
                        <td>{machine.compatibility_notes || '—'}</td>
                        <td>{machine.hourly_rate == null ? '—' : `${machine.hourly_rate} / h`}</td>
                        <td><span className={`status ${machine.available && !machine.reserved_for_own_use && !machine.is_allocated ? 'approved' : 'rejected'}`}>{machine.available && !machine.reserved_for_own_use && !machine.is_allocated ? 'Disponible' : 'Indisponible'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!visibleMachines.length && <div className="empty"><Tractor size={36} /><h3>Aucun matériel à afficher</h3><p>Le matériel enregistré apparaîtra ici.</p></div>}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}