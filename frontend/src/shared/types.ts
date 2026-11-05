export type MachineRow = {
 id:number; name:string; machine_type:string; location:string|null; hourly_rate:number|null;
 is_allocated?:number|boolean; available:number|boolean; owner_type:'company'|'partner'; reserved_for_own_use:number|boolean;
 available_from:string|null; available_to:string|null; compatibility_notes:string|null; is_demo?:number;
};
export type RequestRow = {
 id:number; farmer_phone:string; status:string; created_at:string; updated_at:string;
 document_checklist?:string; notification?:{id:number;state:string;error:string|null;sent_at:string|null}|null;
 review_state?:string; review_note?:string; allocation_state?:string;
 documents?:{id:number;name:string;assessment:string;note:string}[];
 reviews?:{decision:string;note:string;created_at:string}[];
 allocation?:{resource_kind:string;resource_id:number;resource_name:string}|null;
 priority_score:number; priority_reason:string;
 machine_fit:'local'|'transport-review'|'date-review'|'unavailable'|'not_specified';
 machine_fit_reason:string; matching_machines:MachineRow[];
 payload:{name?:string;resource_kind?:string;intent?:string;machine_type?:string;operation?:string;area_hectares?:number;location?:string;
 preferred_date?:string;preferred_date_text?:string;urgency_level?:'normal'|'urgent'|'critical'|null;
 urgency_reason?:string;verified_by?:string|null;notes?:string};
};
export type Listing = {id:number;kind:'worker'|'job';name:string;location:string;work:string;details:string;contact:string;is_demo:number;created_at:string};
