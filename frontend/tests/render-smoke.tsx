import {renderToStaticMarkup} from 'react-dom/server';
import {App} from '../src/App';
import {Catalogue} from '../src/pages/Catalogue';
import {Inventory} from '../src/pages/Inventory';
import {Operations} from '../src/pages/Operations';
import {Directory} from '../src/pages/Directory';
import type {MachineRow,RequestRow} from '../src/shared/types';
const storage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
Object.assign(globalThis,{sessionStorage:storage,window:{location:{pathname:'/',search:''},sessionStorage:storage,localStorage:storage}});
const routes=['/','/cooperative','/operations','/requests','/machines','/employment','/inspect','/privacy','/terms','/data-deletion'];
for(const path of routes){window.location.pathname=path;const html=renderToStaticMarkup(<App/>);if(!html.length||html.includes('undefined'))throw new Error(`Invalid page: ${path}`);}
const machine:MachineRow={id:1,name:'Tractor A',machine_type:'tractor',location:'Meknes',hourly_rate:150,available:1,owner_type:'partner',reserved_for_own_use:0,available_from:'2099-01-01',available_to:'2099-12-31',compatibility_notes:'Transport à vérifier'};
const request:RequestRow={id:1,farmer_phone:'test-number',status:'pending_review',created_at:'2099-01-01 00:00:00',updated_at:'2099-01-01 00:00:00',priority_score:40,priority_reason:'Declared urgency',machine_fit:'local',machine_fit_reason:'Matching machine',matching_machines:[machine],payload:{machine_type:'tractor',operation:'plowing',area_hectares:2,location:'Meknes',preferred_date:'2099-01-10'}};
for(const view of [<Catalogue machines={[machine]} whatsapp="212600000000"/>,<Inventory machines={[machine]} admin onSaved={async()=>{}}/>,<Operations requests={[request]} machines={[machine]}/>,<Operations requests={[{...request,status:'approved'}]} machines={[machine]} cooperative/>,<Directory operator whatsapp="212600000000"/>]){
 const html=renderToStaticMarkup(view);if(!html.length||html.includes('undefined'))throw new Error('Invalid populated view');
}
console.log(`Rendered ${routes.length} routes and 5 populated views successfully.`);
