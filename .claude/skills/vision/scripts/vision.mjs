#!/usr/bin/env node
/* vision.mjs — Vision Skill (ref: penfick/skills/vision-support) */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline";
import { execSync } from "node:child_process";
import { createConnection } from "node:net";

const __f = fileURLToPath(import.meta.url);
const __d = dirname(__f);
const SKILL = resolve(__d, "..");
const MIME = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".bmp": "image/bmp",
  ".svg": "image/svg+xml"
};
const CAT = [
  { id: "openai", name: "OpenAI", fmt: "openai", url: "https://api.openai.com/v1", env: "OPENAI_API_KEY", mods: ["gpt-4o", "gpt-4o-mini"] },
  { id: "google", name: "Gemini", fmt: "google", url: "https://generativelanguage.googleapis.com/v1beta", env: "GEMINI_API_KEY", mods: ["gemini-2.5-pro", "gemini-2.5-flash"] },
  { id: "dashscope", name: "Qwen VL", fmt: "openai", url: "https://dashscope.aliyuncs.com/compatible-mode/v1", env: "DASHSCOPE_API_KEY", mods: ["qwen-vl-max", "qwen-vl-plus"] },
  { id: "zhipuai", name: "GLM-4V", fmt: "openai", url: "https://open.bigmodel.cn/api/paas/v4", env: "GLM_API_KEY", mods: ["glm-4v-plus", "glm-4v"] },
  { id: "siliconflow", name: "SiliconFlow", fmt: "openai", url: "https://api.siliconflow.cn/v1", env: "SILICONFLOW_API_KEY", mods: [] },
  { id: "custom", name: "OpenAI Compatible", fmt: "openai", url: "", env: "", mods: [], custom: true }
];

const log=(l,m)=>process.stderr.write("["+new Date().toISOString().slice(11,19)+"] "+(l==="error"?"X":"-")+" [vision] "+m+"\n");
const err=m=>log("error",m);
function loadEnv(){const p=join(SKILL,".env");if(!existsSync(p))return;const t=readFileSync(p,"utf-8");for(const l of t.split("\n")){const m=l.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$/);if(m){let v=m[2].replace(/^["']|["']$/g,"");process.env[m[1]]=process.env[m[1]]||v;}}}
loadEnv();
function cfgP(){return process.env.VISION_CONFIG_PATH?resolve(process.env.VISION_CONFIG_PATH):join(SKILL,"config.json")}
function load(){const p=cfgP();if(!existsSync(p)){err("no config: "+p);process.exit(1)}return JSON.parse(readFileSync(p,"utf-8"))}
function save(c){writeFileSync(cfgP(),JSON.stringify(c,null,2)+"\n","utf-8")}

async function callV(m,prompt,imgs,det){
const key=m.apiKey||process.env[m.apiKeyEnv]||process.env.VISION_API_KEY||"";
if(!key)throw Error("no key");
const url=(m.baseUrl||"").replace(/\/+$/,"")+"/chat/completions";
const c=[];
for(const s of imgs){
    if(s.startsWith("data:")||s.startsWith("http")){c.push({type:"image_url",image_url:{url:s,detail:det}});continue}
    const ext=extname(s).toLowerCase();
    c.push({type:"image_url",image_url:{url:"data:"+(MIME[ext]||"image/png")+";base64,"+readFileSync(resolve(s)).toString("base64"),detail:det}});
}
const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},body:JSON.stringify({model:m.model,messages:[{role:"user",content:[{type:"text",text:prompt},...c]}],max_tokens:4096}),signal:AbortSignal.timeout(m.timeout||60000)});
if(!r.ok)throw Error("HTTP "+r.status);
return(await r.json()).choices[0].message.content;
}

async function rec(cfg,prompt,imgs,det){
const ms=cfg.models||[];if(!ms.length)throw Error("no models");
const pp=prompt?(cfg.defaultPrompt||"desc")+"\n\n"+prompt:(cfg.defaultPrompt||"desc");
let le=null;
for(let i=0;i<ms.length;i++){try{return await callV(ms[i],pp,imgs,det)}catch(e){le=e;if(i<ms.length-1)continue}}
throw le||Error("all failed");
}

async function ask(q,d){return new Promise(r=>{const i=createInterface({input:process.stdin,output:process.stderr});i.question(" "+q+(d?" ["+d+"]":"")+": ",a=>{i.close();r((a.trim()||d||"").trim())})})}
async function confirm(q,d){return new Promise(r=>{const i=createInterface({input:process.stdin,output:process.stderr});i.question(" "+q+" "+(d?"[Y/n]":"[y/N]")+": ",a=>{i.close();const t=a.trim().toLowerCase();if(!t)r(d);else r(t==="y"||t==="yes")})})}

async function selProvider(){
const gs=[
    {label:"Intl",items:CAT.filter(p=>!p.id.match(/^(dashscope|zhipuai|siliconflow|custom)$/))},
    {label:"CN",items:CAT.filter(p=>p.id.match(/^(dashscope|zhipuai|siliconflow)$/))},
    {label:"Custom",items:CAT.filter(p=>p.custom)}
];
const all=[];let idx=1;
for(const g of gs){console.error("\n -- "+g.label+" --");for(const p of g.items){console.error(" "+idx+". "+p.name);all.push(p);idx++}}
console.error("");const s=await ask("pick 1-"+all.length);const n=parseInt(s,10);if(n<1||n>all.length)return null;return all[n-1]
}

async function initCmd(){
console.error("\n Vision Init\n");const p=await selProvider();if(!p)return;
let ak="",ake=p.env||"";const ki=await ask("API key or env name");
if(ki){if(/^[A-Z_][A-Z0-9_]*$/.test(ki)){ake=ki;ak=""}else{ak=ki;ake=""}}
let bu=p.url;if(p.custom){bu=await ask("API baseUrl");if(!bu)return}
const mi=await ask("model",p.mods[0]||"");if(!mi)return;
const e={name:p.name+"/"+mi,provider:p.fmt,model:mi,baseUrl:bu,apiKeyEnv:ake,apiKey:ak,timeout:60000};
const cfg=existsSync(cfgP())?load():{models:[]};cfg.models=cfg.models||[];cfg.models.unshift(e);save(cfg);
console.error("\n ok: "+e.name);if(await confirm("add fallback?",false))await addFallback()
}

async function addFallback(){
const p=await selProvider();if(!p)return;
let ak="",ake=p.env||"";const ki=await ask("API key");
if(ki){if(/^[A-Z_][A-Z0-9_]*$/.test(ki)){ake=ki;ak=""}else{ak=ki;ake=""}}
let bu=p.url;if(p.custom){bu=await ask("baseUrl");if(!bu)return}
const mi=await ask("model",p.mods[0]||"");if(!mi)return;
const cfg=load();cfg.models.push({name:p.name+"/"+mi,provider:p.fmt,model:mi,baseUrl:bu,apiKeyEnv:ake,apiKey:ak,timeout:60000});
save(cfg);console.error(" added: "+mi)
}

function listCmd(c){const ms=c.models||[];console.log("\n"+ms.length+" models:\n");ms.forEach((m,i)=>{console.log(" "+(i+1)+". "+m.name+(i===0?" *main":" fb"+i)+"\n   "+m.model+" | key:"+(m.apiKey||process.env[m.apiKeyEnv]?"Y":"N")+"\n")})}

async function testCmd(cfg){let testImg="";for(const p of["/tmp/test.jpg","C:/Users/Linus/AppData/Local/Temp/test.jpg","red.png"]){if(existsSync(p)){testImg=p;break}}for(const m of cfg.models){process.stderr.write(" "+m.name+"... ");try{if(!testImg){process.stderr.write("SKIP (no test image)\n");continue}const r=await callV(m,"Describe in one word.",[testImg],"low");process.stderr.write("OK: "+r.slice(0,40)+"\n")}catch(e){process.stderr.write("FAIL: "+e.message.slice(0,60)+"\n")}}}

function clipImg(){
const tmp=join(process.env.TEMP||"/tmp","vision-clip-"+Date.now()+".png");
try{execSync("powershell -NoProfile -Command \"Add-Type -AssemblyName System.Windows.Forms;if([Windows.Forms.Clipboard]::ContainsImage()){[Drawing.Bitmap]::new([Windows.Forms.Clipboard]::GetImage()).Save('"+tmp.replace(/\\/g,"\\\\")+"',[Drawing.Imaging.ImageFormat]::Png)}else{exit 1}\"",{stdio:"pipe"});return tmp}
catch{return null}
}

async function main(){
const a=process.argv.slice(2),c0=a[0];
if(c0==="init"){return initCmd()}
if(c0==="config"||c0==="cfg"){
    const sub=a[1]||"list",cfg=load();
    if(sub==="list")listCmd(cfg);else if(sub==="add")await addFallback();else if(sub==="remove"){const n=a[2];const i=cfg.models.findIndex(m=>m.name===n||m.model===n);if(i>=0){cfg.models.splice(i,1);save(cfg);console.log("removed")}}else if(sub==="test"){await testCmd(cfg)}
    return
}
const cfg=load(),imgs=[];let prompt=null,det="auto",tmpClip=null;
for(let i=0;i<a.length;i++){const x=a[i];if(x==="-c"||x==="--clip"){const t=clipImg();if(!t){err("no image in clipboard");process.exit(1)}tmpClip=t;imgs.push(t)}else if(x.startsWith("http")||x.startsWith("data:"))imgs.push(x);else if(x==="-d")det=a[++i];else if(x==="-p")prompt=a[++i];else imgs.push(x)}
if(!imgs.length){err("need image path");process.exit(1)}
try{const r=await rec(cfg,prompt,imgs,det);console.log(r);if(tmpClip)try{require("node:fs").unlinkSync(tmpClip)}catch{}}catch(e){if(tmpClip)try{require("node:fs").unlinkSync(tmpClip)}catch{}err(e.message);process.exit(1)}
}
main().catch(e=>{err(e.message);process.exit(1)})