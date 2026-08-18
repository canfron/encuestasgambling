#!/usr/bin/env python3
import html, json, os, re, shutil, subprocess
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

APP=Path(__file__).parent; MATRIX=Path(os.environ.get("MATRAIX_ROOT","/home/canfron/MatrAIx"))
SOURCE="application/tasks/betting-insights-responsible-concept"
COHORTS={"professional":(500,"edgescope-responsible-professional-n500.yaml"),"recreational":(9500,"edgescope-responsible-recreational-n9500.yaml")}
def slug(x):
    x=re.sub(r"[^a-z0-9]+","-",x.lower()).strip("-")[:80]
    if not x: raise ValueError("Identificador no válido")
    return x
def form(data):
    out=[]
    for n,q in enumerate(data.get("questions",[]),1):
        p=str(q.get("prompt"," ")).strip(); opts=[str(x).strip() for x in q.get("options",[]) if str(x).strip()]
        t=q.get("type","single_choice")
        if not p or len(opts)<2 or t not in ("single_choice","multi_choice"): raise ValueError(f"Pregunta {n}: texto, tipo y dos opciones como mínimo")
        i=f"q{n:03d}"; out.append({"id":i,"prompt":p,"type":t,"construct":i,"required":True,"options":[{"id":f"{i}_o{j}","label":v} for j,v in enumerate(opts,1)]})
    if not out: raise ValueError("Añade una pregunta")
    return {"schemaVersion":"1.0","id":slug(data.get("title","encuesta")).replace("-","_")+"_v1","title":data.get("title","Encuesta"),"questions":out}
def recpath(i): return APP/"local-output"/(slug(i)+".json")
def save(x):
    (APP/"local-output").mkdir(exist_ok=True); recpath(x["id"]).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def load(i):
    p=recpath(i)
    if not p.exists(): raise ValueError("Encuesta no encontrada")
    return json.loads(p.read_text())
def create(i,data):
    i=slug(i); task=MATRIX/"application/tasks"/f"user-survey-{i}"
    if task.exists(): raise ValueError("Ese identificador ya existe")
    q=form(data); template=MATRIX/SOURCE
    if not template.exists(): raise ValueError("No encuentro MatrAIx o la plantilla")
    (task/"input").mkdir(parents=True); (task/"tests").mkdir(); (task/"solution").mkdir()
    (task/"task.toml").write_text("\n".join(["version = \"1.0\"","artifacts = [ \"/app/output\",]","[task]",f"name = \"application/user-survey-{i}\"","[metadata]","difficulty = \"easy\"","type = \"survey\"","[verifier]","timeout_sec = 120.0","[agent]","timeout_sec = 600.0","[environment]","definition = \"application/shared-survey-form\"","cpus = 1","memory_mb = 2048","storage_mb = 10240","gpus = 0",""]))
    (task/"instruction.md").write_text("# Encuesta responsable\n\nSimulación adulta. No fomentes crédito, persecución de pérdidas, elusión de límites ni juego problemático.\n")
    (task/"input/context.md").write_text("# Muestra\n\n500 perfiles profesionales simulados y 9.500 recreacionales Persona8B. No se diagnostica juego problemático.\n")
    (task/"input/questionnaire.yaml").write_text(json.dumps(q,ensure_ascii=False,indent=2))
    (task/"reporting.json").write_text('{"schemaVersion":"1.0","contextRules":[]}')
    for n in ("test.sh","test_state.py","verifier_env.sh"): shutil.copy2(template/"tests"/n,task/"tests"/n)
    shutil.copy2(template/"solution/solve.sh",task/"solution/solve.sh")
    rel=task.relative_to(MATRIX).as_posix(); jobs=[]; names=[]; d=MATRIX/"configs/jobs/application-task-job-recipe"
    for segment,(count,source) in COHORTS.items():
        name=f"{i}-{segment}-n{count}"; target=d/(name+".yaml")
        target.write_text((d/source).read_text().replace(SOURCE,rel).replace("edgescope-responsible-",i+"-")); jobs.append(str(target)); names.append(name)
    run=task/"run_with_hermes.sh"; cmds="\n".join(f'uv run matraix run -c "{Path(x).relative_to(MATRIX)}"' for x in jobs)
    run.write_text(f'#!/usr/bin/env bash\nset -euo pipefail\ncd "{MATRIX}"\nexport OPENAI_BASE_URL="${{OPENAI_BASE_URL:-http://127.0.0.1:11434/v1}}"\nexport OPENAI_API_KEY="${{OPENAI_API_KEY:-ollama}}"\n{cmds}\n'); run.chmod(0o775)
    r={"id":i,"title":q["title"],"questions":len(q["questions"]),"task":str(task),"run":str(run),"jobs":names,"status":"ready"}; save(r); return r
def launch(i):
    r=load(i); log=Path(r["task"])/"execution.log"
    with log.open("ab") as f: p=subprocess.Popen(["bash",r["run"]],cwd=MATRIX,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    r.update(status="running",pid=p.pid,log=str(log)); save(r); return r
def results(i):
    r=load(i); c=defaultdict(Counter); total=0
    for name in r["jobs"]:
        for p in (MATRIX/"jobs"/name).rglob("survey_result.json") if (MATRIX/"jobs"/name).exists() else []:
            try:
                for a in json.loads(p.read_text()).get("answers",[]): c[str(a.get("questionId"))][str(a.get("value"))]+=1
                total+=1
            except Exception: pass
    return r,total,c
PAGE='''<!doctype html><meta charset="utf-8"><style>body{font:16px system-ui;max-width:900px;margin:30px auto}.card{border:1px solid #ccc;padding:12px;margin:12px 0}input,select,button{padding:8px;font:inherit}input{width:90%}.danger{background:#a22;color:white}.ok{background:#e6f6e9;padding:10px}.error{background:#fee;padding:10px}</style><h1>Encuestas Gambling</h1><p>Construye la encuesta, ejecútala sobre 10.000 perfiles Persona8B y consulta resultados agregados. Hermes produce una respuesta por perfil.</p>{message}<form method="post" action="/create"><p>Identificador <input name="id" value="mi-encuesta"></p><p>Título <input id="title" name="title" value="Encuesta de apuestas deportivas"></p><p>Cargar cuestionario JSON <input id="file" type="file" accept=".json,application/json"></p><input id="payload" name="payload" type="hidden"><div id="qs"></div><button type="button" onclick="add()">+ Nueva pregunta</button><button type="button" class="danger" onclick="if(confirm('¿Limpiar?')){q=[];draw()}">Limpiar encuesta</button><button>Preparar encuesta</button></form><script>let q=[];function esc(x){return String(x).replaceAll('&','&amp;').replaceAll('"','&quot;')}function add(x={prompt:'',type:'single_choice',options:['','']}){q.push(x);draw()}function draw(){qs.innerHTML=q.map((x,i)=>`<div class=card><button type=button class=danger onclick="q.splice(${i},1);draw()">Quitar pregunta</button><p><input placeholder="Pregunta" value="${esc(x.prompt)}" oninput="q[${i}].prompt=this.value"></p><select onchange="q[${i}].type=this.value"><option value=single_choice ${x.type==='single_choice'?'selected':''}>Opción única</option><option value=multi_choice ${x.type==='multi_choice'?'selected':''}>Múltiples respuestas</option></select>${x.options.map((o,j)=>`<p><input placeholder="Opción" value="${esc(o)}" oninput="q[${i}].options[${j}]=this.value"><button type=button onclick="q[${i}].options.splice(${j},1);draw()">Quitar</button></p>`).join('')}<button type=button onclick="q[${i}].options.push('');draw()">+ Opción</button></div>`).join('')}file.onchange=async e=>{try{let d=JSON.parse(await e.target.files[0].text());if(!Array.isArray(d.questions))throw Error("Falta questions");title.value=d.title||title.value;q=d.questions.map(x=>({prompt:x.prompt||"",type:x.type||"single_choice",options:(x.options||[]).map(o=>typeof o==="string"?o:o.label||"")}));draw()}catch(err){alert("JSON no válido: "+err.message)}};document.querySelector('form').onsubmit=e=>{if(!q.length){alert('Añade una pregunta');e.preventDefault()}payload.value=JSON.stringify({title:title.value,questions:q})};add({prompt:'¿Qué valor tendría para ti una herramienta de análisis de cuotas?',type:'single_choice',options:['Ninguno','Bajo','Moderado','Alto']})</script>'''
class H(BaseHTTPRequestHandler):
    def post(self): return {k:v[0] for k,v in parse_qs(self.rfile.read(int(self.headers.get("Content-Length",0))).decode()).items()}
    def do_GET(self):
        if self.path.startswith("/results?"):
            try:
                i=parse_qs(self.path.split("?",1)[1])["id"][0]; r,n,c=results(i); rows="".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td><td>{x}</td></tr>" for k,vs in c.items() for v,x in vs.items()) or "<tr><td colspan=3>Aún no hay respuestas.</td></tr>"; self.page(f'<div class=ok>Respuestas encontradas: {n}/10.000. <a href="/results?id={i}">Actualizar</a><table>{rows}</table></div>'); return
            except Exception as e: self.page(f'<div class=error>{html.escape(str(e))}</div>'); return
        self.page("")
    def do_POST(self):
        try:
            f=self.post()
            if self.path=="/create": r=create(f["id"],json.loads(f["payload"])); m=f'<div class=ok>Preparada: {r["questions"]} preguntas. <form method=post action=/execute><input type=hidden name=id value="{r["id"]}"><button onclick="return confirm(\'Iniciar 10.000 inferencias locales?\')">Ejecutar 10.000 respuestas</button></form><a href="/results?id={r["id"]}">Ver resultados</a></div>'
            else: r=launch(f["id"]); m=f'<div class=ok>Ejecución iniciada. <a href="/results?id={r["id"]}">Ver resultados</a></div>'
        except Exception as e: m=f'<div class=error>{html.escape(str(e))}</div>'
        self.page(m)
    def page(self,m):
        b=PAGE.replace("{message}",m).encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self,*_): pass
if __name__=="__main__": ThreadingHTTPServer(("127.0.0.1",8765),H).serve_forever()
