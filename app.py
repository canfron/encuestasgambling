#!/usr/bin/env python3
"""Local builder for Persona8B questionnaire jobs."""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).parent.resolve()
MATRIX = Path(os.environ.get("MATRAIX_ROOT", "/home/canfron/MatrAIx")).resolve()
SOURCE_TASK = "application/tasks/betting-insights-responsible-concept"
COHORTS = {"professional": (500, "edgescope-responsible-professional-n500.yaml"),
           "recreational": (9500, "edgescope-responsible-recreational-n9500.yaml")}


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]
    if not value:
        raise ValueError("El identificador debe contener letras o números.")
    return value


def parse_questions(raw: str, title: str) -> dict:
    raw = raw.strip()
    if raw.startswith("{"):
        data = json.loads(raw)
        if not isinstance(data.get("questions"), list):
            raise ValueError("El JSON debe incluir una lista 'questions'.")
        return data
    groups = [block.splitlines() for block in re.split(r"\n\s*\n", raw) if block.strip()]
    questions = []
    for index, lines in enumerate(groups, 1):
        prompt = lines[0].removeprefix("Q:").strip()
        options = [line.strip()[2:].strip() for line in lines[1:] if line.strip().startswith(("- ", "* "))]
        if not prompt or len(options) < 2:
            raise ValueError(f"La pregunta {index} necesita texto y al menos dos opciones.")
        qid = f"q{index:03d}"
        questions.append({"id": qid, "prompt": prompt, "type": "single_choice",
                          "construct": f"question_{index:03d}", "required": True,
                          "options": [{"id": f"{qid}_o{n}", "label": opt}
                                      for n, opt in enumerate(options, 1)]})
    if not questions:
        raise ValueError("Pega al menos una pregunta.")
    return {"schemaVersion": "1.0", "id": slug(title).replace("-", "_") + "_v1",
            "title": title, "description": "Questionnaire created by Encuestas Gambling.",
            "questions": questions}


def task_toml(name: str) -> str:
    return f'''version = "1.0"
artifacts = [ "/app/output",]
[task]
name = "application/{name}"
[metadata]
difficulty = "easy"
type = "survey"
domain = "sports-analytics"
tags = ["sports", "responsible-gambling", "survey"]
[verifier]
timeout_sec = 120.0
[agent]
timeout_sec = 600.0
[environment]
definition = "application/shared-survey-form"
build_timeout_sec = 600.0
cpus = 1
memory_mb = 2048
storage_mb = 10240
gpus = 0
'''


def create(survey_id: str, title: str, raw: str) -> dict:
    if not (MATRIX / "application/scripts/generate_application_job.py").is_file():
        raise ValueError(f"MATRAIX_ROOT no es válido: {MATRIX}")
    survey_id = slug(survey_id)
    task_name = f"user-survey-{survey_id}"
    task = MATRIX / "application/tasks" / task_name
    if task.exists():
        raise ValueError("Ese identificador ya existe; usa otro.")
    questionnaire = parse_questions(raw, title)
    template = MATRIX / SOURCE_TASK
    (task / "input").mkdir(parents=True)
    (task / "tests").mkdir(); (task / "solution").mkdir()
    (task / "task.toml").write_text(task_toml(task_name), encoding="utf-8")
    (task / "instruction.md").write_text('''# Encuesta responsable\n\nResponde todas las preguntas según el perfil asignado. Esta es una simulación con perfiles adultos. No fomentes persecución de pérdidas, crédito para apostar, elusión de límites ni juego problemático. Si una pregunta presupone pérdida de control, elige la opción prudente disponible.\n''', encoding="utf-8")
    (task / "input/context.md").write_text('''# Muestra\n\nCohorte Persona8B: 500 perfiles profesionales simulados y 9.500 recreacionales interesados en deporte. La participación responsable es una condición de simulación; no se diagnostica ni infiere juego problemático.\n''', encoding="utf-8")
    (task / "input/questionnaire.yaml").write_text(json.dumps(questionnaire, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (task / "reporting.json").write_text('{"schemaVersion":"1.0","contextRules":[]}\n', encoding="utf-8")
    for name in ("test.sh", "test_state.py", "verifier_env.sh"):
        shutil.copy2(template / "tests" / name, task / "tests" / name)
    shutil.copy2(template / "solution/solve.sh", task / "solution/solve.sh")
    task_rel = task.relative_to(MATRIX).as_posix()
    jobs_dir = MATRIX / "configs/jobs/application-task-job-recipe"
    jobs = []
    for segment, (count, source_name) in COHORTS.items():
        source = jobs_dir / source_name
        if not source.is_file():
            raise ValueError(f"Falta la cohorte congelada: {source}")
        target = jobs_dir / f"{survey_id}-{segment}-n{count}.yaml"
        text = source.read_text(encoding="utf-8").replace(SOURCE_TASK, task_rel)
        text = text.replace("edgescope-responsible-", f"{survey_id}-")
        target.write_text(text, encoding="utf-8"); jobs.append(target)
    run = task / "run_with_hermes.sh"
    commands = "\n".join(f'uv run matraix run -c "{path.relative_to(MATRIX)}"' for path in jobs)
    run.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
cd "{MATRIX}"
export OPENAI_BASE_URL="${{OPENAI_BASE_URL:-http://127.0.0.1:11434/v1}}"
export OPENAI_API_KEY="${{OPENAI_API_KEY:-ollama}}"
export MATRIX_SURVEY_TASK_PATH="{task_rel}"
# Revisa el cuestionario antes: este script ejecuta 10.000 respuestas locales.
{commands}
''', encoding="utf-8")
    run.chmod(0o775)
    record = {"createdAt": datetime.now(timezone.utc).isoformat(), "task": str(task),
              "questions": len(questionnaire["questions"]), "jobs": [str(x) for x in jobs], "run": str(run)}
    (ROOT / "local-output").mkdir(exist_ok=True)
    (ROOT / "local-output" / f"{survey_id}.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


PAGE = '''<!doctype html><meta charset="utf-8"><title>Encuestas Gambling</title><style>body{font:16px system-ui;max-width:900px;margin:40px auto;padding:0 18px}input,textarea{box-sizing:border-box;width:100%;padding:10px;font:inherit}textarea{height:310px}label{display:block;margin-top:16px;font-weight:700}button{margin-top:18px;padding:12px;background:#146c43;color:#fff;border:0;border-radius:6px;font:inherit}.note,.ok,.error{padding:12px;border-radius:6px}.note{background:#eef2f4}.ok{background:#eaf8ed}.error{background:#fff0f0;color:#8c1717}code{word-break:break-all}</style><h1>Encuestas Gambling</h1><p>Convierte tus cuestionarios en trabajos sobre la cohorte Persona8B de 10.000 perfiles.</p><div class="note">Persona8B proporciona perfiles; Hermes genera las respuestas. La app no lanza las 10.000 ejecuciones automáticamente.</div>{message}<form method="post"><label>Identificador</label><input name="id" value="mi-encuesta" required><label>Título</label><input name="title" value="Encuesta de apuestas deportivas" required><label>Preguntas y respuestas</label><textarea name="questions" required>¿Qué valor tendría para ti una herramienta de análisis de cuotas?
- Ninguno
- Bajo
- Moderado
- Alto

¿Qué información te genera más confianza?
- Fuentes visibles y datos históricos
- Pronósticos sin explicación
- Bonos o promociones
</textarea><button>Crear tarea y YAML</button></form><p>Formato: pregunta y opciones con <code>- </code>, separadas por una línea vacía. También acepta un cuestionario JSON con <code>questions</code>.</p>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.reply("")
    def do_POST(self):
        fields = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(), keep_blank_values=True)
        try:
            out = create(fields["id"][0], fields["title"][0], fields["questions"][0])
            jobs = "<br>".join(f"<code>{html.escape(x)}</code>" for x in out["jobs"])
            message = f'<div class="ok"><b>Creada:</b> {out["questions"]} preguntas.<br>{jobs}<br>Cuando valides la encuesta, ejecuta <code>{html.escape(out["run"])}</code>.</div>'
        except Exception as error:
            message = f'<div class="error">{html.escape(str(error))}</div>'
        self.reply(message)
    def reply(self, message):
        body = PAGE.replace("{message}", message).encode(); self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass


if __name__ == "__main__":
    ThreadingHTTPServer((os.environ.get("ENCUESTAS_HOST", "127.0.0.1"), int(os.environ.get("ENCUESTAS_PORT", "8765"))), Handler).serve_forever()
