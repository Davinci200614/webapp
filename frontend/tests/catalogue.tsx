import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {Script,runInNewContext} from 'node:vm';
import {renderToStaticMarkup} from 'react-dom/server';
import {OriginalSite} from '../src/machinati/OriginalSite';

async function main(){
 const base='public/assets/machinati/';
 const manifest=JSON.parse(readFileSync(base+'source-manifest.json','utf8'));
 for(const kind of ['catalogue','cooperative','operations']){
  const html=readFileSync(base+kind+'.html','utf8');
  const css=html.match(/<style>([\s\S]*?)<\/style>/)![1];
  assert.equal(createHash('sha256').update(css).digest('hex'),manifest[kind].original_style_sha256,kind+' original CSS changed');
  assert.ok(!html.includes('get("apiBaseUrl")'));
  for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new Script(match[1]);
  if(kind!=='catalogue')assert.ok(html.includes('data-operator="true"'));
 }
 const catalogue=readFileSync(base+'catalogue.html','utf8');
 assert.ok(catalogue.includes('id="heroTitle"'));assert.ok(catalogue.includes('id="categoryFilters"'));
 assert.ok(catalogue.includes('classList.toggle("open", expanded)'));
 assert.ok(catalogue.includes('!machine.reserved_for_own_use'));
 assert.ok(catalogue.includes('window.machinatiWhatsApp'));
 assert.ok(catalogue.includes('Durée (heures)'));
 assert.ok(readFileSync(base+'operations.html','utf8').includes('selectedRequestId = null;'));
 assert.ok(readFileSync(base+'cooperative.html','utf8').includes('Gérer les machines'));
 Object.assign(globalThis,{window:{location:{search:'',hash:''}}});
 const props={role:'',checking:false,login:<form>Credentials required</form>,onLogout:()=>{}};
 const publicHtml=renderToStaticMarkup(<OriginalSite {...props} page="/"/>);
 assert.ok(publicHtml.includes('src="/assets/machinati/catalogue.html"'));
 for(const page of ['/cooperative','/operations','/requests'] as const){
  const html=renderToStaticMarkup(<OriginalSite {...props} page={page}/>);
  assert.ok(html.includes('Credentials required'));assert.ok(!html.includes('<iframe'));assert.ok(!html.includes('Toutes les demandes'));
 }
 assert.ok(renderToStaticMarkup(<OriginalSite {...props} role="operator" page="/cooperative"/>).includes('src="/assets/machinati/cooperative.html"'));
 assert.ok(renderToStaticMarkup(<OriginalSite {...props} role="operator" page="/requests"/>).includes('Comparaison')===false); // No invented requests in empty queue.
 const bridge=readFileSync(base+'bridge.js','utf8');
 async function boot(privatePage:boolean,token:string|null,status=200){
  const calls:any[]=[],redirects:string[]=[];let stored=token;
  const document={documentElement:{dataset:{operator:String(privatePage),loginPath:'/operations'},classList:{remove:()=>{}}},body:{textContent:''},addEventListener:()=>{}};
  const window:any={sessionStorage:null,top:{location:{assign:(value:string)=>redirects.push(value)}},fetch:async(input:any,init:any={})=>{
   calls.push({input,init});const auth=String(input).endsWith('/auth/me');return {ok:!auth||status===200,status:auth?status:200,json:async()=>({whatsapp_number:'212 600 000 000'})};
  }};
  runInNewContext(bridge,{window,document,URL,Headers,Request,location:{href:'https://local.test/assets/machinati/catalogue.html',origin:'https://local.test'},sessionStorage:{getItem:()=>stored,removeItem:()=>{stored=null;}}});
  await window.machinatiReady;return {window,calls,redirects};
 }
 const absent=await boot(true,null,401);assert.deepEqual(absent.redirects,['/operations']);assert.equal(absent.calls.length,1);
 const demo=await boot(true,null,200);assert.equal(demo.redirects.length,0);assert.equal(demo.calls.length,1);
 const expired=await boot(true,'expired',401);assert.deepEqual(expired.redirects,['/operations']);
 const valid=await boot(true,'session-secret');
 await valid.window.fetch('/api/requests');assert.equal(valid.calls.at(-1).init.headers.get('Authorization'),'Bearer session-secret');
 await valid.window.fetch('https://other.test/api/requests');assert.equal(valid.calls.at(-1).init.headers,undefined);
 await valid.window.fetch(new URL('https://other.test/api/requests'));assert.equal(valid.calls.at(-1).init.headers,undefined);
 const publicBoot=await boot(false,null);assert.equal(publicBoot.window.machinatiWhatsApp,'212600000000');
 console.log('Original page CSS, script syntax, login gates, session expiry, same-origin authorization and integration fixes passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
