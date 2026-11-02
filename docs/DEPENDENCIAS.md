# Gestión de Dependencias — Enterprise Legacy Assistant

> **Documento vivo.** Toda alta, baja o cambio de versión debe registrarse aquí con fecha, comando ejecutado, motivo y verificación realizada. Ver `AGENTS.md` § 5 y § 6.

---

## 1. Modelo de gestión: uv

| Elemento | Rol |
| :--- | :--- |
| `pyproject.toml` | **Declaración** de dependencias directas con versión exacta (`==`) y configuración de herramientas. |
| `uv.lock` | **Fuente de verdad** del grafo completo (127+ paquetes, hashes y resolución determinista). Se versiona en Git. |
| `.venv/` | Entorno virtual gestionado por uv. Ignorado por Git. |
| `.python-version` | Versión de Python del proyecto (`3.12`). Se versiona. |

Se descarta `requirements.txt` como fuente de verdad: no fija transitivas ni hashes. Para artefactos que lo exigen (Docker, Azure App Service), se **exporta** desde el lock (§ 8).

**Comandos canónicos**

```powershell
uv add "paquete==X.Y.Z"                    # alta de dependencia de ejecución
uv add --dev "paquete==X.Y.Z"              # alta de dependencia de desarrollo
uv remove paquete                          # baja
uv sync                                    # materializa .venv desde el lock
uv sync --frozen --no-dev                  # CI / imagen de producción (falla si el lock no cuadra)
uv lock --upgrade-package paquete          # actualización controlada
uv run <comando>                           # ejecuta dentro del entorno del proyecto
```

---

## 2. Dependencias de ejecución

Instaladas el **2026-10-31** con:

```powershell
uv add "fastapi==0.162.0" "uvicorn[standard]==0.54.0" "pydantic==2.14.2" "pydantic-settings==2.16.2" "python-multipart==0.0.33" "langchain-core==1.7.3" "langchain-openai==1.7.3" "langchain-text-splitters==1.1.3" "langgraph==1.2.19" "langchain-chroma==1.1.0" "chromadb==1.5.9" "openai==3.42.0" "tenacity==9.2.1" "structlog==26.1.0" "tiktoken==0.14.0"
```

| Paquete | Versión | Rol en la solución | Restricción que impone o recibe |
| :--- | :--- | :--- | :--- |
| `fastapi` | 0.162.0 | Capa HTTP, validación y OpenAPI automático. | `starlette>=0.46`, `pydantic>=2.9` |
| `uvicorn[standard]` | 0.54.0 | Servidor ASGI. Extras: `httptools`, `watchfiles`, `websockets`, `uvloop` (no aplica en Windows). | `requires-python>=3.10` |
| `python-multipart` | 0.0.33 | Parseo de `multipart/form-data` para subir manuales al endpoint de ingesta. | `requires-python>=3.11` |
| `pydantic` | 2.14.2 | Validación de contratos de entrada/salida. | núcleo del stack: `langchain-core` exige `>=2.7.4,<3` |
| `pydantic-settings` | 2.16.2 | Carga y validación del `.env` (`BaseSettings`, `SecretStr`). | **`requires-python>=3.11`**, `pydantic>=2.7`, `python-dotenv>=1.2.2` |
| `langchain-core` | 1.7.3 | Primitivas LCEL: `Runnable`, prompts, mensajes, parsers, `bind_tools`. | `pydantic<3`, `httpx>=0.23`, `tenacity>=8.1` |
| `langchain-openai` | 1.7.3 | `ChatOpenAI` y `OpenAIEmbeddings` (OpenAI y Azure OpenAI). | `langchain-core>=1.7.0`, `openai>=2.45.0`, `tiktoken>=0.7.0` |
| `langchain-text-splitters` | 1.1.3 | `RecursiveCharacterTextSplitter` para el chunking (600/80). | `langchain-core>=1.4.7` |
| `langgraph` | 1.2.19 | Orquestación del agente como grafo de estados. | `langchain-core>=1.4.7`, `pydantic>=2.7.4`, arrastra `langgraph-prebuilt` |
| `langchain-chroma` | 1.1.0 | Adaptador entre LangChain y ChromaDB (`Chroma` como `VectorStore`). | `chromadb>=1.3.5,<2.0.0`, `langchain-core>=1.1.3` |
| `chromadb` | 1.5.9 | Vector store local persistente. | pinneado explícitamente (§ 5) |
| `openai` | 3.42.0 | Cliente oficial del proveedor (usado por `langchain-openai`). | satisface `openai>=2.45.0` |
| `tenacity` | 9.2.1 | Reintentos con backoff exponencial + jitter en llamadas al LLM. | `langchain-core` exige `>=8.1,!=8.4.0` |
| `structlog` | 26.1.0 | Logging estructurado en JSON Lines. | `requires-python>=3.10` |
| `tiktoken` | 0.14.0 | Conteo de tokens para métricas de coste y control de contexto. | `langchain-openai` exige `>=0.7.0` |

### 2.1 Justificación de cada elección

| Paquete | Por qué se eligió | Alternativa descartada |
| :--- | :--- | :--- |
| **fastapi** | Async nativo, validación integrada con Pydantic v2 y OpenAPI/Swagger automático (requisito 5.1 de la prueba). | Flask (sin async ni OpenAPI nativo) y Django REST (framework completo para 4 endpoints). |
| **uvicorn[standard]** | Servidor ASGI de referencia para FastAPI; el extra `standard` aporta `httptools` (parseo HTTP en C) y `watchfiles` (recarga en caliente). | Hypercorn (menos ecosistema) y Gunicorn (en Windows no orquesta workers ASGI sin WSL). |
| **python-multipart** | Sin él FastAPI no parsea `multipart/form-data` y el endpoint de ingesta de documentos falla al arrancar. | Enviar documentos en base64 dentro de JSON (hincha el payload y complica el cliente). |
| **pydantic** | Núcleo de validación y serialización; requisito explícito de validación de entradas (§ 5.5). | `dataclasses` + validación manual: reinventar el contrato y perder el esquema OpenAPI. |
| **pydantic-settings** | Carga del `.env` con tipos, `SecretStr` y validación cruzada (fail-fast al arrancar). | `os.getenv` disperso por el código + `python-dotenv` sin validación de tipos. |
| **langchain-core** | Primitivas LCEL (`Runnable`, `bind_tools`, prompts, parsers) sin arrastrar cadenas legacy. | El meta-paquete `langchain` (incluye APIs deprecadas que la prueba penaliza). |
| **langchain-openai** | Adaptadores mantenidos de `ChatOpenAI` / `OpenAIEmbeddings`; soporta `base_url` (Azure v1), tool calling y reintentos. | Cliente `openai` a pelo (más código de glue, menos integración con LangGraph). |
| **langchain-text-splitters** | `RecursiveCharacterTextSplitter` con separadores jerárquicos (párrafo → frase), adecuado para manuales con encabezados. | Splitter propio por longitud fija: parte procedimientos a mitad de paso y rompe el contexto del vector. |
| **langgraph** | Grafo de estados explícito con routing condicional, límite de recursión y checkpointer para multi-turno. Es el estándar actual de LangChain para agentes. | `AgentExecutor` (deprecado) y cadena LCEL pura (sin ciclos ni condición de parada explícita). |
| **langchain-chroma** | Adaptador oficial `VectorStore`; expone `similarity_search_with_relevance_scores`, necesario para el umbral de 0.70, y conserva metadatos por chunk. | Usar el SDK de Chroma directamente: más glue y se pierde la interfaz `VectorStore` intercambiable. |
| **chromadb** | Vector store embebido y persistente en disco, sin servidor: el revisor clona, sincroniza y ejecuta. Detalle en § 10. | FAISS (solo índice, sin metadatos ni persistencia de documentos) y pgvector (exige Postgres, ver § 10). |
| **openai** | Cliente oficial que usa `langchain-openai`; fijarlo evita que un cambio de rango rompa el tool calling. | Cliente HTTP propio contra la API de chat completions. |
| **tenacity** | Backoff exponencial con jitter ante 429/5xx sin escribir el bucle a mano. | `urllib3.Retry` (orientado a HTTP puro, no a operaciones async arbitrarias). |
| **structlog** | Eventos JSON con contexto enlazado (`request_id`, `session_id`, `latency_ms`), integrable con `logging` y con Azure Monitor. | `python-json-logger` (más manual) y `print` (no indexable ni correlacionable). |
| **tiktoken** | Conteo real de tokens para coste y control de contexto; es el tokenizador de los modelos de OpenAI. | Estimar por caracteres (desvío típico del 20-30%). |

---

## 3. Dependencias de desarrollo

Instaladas el **2026-10-31** con:

```powershell
uv add --dev "pytest==9.2.0" "pytest-asyncio==1.4.1" "pytest-cov==7.1.0" "ruff==0.17.3" "mypy==2.4.1"
```

| Paquete | Versión | Rol |
| :--- | :--- | :--- |
| `pytest` | 9.2.0 | Runner de pruebas. Configurado en `[tool.pytest.ini_options]`. |
| `pytest-asyncio` | 1.4.1 | Soporte `async` con `asyncio_mode = "auto"`. |
| `pytest-cov` | 7.1.0 | Cobertura con `branch = true`. |
| `ruff` | 0.17.3 | Linter + formatter (sustituye a flake8 + isort + black). |
| `mypy` | 2.4.1 | Tipado estático con el plugin oficial de Pydantic. |

### 3.1 Justificación de cada elección

| Paquete | Por qué se eligió | Alternativa descartada |
| :--- | :--- | :--- |
| **pytest** | Runner estándar del ecosistema, con fixtures, parametrización y `testpaths` declarativo. | `unittest` (verboso, sin fixtures idiomáticas ni plugins de async). |
| **pytest-asyncio** | `asyncio_mode = "auto"` permite probar endpoints y nodos del grafo sin decoradores repetidos. | Plugin `anyio` (menos explícito sobre qué es una prueba async). |
| **pytest-cov** | Cobertura con `branch = true`, que es la que revela ramas de error no probadas. | `coverage` invocado a mano (sin integración con el runner). |
| **ruff** | Un solo binario sustituye a flake8 + isort + black; reglas modernas (`UP`, `B`, `SIM`, `S`) y formato determinista. | Tríada `flake8` + `black` + `isort` (tres herramientas y tres configuraciones). |
| **mypy** | Tipado estricto real y plugin oficial de Pydantic (entiende `BaseModel` y `BaseSettings`). | `pyright` (no interpreta los plugins de Pydantic igual y añade toolchain de Node). |

> **Nota sobre `httpx2`:** no se declara en `dev`. Se verificó con `uv tree --invert --package httpx2` que llega como transitiva de `langsmith` (→ `langchain-core`) y de `huggingface-hub` (→ `tokenizers` → `chromadb`). Se necesita porque **`starlette 1.10.0` usa `httpx2` en `TestClient`** y solo cae a `httpx` con `StarletteDeprecationWarning`. Al estar garantizada por el lock, declararla sería redundante (`AGENTS.md` § 6.6).

---

## 4. Restricciones cruzadas verificadas

Antes de fijar versiones se consultó el metadata real de PyPI (`https://pypi.org/pypi/<paquete>/json`). Estas son las cadenas que **condicionan** el stack:

| Cadena | Restricción | Consecuencia |
| :--- | :--- | :--- |
| `langchain-openai 1.7.3` → `langchain-core` | `>=1.7.0,<2.0.0` | Fija `langchain-core` en la rama 1.x. |
| `langchain-openai 1.7.3` → `openai` | `>=2.45.0` | Permite `openai 3.x` (instalado: 3.42.0). |
| `langgraph 1.2.19` → `langchain-core` | `>=1.4.7,<2` | Compatible con 1.7.3. |
| `langchain-chroma 1.1.0` → `chromadb` | `>=1.3.5,<2.0.0` | Bloquea saltos a Chroma 2.x. |
| `pydantic-settings 2.16.2` | `requires-python>=3.11` | **Suelo real del proyecto: Python 3.11.** |
| `python-multipart 0.0.33` | `requires-python>=3.11` | Refuerza el mismo suelo. |
| `langchain-core 1.7.3` → `pydantic` | `>=2.7.4,<3` | Compatible con `pydantic 2.14.2`. |
| `fastapi 0.162.0` → `pydantic` | `>=2.9.0` | Compatible con `pydantic 2.14.2`. |

**Transitivas críticas observadas en el lock** (no se declaran, se consumen):

`starlette 1.10.0`, `langgraph-prebuilt 1.1.1`, `langgraph-checkpoint 4.3.1`, `langgraph-sdk 0.4.11`, `langsmith 0.14.16`, `httpx 0.28.1`, `httpx2 2.16.0`, `httpcore2 2.16.0`, `onnxruntime 1.31.1`, `numpy 2.5.4`, `tokenizers 0.23.3`, `huggingface-hub 2.4.0`, `kubernetes 37.0.1`, `grpcio 1.85.1`, `opentelemetry-sdk 1.45.2`.

> `uv` resuelve `numpy` por tramos de versión de Python (2.5.4 en 3.12, 2.4.6 en tramos superiores), por eso el lock contiene más de una resolución. Es comportamiento esperado, no un conflicto.

---

## 5. Decisiones y alternativas descartadas

| Decisión | Motivo | Alternativa descartada |
| :--- | :--- | :--- |
| **No instalar el meta-paquete `langchain`** | Todo lo necesario está en `langchain-core` + `langgraph` (+ `langgraph-prebuilt`). Menos superficie de dependencias y cero APIs deprecadas. | `langchain` completo (arrastra cadenas legacy: `LLMChain`, `RetrievalQA`, `AgentExecutor`). |
| **Pin exacto (`==`) en dependencias directas** | Resolución reproducible y defendible ante revisión técnica; el lock congela el resto. | Rangos compatibles (`>=x,<y`) delegando todo al lock. |
| **`chromadb` declarado explícitamente** | Es la dependencia más pesada (arrastra `onnxruntime`, `tokenizers`, `kubernetes`, `grpcio`). Controlar su versión evita sorpresas de tamaño de imagen y de API. | Dejar que `langchain-chroma` la resuelva en silencio. |
| **`tiktoken` declarado explícitamente** | El código lo importa directamente para estimar tokens y coste (`AGENTS.md` § 6.6). | Usar solo el contador interno de LangChain. |
| **`ruff` en lugar de flake8 + black** | Un binario, un archivo de configuración, reglas modernas (`UP`, `B`, `SIM`, `S`). | `flake8` + `black` + `isort` (tres herramientas, tres configuraciones). |
| **`uv.lock` en lugar de `requirements.txt`** | Incluye transitivas, hashes y marcadores de entorno. | `pip freeze` manual (no reproducible entre SO). |

---

## 6. Evidencia de verificación

Comando ejecutado (2026-10-31) tras la instalación:

```powershell
uv run python -c "import fastapi, pydantic, langchain_core, langgraph, chromadb"
```

Verificación ampliada ejecutada en el entorno real del proyecto — **resultado: OK**:

```text
fastapi 0.162.0 · starlette 1.10.0 · uvicorn 0.54.0
pydantic 2.14.2 · pydantic-settings 2.16.2
langchain-core 1.7.3 · langchain-openai 1.7.3 · langchain-text-splitters 1.1.3
langgraph 1.2.19 · langgraph-prebuilt 1.1.1 · langchain-chroma 1.1.0
chromadb 1.5.9 · openai 3.42.0 · httpx 0.28.1 · httpx2 2.16.0
structlog 26.1.0 · tenacity 9.2.1 · tiktoken 0.14.0 · pytest 9.2.0

chunking OK -> 4 chunks (max 593 chars)          # RecursiveCharacterTextSplitter(600, 80)
langgraph OK -> nodos=['noop'] tool_node=ToolNode # StateGraph + prebuilt
langchain OK -> ChatOpenAI, OpenAIEmbeddings, tools_condition
testclient OK -> 200 {'status': 'ok'}             # FastAPI + starlette TestClient
STACK VERIFICADO
```

Esto cubre el **riesgo de incompatibilidad real** (no solo de resolución): los imports deprecados que menciona `AI_DEVELOPMENT_LOG.md` § 3.A (`RetrievalQA`, `langchain.chains`) no existen en este stack; las rutas válidas son `langchain_core.*`, `langchain_openai.*` y `langgraph.*`.

---

## 7. Riesgos identificados del stack

| Riesgo | Impacto | Mitigación |
| :--- | :--- | :--- |
| Peso de `chromadb` (`onnxruntime`, `tokenizers`, `kubernetes`, `grpcio`) | Imagen Docker grande y arranque en frío más lento. | Build multi-stage con `uv sync --frozen --no-dev` y `.dockerignore`; en producción migrar a Azure AI Search o pgvector tras la interfaz de vector store. |
| `requires-python>=3.11` por `pydantic-settings` | El proyecto no corre en 3.10. | Declarado en `pyproject.toml`, en `.python-version` y en el README. |
| Pines exactos | Actualizar exige intervención manual. | `uv lock --upgrade-package <paquete>` + re-verificación (§ 9). |
| Warning de *hardlink* al instalar | Cache y `.venv` en discos distintos: copia completa, más lento. | Cosmético. Si molesta: `$env:UV_LINK_MODE="copy"` o `uv sync --link-mode=copy`. |

---

## 8. Exportación para Docker y Azure App Service

```powershell
# Imagen de producción: solo dependencias de ejecución, desde el lock
uv export --frozen --no-dev --no-hashes --format requirements-txt -o requirements.txt

# Build dentro del contenedor
uv sync --frozen --no-dev
```

En Azure App Service con código (no contenedor), la plataforma detecta `requirements.txt`; genera el archivo con el comando anterior y **no** lo uses como fuente de verdad local.

---

## 9. Procedimiento de actualización

```powershell
uv lock --upgrade-package <paquete>     # 1. actualizar una sola cosa
uv sync                                 # 2. materializar
uv run python -c "import <paquete>"     # 3. verificar import real
uv run pytest -q                        # 4. regresión funcional
```

Después, registrar en la tabla siguiente: fecha, paquete, versión anterior → nueva, motivo y resultado.

---

## 10. Persistencia: ¿dónde está (y dónde no está) la base de datos?

### 10.1 De dónde sale la palabra "base de datos"

| Documento | Mención | Alcance real |
| :--- | :--- | :--- |
| `docs/PRUEBA_ORIGINAL.md` § 4 (tabla de rutas) | "Base de datos: DynamoDB **o base de datos local** / Cosmos DB **o base de datos local**" | La prueba **permite explícitamente** una base de datos local. |
| `docs/PRUEBA_ORIGINAL.md` § 5.3 | "Consultar estado de una solicitud en **un archivo JSON** o base de datos mock" | El mock en JSON es una opción **sancionada por el enunciado**. |
| `README.md` § 1 (diagrama) | `MockDB[(Legacy Mock DB: JSON/SQL)]` | Representa el sistema legado simulado. |
| `docs/ARCHITECTURE.md` § 4 | `Azure Database for PostgreSQL (Flexible Server)` | **Ruta de despliegue a producción**, no parte de la entrega ejecutable. |

### 10.2 Decisión: no hay SGBD en la entrega

Tres artefactos cubren toda la persistencia, sin servidor y sin credenciales:

| Artefacto | Ruta | Naturaleza | Uso |
| :--- | :--- | :--- | :--- |
| Sistema legado simulado | `data/mock_tickets.json` | Archivo de solo lectura, versionado. | Alimenta la tool `get_ticket_status`. |
| Auditoría y trazabilidad | `data/audit/audit.jsonl` | Append-only, una línea JSON por interacción. | Alimenta `GET /api/v1/audit/logs`. |
| Índice vectorial | `data/vectorstore/` | Directorio persistente de Chroma. | Recuperación semántica del RAG. |

**Por qué:**

1. El peso de la evaluación está en RAG (20 %), agente y herramientas (15 %) y arquitectura (15 %); administrar un SGBD no aporta puntaje.
2. El revisor clona el repositorio, ejecuta `uv sync` y arranca: **cero infraestructura, cero credenciales de base de datos**.
3. La prueba permite expresamente "archivo JSON o base de datos mock", así que cumple el alcance mínimo sin sobre-ingeniería.
4. Un JSON versionado hace **reproducible** el caso de prueba TC-02 (`TCK-104` responde siempre lo mismo), algo que una BD viva no garantiza.

**Lo que NO cubre (deuda asumida y documentada):** concurrencia multiusuario, transacciones, consultas ad-hoc, retención y rotación de auditoría, y crecimiento del índice.

**Ruta de producción:** `Azure Database for PostgreSQL — Flexible Server` para tickets y auditoría, con `pgvector` para el índice (unificando relacional y vectorial en un solo motor), o `Cosmos DB` si se requiere escala global. Está descrito en `docs/ARCHITECTURE.md` § 4 y **no se implementa** en esta entrega.

**Si el evaluador exigiera un motor real:** la alternativa de mínimo impacto es **SQLite** (biblioteca estándar, sin dependencias nuevas): sustituye `mock_tickets.json` y `audit.jsonl` por dos tablas, con el mismo contrato de lectura para las tools.

---

## 11. Estrategia de proveedor: Azure OpenAI vs OpenAI

### 11.1 Una sola ruta de código para ambos proveedores

Desde agosto de 2025, Azure OpenAI expone la **API v1**, que elimina el parámetro `api-version` y permite usar el cliente estándar de OpenAI apuntando al endpoint:

```text
base_url = https://<recurso>.openai.azure.com/openai/v1/
```

**Consecuencias de diseño:**

| Antes (API con fecha) | Ahora (API v1) |
| :--- | :--- |
| `AzureChatOpenAI(azure_endpoint=..., api_version=..., azure_deployment=...)` | `ChatOpenAI(model=<deployment>, base_url=..., api_key=...)` |
| Requería `AZURE_OPENAI_API_VERSION` | **Ya no es necesaria** |
| Dos clases distintas según proveedor | **Una sola clase**; el proveedor es solo configuración |

Esto reduce la superficie de configuración y elimina una fuente clásica de error (versiones de API retiradas).

### 11.2 Requisitos para usar Azure OpenAI

1. Suscripción de Azure con un recurso de **Azure OpenAI / Microsoft Foundry Models** creado y aprobado.
2. **Dos deployments**: uno de chat y uno de embeddings (`text-embedding-3-small`). En Azure se invoca por **nombre de deployment**, no por nombre de modelo.
3. Endpoint, clave y nombres de deployment en el `.env` (nunca en el código).
4. Verificar la **cuota y disponibilidad del modelo en la región** elegida: no todos los modelos están en todas las regiones.

**Sobre los créditos:** Azure OpenAI **no tiene capa gratuita permanente**; consume el crédito de la suscripción y luego se factura por uso. El crédito inicial y el plan gratuito cubren servicios de cómputo/almacenamiento, no necesariamente inferencia. Hay que verificar el saldo real y la cuota del modelo en el portal antes de comprometer la demo.

### 11.3 Riesgo detectado: modelos y parámetros

| Elemento | Estado (verificado en la programación de retiros de Microsoft) | Implicación |
| :--- | :--- | :--- |
| `gpt-4o-mini` (versión anterior de esta documentación) | **Deprecated**, retiro 2027-04-14 | Descartado como base: habría nacido con fecha de caducidad. |
| `text-embedding-3-small` | GA hasta 2028-02-09 | Elección segura y vigente. **Adoptado.** |
| `gpt-5-mini` | GA, familia activa | **Adoptado** como deployment de chat (decisión 3A). |

**Riesgo abierto:** los deployments de la familia `gpt-5` pueden **rechazar `temperature` y `max_tokens`** (usan `max_completion_tokens`). Antes de construir el agente hay que hacer **una llamada real de 1 token** al deployment y confirmar qué parámetros acepta; el contrato de configuración se ajusta a esa evidencia, no a la documentación genérica. Mientras tanto, `LLM_TEMPERATURE` es opcional y vacía por defecto, de modo que el parámetro **no se envía**.

### 11.4 Configuración resultante (implementada en `app/core/config.py`)

| Variable | Valor por defecto | Comentario |
| :--- | :--- | :--- |
| `AI_PROVIDER` | `azure_openai` | `openai` activa el *fallback* sin cambiar código. |
| `AZURE_OPENAI_ENDPOINT` | *(obligatoria)* | `HttpUrl`. El `/openai/v1` lo añade el cliente, no el operador. |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | *(obligatoria)* | Nombre de deployment, no de modelo. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | *(obligatoria)* | Ídem. |
| `AZURE_OPENAI_API_VERSION` | **eliminada** | La API v1 no la usa. |
| `LLM_TEMPERATURE` | *(vacía)* | Vacía ⇒ el parámetro no se envía. |
| `VECTOR_STORE_SPACE` | `cosine` | Obligatoria para que el umbral 0.70 sea interpretable. |

La validación es **fail-fast**: si `AI_PROVIDER=azure_openai` y falta cualquier credencial o deployment, el proceso no arranca y el mensaje nombra exactamente la variable ausente.

---

## 12. Registro de cambios

| Fecha | Acción | Detalle | Resultado |
| :--- | :--- | :--- | :--- |
| 2026-10-31 | Inicialización | `uv init` (Python 3.12.7, uv 0.10.8). | `pyproject.toml`, `.python-version`, `.venv`. |
| 2026-10-31 | Alta de 15 dependencias de ejecución | Ver § 2 (una sola resolución). | 112 paquetes instalados, 0 conflictos. |
| 2026-10-31 | Alta de 5 dependencias de desarrollo | Ver § 3. | 12 paquetes instalados. |
| 2026-10-31 | `requires-python`: `>=3.12` → `>=3.11` | Alinear con README/ARCHITECTURE y con el suelo de `pydantic-settings`. | `uv lock` re-resuelto (128 paquetes, resolución de `numpy` por tramos). |
| 2026-10-31 | Verificación de imports del stack | § 6. | OK. |
| 2026-10-31 | Reorganización del repositorio | `Remove-Item main.py` · `Move-Item ARCHITECTURE.md, AI_DEVELOPMENT_LOG.md, PRUEBA_ORIGINAL.md docs\` | Raíz limpia; documentación alineada con el árbol del README. |
| 2026-10-31 | Documentación de motivos de elección | § 2.1 y § 3.1: por qué se eligió cada paquete y qué alternativa se descartó. | OK. |
| 2026-10-31 | Clarificación de persistencia y proveedor | § 10 (no hay SGBD en la entrega) y § 11 (Azure OpenAI vía API v1). | OK. |
| 2026-10-31 | Decisiones D1-D5 adoptadas | 1A archivo · 2A Azure + fallback · 3A `gpt-5-mini` · 4A `calculate_incident_priority` · 5A API key con `SecretStr`. | § 11.4 documenta la configuración resultante. |
| 2026-10-31 | Alta de `app/core/config.py` | `pydantic-settings` con `frozen=True`, `SecretStr`, validación cruzada y `ensure_directories()`. | Verificado con 28 aserciones (28 PASS). Sin dependencias nuevas. |
| 2026-10-31 | Alineación documental | README §2/§3/§4/§7/§8 y ARCHITECTURE §2/§3.B/§3.D/§4/§5. | Eliminadas referencias a `pip`, `requirements.txt`, Chroma in-memory y `gpt-4o-mini`. |
| 2026-10-31 | Revisión adversarial con contexto fresco | 6 WARNING + 7 SUGGESTION sobre `config.py` y `.env.example`; ver `docs/AI_DEVELOPMENT_LOG.md` § 6.4. | 6 WARNING corregidos, 5 de 7 sugerencias aplicadas, 2 rechazadas con justificación. |
| 2026-10-31 | Verificación ampliada | La batería pasó de 28 a 42 aserciones, incluyendo 8 regresiones de la revisión. | `TOTAL 42 \| PASS 42 \| FAIL 0`. |
