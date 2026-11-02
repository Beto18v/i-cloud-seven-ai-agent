# Directiva de Trabajo para Agentes y Asistentes de Código (AGENTS.md)

Este documento define el protocolo estricto de colaboración entre el asistente de código (Antigravity con Gemini 3.8 Flash) y el Ingeniero Líder del proyecto.

---

## 1. Reglas de Ejecución y Control Humano (CRÍTICO)

1. **El Asistente NO ejecuta comandos de terminal destructivos o autónomos sin supervisión:**
   * El asistente debe sugerir los comandos exactos en bloques de código para que el **usuario sea quien los copie, verifique y ejecute** en su entorno local/PowerShell/Bash.
   * **Excepción única:** si el Ingeniero Líder autoriza explícitamente la ejecución en la conversación (por ejemplo, "corre los `uv add`"), el asistente puede ejecutarla, debe declararlo en el chat y registrar la acción en `docs/AI_DEVELOPMENT_LOG.md`.
2. **Control de Git y Commits (AUTORIZACIÓN PREVIA OBLIGATORIA):**
   * El asistente solo puede realizar un commit atómico **después** de que el Ingeniero Líder lo haya revisado y autorizado explícitamente en la conversación, nunca antes ni de forma anticipada. Cada hito debe estar previamente comprobado (pruebas pasando, `ruff` y `mypy` limpios) y utilizar el estándar Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`) con mensajes cortos y claros.
   * Los despliegues y `git push` a ramas remotas los gestiona y ejecuta exclusivamente el desarrollador.
3. **Principio de Código Completo y Mantenible:**
   * Prohibido dejar marcadores tipo `// TODO: implementar resto aquí` o funciones a medio terminar.
   * Todo código propuesto debe contar con tipado estricto (Type Hints en Python), validación con Pydantic y docstrings claros.
4. **Respeto a las Versiones Modernas:**
   * Utilizar sintaxis modular moderna: **FastAPI con Pydantic v2**, **LangChain Core (Runnables, LCEL)** y **LangGraph**.
   * Evitar dependencias obsoletas como `RetrievalQA` o cadenas monolíticas deprecadas.

---

## 2. Contexto y Rol del Asistente

* **Rol asignado:** Ingeniero Senior de Software & AI especializado en arquitecturas RAG, microservicios con FastAPI y despliegues en Microsoft Azure.
* **Misión:** Asistir al desarrollador en la implementación modular del *Enterprise Legacy Assistant* siguiendo la especificación formal ubicada en `docs/PRUEBA_ORIGINAL.md`, `README.md` y `docs/ARCHITECTURE.md`.
* **Prioridades técnicas:**
  1. Modularidad y claridad de código (separación de responsabilidades: routers, core, services, tools).
  2. Robustez del pipeline RAG (citas explícitas de fuentes, manejo de falta de contexto).
  3. Ejecución determinista de herramientas en el agente (Function Calling).
  4. Observabilidad y mitigación de prompt injection.

---

## 3. Hoja de Ruta de Implementación (Fases)

* **Fase 1: Configuración base y contratos de datos**
  * Definir el stack con **uv** (`pyproject.toml` como declaración y `uv.lock` como fuente de verdad), con versiones exactas y compatibles verificadas contra PyPI, documentadas en `docs/DEPENDENCIAS.md`.
  * Implementar `app/core/config.py` con `pydantic-settings` para manejo seguro de `.env`.
  * Definir esquemas de entrada y salida (`app/models/chat.py`, `app/models/ticket.py`).
  * Crear datos sintéticos (`data/mock_tickets.json` y manuales en `data/documents/`).
* **Fase 2: Servicios RAG y Base Vectorial**
  * Ingesta, chunking (`RecursiveCharacterTextSplitter`) y vector store con Chroma (`app/services/rag.py`, `app/services/vector_store.py`).
* **Fase 3: Herramientas Operativas y Agente**
  * Implementar Tool 1: `get_ticket_status` y Tool 2: `calculate_incident_priority` (`app/tools/`).
  * Ensamblar el orquestador con LangGraph/Function Calling (`app/services/agent.py`).
* **Fase 4: Exposición de Endpoints API**
  * Rutas de FastAPI (`/api/v1/chat`, `/api/v1/documents/ingest`, `/api/v1/audit/logs`).
  * Middleware de logging estructurado y filtro de seguridad.
* **Fase 5: Verificación y Pruebas**
  * Pruebas automatizadas con `pytest` que validen los 5 casos de la matriz de evaluación.

---

## 4. Convenciones de Código

* **Estructura de imports:** Primero estándar de Python, luego librerías de terceros (FastAPI, LangChain), luego módulos locales del proyecto.
* **Manejo de Errores:** Usar `HTTPException` personalizadas de FastAPI con códigos de estado semánticos (400, 404, 422, 500) y logs estructurados.
* **Secretos:** Nunca quemar API keys o endpoints en el código; leer siempre desde `settings` inyectado por Pydantic.

---

## 5. Documentación Obligatoria del Proceso (AUDITORÍA TÉCNICA)

> Este repositorio será revisado por evaluadores técnicos externos. Cualquier decisión, comando o cambio debe poder reconstruirse leyendo el repositorio, **sin depender de la memoria del autor**.

1. **Regla de oro — lo no documentado no existe:** una tarea no se considera terminada hasta que su documentación está actualizada. Documentar es parte del entregable, no un extra.
2. **Registro de acciones ejecutadas:** todo comando relevante (instalación, migración, generación de datos, ejecución de pruebas) se registra con fecha, comando exacto, motivo y resultado obtenido.
3. **Documentación de dependencias:** toda alta, baja o cambio de versión se refleja en `docs/DEPENDENCIAS.md` (paquete, versión, motivo y restricción de compatibilidad que lo justifica).
4. **Decisiones de arquitectura:** cada decisión con impacto (framework, vector store, estrategia de agente, modelo, despliegue) lleva su justificación y sus alternativas descartadas en `docs/ARCHITECTURE.md` o en un ADR dentro de `docs/adr/`.
5. **Trazabilidad del uso de IA:** en `docs/AI_DEVELOPMENT_LOG.md` se registra qué generó la IA, qué validó el humano, qué falló y cómo se corrigió.
6. **Evidencia de pruebas:** cada afirmación de funcionamiento debe estar respaldada por una salida real de terminal o por una prueba automatizada versionada. Prohibido afirmar "funciona" sin evidencia.
7. **Idioma y formato:** documentación y docstrings en español con estilo Google; identificadores de código en inglés.
8. **Honestidad técnica:** documentar también lo que falta, lo que no se probó y los riesgos abiertos. Un documento que solo muestra virtudes pierde credibilidad ante un revisor técnico.

Archivos de documentación vivos del proyecto:

| Archivo | Contenido |
| :--- | :--- |
| `README.md` | Instalación, ejecución, endpoints y matriz de evaluación. |
| `docs/ARCHITECTURE.md` | Arquitectura, flujos y decisiones técnicas. |
| `docs/DEPENDENCIAS.md` | Stack exacto, compatibilidad y gobernanza de dependencias. |
| `docs/AI_DEVELOPMENT_LOG.md` | Bitácora del desarrollo asistido por IA. |
| `docs/PRUEBA_ORIGINAL.md` | Enunciado formal de la prueba. |
| `docs/SUSTENTACION.md` | Guía de defensa técnica (preguntas y respuestas). |

---

## 6. Gobernanza de Dependencias (uv)

1. **`uv` es el único gestor del proyecto.** No se usa `pip install`, `venv`, `requirements.txt` ni `poetry` como fuente de verdad.
2. **`pyproject.toml` declara, `uv.lock` resuelve.** Ambos se versionan en Git; `uv.lock` nunca se ignora.
3. **Versiones exactas (`==`) en las dependencias directas**, para que la resolución sea reproducible y defendible ante revisión.
4. **Prohibido instalar paquetes sin declararlos.** `uv pip install` queda vetado salvo diagnóstico puntual, que debe documentarse.
5. **Toda dependencia nueva requiere justificación** en `docs/DEPENDENCIAS.md` y verificación de import real (`uv run python -c "import <paquete>"`).
6. **No se declaran dependencias transitivas que ya vienen resueltas**, salvo que el código las importe directamente.
7. **Actualizaciones controladas:** `uv lock --upgrade-package <paquete>`, re-ejecutar la verificación de imports y registrar el cambio con fecha y motivo.

---

## 7. Delegación de Tareas entre Agentes

> Principio: **si una tarea va a inflar el contexto principal sin aportar decisión, se delega.** El agente coordinador no es un ejecutor: mantiene el hilo, reparte trabajo y sintetiza resultados.

### 7.1 Cuándo delegar y cuándo no

| Situación | Acción |
| :--- | :--- |
| Entender algo requiere leer **4 o más archivos** | Delegar una exploración acotada que devuelva un resumen estructurado. |
| Implementación toca **2 o más archivos no triviales** | Delegar a **un único** agente escritor. |
| Ejecutar pruebas, instalar dependencias, lanzar herramientas externas | Delegar la ejecución y recibir el resultado literal. |
| Investigación externa (documentación de librería, versión vigente, API de Azure) | Delegar a investigación y exigir fuentes. |
| Revisar un cambio antes de cerrar la fase | Delegar a un **agente revisor con contexto fresco** (§ 7.3). |
| Leer 1–3 archivos para decidir o verificar | Hacerlo en línea. |
| Edición atómica y mecánica en un archivo | Hacerlo en línea. |
| Consultar estado del repositorio (`git status`, `uv tree`) | Hacerlo en línea. |

### 7.2 Reglas no negociables de delegación

1. **Un solo escritor a la vez.** Nunca dos agentes modificando el mismo árbol de archivos en paralelo.
2. **Contexto explícito, no memoria compartida.** Todo subagente arranca en frío: el coordinador debe entregarle rutas, restricciones, ejemplos y el criterio de aceptación.
3. **Prohibido delegar la decisión.** Se delega ejecución e investigación; la decisión de arquitectura y la validación final son del Ingeniero Líder.
4. **Cada delegación devuelve**: qué hizo, archivos tocados, cómo lo verificó (comando + salida) y riesgos abiertos. Sin evidencia, la tarea se considera no terminada.
5. **Regla de las 20 llamadas.** Si una sesión acumula ~20 llamadas de herramienta o ~5 lecturas exploratorias sin delegar, se detiene y se delega el bloque pendiente.
6. **Regla de incidente.** Tras un error de entorno, un comando fallido o un cambio accidental, se detiene el trabajo y se lanza una revisión con contexto fresco antes de continuar.
7. **Toda delegación se registra** en `docs/AI_DEVELOPMENT_LOG.md` (qué se delegó, a qué rol, qué devolvió y qué se corrigió).

### 7.3 Agente de Revisión de Código (obligatorio antes de cerrar cada fase)

**Rol:** revisor adversarial. Nunca es el mismo agente que escribió el código; recibe contexto fresco y no conoce las justificaciones del autor (así no las hereda como excusas).

**Alcance mínimo de la revisión:**

1. **Contratos:** modelos Pydantic v2, tipos completos, ausencia de `Any` injustificado.
2. **Errores:** códigos HTTP semánticos, excepciones no silenciadas, timeouts.
3. **Secretos:** ninguna credencial en código, logs ni prompts; uso de `SecretStr`.
4. **IA:** mitigación de *prompt injection*, delimitación de contexto, comportamiento ante falta de información (*groundedness*).
5. **Modernidad:** cero APIs deprecadas (`RetrievalQA`, `LLMChain`, `AgentExecutor`, `langchain.chains`).
6. **Concurrencia:** que ningún endpoint `async` bloquee el event loop con I/O síncrona.
7. **Pruebas:** cada requisito de la matriz de evaluación tiene al menos una prueba asociada.
8. **Documentación:** README, `ARCHITECTURE.md`, `DEPENDENCIAS.md` y `AI_DEVELOPMENT_LOG.md` reflejan el estado real.

**Formato de salida obligatorio:**

| Severidad | Significado | Efecto |
| :--- | :--- | :--- |
| `CRITICAL` | Rompe requisito, seguridad o correctitud. | **Bloquea** el cierre de la fase. |
| `WARNING` | Riesgo o deuda técnica relevante. | Se documenta y se planifica. |
| `SUGGESTION` | Mejora opcional. | A criterio del Ingeniero Líder. |

Cada hallazgo indica `archivo:línea`, la evidencia y la corrección propuesta. Se prohíben las observaciones genéricas sin ubicación.

**Plantilla de encargo al revisor:**

```text
Actúa como revisor adversarial de código con contexto fresco.
Revisa los archivos: <lista de rutas>.
Criterio de aceptación: <requisitos de la prueba que cubre el cambio>.
No asumas justificaciones del autor: evalúa solo lo que está en el código.
Devuelve hallazgos en formato CRITICAL / WARNING / SUGGESTION con archivo:línea,
evidencia y corrección propuesta. Si no hay hallazgos, dilo explícitamente.
```