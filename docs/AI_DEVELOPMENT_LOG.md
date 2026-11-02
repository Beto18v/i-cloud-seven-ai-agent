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