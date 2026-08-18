# Encuestas Gambling

App local para convertir cuestionarios en tareas MatrAIx sobre la cohorte Persona8B descargada: 500 perfiles profesionales simulados y 9.500 recreacionales.

Persona8B aporta los perfiles; tu Hermes local (`gpt-oss:20b-hermes` mediante Ollama) genera una respuesta por perfil.

```bash
./start.sh
```

Abre `http://127.0.0.1:8765`. Puedes crear preguntas en pantalla o cargar un cuestionario completo desde el bloque azul: admite JSON y XML. Tras cargarlo, las preguntas quedan visibles y editables antes de preparar la ejecución.

Usa como plantilla `ejemplo_cuestionario.json` o `ejemplo_cuestionario.xml`. Cada fichero puede contener todas las preguntas que quieras. Para XML, la estructura es `<survey title="..."><question type="single_choice|multi_choice"><prompt>...</prompt><options><option>...</option></options></question></survey>`.

La app creará dentro de MatrAIx una tarea, dos YAML de cohorte y un script `run_with_hermes.sh`.

La app no ejecuta las 10.000 respuestas automáticamente. Revisa primero el cuestionario generado.

Requiere MatrAIx en `/home/canfron/MatrAIx` (o `MATRAIX_ROOT`) y las cohortes Persona8B ya descargadas.
