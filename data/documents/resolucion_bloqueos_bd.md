# Procedimiento de Resolución de Bloqueos y Saturación de Conexiones en Base de Datos Relacional Legada

## 1. Contexto y Objetivos Operativos

La base de datos relacional PostgreSQL del ecosistema legado soporta la carga transaccional de facturación, almacén y gestión de solicitudes. Debido al diseño legado con transacciones de larga duración y clientes que mantienen conexiones persistentes inactivas, la base de datos puede experimentar situaciones críticas de contención: bloqueos exclusivos prolongados (*lock contention*) y saturación del límite de conexiones en el agrupador (*connection pool starvation*).

Este manual describe los procedimientos autorizados para diagnosticar el estado del motor relacional, aislar transacciones bloqueantes y ejecutar acciones correctivas inmediatas sin comprometer la integridad referencial de los datos.

---

## 2. Diagnóstico de Conexiones y Saturación del Pool

### 2.1 Monitoreo de Conexiones por Estado
Cuando los servicios legados reportan errores del tipo `FATAL: remaining connection slots are reserved for non-replication superuser connections` o demoras severas en el establecimiento del enlace, el operador debe conectarse a la instancia mediante una sesión administrativa y ejecutar la consulta de distribución de estados:

```sql
SELECT state, count(*) 
FROM pg_stat_activity 
WHERE datname = 'legacy_db' 
GROUP BY state;
```

Si el número de conexiones en estado `idle in transaction` o `active` supera el 85% del parámetro `max_connections` (fijado en 200 para este entorno), se declara saturación inminente del pool.

### 2.2 Identificación de Consultas de Larga Duración
Para localizar las consultas que llevan más de 5 minutos ejecutándose sin concluir y que retienen recursos de memoria y cerraduras de fila:

```sql
SELECT pid, now() - query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' 
  AND (now() - query_start) > interval '5 minutes'
ORDER BY duration DESC;
```

---

## 3. Identificación y Mitigación de Bloqueos Exclusivos (Lock Contention)

### 3.1 Detección del Proceso Bloqueante Raíz
Cuando múltiples transacciones quedan en estado `waiting` intentando acceder a una tabla (por ejemplo, `legado_stock_movements` o `facturacion_lote`), es indispensable aislar el proceso raíz (PID bloqueante) que encabeza la cadena de retención:

```sql
SELECT
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

### 3.2 Procedimiento de Cancelación y Terminación de Procesos Bloqueantes
Una vez confirmado el `blocking_pid` causante de la anomalía, se debe proceder en dos fases:

1. **Intento de cancelación no disruptiva:** Envíe una señal de cancelación de consulta activa para permitir que el proceso libere recursos de manera ordenada:
```sql
SELECT pg_cancel_backend(<blocking_pid>);
```
Espere 10 segundos y compruebe si el bloqueo cesó.

2. **Terminación forzada de la sesión:** Si el proceso permanece reteniendo la cerradura o se encuentra en estado `idle in transaction`, proceda con la terminación inmediata del backend mediante la función nativa del motor:
```sql
SELECT pg_terminate_backend(<blocking_pid>);
```
Esta acción cierra la conexión TCP del cliente, revierte la transacción no confirmada y libera inmediatamente todas las cerraduras retenidas en las tablas de la base de datos relacional.

---

## 4. Procedimiento de Reinicio y Recuperación del Pool de Conexiones

### 4.1 Diagnóstico de PgBouncer
La capa intermedia utiliza **PgBouncer** como agrupador transaccional en el puerto `6432`. Si la base de datos responde pero los microservicios y el gateway API no logran establecer sesión, conecte a la consola de administración de PgBouncer:
```bash
psql -p 6432 -U pgbouncer pgbouncer
```
Ejecute los comandos de inspección:
```sql
SHOW POOLS;
SHOW CLIENTS;
```
Verifique la columna `cl_waiting`. Si el conteo de clientes en espera es mayor a 50, el pool está saturado o bloqueado por falta de descriptores de socket.

### 4.2 Reinicio Controlado del Servicio PgBouncer
Para restablecer el pool de conexiones sin reiniciar el motor PostgreSQL principal ni provocar caída total del servicio de base de datos, ejecute en el servidor intermediario:
```bash
# Pausar temporalmente tráfico entrante:
systemctl reload pgbouncer

# En caso de agotamiento crítico y falta de respuesta:
systemctl restart pgbouncer
```
Posteriormente confirme el estado del servicio con `systemctl status pgbouncer` y verifique la reapertura de puertos con `netstat -tlpn | grep 6432`.
