// Compatibility export: the public site now renders the original document, not a recreation.
import {OriginalSite} from '../machinati/OriginalSite';
import type {MachineRow} from '../shared/types';
export function Catalogue(_props:{machines:MachineRow[];whatsapp:string;loading?:boolean;error?:string;onRefresh?:()=>void}){
 return <OriginalSite page="/" role="" checking={false} login={null} onLogout={()=>{}}/>;
}
