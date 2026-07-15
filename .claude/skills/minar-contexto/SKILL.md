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
argument-hint: "[full | poda | auditar | desde:AAAA-MM-DD]"
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

**Presupuesto de tamaño**: cada puntero en `MEMORY.md` es **una línea real** (título +
gancho de relevancia), NO un párrafo — `MEMORY.md` se carga entero en cada sesión. Si un
puntero creció a párrafo, es señal de que la ficha debe **dividirse** o el puntero recortarse;
el detalle vive en el cuerpo de la ficha, no en el índice. La Fase 3.5 vigila este presupuesto
y las fichas hermanas que se traslapan (candidatas a fusionar).

## Parseo del argumento

- **vacío** → modo **incremental**: leer `.state.json`; usar su `last_run_ts` como
  `--since`. Si no existe `.state.json` (primera corrida) → barrido completo y avisar.
- **`full`** → barrido completo (sin `--since`); reprocesa todo el historial.
- **`poda`** → **modo poda profunda** (combinable con `full`): además del minado normal,
  correr la **Fase 3.5** — un agente lee TODAS las fichas completas (no solo el índice) y las
  reta por recencia, contradicción, traslape y presupuesto de tamaño. Recomendado trimestral o
  cuando el índice crezca.
- **`auditar`** → **auditoría adversarial opt-in** (combinable con cualquier modo, p. ej.
  `poda auditar`): tras la síntesis, corre la **Fase 3.7** — un agente **Fable 5** (modelo
  DISTINTO, no un 2º Opus) relee la evidencia cruda y reta cada hallazgo/poda antes de
  presentarlos. Gate por **peso de decisión, no por volumen**: máximo valor en corridas `poda`
  (borrar/fusionar = irreversible y poco auto-evidente); valor marginal modesto en incrementales
  chicas (la confirmación de Carlos en la Fase 4 ya es un adversario fuerte). Ver
  [[feedback_fable_reconciliation_pattern]].
- **`desde:AAAA-MM-DD`** → usar esa fecha como `--since` (override manual).

---

## Fase 0 — Estado

Leer la marca de agua:

```bash
cat ~/.claude/skills/minar-contexto/.state.json 2>/dev/null || echo '{}'
```

Extraer `last_run_ts`. Determinar `SINCE` según el argumento (arriba). Resolver tu
directorio scratchpad de sesión (está en tu system prompt) como `OUT=<scratchpad>/minar-contexto`.

**Cadencia**: reportar los días desde `last_run_date`; si son **> 30**, recomendar además una
corrida `poda` (la memoria acumula rancio y traslape con el tiempo, y nada la recuerda
automáticamente — la nube de `/schedule` no alcanza los transcripts locales).

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

## Fase 3.5 — Poda profunda (solo modo `poda`; recomendada trimestral)

La poda de la Fase 3 es **estructuralmente débil**: los lectores de la Fase 2 solo ven el
índice `MEMORY.md` (punteros de una línea) y abren una ficha "si sospechan" — no pueden retar
lo que el puntero no revela, así que una ficha simplemente **rancia** (sin mensaje nuevo que la
contradiga) nunca se cuestiona. El modo `poda` lo corrige: un agente `general-purpose` (o el
hilo) lee **TODAS las fichas completas** de `~/.claude/projects/-home-marin/memory/*.md` y, por
cada una, evalúa con evidencia:

- **¿Sigue siendo cierta?** Contrastar contra el repo/git y contra fichas más recientes (una
  ficha que dice "NO commiteado" cuando el git log ya muestra el commit está rancia).
- **¿La contradice o subsume una ficha más reciente?** → candidata a jubilar/actualizar.
- **¿Se traslapa con una ficha hermana?** Varias fichas del mismo tema = candidatas a
  **fusionar** (p.ej. las de la suite ejecutiva). Proponer la fusión, nunca duplicar.
- **¿Excede el presupuesto de tamaño?** (puntero de párrafo en `MEMORY.md`, ver Fase 0) →
  proponer recorte del puntero o división de la ficha.

Salida: propuestas de **fusionar / recortar / jubilar / dividir**, con evidencia, que entran al
informe de la Fase 4 como cualquier otra poda. **Nunca borrar/fusionar sin OK.**

## Fase 3.7 — Auditoría adversarial Opus→Fable (solo token `auditar`)

Instancia del patrón Opus→Fable de Carlos ([[feedback_fable_reconciliation_pattern]]) aplicado a
minar contexto. El **valor NO es "un 2º par de ojos"** sino **diversidad de mirador**: un modelo
distinto que relee la fuente y reta el encuadre caza lo que un 2º Opus no vería. Corre DESPUÉS de
la síntesis (Fase 3, y 3.5 si aplica) y ANTES del informe (Fase 4), sobre los hallazgos ya
consolidados.

Primero **escribir los hallazgos de Opus a un archivo en scratchpad** (blanco estable para la
refutación). Luego lanzar **un agente `general-purpose` con `model: fable`** y darle **tres
blancos**:

1. **Refutar cada hallazgo vivo**: ¿está respaldado por lo que Carlos DIJO (cita `[timestamp]`)?
   ¿se sobre-infirió? ¿el `novelty`/`target_slug` es correcto, o ya está cubierto por una ficha?
2. **Retar los descartes**: ¿algún ítem descartado como "ya cubierto" era en realidad un rasgo
   durable que sí merecía ser hallazgo?
3. **Crítico de completitud**: relee el/los lote(s) enteros — ¿qué hecho durable no se listó ni
   como hallazgo ni como descarte? (En el piloto 2026-07-15 esto cazó la refinación más
   consecuente: commits rancios que dejaban el índice `MEMORY.md` apuntando a hashes muertos.)

Insumos al agente: el archivo de hallazgos de Opus, el/los lote(s) crudos, `MEMORY.md`, y las
fichas completas que cada hallazgo toque.

**Reglas del patrón (no negociable):**
- Los hallazgos de Fable son **CANDIDATOS, no veredictos**. **Opus DEBE re-verificar en disco**
  (git log, grep del repo, leer la ficha) **antes de aplicar** cualquier hallazgo de Fable — en
  el piloto Fable afirmó "los commits no existen" cuando estaban huérfanos pero presentes; solo
  la re-verificación lo corrigió. Fable **dispara** re-verificación, no la reemplaza.
- Dar a Fable **latitud escéptica explícita** para cuestionar el encuadre/dominio, no solo para
  recontar (pinear el objetivo caza artefactos de extracción pero NO de encuadre).
- **Fallback de modelo**: si Fable 5 no está disponible, usar otro modelo DISTINTO al minador
  (p. ej. Sonnet) con prompting duro; **nunca un 2º Opus** (redundancia, no diversidad).

## Fase 4 — Informe + confirmación (SIEMPRE)

Presentar a Carlos, en español, claro y directo (sin relleno), separando:

- **✅ Ya cubierto** (breve, para mostrar que no se duplica).
- **🆕 Nuevas** / **✏️ Ampliaciones** — tabla: hallazgo · acción · ficha · prioridad.
- **🗑️ Poda propuesta** — fichas obsoletas/contradichas con el motivo.
- **🔎 Observaciones críticas** — puntos ciegos del barrido, inferencias a validar.

Si corrió la **Fase 3.7** (`auditar`): añadir a cada fila el **veredicto de Fable**
(CONFIRMADO / CON-CORRECCIÓN / REFUTADO / ESCALAR-A-HALLAZGO) junto con la nota de
**re-verificación en disco de Opus**; los hallazgos que Fable elevó por completitud entran como
filas nuevas. Cerrar con un **balance honesto del patrón** (qué cazó Fable que Opus no vio, qué
afirmó de más), para que Carlos calibre si deja `auditar` de planta.

Dar una **recomendación** explícita. Luego pedir confirmación con `AskUserQuestion`
(p.ej. "guardar todo / solo altas / reviso una por una / nada"). **No escribir nada
hasta tener el OK.**

## Fase 5 — Aplicar + avanzar la marca de agua

Solo tras confirmación:

1. Escribir/ampliar/podar las fichas aprobadas, igualando la convención (Fase 0).
2. Actualizar `MEMORY.md`: añadir punteros de las nuevas; refrescar descripciones de
   las que cambiaron materialmente; quitar las jubiladas.
3. **Avanzar la marca de agua** con el `max_ts` del manifest — **solo si el barrido
   fue completo**. Gate de completitud: verificar que TODOS los `n_batches` del
   manifest devolvieron resultado (nº de conjuntos de hallazgos recibidos ==
   `n_batches`). Si un lector murió a media tanda (los límites de sesión matan agentes
   en esta máquina, ver [[project_suite_lote_coordinacion]]), **NO avanzar la marca de
   agua este run**: déjala como estaba y la próxima corrida incremental re-mina todo
   desde el último watermark (la dedup de la Fase 3 absorbe el traslape → hay
   sobre-cobertura, nunca pérdida silenciosa). Tampoco avanzar si `max_ts` viene
   vacío. Reportar "N de M lotes minados" en el resumen para no presentar un barrido
   parcial como completo. Cuando el barrido esté completo, avanzar con:

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
