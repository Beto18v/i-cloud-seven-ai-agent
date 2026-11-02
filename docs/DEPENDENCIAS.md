# Gestión y Gobernanza de Dependencias — Enterprise Legacy Assistant

> **Documento técnico de arquitectura y dependencias.** Define el stack tecnológico, compatibilidad de librerías, decisiones de exclusión (sin drivers SGBD ni meta-paquetes deprecados), estrategia de proveedores IA y protocolo estricto de gobernanza con `uv`. Ver `AGENTS.md` § 5 y § 6.

---

## 1. Modelo de gestión: uv y reproducibilidad

| Artefacto | Propósito | Rol en el Proyecto |
| :--- | :--- | :--- |
| `pyproject.toml` | Declaración | Define dependencias directas con versión exacta (`==`), metadatos del proyecto y linters. |
| `uv.lock` | Fuente de verdad | Congela el grafo determinista completo (128 paquetes con hashes SHA-256). Se versiona en Git. |
| `.venv/` | Entorno virtual | Directorio de ejecución aislado gestionado por `uv`. Ignorado por Git. |
| `.python-version` | Versión del runtime | Fija Python `3.12` para paridad estricta entre entornos locales, CI y Docker. |

> **Regla de oro:** Se prohíbe `pip install`, `requirements.txt` manual y `poetry`. `uv.lock` es la única fuente de verdad inmutable.

### Comandos canónicos de administración

```powershell
uv add "paquete==X.Y.Z"                    # Alta de dependencia de ejecución directa
uv add --dev "paquete==X.Y.Z"              # Alta de dependencia de desarrollo / pruebas
uv remove paquete                          # Baja controlada de una dependencia
uv sync                                    # Sincroniza .venv local contra uv.lock
uv sync --frozen --no-dev                  # Instalación determinista para Docker / Producción
uv lock --upgrade-package paquete          # Actualización controlada de un paquete
uv run <comando>                           # Ejecución encapsulada dentro del entorno virtual
```

---

## 2. Dependencias de ejecución (Runtime Stack)

Instaladas con versión exacta (`==`) verificadas contra PyPI. Se consolidan en una sola tabla su rol, restricciones y justificación técnica frente a alternativas descartadas:

| Paquete | Versión | Rol en Arquitectura | Justificación Técnica vs Alternativa Descartada | Restricciones Clave |
| :--- | :--- | :--- | :--- | :--- |
| `fastapi` | 0.162.0 | Framework ASGI principal | Async nativo de alto rendimiento, OpenAPI/Swagger interactivo automático y soporte directo de Pydantic v2. *Descartados:* Flask (sin async nativo ni OpenAPI) y Django REST (exceso de complejidad para un microservicio). | `starlette>=0.46`, `pydantic>=2.9` |
| `uvicorn[standard]` | 0.54.0 | Servidor web ASGI | Servidor de referencia en producción con extras de C (`httptools` para parseo HTTP y `watchfiles` para recarga). *Descartados:* Gunicorn (no orquesta workers ASGI en Windows nativo) e Hypercorn. | `requires-python>=3.10` |
| `pydantic` | 2.14.2 | Validación y contratos | Núcleo de contratos de datos (`ChatRequest`, `ChatResponse`, `Ticket`) con tipado estricto y serialización veloz en Rust. *Descartados:* `dataclasses` (sin validación en runtime ni OpenAPI). | Requisito de `langchain-core` (`>=2.7.4,<3`) |
| `pydantic-settings` | 2.16.2 | Configuración segura | Carga inmutable de `.env` (`BaseSettings`), fail-fast al arrancar y redacción de credenciales (`SecretStr`). *Descartados:* `os.getenv` disperso y `python-dotenv` sin tipado. | **`requires-python>=3.11`** |
| `python-multipart` | 0.0.33 | Ingesta de archivos | Parseo de `multipart/form-data` para subida de manuales en `/api/v1/documents/ingest`. *Descartados:* Base64 en JSON (hincha el payload un 33% y degrada memoria). | `requires-python>=3.11` |
| `langchain-core` | 1.7.3 | Primitivas LCEL | Runnables, mensajes, `bind_tools`, parsers y manejo modular de prompts sin arrastrar código heredado. *Descartado:* Meta-paquete `langchain` (arrastra APIs obsoletas y penalizadas). | `pydantic<3`, `tenacity>=8.1` |
| `langchain-openai` | 1.7.3 | Integración con LLM/Embeddings | Soporte unificado de `ChatOpenAI` y `OpenAIEmbeddings` para OpenAI y Azure OpenAI (API v1). *Descartado:* SDK `openai` puro sin abstracción de Runnable ni tool-calling LangGraph. | `langchain-core>=1.7.0`, `openai>=2.45.0` |
| `langchain-text-splitters` | 1.1.3 | Segmentación RAG | `RecursiveCharacterTextSplitter` con solapamiento y separadores jerárquicos (párrafos, encabezados Markdown). *Descartado:* Splitter plano por longitud fija (corta pasos técnicos a la mitad). | `langchain-core>=1.4.7` |
| `langgraph` | 1.2.19 | Orquestador de agente | Grafo de estados (`StateGraph`) con control cíclico determinista, límites de recursión (`recursion_limit=5`) y trazabilidad. *Descartados:* `AgentExecutor` (deprecado en LangChain v0.1). | `langchain-core>=1.4.7`, `pydantic>=2.7.4` |
| `langchain-chroma` | 1.1.0 | Conector Vector Store | Adaptador oficial de `VectorStore` para Chroma; expone `similarity_search_with_relevance_scores` para umbral de 0.70. *Descartado:* Cliente nativo de Chroma sin interfaz LCEL. | `chromadb>=1.3.5,<2.0.0` |
| `chromadb` | 1.5.9 | Base de datos vectorial | Motor embebido persistente en disco (`data/vectorstore/`) con métrica coseno. No requiere servidor externo. *Descartados:* FAISS (sin metadatos ni persistencia estructurada) y pgvector (exige servidor PostgreSQL). | Pinneado explícito para controlar dependencias pesadas (`onnxruntime`, `tokenizers`). |
| `openai` | 3.42.0 | Cliente oficial de IA | Cliente subyacente para comunicación HTTP robusta con Azure OpenAI y OpenAI directo. | Satisface `openai>=2.45.0` |
| `tenacity` | 9.2.1 | Resiliencia de red | Reintentos configurables con retroceso exponencial (*exponential backoff + jitter*) ante códigos HTTP 429/5xx. *Descartado:* Bucles `while` ad-hoc o `urllib3.Retry`. | Exigido por `langchain-core` |
| `structlog` | 26.1.0 | Logging estructurado | Generación de eventos JSON estructurados con contexto enriquecido (`session_id`, `latency_ms`, `event`). *Descartados:* `print` y `python-json-logger` manual. | `requires-python>=3.10` |
| `tiktoken` | 0.14.0 | Conteo de tokens | Tokenizador oficial BPE de OpenAI para auditoría de tokens de entrada/salida y estimación de costos. *Descartado:* Estimaciones heurísticas por caracteres (error del 25-30%). | Exigido por `langchain-openai` |

---

## 3. Dependencias de desarrollo y calidad

| Paquete | Versión | Rol | Justificación Técnica vs Alternativa Descartada |
| :--- | :--- | :--- | :--- |
| `pytest` | 9.2.0 | Test runner | Estándar de la industria, soporte de fixtures avanzadas, parametrización y configuración declarativa en `pyproject.toml`. |
| `pytest-asyncio` | 1.4.1 | Testing asíncrono | Permite ejecutar pruebas de endpoints `async` y nodos de LangGraph de forma nativa con `asyncio_mode = "auto"`. |
| `pytest-cov` | 7.1.0 | Cobertura de código | Medición de cobertura con análisis de ramas (`branch = true`), identificando caminos de fallo no ejercitados. |
| `ruff` | 0.17.3 | Linter y formateador | Reemplaza a Flake8, Black e Isort en un único binario ultra-rápido escrito en Rust con reglas modernas (`UP`, `B`, `SIM`, `S`). |
| `mypy` | 2.4.1 | Tipado estático | Verificación de tipos estáticos rigurosa con integración nativa del plugin de Pydantic (`pydantic.mypy`). |

> **Nota técnica sobre `httpx2`:** No se declara como dependencia directa de desarrollo porque llega resuelta en `uv.lock` como transitiva de `langsmith` y `huggingface-hub`. Se requiere porque `Starlette 1.10.0` emplea `httpx2` internamente en su `TestClient`.

---

## 4. Restricciones cruzadas y compatibilidad de versiones

El stack fue verificado mediante metadatos de PyPI para garantizar un grafo de resolución acotado y libre de conflictos:

| Relación entre Paquetes | Restricción Oficial | Impacto en la Arquitectura |
| :--- | :--- | :--- |
| `pydantic-settings` / `python-multipart` | `requires-python>=3.11` | **Fija el suelo mínimo de ejecución en Python 3.11.** |
| `langchain-openai` → `langchain-core` | `>=1.7.0,<2.0.0` | Congela la línea moderna 1.x sin librerías deprecadas. |
| `langchain-openai` → `openai` | `>=2.45.0` | Habilita compatibilidad completa con OpenAI SDK v3.x. |
| `langchain-chroma` → `chromadb` | `>=1.3.5,<2.0.0` | Previene roturas con versiones futuras Chroma 2.x. |
| `langchain-core` / `fastapi` → `pydantic` | `>=2.7.4,<3` y `>=2.9.0` | Ambos convergen de forma limpia sobre `pydantic 2.14.2`. |

---

## 5. Persistencia y ausencia de drivers SGBD (¿Dónde están los datos?)

> **Aclaración para evaluadores técnicos:** En `pyproject.toml` no figuran librerías de bases de datos relacionales o documentales como `sqlalchemy`, `psycopg2`, `asyncpg` o `azure-cosmos`. A continuación se explica cómo se resuelve la persistencia y por qué esta decisión es la óptima para la evaluación técnica.

### 5.1 Dónde residen los datos en la solución entregada

Toda la persistencia del sistema está resuelta de forma local, determinista y sin necesidad de servicios externos:

1. **Sistema legado simulado (Tickets):** Reside en `data/mock_tickets.json` (7 tickets sintéticos versionados).
   - Se consulta en memoria mediante la biblioteca estándar de Python (`json`).
   - Alimenta tanto la herramienta del agente (`get_ticket_status`) como el endpoint REST directo (`GET /api/v1/tickets/{ticket_id}`), verificado en Swagger UI con retorno HTTP 200 OK y modelo `Ticket` serializado.
2. **Trazabilidad y auditoría operativa:** Reside en `data/audit/audit.jsonl`.
   - Registro *append-only* en disco donde cada ejecución de herramienta registra una línea JSON con `call_id`, `session_id`, `tool_name`, parámetros, resultado y latencia.
   - Es consultable mediante el endpoint `GET /api/v1/audit/logs`.
3. **Base de datos vectorial (RAG):** Reside en el directorio `data/vectorstore/`.
   - ChromaDB almacena las colecciones de embeddings y documentos fragmentados persistiendo en disco local mediante el motor embebido SQLite3 nativo de Python.

### 5.2 Justificación de la decisión

* **Alineación con los requerimientos (`PRUEBA_ORIGINAL.md` § 5.3):** El enunciado autoriza expresamente: *"Consultar estado de una solicitud en un archivo JSON o base de datos mock"* y *"Base de datos local"*.
* **Cero fricción de evaluación (Zero-Setup):** El evaluador clona el repositorio, ejecuta `uv sync` y arranca la aplicación de inmediato (`docker run` o `uvicorn`). No se requiere aprovisionar contenedores adicionales de PostgreSQL, MySQL ni configurar cuentas de Cosmos DB en la nube para probar la solución.
* **Reproducibilidad en pruebas:** Un archivo JSON versionado garantiza que los casos de prueba de evaluación (ej. `TCK-104` en TC-02) arrojen siempre el mismo resultado determinista.
* **Eficiencia de la imagen Docker:** Evita instalar compiladores de C y bibliotecas pesadas de clientes de base de datos, manteniendo la imagen ligera y segura.

### 5.3 Ruta de transición hacia producción en Microsoft Azure

En un entorno corporativo de producción a gran escala, la arquitectura desacoplada permite migrar fácilmente la persistencia incorporando las dependencias correspondientes:
* **Tickets y Auditoría:** Migran a **Azure Database for PostgreSQL (Flexible Server)** incorporando `sqlalchemy==2.0.*` y `asyncpg==0.30.*`, manteniendo el mismo contrato de interfaz de repositorio sin alterar las rutas ni el agente.
* **Vector Store:** Migra a **Azure AI Search** incorporando `azure-search-documents` o a la extensión **pgvector** en el mismo PostgreSQL unificando datos relacionales y semánticos.

---

## 6. Estrategia de proveedor IA: Azure OpenAI vs OpenAI Directo

### 6.1 Una única ruta de código mediante la API v1

Desde agosto de 2025, Azure OpenAI ofrece la **API v1 unificada**, eliminando el parámetro obsoleto `api-version` y permitiendo utilizar el cliente estándar de `langchain-openai` / `openai` simplemente apuntando a la URL base de Azure:

```text
base_url = https://<recurso>.openai.azure.com/openai/v1/
```

| Configuración Clásica (Legacy) | Arquitectura Implementada (API v1) |
| :--- | :--- |
| `AzureChatOpenAI(azure_endpoint=..., api_version="2024-02-15-preview")` | `ChatOpenAI(model=<deployment>, base_url=..., api_key=...)` |
| Requiere variable `AZURE_OPENAI_API_VERSION` | **Variable eliminada:** se evita la caducidad periódica de APIs |
| Dos clientes de código distintos | **Un solo cliente:** `AI_PROVIDER` (`azure_openai` o `openai`) alterna el proveedor sin tocar código |

### 6.2 Modelos adoptados y control de obsolescencia

| Modelo | Rol | Estado en Microsoft / OpenAI | Decisión y Parámetros |
| :--- | :--- | :--- | :--- |
| `gpt-5-mini` | Chat y Agentic Flow | General Availability (Familia activa) | **Adoptado.** `LLM_TEMPERATURE` es opcional y vacía por defecto para máxima compatibilidad con modelos que limitan parámetros estocásticos. |
| `text-embedding-3-small` | Vectorización RAG | General Availability (Vigente hasta 2028) | **Adoptado.** Genera vectores de 1536 dimensiones de alta precisión y bajo costo. |
| `gpt-4o-mini` | Predecesor evaluado | Deprecado (Retiro en 2027) | **Descartado.** No se adopta como base para evitar obsolescencia temprana en producción. |

---

## 7. Exportación para Docker y Despliegues Cloud

Aunque `uv.lock` es la fuente de verdad del repositorio, para plataformas que exigen formato estándar `requirements.txt` (como Azure App Service sin contenedores), se utiliza el exportador determinista:

```powershell
# Exportación congelada sin dependencias de desarrollo ni hashes para producción
uv export --frozen --no-dev --no-hashes --format requirements-txt -o requirements.txt

# Instalación en imagen Docker multi-stage (Dockerfile nativo con uv)
uv sync --frozen --no-dev
```

---

## 8. Procedimiento de actualización y gobernanza

Para garantizar la estabilidad del stack, cualquier actualización sigue este protocolo estricto:

```powershell
# 1. Actualizar el paquete en uv.lock manteniendo la compatibilidad
uv lock --upgrade-package <paquete>

# 2. Materializar los cambios en el entorno virtual
uv sync

# 3. Comprobar que los imports críticos funcionan
uv run python -c "import <paquete>"

# 4. Ejecutar la suite completa de pruebas unitarias e integración
uv run pytest -q
```
