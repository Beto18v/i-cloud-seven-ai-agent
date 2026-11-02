# Documento de Arquitectura y Decisiones Técnicas

Este documento formaliza la arquitectura del sistema, el flujo de procesamiento de información, las decisiones de diseño adoptadas y la estrategia de despliegue sobre Microsoft Azure.

---

## 1. Objetivos Arquitectónicos

1. **Desacoplamiento:** Separar de forma tajante la capa de transporte (FastAPI REST), la capa de orquestación de agentes (LangGraph), la capa de recuperación de conocimiento (RAG) y la capa de datos.
2. **Determinismo:** Limitar el comportamiento probabilístico de los LLMs mediante validación estricta de esquemas (Pydantic), tool calling supervisado y umbrales mínimos de similitud vectorial.
3. **Observabilidad:** Facilitar auditoría en tiempo real registrando tiempos de inferencia, tokens estimados y nombres de herramientas ejecutadas en cada petición.

---

## 2. Flujo de Datos y Razonamiento

```mermaid
flowchart TD
    subgraph Gateway["1. Puerta de Entrada (FastAPI + Pydantic v2)"]
        User([Usuario / Swagger / Cliente]) -->|POST /api/v1/chat| Ingest[Validación de Esquema ChatRequest]
        Ingest --> Guardrail[Filtro Sanitizador & Control de Prompt Injection]
    end

    subgraph Orchestrator["2. Orquestador Agentic (LangGraph)"]
        Guardrail --> StateGraph[Grafo de Estados con límite de pasos = 5]
        StateGraph --> LLM[ChatOpenAI: gpt-5-mini]
        
        LLM -->|Decide Tool Calling| Router{¿Qué acción requiere?}
    end

    subgraph Execution["3. Capa de Ejecución y Datos"]
        Router -->|Requiere procedimiento técnico| RAGTool[search_technical_documentation]
        Router -->|Requiere ver un ticket| TicketTool[get_ticket_status]
        Router -->|Requiere priorizar incidente| IncidentTool[calculate_incident_priority]
        
        RAGTool --> ChromaDB[(ChromaDB: Colección con Métrica Coseno)]
        TicketTool --> MockDB[(data/mock_tickets.json)]
        IncidentTool --> RuleEngine[Matriz de Reglas de SLA]
    end

    subgraph Observability["4. Observabilidad & Respuesta"]
        RAGTool & TicketTool & IncidentTool --> AuditLog[(data/audit/audit.jsonl)]
        RAGTool & TicketTool & IncidentTool --> LLM
        LLM --> Formatter[Evaluador de Groundedness & Formateador ChatResponse]
        Formatter --> Output([Respuesta JSON con Citas, Tools y Latencia])
    end
```

### Ciclo de Procesamiento Paso a Paso:
1. **Entrada y Validación:** El endpoint `POST /api/v1/chat` recibe el payload validado contra `ChatRequest`, asigna o genera `session_id` (UUID4) e inyecta el `correlation_id` en el contexto de logging.
2. **Razonamiento en Grafo:** LangGraph evalúa la consulta dentro de delimitadores XML (`<context>`, `<question>`) para neutralizar inyecciones de prompt (TC-05).
3. **Ejecución Determinista:** Según la intención, invoca `get_ticket_status` (TC-02), `calculate_incident_priority` (TC-03) o `search_technical_documentation` (TC-01). Cada llamada se audita en `data/audit/audit.jsonl` (D12).
4. **Síntesis y Groundedness:** El LLM redacta la respuesta usando solo las fuentes. Se evalúa `grounded: bool` deterministamente frente a `SIMILARITY_THRESHOLD=0.70` (D11). Si no hay información suficiente, emite la respuesta estándar de TC-04.
5. **Respuesta Estructurada:** Retorna `ChatResponse` con texto, citas, métricas de herramientas y latencia.

---

## 3. Decisiones Técnicas Clave

### A. Framework Backend: FastAPI
* **Razón:** Asincronía nativa (`async/await`), rendimiento de primer nivel (basado en Starlette y Pydantic), y generación automática de especificaciones OpenAPI/Swagger, fundamental para la evaluación técnica.

### B. Pipeline RAG: Chunking Recursivo y Búsqueda Vectorial
* **Chunking:** `RecursiveCharacterTextSplitter` con **600 caracteres** de tamaño y **80** de solapamiento, usando la jerarquía de separadores de Markdown (encabezados, listas, párrafos). Aquí "chunking semántico" se interpreta como **respeto de la estructura y jerarquía del documento** —no cortar un procedimiento a la mitad— y no como *clustering* por embeddings: esa variante requiere una llamada al modelo por documento, introduce no determinismo y encarece la ingesta sin mejorar la recuperación en manuales de procedimiento. El splitter queda detrás de una estrategia de chunking sustituible.
* **Vector Store:** **Chroma persistente** en `data/vectorstore/`, creada con `hnsw:space="cosine"` explícito. La métrica importa: con la distancia L2 por defecto, `SIMILARITY_THRESHOLD=0.70` **no** significa "70 % de similitud" y el umbral se vuelve arbitrario. Se encapsula tras la interfaz `VectorStore` para permitir la sustitución por **Azure AI Search** o **pgvector** sin tocar el dominio.

### C. Estrategia de Agente: Function Calling
* En lugar de agentes reactivos libres propensos a alucinación o bucles infinitos, se implementa una arquitectura basada en **selección explícita de herramientas (Tool Calling)** donde el modelo recibe la firma tipada de las funciones y decide si invocar el RAG o las herramientas de tickets.

### D. Proveedor de IA: Azure OpenAI con API v1
* **Proveedor primario:** Azure OpenAI sobre la **API v1** (GA desde agosto de 2025). Se invoca contra `<endpoint>/openai/v1/...` y **no requiere** el parámetro `api-version` ni la ruta `/openai/deployments/<nombre>/...`. Consecuencia directa: desaparece la variable `AZURE_OPENAI_API_VERSION` y el cliente conserva la firma estándar de OpenAI, por lo que **el mismo código** sirve para Azure y para OpenAI directo conmutando `AI_PROVIDER`.
* **Modelo de chat:** deployment basado en `gpt-5-mini`. `gpt-4o-mini` está marcado como *Deprecated* con retiro el **14/04/2027** y no se adopta como base. **Embeddings:** `text-embedding-3-small` (GA hasta el 09/02/2028).
* **Alternativas descartadas:** (a) API clásica con `api-version` — obliga a fijar una versión por recurso y complica el *fallback*; (b) `azure-identity` con Managed Identity — más seguro, pero no ejecutable fuera de Azure y el evaluador debe poder correr el proyecto en local; (c) Amazon Bedrock — fuera del ecosistema objetivo y del stack declarado.
* **Riesgo asumido y mitigación:** la familia `gpt-5*` puede rechazar `temperature` y `max_tokens` (usa `max_completion_tokens`). Por eso `LLM_TEMPERATURE` es **opcional y vacía por defecto**: si no se define, el parámetro **no se envía**. El determinismo se garantiza con esquema de salida validado, *tool calling* tipado y umbral de recuperación, no con la temperatura.

### E. Contratos de datos de la API

Estas decisiones fijan el contrato público de `app/models/chat.py` y `app/models/ticket.py` antes de su implementación. El registro completo —con alternativas descartadas— está en `docs/AI_DEVELOPMENT_LOG.md` § 6.5 (D10-D12).

* **Prioridad compartida (D10):** `Ticket.priority` y `IncidentClassification.severity` usan el mismo enum `Priority` (`low`, `medium`, `high`, `critical`) porque en el alcance de la prueba el mapeo es 1:1. El supuesto queda documentado: si el negocio define prioridades propias que diverjan de la severidad técnica, se separan en dos enums con mapeo explícito.
* **Fundamentación observable (D11):** la respuesta incluye el campo `grounded`, calculado **exclusivamente** desde el mejor score de recuperación frente a `SIMILARITY_THRESHOLD`. No se delega al LLM ni se infiere del texto de la respuesta. Un valor `False` indica ausencia de contexto suficiente, no incorrección de la respuesta.
* **Trazabilidad de herramientas (D12):** la respuesta expone un resumen sanitizado (`name`, `success`, `latency_ms`); los argumentos y el resultado completo se persisten en `data/audit/audit.jsonl` y se consultan mediante `GET /api/v1/audit/logs`. Así se demuestra la invocación de herramientas sin acoplar el contrato público a la implementación del agente ni exponer datos personales.
* **Contratos tipados:** `ChatRequest` limita la consulta a 1–2000 caracteres y prohíbe campos adicionales; `Ticket` refleja el archivo mock con timestamps UTC; `SourceReference` es obligatorio en la respuesta para cumplir el requisito de citar fuentes (§ 5.2 del enunciado).

---

## 4. Estrategia de Despliegue en Microsoft Azure

La arquitectura está concebida para operar en el ecosistema de Microsoft Azure de forma nativa:

> **Alcance explícito:** lo que sigue es la **ruta de despliegue productivo**, no el estado del entregable. La ejecución local de la prueba **no requiere** ni Azure AI Search, ni PostgreSQL, ni Key Vault: solo un recurso de Azure OpenAI accesible (o `AI_PROVIDER=openai`). La entrega usa persistencia en archivo, tal como se detalla en el punto 4.

```mermaid
graph LR
    subgraph Azure Cloud Platform
        AppService[Azure App Service / Web App for Containers]
        KeyVault[Azure Key Vault / Application Settings]
        AISearch[(Azure AI Search / Vector Store)]
        Postgres[(Azure Database for PostgreSQL)]
        AppInsights[Azure Monitor & App Insights]
    end

    Client([Usuario / Sistemas Legados]) -->|HTTPS| AppService
    AppService -->|Lectura de Secretos| KeyVault
    AppService -->|Embeddings & Retrieval| AISearch
    AppService -->|Persistencia de Tickets & Logs| Postgres
    AppService -.->|Telemetría y Métricas| AppInsights
```

### Componentes Mapeados en Azure:
1. **Cómputo (Backend API):**
   * **Servicio:** *Azure App Service (Linux B1 / Basic Tier)* o *Azure Container Apps*.
   * **Implementación:** La aplicación se empaqueta como contenedor Docker (`Dockerfile`) y se despliega directamente configurando el puerto `8000`.
2. **Gestión de Secretos y Configuración:**
   * Las credenciales (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_KEY`) y el resto de parámetros se inyectan mediante **Configuration > Application settings** del App Service (o referencias a Key Vault), manteniéndolas fuera del repositorio. La aplicación las consume vía `app/core/config.py` (`SecretStr`), nunca con `os.environ` directo.
3. **Escalabilidad del Almacén Vectorial:**
   * En producción a gran escala, la capa vectorial local se migra a **Azure AI Search** (con indexación híbrida: búsqueda semántica + búsqueda por palabras clave BM25).
4. **Persistencia de Datos Legados y Auditoría (ruta de producción):**
   * **La entrega ejecutable no usa ningún SGBD.** El sistema legado se simula con `data/mock_tickets.json` y la auditoría se escribe en `data/audit/audit.jsonl` (JSON Lines). Esta decisión es deliberada y se apoya en el enunciado: § 4 admite "base de datos local" y § 5.3 admite explícitamente "archivo JSON". Añadir un motor relacional solo para leer 7 registros mock habría introducido infraestructura que el revisor tendría que levantar, sin aportar valor evaluable.
   * En producción, tickets y auditoría migran a **Azure Database for PostgreSQL (Flexible Server)** con RLS, **sin cambiar el dominio**: el acceso va detrás de un repositorio (`TicketRepository`, `AuditRepository`) que se sustituye por adaptador. Detalle y trade-offs en `docs/DEPENDENCIAS.md` § 5.

---

## 5. Consideraciones de Seguridad y Resiliencia en Producción

* **Mitigación de Prompt Injection:** Se aplican dos barreras: (1) sanitización sintáctica de entradas para descartar comandos típicos de anulación de instrucciones y (2) prompts de sistema estrictos con delimitadores (`<context>`, `<question>`).
* **Manejo de Errores y Timeouts:** Todas las llamadas al proveedor de LLM cuentan con límite de tiempo de espera (timeout de 10 segundos, `LLM_TIMEOUT_SECONDS`) y reintentos con backoff exponencial y jitter (`LLM_MAX_RETRIES`).
* **Control de Costos:** Se usa un modelo liviano de la familia vigente (`gpt-5-mini`) para la síntesis rutinaria y se limita la salida a `LLM_MAX_OUTPUT_TOKENS` (500 por defecto). El grafo tiene un tope de pasos (`AGENT_RECURSION_LIMIT=5`) para impedir bucles que multiplican el gasto.
* **Contención de Prompts:** El contexto recuperado se delimita en `<context>` y la pregunta del usuario en `<question>`, con instrucción explícita de que el contenido de esas etiquetas es **datos, no instrucciones**.