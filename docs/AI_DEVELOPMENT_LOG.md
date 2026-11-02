# Registro de Desarrollo Asistido por IA (AI-Assisted Development Log)

Este documento detalla la metodología, gobierno y protocolos de supervisión humana aplicados durante el ciclo de vida de desarrollo asistido por Inteligencia Artificial (AI-CDL), en estricto cumplimiento de los requerimientos de la prueba técnica.

---

## 1. Herramientas Utilizadas y Entorno de Trabajo

* **Cursor IDE & Claude Code:** Utilizados como asistentes de ingeniería contextual para aceleración de boilerplate, tipado estricto con Pydantic y generación de contratos OpenAPI.
* **GitHub Copilot:** Empleado para autocompletado en línea de funciones repetitivas y transformaciones de datos JSON.

---

## 2. Fases de Asistencia y Distribución del Trabajo

```text
[Arquitectura & Requisitos]  --> 100% Definición y Criterio Humano
[Scaffolding & Boilerplate]  --> 70% Asistido por IA / 30% Revisión y Refactor
[Lógica RAG & Agentic Flow] --> 40% Asistido por IA / 60% Implementación y Pruebas Humanas
[Seguridad & Guardrails]     --> 100% Validación y Auditoría Humana
```

### Tareas Específicas Apoyadas por IA:
1. **Generación de Estructuras Pydantic:** Creación rápida de modelos de validación con tipado riguroso a partir de esquemas JSON.
2. **Generación de Documentación y Docstrings:** Estandarización de documentación inline bajo estándar Google/Sphinx.
3. **Generación de Conjuntos de Datos Mock:** Creación de registros sintéticos realistas para `mock_tickets.json` y manuales de procedimientos técnicos en Markdown.
4. **Diseño Preliminar de Casos de Prueba:** Sugerencia de matrices de testing unitario para endpoints de FastAPI usando `pytest`.

---

## 3. Protocolo de Control de Calidad y Validación Humana

Para evitar el sesgo de "caja negra" y garantizar la integridad del código en producción, se aplicaron las siguientes reglas de verificación:

### A. Prevención de Alucinaciones en Librerías de IA
* **Problema detectado:** Los modelos de asistencia tienden a sugerir métodos obsoletos de LangChain (sintaxis heredada v0.1 como `RetrievalQA` o imports deprecados de `langchain.chains`).
* **Acción correctiva humana:** Se reescribió la arquitectura usando la sintaxis moderna y modular basada en **LangChain Core (Runnables, LCEL)** y **LangGraph**, garantizando código mantenible a largo plazo.

### B. Auditoría de Seguridad y Secretos
* **Principio:** Cero exposición de credenciales en código fuente o contextos de prompts.
* **Acción correctiva humana:** Se implementó `pydantic-settings` para la inyección estricta de variables de entorno, verificando que los prompts de sistema no contuvieran datos sensibles o directivas fácilmente vulnerables.

### C. Prevención de Bucles Infinitos en el Agente
* **Problema detectado:** Al generar flujos agentic, el LLM puede proponer grafos cíclicos sin condiciones claras de parada al invocar herramientas.
* **Acción correctiva humana:** Se definieron validaciones explícitas de estados finales y un límite estricto de recursión (`AGENT_RECURSION_LIMIT=5`) para salvaguardar costos y latencia. El límite es configuración, no una constante escondida en el código.

### D. Auditoría de Vigencia de Modelos
* **Problema detectado:** el README original fijaba `gpt-4o-mini` como modelo base. La verificación contra la documentación de Azure OpenAI reveló que está marcado como **Deprecated con retiro el 14/04/2027**, es decir, la entrega habría nacido con fecha de caducidad.
* **Acción correctiva humana:** se migró a `gpt-5-mini` como deployment de chat y se conservó `text-embedding-3-small` (GA hasta 09/02/2028). Se documentó además que la familia `gpt-5*` puede rechazar `temperature`, motivo por el que esa variable es opcional y se omite por defecto.

---

## 4. Riesgos Identificados y Estrategias de Mitigación

| Riesgo Técnico Identificado | Impacto Potencial | Estrategia de Mitigación Aplicada |
| :--- | :--- | :--- |
| **Dependencia ciega de código generado** | Introducción de vulnerabilidades de inyección o código subóptimo en latencia. | Revisión manual línea por línea; ejecución obligatoria de `ruff check`, `ruff format --check` y tipado estricto (`mypy`). |
| **Fuga de contexto en respuestas RAG** | El modelo inventa respuestas coherentes pero falsas si el chunk recuperado es ambiguo. | Ingeniería de prompts defensiva: instrucción estricta de responder *"No disponible en los manuales"* ante umbrales de similitud menores a 0.70. |
| **Sobrecarga de tokens** | Ingesta de documentos completos sin filtrado, encareciendo el costo por turno. | Fragmentación controlada con `RecursiveCharacterTextSplitter` (chunk size: 600, overlap: 80). |

---

## 5. Conclusión del Ejercicio AI-Assisted
El uso de herramientas de asistencia redujo el tiempo de desarrollo en un estimado del **45%**, principalmente en tareas de scaffolding y datos mock, permitiendo concentrar el esfuerzo del ingeniero en la toma de decisiones arquitectónicas, la robustez del pipeline RAG y la confiabilidad del agente.

---

## 6. Bitácora de Ejecución (trazabilidad de comandos)

> Obligatorio según `AGENTS.md` § 5.2. Cada fila permite reconstruir qué se ejecutó, por qué y con qué resultado, incluyendo lo que **no** se ejecutó.

### 6.1 Sesión 2026-10-31 — Bootstrap del stack con uv

**Autorización:** los comandos 1, 2, 4, 5 y 6 los ejecutó el asistente con autorización explícita del Ingeniero Líder en la conversación (excepción de `AGENTS.md` § 1.1). Comprobación del entorno: `Python 3.12.7`, `uv 0.10.8`.

| # | Comando | Motivo | Resultado |
| :-: | :--- | :--- | :--- |
| 1 | `uv add "fastapi==0.162.0" ... (15 paquetes)` | Fijar dependencias de ejecución con versiones exactas verificadas contra PyPI. | 112 paquetes instalados, 0 conflictos. |
| 2 | `uv add --dev "pytest==9.2.0" ... (5 paquetes)` | Herramientas de calidad y pruebas. | 12 paquetes instalados. |
| 3 | Edición de `pyproject.toml`: `requires-python` `>=3.12` → `>=3.11` | Alinear con README/ARCHITECTURE y con el suelo real impuesto por `pydantic-settings 2.16.2`. | `uv lock` re-resuelto. |
| 4 | `uv lock` + `uv sync --frozen` | Materializar el grafo completo en `.venv`. | 128 paquetes resueltos. |
| 5 | Verificación de imports del stack (script temporal) | Probar compatibilidad **real**, no solo de resolución. | OK: chunking 600/80, `StateGraph`, `ToolNode`, `ChatOpenAI`, `OpenAIEmbeddings`, `TestClient` → 200. |
| 6 | `uv lock --check` · `uv run ruff check main.py` · `uv run pytest --collect-only` | Validar que las configuraciones de herramientas del `pyproject.toml` son válidas. | Lock al día · "All checks passed!" · "no tests collected" (aún no existen pruebas). |
| 7 | `uv export --frozen --no-dev --no-hashes ...` | Documentar el export para Docker / Azure App Service. | **NO EJECUTADO**: el Ingeniero Líder rechazó la autorización. El comando queda documentado en `docs/DEPENDENCIAS.md` § 8 y deberá validarse al construir la imagen. |
| 8 | `Remove-Item main.py` · `Move-Item ARCHITECTURE.md, AI_DEVELOPMENT_LOG.md, PRUEBA_ORIGINAL.md docs\` | Eliminar el entrypoint de ejemplo de `uv init` y alinear la documentación con el árbol declarado en el README. | Raíz con solo `AGENTS.md`, `README.md`, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`; los tres documentos viven en `docs/`. |

### 6.2 Hallazgos técnicos de la sesión

1. **`httpx2` es requerido por `starlette 1.10.0`** para `TestClient`; llega como transitiva de `langsmith` y `huggingface-hub`, por lo que no se declara explícitamente.
2. **`uvicorn` resuelve `sys.path`** insertando `--app-dir` (default `""`, el directorio de trabajo); `uv run uvicorn app.main:app` funcionará desde la raíz. **`pytest` no lo hace**: requiere `pythonpath = ["."]` porque `tests/` no es un paquete.
3. **`numpy` se resuelve por tramos de versión de Python** (2.5.4 en 3.12, 2.4.6 en tramos superiores), por eso `uv.lock` contiene varias resoluciones. No es un conflicto.
4. **No se instala el meta-paquete `langchain`**: `langchain-core` + `langgraph` (+ `langgraph-prebuilt`) cubren el alcance y evitan las cadenas deprecadas.
5. **Azure OpenAI soporta la API v1 sin `api-version`** (GA agosto 2025): se invoca contra `<endpoint>/openai/v1/` y acepta la firma estándar de OpenAI, lo que permite un único cliente para Azure y OpenAI directo. Se eliminó `AZURE_OPENAI_API_VERSION` del diseño.
6. **`gpt-4o-mini` está deprecado** (retiro 14/04/2027). Sustituido por `gpt-5-mini`.
7. **El umbral de similitud solo tiene sentido con métrica coseno.** Chroma usa L2 por defecto: con esa métrica, `SIMILARITY_THRESHOLD=0.70` no representa "70 % de similitud". La colección se crea con `hnsw:space="cosine"` explícito y la métrica quedó como configuración (`VECTOR_STORE_SPACE`).
8. **`env_ignore_empty=True` en `pydantic-settings`**: una variable declarada pero vacía (`LLM_TEMPERATURE=`) se interpreta como *no definida*. Se usa deliberadamente para expresar "no enviar este parámetro", sin necesidad de comentar líneas del `.env`.
9. **`uv run python <script fuera del proyecto>` no añade el directorio de trabajo a `sys.path`** (Python añade el directorio del script). La verificación requirió `PYTHONPATH` explícito. Consecuencia práctica: `pytest` sí lo necesita declarado en `pyproject.toml`.

### 6.3 Sesión 2026-10-31 — Decisiones de diseño y configuración base

**Autorización:** comandos 9, 10 y 11 ejecutados por el asistente con autorización explícita del Ingeniero Líder.

| # | Comando / Acción | Motivo | Resultado |
| :-: | :--- | :--- | :--- |
| 9 | Creación de `.env.example`, `app/__init__.py`, `app/core/__init__.py`, `app/core/config.py` | Materializar la configuración tipada decidida en D1-D5. | 4 archivos; `config.py` con `frozen=True`, `SecretStr`, validación cruzada y fail-fast. |
| 10 | `uv run python <script temporal>` (28 aserciones) | Probar la configuración **ejecutándola**: base URL v1, deployments, `SecretStr` sin fuga, fail-fast, enums case-insensitive, inmutabilidad. | `TOTAL 28 | PASS 28 | FAIL 0`. |
| 11 | `uv run ruff check app` · `uv run ruff format app` · `uv run mypy app` | Calidad estática sobre el nuevo código. | 6 hallazgos iniciales (RUF022 ×2, S104, E501 ×2, I001) corregidos → "All checks passed!", "3 files already formatted", `mypy`: "Success: no issues found in 3 source files". |
| 12 | Edición de `README.md`, `docs/ARCHITECTURE.md`, `docs/DEPENDENCIAS.md` | Eliminar la documentación ficticia (pip, `requirements.txt`, Chroma in-memory, `gpt-4o-mini`, Postgres como componente entregado, tool con dos nombres). | README §2/§3/§4/§7/§8 reescritos; ARCHITECTURE §2/§3.B/§3.D/§4/§5 corregidos; DEPENDENCIAS §11.3/§11.4/§12 actualizados. |

#### Decisiones adoptadas (D1-D5)

| ID | Decisión | Alternativa descartada | Justificación |
| :--: | :--- | :--- | :--- |
| **D1** | **1A** — persistencia en archivo: `data/mock_tickets.json`, `data/audit/audit.jsonl`, Chroma en `data/vectorstore/`. | SQLite; PostgreSQL + pgvector en Docker. | El enunciado admite "base de datos local" y "archivo JSON". Cero infraestructura para el revisor y trazabilidad por `git diff`. |
| **D2** | **2A** — Azure OpenAI primario, OpenAI directo como *fallback* por configuración (`AI_PROVIDER`). | Solo Azure; solo OpenAI. | Un único proveedor elimina el riesgo de bloqueo del evaluador; mantener ambos cuesta una propiedad y cero código duplicado. |
| **D3** | **3A** — `gpt-5-mini`. | `gpt-5.4-mini`, `gpt-5-nano`, quedarse en `gpt-4o-mini`. | Equilibrio calidad/coste y vigencia garantizada; `gpt-4o-mini` caduca en 2027. |
| **D4** | **4A** — `calculate_incident_priority`. | `calculate_sla_priority`. | Es el nombre exigido por el README § 6 (TC-03) y por `AGENTS.md` § 3. Se unificó ARCHITECTURE, que usaba el otro. |
| **D5** | **5A** — API key de Azure en `SecretStr` vía `pydantic-settings`. | `azure-identity` con Managed Identity. | Debe funcionar en la máquina del evaluador, fuera de Azure. La ruta con Managed Identity queda documentada para producción. |

### 6.4 Revisión adversarial con contexto fresco (obligatoria, `AGENTS.md` § 7.3)

La revisión la ejecutó un **agente distinto del autor**, sin acceso a las justificaciones previas, sobre `app/core/config.py`, `.env.example` y `pyproject.toml`. Veredicto: **0 CRITICAL, 6 WARNING, 7 SUGGESTION**.

| # | Severidad | Hallazgo verificado | Corrección aplicada |
| :-: | :--- | :--- | :--- |
| 1 | WARNING | `env_file=(".env",)` se resolvía contra el **CWD**: lanzado desde otro directorio, el `.env` se ignoraba en silencio y el error culpaba a variables que sí existían. | `env_file=(str(PROJECT_ROOT / ".env"),)`. |
| 2 | WARNING | `AZURE_OPENAI_API_KEY=" "` (un espacio) pasaba la validación: `env_ignore_empty` no filtra espacios. El servicio arrancaba y fallaba con 401 en la primera petición. | Validador `_blank_secret_is_absent` que normaliza secreto vacío a `None`. |
| 3 | WARNING | `llm_base_url` solo hacía `rstrip("/")`: un endpoint con query o ruta generaba una URL inválida y podía volcar la credencial a los logs de arranque. | Validador de endpoint: https obligatorio, sin ruta, sin query, sin fragmento. |
| 4 | WARNING | `HttpUrl` acepta `http://`: la API key habría viajado en claro. | Validación de esquema `https`. |
| 5 | WARNING | El patrón de `COLLECTION_NAME` no replicaba la regla real de Chroma (`_docs`, `docs-` explotaban en runtime). | Patrón alineado con Chroma + rechazo de `..` y de formato IPv4. |
| 6 | WARNING | Los marcadores `REPLACE_ME` de la plantilla eran valores **válidos**: copiar `.env.example` a `.env` arrancaba "correctamente" y fallaba en la primera llamada. | `_reject_placeholder()` en la validación cruzada. |

De las 7 SUGGESTION se aplicaron 5 (normalización de `BASE_DIR` contra la raíz, `BASE_DIR` documentada en la plantilla, métrica vectorial *case-insensitive*, `chat_model_name` sin `or ""` silencioso, CORS `*` rechazado en producción). Se rechazaron 2 con criterio explícito:

* **`extra="forbid"`:** se mantiene `ignore` porque en despliegue la plataforma inyecta variables ajenas (`WEBSITE_*`, `APPLICATIONINSIGHTS_*`) y un `.env` con claves heredadas impediría el arranque. El riesgo de *typo* se acepta y se documenta.
* **Aviso en log al usar `gpt-5*` con `temperature`:** no se registra nada desde el validador (efecto secundario en la construcción del objeto). Se expone `settings.sends_temperature` para que el cliente decida y para que el valor aparezca en `redacted_summary()`.

**Evidencia de la corrección:** la batería de verificación pasó de **28 a 42 aserciones** (8 de ellas cubren regresiones de esta revisión) → `TOTAL 42 | PASS 42 | FAIL 0`. En la primera ejecución 2 aserciones fallaron por un error **de la propia prueba** (buscaban `COLLECTION_NAME` cuando pydantic reporta `collection_name`), no del código; se corrigió la aserción y se documenta el episodio.

### 6.5 Sesión 2026-11-02 — Fase 1: logging estructurado, contratos de salud y entrypoint ASGI

**Autorización:** el Ingeniero Líder solicitó explícitamente implementar esta unidad de trabajo y ejecutar los cuatro comandos de verificación (`ruff`, `ruff format`, `mypy`, `pytest`). No se modificó `app/core/config.py`, no se leyó `.env`, no se instalaron dependencias y no se hizo `git add`, `commit` ni `push`.

| # | Comando / Acción | Motivo | Resultado |
| :-: | :--- | :--- | :--- |
| 13 | Creación de `app/core/logging.py`, `app/models/health.py`, `app/models/__init__.py`, `app/main.py` | Materializar el logging JSON con redacción de secretos, el contrato de `/health` y el entrypoint ASGI con `create_app()`. | 4 archivos; `uvicorn app.main:app` deja de fallar por ausencia de módulo. |
| 14 | Creación de `tests/conftest.py`, `tests/test_config.py`, `tests/test_health.py`, `tests/test_logging.py` | Aislar la suite del `.env` real y cubrir configuración, sonda de salud y seguridad del logging. | 13 pruebas, sin red ni credenciales reales. |
| 15 | `uv run ruff check app tests` | Calidad estática (incluye reglas `S`, `ASYNC`, `B`, `SIM`). | `All checks passed!` |
| 16 | `uv run ruff format --check app tests` | Formato obligatorio del proyecto. | `11 files already formatted` |
| 17 | `uv run mypy app` | Tipado estricto (`disallow_untyped_defs`). | `Success: no issues found in 7 source files` |
| 18 | `uv run pytest -q` | Evidencia ejecutable de los contratos. | `13 passed in 0.36s` |

#### Decisiones adoptadas (D6-D9)

| ID | Decisión | Alternativa descartada | Justificación |
| :--: | :--- | :--- | :--- |
| **D6** | Cadena única de procesadores compartida por structlog y por `logging` mediante `ProcessorFormatter` (`foreign_pre_chain`), con un procesador propio que inyecta `timestamp`, `level`, `logger` y `correlation_id`. | Formatear solo structlog y dejar que `uvicorn`/`fastapi` conserven su formato por defecto. | El requisito exige que los logs de terceros también sean JSON Lines; una sola cadena evita divergencias entre logs nativos y ajenos. |
| **D7** | Redacción en **dos capas**: (1) por partes de clave normalizadas (camelCase, guion y guion bajo) más detección de `SecretStr`; (2) escaneo de texto posterior a `format_exc_info` sobre `event`, `exception`, argumentos formateados y `extra`. Las métricas numéricas de tokens (`token_count`, `token_usage`, `llm_max_output_tokens`) no se redactan cuando su valor es `int` o `float`. | Coincidencia por subcadena simple; redacción **solo** por clave. | La subcadena simple redactaría texto benigno; la comparación por partes cubre `openai_api_key`, `access_token`, `client_secret` y `X-Api-Key`. La redacción por clave sola no detectaba secretos embebidos en mensajes, tracebacks ni líneas de `uvicorn.access`, de ahí la segunda capa. **Contrapartida aceptada:** el escaneo de texto puede sobrerredactar valores con forma de credencial (`authorization: Bearer ...` produce dos marcadores) y toda clave que contenga `api_key` se redacta aunque su valor sea el booleano de `redacted_summary()`. No se afirma "cero falsos positivos". |
| **D8** | Aislamiento de pruebas con `monkeypatch.setenv`, `monkeypatch.setitem(Settings.model_config, "env_file", None)`, `reset_settings_cache()` e **importación diferida** de `app.main` dentro de la fixture. | Depender del `.env` local o importar `app.main` a nivel de módulo en los tests. | `pydantic-settings` construye sus fuentes en cada instanciación, así que neutralizar `env_file` elimina por completo la lectura del `.env` real; la importación diferida garantiza que `create_app()` se ejecute después de inyectar el entorno. `monkeypatch` restaura ambos cambios al terminar. |
| **D9** | `ENVIRONMENT=testing` (no `ENVIRONMENT=test`) en la fixture. | Usar literalmente `test`. | `Environment` solo declara `development`, `testing`, `staging` y `production`; `test` no es un valor válido y haría fallar la configuración. Se documenta la desviación respecto del enunciado de la tarea. |

#### Decisiones de contratos de datos (D10-D12)

Estas decisiones fijan el contrato público de `app/models/chat.py` y `app/models/ticket.py` **antes** de implementarlos. Se adoptan en este punto porque D10 es la menos reversible: afecta al archivo de datos mock y a la forma de la respuesta de la API.

| ID | Decisión | Alternativa descartada | Justificación |
| :--: | :--- | :--- | :--- |
| **D10** | Un único enum `Priority` (`low`, `medium`, `high`, `critical`) compartido por `Ticket.priority` y `IncidentClassification.severity`. | Dos enums independientes (`TicketPriority` e `IncidentSeverity`) con una función de mapeo explícita. | En el alcance de la prueba el mapeo es 1:1; compartir el enum elimina duplicación y divergencias de validación. **Supuesto documentado:** si el negocio introduce reglas propias de prioridad (por ejemplo, clientes VIP) que no coincidan con la severidad técnica, se separan los enums y se mapea explícitamente. |
| **D11** | `ChatResponse.grounded: bool`, calculado **solo** desde el mejor score de recuperación frente a `SIMILARITY_THRESHOLD`. | (a) Preguntar al LLM si su respuesta está fundamentada; (b) inferirlo buscando una frase concreta en el texto. | El umbral es determinista y barato; el auto-reporte del modelo cuesta tokens y no es fiable, y la inferencia textual se rompe al cambiar la redacción. Permite verificar TC-04 sin analizar prosa. `grounded=False` significa "no hubo contexto por encima del umbral", **no** "la respuesta es incorrecta". |
| **D12** | `ChatResponse.tool_calls` expone únicamente `name`, `success` y `latency_ms`. Los argumentos y el resultado completo se escriben en `data/audit/audit.jsonl` y se consultan en `GET /api/v1/audit/logs`. | (a) Exponer argumentos y resultados completos en la respuesta; (b) no exponer nada y dejar la evidencia solo en los logs. | La versión sanitizada demuestra la invocación de herramientas (TC-02/TC-03) sin acoplar el contrato público a los internos de LangGraph ni arriesgar datos personales en la respuesta. El detalle queda disponible para auditoría. |

#### Estado de avance al cierre de esta unidad

| Componente | Estado | Evidencia |
| :--- | :--- | :--- |
| Stack `uv` y `uv.lock` | Completo | 128 paquetes resueltos; `uv lock --check` |
| Configuración central (`app/core/config.py`) | Completo | Batería de aserciones y revisión adversarial cerrada (§ 6.4) |
| Logging estructurado (`app/core/logging.py`) | Completo, con correcciones adversariales aplicadas | `tests/test_logging.py`; ver § 6.5.1 |
| Contrato de salud (`app/models/health.py`) | Completo | `/health` y `/docs` cubiertos con `TestClient` |
| Entrypoint ASGI (`app/main.py`) | Completo | `create_app()`, `lifespan` y CORS desde settings |
| Pruebas automatizadas versionadas | 44 pasando | `uv run pytest -q` → `44 passed in 0.41s` (ver § 6.5.1) |
| Contratos de chat y ticket (`app/models/chat.py`, `ticket.py`) | Pendiente (siguiente unidad) | Decisiones D10-D12 fijadas |
| Datos sintéticos (`data/documents/`, `data/mock_tickets.json`) | Pendiente | Directorios creados por el `lifespan`, aún vacíos |
| Servicios RAG y vector store | Pendiente | — |
| Herramientas y agente | Pendiente | — |
| API `/api/v1` | Pendiente | — |
| Dockerfile, IaC y CI/CD | Pendiente | — |
| Matriz TC-01…TC-05 | Pendiente | — |

> La revisión adversarial de esta unidad está en curso; su resultado se anexará al cerrar la fase, conforme a `AGENTS.md` § 7.3.

#### Riesgos abiertos y hallazgos

1. **Resuelto (§ 6.5.1):** `ruff` clasificaba `app` como tercero porque `src = ["app", "tests"]` apunta al *interior* del paquete. Se añadió `known-first-party = ["app"]` en `[tool.ruff.lint.isort]` y se reordenaron los imports de `tests/`; `ruff check --select I` pasa.
2. **Resuelto (§ 6.5.1):** la fixture redirige `BASE_DIR` a `tmp_path`, por lo que el `lifespan` ya no crea `data/` dentro del repositorio durante las pruebas. `test_lifespan_creates_directories_under_tmp_path` verifica que `documents`, `vectorstore` y `audit` quedan bajo `tmp_path` y fuera de `PROJECT_ROOT`.
3. **Resuelto (§ 6.5.1):** `redact_text_secrets` se ejecuta **después** de `format_exc_info`, de modo que el traceback formateado también se inspecciona. Regresión cubierta por `test_redacts_secret_in_formatted_exception`.
4. **`/health` no comprueba conectividad con el proveedor de IA**, por diseño: es una sonda de *liveness/readiness* y no debe depender de servicios externos. La disponibilidad del proveedor se validará en la fase del cliente LLM. README § 5 se corrigió para no prometer conectividad.

#### Correcciones de la revisión adversarial (unidad logging/health/main)

**Veredicto recibido:** **1 CRITICAL, 6 WARNING, 10 SUGGESTION — BLOCK.**

La revisión adversarial con contexto fresco (`AGENTS.md` § 7.3) se ejecutó sobre `app/core/logging.py`, `app/models/health.py`, `app/models/__init__.py`, `app/main.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_health.py`, `tests/test_logging.py`, `docs/AI_DEVELOPMENT_LOG.md` § 6.5 y `pyproject.toml`.

| ID | Severidad | Qué estaba mal | Corrección aplicada | Ubicación |
| :--: | :--- | :--- | :--- | :--- |
| **C1** | CRITICAL | `redact_secrets` decidía solo por clave; `event`, `exception` y argumentos formateados no se inspeccionaban. Fuga real en `uvicorn.access`, tracebacks y cabeceras `Cookie`. | Procesador de texto `redact_text` + `redact_text_secrets`, ejecutado **después** de `format_exc_info`; recorre `dict`/`list`/`tuple`/`str`. Se mantiene la redacción por clave. | `app/core/logging.py:225` (`redact_text`), `:293` (`redact_text_secrets`), `:362` (orden de la cadena) |
| **W1** | WARNING | Denylist incompleta (`credentials`, `connection_string`, `cookie`, `access_key`, `private_key`, `client_secret`, `x-api-key`...). | Partes y compuestos ampliados; normalización camelCase/guion/guion bajo. | `app/core/logging.py:74-110`, `:167` |
| **W2** | WARNING | `app.*` se clasificaba como tercero y el orden de imports contradecía `AGENTS.md` § 4. | `known-first-party = ["app"]` y reordenación de imports en `tests/`. | `pyproject.toml:47-48`; `tests/*.py` |
| **W3** | WARNING | Las primeras líneas de `uvicorn` salían en texto plano porque el logging solo se configuraba en el `lifespan`. | `configure_logging(settings)` al inicio de `create_app()` (idempotente) y desconexión de los handlers propios de `uvicorn`. | `app/main.py:71`; `app/core/logging.py:396` |
| **W4** | WARNING | README prometía "conectividad" en `/health`, que no comprueba servicios externos. | Descripción corregida a sonda *liveness/readiness* sin dependencias externas. | `README.md:138` |
| **W5** | WARNING | Las pruebas creaban `data/` real dentro del repositorio. | `BASE_DIR` se inyecta como `tmp_path` y una prueba verifica las rutas derivadas. | `tests/conftest.py:58`; `tests/test_health.py:56` |
| **W6** | WARNING | No había prueba end-to-end de redacción. | Cuatro regresiones de extremo a extremo más el caso `extra={"authorization": ...}`. | `tests/test_logging.py:197-266` |

**Evidencia literal BEFORE/AFTER de C1** (secretos ficticios, `LEAKME`). `BEFORE` es la salida con la redacción antigua (solo por clave); `AFTER` es la salida del escaneo de texto nuevo:

```text
BEFORE: GET /api/v1/chat?api_key=LEAKME7&x=1 HTTP/1.1
AFTER:  GET /api/v1/chat?api_key=***REDACTED***&x=1 HTTP/1.1
BEFORE: RuntimeError: boom sk-LEAKME4
AFTER:  RuntimeError: boom ***REDACTED***
BEFORE: headers={'Cookie': 'session=LEAKME6'}
AFTER:  headers={'Cookie': '***REDACTED***'}
BEFORE: authorization: Bearer LEAKME5
AFTER:  authorization: ***REDACTED*** ***REDACTED***
```

**Sugerencias aplicadas:** S1 (`Processor` en lugar de `Any`), S2 (`ExtraAdder` conserva y redacta `extra=`), S3 (métrica numérica de tokens preservada y D7 corregido), S4 (`asyncio.to_thread` para `ensure_directories`), S5 (`Depends(get_settings)` también en `/`), S6 (aislamiento documentado en el docstring de `app/main.py`), S7 (handlers retirados y cerrados), S8 (`asyncio_default_fixture_loop_scope = "function"`), S9 (smoke test real registrado abajo) y S10 (`_HANDLER_MARKER` importado; archivo con salto de línea final).

**Aislamiento de pruebas (S6):** se mantiene `app = create_app()` a nivel de módulo porque `uvicorn app.main:app` exige un objeto ASGI resoluble; las pruebas siguen importando `create_app` de forma diferida después de inyectar el entorno. La regla queda documentada en el docstring de `app/main.py` y en D8.

**Sugerencias no aplicadas:** ninguna se rechazó. Matiz sobre S7: el `handlers.clear()` no era redundante. Al quitarlo, el smoke test demostró que `uvicorn` conservaba sus handlers y emitía **texto plano duplicado** (`INFO: Started server process [27716]`) antes del JSON. Se sustituyó por `_detach_all_handlers()` explícito, que retira y **cierra** todos los handlers de los loggers gestionados; así se cumple W3 sin la llamada redundante original.

**Verificación de la corrección (salida literal):**

```text
$ uv run ruff check app tests
All checks passed!

$ uv run ruff format --check app tests
11 files already formatted

$ uv run mypy app
Success: no issues found in 7 source files

$ uv run pytest -q
44 passed in 0.41s
```

**Smoke test real de `uvicorn`** (`app.main:app`, puerto 8099):

```text
STATUS=200
{"status":"ok","app_name":"Enterprise Legacy Assistant","version":"0.1.0","environment":"development","ai_provider":"openai","timestamp":"2026-11-02T15:42:05.917212Z"}
--- STDERR (first 6 lines) ---
{"event": "Started server process [20056]", "color_message": "Started server process [\u001b[36m%d\u001b[0m]", "timestamp": "2026-11-02T15:42:00.775384+00:00", "level": "INFO", "logger": "uvicorn.error"}
{"event": "Waiting for application startup.", "timestamp": "2026-11-02T15:42:00.775858+00:00", "level": "INFO", "logger": "uvicorn.error"}
{"app_name": "Enterprise Legacy Assistant", "app_version": "0.1.0", "environment": "development", "debug": false, "ai_provider": "openai", "chat_model": "gpt-5-mini", "embedding_model": "text-embedding-3-small", "llm_base_url": "https://api.openai.com/v1", "llm_temperature": null, "sends_temperature": false, "llm_max_output_tokens": 500, "llm_timeout_seconds": 10.0, "agent_recursion_limit": 5, "chunk_size": 600, "chunk_overlap": 80, "top_k_results": 3, "similarity_threshold": 0.7, "vector_store_space": "cosine", "vector_store_dir": "D:\\Documentos\\Repositories\\demos\\i-cloud-seven-ai-agent\\data\\vectorstore", "openai_api_key_configured": "***REDACTED***", "azure_openai_api_key_configured": "***REDACTED***", "event": "application_startup", "timestamp": "2026-11-02T15:42:00.780862+00:00", "level": "INFO", "logger": "app.main"}
{"event": "Application startup complete.", "timestamp": "2026-11-02T15:42:00.781367+00:00", "level": "INFO", "logger": "uvicorn.error"}
{"event": "Uvicorn running on http://127.0.0.1:8099 (Press CTRL+C to quit)", "color_message": "Uvicorn running on \u001b[1m%s://%s:%d\u001b[0m (Press CTRL+C to quit)", "timestamp": "2026-11-02T15:42:00.781870+00:00", "level": "INFO", "logger": "uvicorn.error"}
{"event": "127.0.0.1:65219 - \"GET /health HTTP/1.1\" 200", "timestamp": "2026-11-02T15:42:05.917212+00:00", "level": "INFO", "logger": "uvicorn.access"}
```

Observación honesta: `openai_api_key_configured` y `azure_openai_api_key_configured` aparecen como `***REDACTED***` porque sus claves contienen `api_key`. Es sobrerredacción conservadora aceptada: `redacted_summary()` sigue devolviendo booleanos, pero el logger los oculta. Se documenta para que el revisor no lo interprete como un fallo de la sonda.

**Estado:** correcciones aplicadas y verificadas.

### 6.6 Sesión 2026-11-02 — Fase 1: Contratos de datos de dominio y chat (`app/models/`)

**Autorización:** el Ingeniero Líder autorizó explícitamente la implementación de los contratos de datos tras verificar la persistencia en Engram y confirmar las decisiones de diseño (D10 compartida, UUID4 para sesiones, regex `TCK-\d{3,6}` para soportar `TCK-104` del README § 6, regla de SLA determinista para incidentes y compatibilidad de `query` con alias `message`).

**Delegación:** conforme a `AGENTS.md` § 7.1 (implementación que toca 2+ archivos no triviales), la tarea se delegó a un único agente escritor (`model-contracts-writer`) con contexto explícito y restricciones estrictas (sin modificar `.env` ni `config.py`, sin commits de Git, sin placeholders).

| # | Comando / Acción | Motivo | Resultado |
| :-: | :--- | :--- | :--- |
| 19 | Creación de `app/models/ticket.py`, `app/models/chat.py` y actualización de `app/models/__init__.py` | Materializar los contratos tipados de dominio (tickets, incidentes) y de transporte HTTP (chat, citas, herramientas). | 3 archivos; 11 contratos y enumeraciones exportados con `frozen=True` y `extra="forbid"`. |
| 20 | Creación de `tests/test_models.py` | Batería exhaustiva de pruebas unitarias para contratos Pydantic v2. | 51 nuevas pruebas unitarias (casos límite, inmutabilidad, regex, alias, serialización). |
| 21 | `uv run ruff format app tests` | Formato obligatorio del proyecto. | `14 files left unchanged` |
| 22 | `uv run ruff check app tests` | Verificación de linting estático e imports (`isort`). | `All checks passed!` |
| 23 | `uv run mypy app` | Verificación de tipado estricto (`disallow_untyped_defs`). | `Success: no issues found in 9 source files` |
| 24 | `uv run pytest -q` | Ejecución de la suite completa aislada. | `95 passed in 0.45s` |

#### Estado de avance tras esta unidad

| Componente | Estado | Evidencia |
| :--- | :--- | :--- |
| Stack `uv` y `uv.lock` | Completo | 128 paquetes resueltos; `uv lock --check` |
| Configuración central (`app/core/config.py`) | Completo | 42 aserciones y revisión adversarial cerrada |
| Logging estructurado (`app/core/logging.py`) | Completo | Escaneo de texto de dos capas validado |
| Contrato de salud (`app/models/health.py`) | Completo | `/health` y `/docs` cubiertos con `TestClient` |
| Entrypoint ASGI (`app/main.py`) | Completo | `create_app()`, `lifespan` y CORS desde settings |
| Contratos de chat y ticket (`app/models/chat.py`, `ticket.py`) | Completo | 51 pruebas en `tests/test_models.py` |
| Datos sintéticos (`data/documents/`, `data/mock_tickets.json`) | Completo | 7 tickets validados (incluye `TCK-104`), 3 manuales RAG y 10 pruebas |
| Servicios RAG y vector store (`app/services/`) | Completo | Ingesta 600/80, Chroma persistente y groundedness (12 pruebas) |
| Pruebas automatizadas versionadas | 117 pasando | `uv run pytest -q` → `117 passed in 5.03s` |
| Herramientas y agente LangGraph | Pendiente (Fase 3) | — |
| Endpoints `/api/v1` | Pendiente (Fase 4) | — |
| Matriz TC-01…TC-05 | Pendiente (Fase 5) | — |

### 6.7 Sesión 2026-11-02 — Fase 1: Datos sintéticos mock, manuales RAG y pruebas de dataset

**Autorización:** el Ingeniero Líder autorizó la generación de datos sintéticos y manuales técnicos, habilitando además la realización de commits atómicos controlados para hitos comprobables.

**Delegación:** se delegó la tarea al subagente escritor `model-contracts-writer`, cumpliendo `AGENTS.md` § 7.1 y § 7.2.

| # | Comando / Acción | Motivo | Resultado |
| :-: | :--- | :--- | :--- |
| 25 | Creación de `data/mock_tickets.json` | Proveer dataset sintético realista para el sistema legado y para la Tool 1 (`get_ticket_status`). | 7 tickets conformes al modelo `Ticket` (incluye `TCK-104` con asignación para TC-02, timestamps UTC y variedad de estados/prioridades). |
| 26 | Creación de `data/documents/*.md` | Generar manuales técnicos para el pipeline RAG estructurados con jerarquía Markdown limpia. | 3 manuales: `manual_operaciones_v2.md` (procedimiento de reinicio legado para TC-01), `resolucion_bloqueos_bd.md` y `politicas_sla_escalamiento.md`. |
| 27 | Creación de `tests/test_mock_data.py` | Pruebas automatizadas de integridad de datos y manuales. | 10 pruebas unitarias pasando (validación de esquema Pydantic, unicidad de IDs y existencia de términos clave). |
| 28 | `uv run ruff format app tests` | Formateo estricto del código. | `15 files left unchanged` |
| 29 | `uv run ruff check app tests` | Análisis estático de linting e imports. | `All checks passed!` |
| 30 | `uv run mypy app` | Tipado estricto sin tipos `Any` injustificados. | `Success: no issues found in 9 source files` |
| 31 | `uv run pytest -q` | Ejecución de la suite completa. | `105 passed in 0.55s` |

### 6.8 Sesión 2026-11-02 — Fase 2: Servicios RAG y Base Vectorial (Chroma + LangChain LCEL)

**Autorización y Limpieza de Repositorio:** el Ingeniero Líder autorizó la continuación con la Fase 2 y solicitó expresamente purgar el directorio `.atl` de todo el historial de Git (Opción 2: `git-filter-branch` sobre `main` e inclusión de `.atl/` en `.gitignore`).

**Implementación de Servicios RAG:**
1. **`app/services/vector_store.py`:** `VectorStoreService` con Chroma persistente (`hnsw:space="cosine"`), cliente `OpenAIEmbeddings`, métodos síncronos y asíncronos (`asyncio.to_thread`), y función de score de relevancia acotada a `[0.0, 1.0]`.
2. **`app/services/rag.py`:** `RAGService` con chunking recursivo (600/80), metadatos estructurados (`source`, `chunk_id`), mapeo a `SourceReference` y evaluación determinista de `is_grounded` (D11).
3. **`tests/test_vector_store.py` y `tests/test_rag.py`:** 12 pruebas unitarias aisladas con `NormalizedDeterministicEmbeddings` sobre `tmp_path`, sin consumir saldo ni requerir red.

**Evidencia de Verificación:**
- `uv run ruff format --check app tests`: `20 files already formatted`
- `uv run ruff check app tests`: `All checks passed!`
- `uv run mypy app`: `Success: no issues found in 12 source files`
- `uv run pytest -q`: `117 passed in 5.03s`

### 6.9 Sesión 2026-11-02 — Fase 3: Herramientas Operativas, Auditoría y Agente LangGraph

**Autorización:** el Ingeniero Líder autorizó la implementación de la Fase 3 del proyecto, cubriendo las herramientas de soporte (`get_ticket_status`, `calculate_incident_priority`), la herramienta documental RAG (`create_rag_tool`), el servicio de auditoría estructurada (`AuditService`) y el orquestador conversacional con LangGraph (`AgentService`).

**Componentes implementados:**
1. **`app/tools/ticket_tools.py`:** herramienta `@tool` `get_ticket_status` para consulta de tickets en `mock_tickets.json` con normalización insensible a mayúsculas y espacios, y retorno estructurado de campos clave o reporte de error si no existe.
2. **`app/tools/incident_tools.py`:** herramienta `@tool` `calculate_incident_priority` con motor determinista de clasificación de severidad y SLA cuantitativo según usuarios afectados y criticidad del servicio (D10).
3. **`app/tools/rag_tools.py`:** función factory `create_rag_tool` que conecta la herramienta con `RAGService` y acumula referencias bibliográficas en un `sources_tracker` para alimentar `ChatResponse.sources`.
4. **`app/tools/__init__.py`:** reexportación unificada de herramientas y factory.
5. **`app/services/audit.py`:** servicio `AuditService` para registro en formato JSON Lines (`data/audit/audit.jsonl`) con latencias, argumentos, resultado y éxito (D12), y lectura con soporte de límite y orden cronológico.
6. **`app/services/agent.py`:** orquestador conversacional LangGraph con `StateGraph`, `ToolNode` y `tools_condition`. Incluye:
   - Límite de recursión configurable (`settings.agent_recursion_limit = 5`).
   - Mitigación de prompt injection con guardrail estricto de entrada y reglas en system prompt (TC-05).
   - Respuesta estándar obligatoria ante falta de información técnica interna (TC-04).
   - Determinación determinista de `grounded` basada en umbral de similitud RAG (D11).
   - Sanitización del contrato público de respuesta (`ToolCallSummary`, D12).
7. **`tests/test_tools.py`, `tests/test_audit.py`, `tests/test_agent.py`:** 38 nuevas pruebas unitarias ejecutadas sin conexión a internet ni consumo de APIs usando `FakeMessagesListChatModel` con `bind_tools` simulado.

**Evidencia de Verificación:**
- `uv run ruff format app tests`: `29 files left unchanged`
- `uv run ruff check app tests`: `All checks passed!`
- `uv run mypy app`: `Success: no issues found in 18 source files`
- `uv run pytest -q`: `155 passed in 5.50s`


