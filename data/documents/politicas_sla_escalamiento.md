# Políticas de Clasificación de Severidad, Tiempos de SLA y Protocolo de Escalamiento

## 1. Alcance y Propósito del Marco de Soporte

Este documento define el marco normativo para la gestión de incidentes y solicitudes de servicio en el ecosistema de aplicaciones de la organización. Su propósito es garantizar una respuesta estandarizada, predecible y oportuna frente a interrupciones tecnológicas, alineando los esfuerzos de los equipos de soporte con el impacto en el negocio.

Todos los incidentes registrados en el sistema de tickets legado o clasificados por el asistente de operaciones deben evaluarse conforme a las reglas descritas en esta política para determinar su nivel de prioridad técnica y su compromiso de nivel de servicio (SLA).

---

## 2. Matriz de Clasificación de Severidad y Prioridad

La severidad técnica y prioridad operativa se determina a partir del volumen de usuarios impactados y la condición de criticidad del servicio afectado:

| Nivel de Severidad | Criterio de Usuarios Afectados | Condición del Servicio | Tiempo de Resolución (SLA) | Requiere Escalamiento Inmediato |
| :--- | :--- | :--- | :--- | :--- |
| **CRITICAL** | Mayor o igual a 500 usuarios (>=500) | Servicio crítico de negocio no disponible o inoperativo | Menor a 2 horas (< 2h) | Sí (Inmediato) |
| **HIGH** | De 100 a 499 usuarios afectados | Servicio crítico degradado o servicio estándar interrumpido | 4 horas | Sí (En caso de riesgo de SLA) |
| **MEDIUM** | De 10 a 99 usuarios afectados | Servicio secundario afectado con alternativa funcional activa | 8 horas | No |
| **LOW** | Menos de 10 usuarios afectados | Incidencia cosmética, consulta o mantenimiento preventivo | 24 horas | No |

### 2.1 Criterios Detallados para Nivel CRITICAL
Un incidente es catalogado como **CRITICAL** cuando se cumple cualquiera de las siguientes condiciones:
1. Interrupción total o caída del servicio de autenticación corporativo (LDAP, SSO) afectando a 500 o más usuarios concurrentes.
2. Inoperatividad total de la plataforma de facturación electrónica o pasarela transaccional de pagos durante horarios laborales o de cierre contable.
3. El tiempo objetivo de resolución del SLA es estrictamente menor a 2 horas (< 2 horas). Se requiere notificación instantánea al equipo de guardia y a la gerencia de tecnología.

### 2.2 Criterios para Niveles HIGH, MEDIUM y LOW
- **HIGH (4 horas):** Incidentes que causan degradación severa del rendimiento, fallos recurrentes en lotes de sincronización entre 100 y 499 usuarios, o saturación del 80% del pool de base de datos.
- **MEDIUM (8 horas):** Errores localizados en generación de reportes secundarios o procesos nocturnos no bloqueantes con un impacto en 10 a 99 usuarios que disponen de procedimientos alternativos.
- **LOW (24 horas):** Peticiones de mantenimiento rutinario, depuración de colas de impresión temporales, renovación preventiva de certificados de prueba o dudas operativas con menos de 10 usuarios involucrados.

---

## 3. Protocolos de Escalamiento Operativo

### 3.1 Escalamiento Inmediato para Incidentes Críticos
Ante la confirmación de un incidente **CRITICAL**, el sistema de gestión y los agentes de guardia deben activar el protocolo de contingencia nivel 1 de inmediato:
1. Notificar en el canal de comunicación crítica de incidentes mayores en Slack/Teams (`#incidents-sev1`).
2. Abrir una sala de crisis virtual (War Room) convocando al Líder de Incidentes y al Ingeniero de Guardia correspondiente.
3. Emitir el primer boletín de estado a los interesados en un lapso no superior a 15 minutos desde la detección.

### 3.2 Escalamiento por Progresión de SLA
Para incidentes de prioridad **HIGH** o **MEDIUM**, si no se observa avance operativo o asignación efectiva al transcurrir el 50% de la ventana máxima de SLA (2 horas para HIGH, 4 horas para MEDIUM), el ticket se escala automáticamente al supervisor de turno del área correspondiente.

---

## 4. Directorio de Contactos de Guardia Técnica

El equipo de soporte 24/7 mantiene roles rotativos asignados según la siguiente distribución operativa:

| Rol Técnico | Especialidad / Área | Canal de Contacto Primario | Teléfono de Guardia |
| :--- | :--- | :--- | :--- |
| **Líder de Incidentes (Incident Commander)** | Coordinación de crisis y comunicación ejecutiva | `@incident-commander` / Teams | +57 (300) 900-1001 |
| **Ingeniero de Infraestructura y Redes** | Servidores Linux, conectividad y proxies | `infra.guardia@empresa.com` | +57 (300) 900-1002 |
| **Administrador de Base de Datos (DBA)** | Bloqueos PostgreSQL, PgBouncer y afinamiento | `dba.oncall@empresa.com` | +57 (300) 900-1003 |
| **Ingeniero de Aplicaciones Legadas** | Daemons de sincronización, lotes y facturación | `legacy.apps@empresa.com` | +57 (300) 900-1004 |
| **Mesa de Ayuda Nivel 1 / Monitoreo** | Detección primaria, apertura y triaje de tickets | `soporte.ti@empresa.com` | +57 (300) 900-1000 |

Todas las comunicaciones realizadas durante la atención de un incidente deben registrarse con fecha y hora UTC para la auditoría técnica posterior (Post-Mortem).
