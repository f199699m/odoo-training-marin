---
name: minar-contexto
description: >
  Mina el historial de conversaciones de Claude Code (transcripciones locales) para
  encontrar hechos nuevos sobre Carlos que aún no están en su memoria persistente, y
  además detecta memorias existentes obsoletas o contradichas para proponer su poda.
  Incremental por defecto (solo sesiones nuevas desde la última corrida), con barrido
  completo bajo demanda. Siempre presenta un informe y pide confirmación antes de
  escribir o borrar memoria. Use when the user types /minar-contexto, o pide
  "actualiza tu contexto sobre mí", "revisa nuestras conversaciones pasadas",
  "amplía lo que sabes de mí", "destila lo nuevo del historial", o "mantén/poda mi
  memoria". Operación meta personal — opera sobre el historial y la memoria de Carlos,
  NO sobre datos de Odoo/AgroMarin.
argument-hint: "[full | desde:AAAA-MM-DD]"
allowed-tools: Agent, Bash, Read, Write, Edit, AskUserQuestion
effort: high
disable-model-invocation: true
---

# Minar contexto: destilar el historial en memoria persistente

Argumento recibido: `$ARGUMENTS`

**Propósito**: Claude Code no tiene memoria conversacional automática entre sesiones;
solo carga las fichas destiladas de `memory/`. Las transcripciones crudas
(`~/.claude/projects/*/*.jsonl`) son un archivo histórico que hay que abrir a
propósito. Este skill lo destila: extrae la señal "sobre Carlos" de sus mensajes,
la cruza contra la memoria existente, y propone **(a)** memorias nuevas, **(b)**
ampliaciones a las existentes, y **(c)** podas de las que ya no aplican. **Nunca
escribe ni borra sin confirmación.**

## Filosofía (no negociable)

- **No inventar.** Todo hallazgo se respalda con evidencia (paráfrasis + fecha del
  marcador `[timestamp]`). Lo inferido por un agente y NO dicho por Carlos se marca
  `⚠️ POR CONFIRMAR`, nunca como hecho.
- **Calidad sobre cantidad.** Preferir rasgos durables sobre detalles de tarea de
  un solo uso. Datos que envejecen mal (números de picking, IDs efímeros) van como
  *ejemplo ilustrativo*, no como dato a recordar literalmente.
- **Honestidad de cobertura.** Esto solo ve lo escrito en Claude Code — no la UI de
  Odoo ni claude.ai (navegador) salvo lo pegado aquí. Declararlo en el informe.
- **El usuario decide.** Memoria es información personal sobre Carlos; él aprueba qué
  se guarda y qué se jubila. Estándar de asesor crítico: recomendar, no solo listar.

## Constantes (rutas estables, máquina de Carlos)

| Concepto | Valor |
|---|---|
| Memoria persistente | `~/.claude/projects/-home-marin/memory/` (fichas `.md` + índice `MEMORY.md`) |
| Transcripciones | `~/.claude/projects/*/*.jsonl` (todos los proyectos) |
| Dir del skill | `~/.claude/skills/minar-contexto/` |
| Extractor | `~/.claude/skills/minar-contexto/mine_prepare.py` |
| Estado / marca de agua | `~/.claude/skills/minar-contexto/.state.json` |
| Salida de trabajo | tu **directorio scratchpad de sesión** `/minar-contexto/` |

Convención de memoria (igualar SIEMPRE el patrón del repo — verificar antes de
escribir leyendo una ficha vecina): archivo en `snake_case` con prefijo de tipo
(`user_…`, `feedback_…`, `project_…`, `reference_…`); frontmatter con `name:`
kebab-case, `metadata: {node_type: memory, type: <tipo>, originSessionId: <id>}`.
Cuerpo conciso; `feedback`/`project` llevan `**Why:**` y `**How to apply:**`;
enlazar fichas con `[[name]]`. Tras crear una ficha, añadir su puntero de una línea
en `MEMORY.md`.

## Parseo del argumento

- **vacío** → modo **incremental**: leer `.state.json`; usar su `last_run_ts` como
  `--since`. Si no existe `.state.json` (primera corrida) → barrido completo y avisar.
- **`full`** → barrido completo (sin `--since`); reprocesa todo el historial.
- **`desde:AAAA-MM-DD`** → usar esa fecha como `--since` (override manual).

---

## Fase 0 — Estado

Leer la marca de agua:

```bash
cat ~/.claude/skills/minar-contexto/.state.json 2>/dev/null || echo '{}'
```

Extraer `last_run_ts`. Determinar `SINCE` según el argumento (arriba). Resolver tu
directorio scratchpad de sesión (está en tu system prompt) como `OUT=<scratchpad>/minar-contexto`.

## Fase 1 — Preparar el corpus

Correr el extractor (filtra ruido de máquina, filtra por marca de agua, arma lotes):

```bash
python3 ~/.claude/skills/minar-contexto/mine_prepare.py \
  --out "<OUT>" $( [ -n "<SINCE>" ] && echo --since "<SINCE>" )
```

Leer el `manifest.json` impreso. **Si `total_messages == 0`** → no hay novedad desde
la última corrida: informarlo ("sin mensajes nuevos desde <fecha>; memoria al día") y
**terminar** (no avanzar la marca de agua, no lanzar agentes). Si hay contenido,
anotar `n_batches` y `max_ts`.

## Fase 2 — Minar (lectores en paralelo)

Lanzar **un lector por lote** en paralelo (un solo mensaje con varios `Agent` de tipo
`general-purpose`; si `n_batches` es grande y el entorno lo permite, orquestar con un
Workflow de fan-out). Escalar al volumen: pocos lotes → pocos lectores.

Prompt de cada lector (sustituir `<RUTA_LOTE>`):

> Estás minando un tramo del historial de conversaciones de Carlos para ampliar el
> contexto persistente del asistente sobre ÉL.
> 1. Lee el índice de memoria existente: `~/.claude/projects/-home-marin/memory/MEMORY.md`.
>    Si un candidato parece ya cubierto, lee la ficha específica para confirmar.
> 2. Lee este lote (solo mensajes humanos, ruido ya removido): `<RUTA_LOTE>`.
> 3. Extrae HECHOS SOBRE CARLOS útiles para servirle mejor: quién es y su alcance;
>    cómo trabaja (cadencia, dolores, KPIs, cómo encuadra problemas); cómo quiere que
>    el asistente se comporte (tono, profundidad, formato, idioma, correcciones que
>    dio, lo que elogió o rechazó); su contexto personal; hechos de proyecto/dominio
>    y punteros de referencia estables que se repiten.
> 4. **Poda**: lista también memorias EXISTENTES que este lote **contradice** o vuelve
>    **obsoletas** (por slug), con la evidencia.
> Reglas: reporta SOLO lo que NO está ya bien cubierto; marca `novelty` =
> new | refines-existing | contradicts-existing y el `related_memory` (slug). Adjunta
> evidencia (paráfrasis + fecha `[timestamp]`). No inventes; si dudas, `confidence=low`.
> Devuelve una lista de hallazgos (fact, category[user|feedback|project|reference],
> evidence, novelty, related_memory, confidence) y una lista de candidatas-a-jubilar
> (slug, motivo, evidence).

## Fase 3 — Síntesis (dedup + clasificar + poda)

Reunir todos los hallazgos. Como hilo principal (o un agente sintetizador con
`effort: high`):

1. **Fusionar** duplicados que aparezcan en varios lotes (repetición entre sesiones =
   más confianza; combinar evidencia).
2. **Descartar** lo ya cubierto adecuadamente por una ficha existente.
3. Para lo que sobrevive, decidir `action`: **create** (nuevo) o **update** (amplía/
   refina/contradice una ficha — fijar `target_slug`). Clasificar `category`.
4. **Poda**: consolidar las candidatas-a-jubilar; para cada una decidir
   **archivar-recomendación** (actualizar la ficha con el cambio) vs **borrar**
   (memoria claramente falsa/obsoleta). Releer la ficha antes de proponer tocarla.
5. Redactar `proposed_body` en el formato de memoria (conciso; Why/How donde aplique).
   Marcar inferencias no dichas por Carlos como `⚠️ POR CONFIRMAR`.

## Fase 4 — Informe + confirmación (SIEMPRE)

Presentar a Carlos, en español, claro y directo (sin relleno), separando:

- **✅ Ya cubierto** (breve, para mostrar que no se duplica).
- **🆕 Nuevas** / **✏️ Ampliaciones** — tabla: hallazgo · acción · ficha · prioridad.
- **🗑️ Poda propuesta** — fichas obsoletas/contradichas con el motivo.
- **🔎 Observaciones críticas** — puntos ciegos del barrido, inferencias a validar.

Dar una **recomendación** explícita. Luego pedir confirmación con `AskUserQuestion`
(p.ej. "guardar todo / solo altas / reviso una por una / nada"). **No escribir nada
hasta tener el OK.**

## Fase 5 — Aplicar + avanzar la marca de agua

Solo tras confirmación:

1. Escribir/ampliar/podar las fichas aprobadas, igualando la convención (Fase 0).
2. Actualizar `MEMORY.md`: añadir punteros de las nuevas; refrescar descripciones de
   las que cambiaron materialmente; quitar las jubiladas.
3. **Avanzar la marca de agua** con el `max_ts` del manifest (para que la próxima
   corrida incremental no reprocese lo ya visto):

```bash
python3 - "$MAX_TS" <<'PY'
import json, os, sys, datetime
p = os.path.expanduser("~/.claude/skills/minar-contexto/.state.json")
st = {}
if os.path.exists(p):
    st = json.load(open(p))
st["last_run_ts"] = sys.argv[1]
st["last_run_date"] = datetime.datetime.now().isoformat(timespec="seconds")
st["runs"] = st.get("runs", 0) + 1
json.dump(st, open(p, "w"), indent=2)
print("watermark ->", st["last_run_ts"])
PY
```

4. Cerrar con un resumen de una línea (cuántas nuevas/ampliadas/podadas) y, si aplica,
   las inferencias que quedaron `⚠️ POR CONFIRMAR` pendientes de su validación.

## Límites conocidos (declararlos)

- Cobertura = solo Claude Code; no UI de Odoo ni claude.ai navegador (salvo pegado).
- Comparación de timestamps ISO lexicográfica; si una sesión tiene timestamps
  ausentes, sus mensajes pueden quedar fuera del filtro incremental — un `full`
  periódico (p.ej. trimestral) los recupera.
- El scratchpad es efímero; los lotes se descartan al cerrar la sesión. La memoria y
  la marca de agua persisten.
