import {useEffect,useState,type ReactNode} from 'react';
import {Tractor,CalendarDays,Users} from 'lucide-react';
import {RequestsDashboard} from './RequestsDashboard';
import './original.css';
import './integration.css';

type Page='/'|'/cooperative'|'/operations'|'/requests';
export function OriginalSite({page,role,checking,login,onLogout}:{page:Page;role:string;checking:boolean;login:ReactNode;onLogout:()=>void}){
 const [section,setSection]=useState(()=>page==='/requests'||new URLSearchParams(window.location.search).get('section')!=='overview'?'requests':'overview');
 function selectSection(next:string){const url=new URL(window.location.href);url.searchParams.set('section',next);window.history.pushState(null,'',url);setSection(next);}
 useEffect(()=>{const sync=()=>setSection(new URLSearchParams(window.location.search).get('section')==='overview'?'overview':'requests');window.addEventListener('popstate',sync);return()=>window.removeEventListener('popstate',sync);},[]);
 const operations=page==='/operations'||page==='/requests';
 const privatePage=page!=='/';
 return <div className="machinati-original"><div className="integrated-app">
  <header className="integrated-nav"><a className="integrated-brand" href="/"><span className="integrated-logo">M.</span> MACHINATI</a><nav aria-label="Navigation principale">
   <a className={page==='/'?'active':''} href="/"><Tractor size={16}/> Catalogue</a>
   <a className={page==='/cooperative'?'active':''} href="/cooperative"><Users size={16}/> Coopérative</a>
   <a className={operations?'active':''} href="/operations"><CalendarDays size={16}/> Opérations</a>
   {role&&<button onClick={onLogout}>Déconnexion</button>}
  </nav></header>
  <div className="integrated-content">
   {privatePage&&checking?<div className="login-wrap" role="status">Vérification de la session…</div>:privatePage&&!role?<div className="login-wrap"><section className="panel login-panel"><p className="eyebrow">ESPACE OPÉRATEUR</p><h1>Connexion opérateur</h1><p className="muted">Connectez-vous pour accéder aux demandes et aux outils de gestion.</p>{login}</section></div>:operations?<div className="operations-workspace"><nav className="operations-tabs" aria-label="Vues des opérations"><button className={section==='requests'?'active':''} aria-pressed={section==='requests'} onClick={()=>selectSection('requests')}>Demandes</button><button className={section==='overview'?'active':''} aria-pressed={section==='overview'} onClick={()=>selectSection('overview')}>Pilotage</button><a href="/machines">Gestion du matériel</a></nav><div className="operations-body">{section==='requests'?<RequestsDashboard/>:<iframe className="operations-frame" title="Équipe opérations" src="/assets/machinati/operations.html?panel=overview"/>}</div></div>:<iframe key={page} className="integrated-frame" title={page==='/'?'Catalogue Machinati':'Espace coopérative'} src={`/assets/machinati/${page==='/'?'catalogue':'cooperative'}.html${page==='/cooperative'?window.location.hash:''}`}/>}
  </div>
 </div></div>;
}
