# I CLOUD SEVEN | Prueba Técnica AI Developer Engineer Semi-senior

* **Perfil:** Generative AI, Agentic Solutions & Cloud Development
* **Tiempo sugerido:** 48 a 72 horas
* **Objetivo de evaluación:** Validar capacidad técnica, criterio de solución, claridad de comunicación y uso responsable de herramientas de desarrollo asistido por AI.

---

## 1. Objetivo de la prueba
Evaluar la capacidad del candidato para diseñar, construir y explicar una solución de AI aplicada a un caso empresarial realista, integrando Generative AI, RAG, agentes, APIs, cloud, seguridad, trazabilidad, evaluación y criterio arquitectónico. 
La prueba debe permitir validar si el candidato puede pasar de un problema ambiguo a una solución funcional, simple, documentada y defendible ante un cliente.

---

## 2. Caso de negocio
Un cliente tiene una **aplicación legada de gestión de solicitudes internas**. Actualmente, los usuarios consultan manualmente documentos técnicos, procedimientos operativos y registros históricos para responder preguntas o tomar decisiones.

El cliente quiere construir un asistente inteligente que permita:
1. Consultar documentación interna.
2. Responder preguntas con base en fuentes cargadas.
3. Ejecutar acciones simples mediante herramientas.
4. Mantener trazabilidad de las interacciones.
5. Ser extensible para integrarse luego con sistemas corporativos.
6. Operar sobre AWS o Azure.

---

## 3. Reto técnico
Construir un **Agente RAG empresarial** con API backend, capacidad de consulta documental, uso de herramientas y criterios básicos de *production readiness*.

### Opción de plataforma
El candidato puede elegir **AWS, Azure o ejecución local documentada**. Si usa ejecución local, debe explicar cómo desplegaría la solución en AWS o Azure.

---

## 4. Rutas técnicas sugeridas

| Componente | Ruta AWS | Ruta Azure |
| :--- | :--- | :--- |
| **Modelos / LLM** | Amazon Bedrock o modelo equivalente | Azure OpenAI o modelo equivalente |
| **Almacenamiento** | S3 o almacenamiento local simulado | Azure AI Search, pgvector, Chroma, FAISS o equivalente |
| **Base de datos** | DynamoDB o base de datos local | Cosmos DB o base de datos local |
| **Vector Store** | OpenSearch, pgvector, Chroma, FAISS o equivalente | Azure AI Search, pgvector, Chroma, FAISS o equivalente |
| **Cómputo / API** | Lambda, ECS o ejecución local documentada | Azure Functions, Container Apps, App Service o ejecución local |
| **Observabilidad** | CloudWatch o logging local estructurado | Application Insights o logging local estructurado |

---

## 5. Alcance mínimo requerido

### 5.1 Backend API
* Construida en Python usando **FastAPI**, Flask o framework similar.
* Endpoint para consultar al asistente.
* Endpoint para cargar o procesar documentos.
* Endpoint para consultar historial o logs básicos.
* Manejo básico de errores.
* Documentación de uso de la API (Swagger / OpenAPI).

### 5.2 Pipeline RAG
* Ingesta de documentos.
* Chunking semántico.
* Generación de embeddings.
* Almacenamiento en vector store.
* Recuperación de contexto.
* Respuesta generada con base en documentos.
* Inclusión explícita de fuentes o fragmentos usados como referencia.

### 5.3 Agente con herramientas
Implementar **al menos 2 herramientas** que el agente pueda usar. Ejemplos sugeridos:
* Consultar estado de una solicitud en un archivo JSON o base de datos mock.
* Crear un resumen ejecutivo de una solicitud.
* Clasificar una solicitud por prioridad.
* Generar una recomendación de modernización.
* Calcular esfuerzo estimado según reglas simples.
* Consultar una lista de servicios cloud sugeridos.

### 5.4 AI-CDL / AI-Assisted Development
El candidato debe usar o documentar cómo usaría herramientas de desarrollo asistido por AI (Kiro, Claude Code, OpenAI Codex, GitHub Copilot, Cursor o equivalentes):
* Qué tareas apoyó con AI.
* Qué validaciones realizó sobre el código generado.
* Qué riesgos identificó.
* Cómo evitó depender ciegamente de la herramienta.

### 5.5 Seguridad y operación
* Manejo de variables de entorno (`.env`).
* Separación de secretos.
* Logging básico estructurado.
* Validación básica de entradas (Pydantic).
* Manejo de errores.
* Identificación de riesgos como *prompt injection*, fuga de datos o respuestas no fundamentadas.
* Recomendaciones para llevar la solución a producción.

### 5.6 Evaluación de calidad
* Incluir **al menos 5 preguntas de prueba** con: pregunta, respuesta esperada o criterio de aceptación, resultado obtenido y observación del candidato.
* Métrica simple de precisión (deseable).
* Evaluación de *groundedness* (deseable).
* Prueba obligatoria de respuesta cuando **no existe información suficiente**.
* Prueba obligatoria de **prompt injection**.

---

## 6. Entregables esperados
1. Repositorio de código.
2. README con instrucciones de instalación y ejecución.
3. Diagrama de arquitectura.
4. Documento corto de decisiones técnicas.
5. Evidencia de pruebas ejecutadas.
6. Video corto de máximo 7 minutos mostrando la solución.
7. Sección de mejoras futuras.
8. Sección de riesgos y consideraciones para producción.

---

## 7. Criterios de evaluación

| Criterio | Peso |
| :--- | :---: |
| **Implementación RAG** | **20%** |
| **Diseño de arquitectura y simplicidad de la solución** | **15%** |
| **Calidad del backend, API y estructura del código** | **15%** |
| **Diseño del agente y uso de herramientas** | **15%** |
| **Seguridad, logging, trazabilidad y readiness para producción** | **15%** |
| **Evaluación de respuestas y pruebas** | **10%** |
| **Documentación, comunicación y claridad de explicación** | **10%** |