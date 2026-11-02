# Manual de Operaciones y Procedimientos de Sistemas Legados v2.0

## 1. Visión General del Entorno Operativo

El presente manual establece los procedimientos estandarizados para el soporte, mantenimiento y resolución de incidentes en la infraestructura de servicios legados de la organización. Los sistemas legados procesan la consolidación transaccional, la sincronización de catálogos y la emisión de lotes nocturnos de facturación hacia las plataformas corporativas modernas.

La arquitectura operativa depende de servicios desacoplados ejecutados en servidores Linux empresariales. Cualquier intervención debe realizarse siguiendo estrictamente la secuencia descrita en este documento, preservando la consistencia transaccional y minimizando el impacto sobre las operaciones activas de los usuarios corporativos.

---

## 2. Gestión del Servicio de Sincronización Legado

### 2.1 Arquitectura y Función del Servicio

El servicio de sincronización legado (`legacy-sync`) es el componente responsable de replicar las transacciones operativas locales hacia los repositorios centrales corporativos. Se ejecuta de manera continua como un daemon de fondo en el servidor de integración principal y procesa colas de mensajes estructurados mediante lotes periódicos cada cinco minutos.

En situaciones de alta carga transaccional, cortes de conectividad de red o caídas abruptas de bases de datos intermedias, el servicio puede entrar en estado inconsistente o generar archivos de bloqueo que impiden la reanudación automática del procesamiento regular.

### 2.2 Procedimiento operativo para reiniciar el servicio de sincronización legado

Ante caídas operativas, bloqueos de hilos de procesamiento o la presencia recurrente de errores en la sincronización, el operador o ingeniero de soporte de guardia debe ejecutar de manera estricta el siguiente procedimiento de cinco pasos:

#### Paso 1: Detención controlada del servicio
Solicite la detención ordenada del daemon de sincronización para asegurar que las transacciones en vuelo se confirmen o se descarten de forma limpia en el almacenamiento local. Ejecute el script de control primario o, en su defecto, el comando del gestor de servicios del sistema operativo:
```bash
/opt/legacy/bin/sync_ctl.sh stop
# Alternativa mediante systemd:
systemctl stop legacy-sync.service
```

#### Paso 2: Verificación de procesos huérfanos
Confirme que no existan subprocesos hijos, hilos de conexión persistentes ni procesos zombis reteniendo recursos del sistema o descriptores de archivos de red. Ejecute la siguiente instrucción:
```bash
ps aux | grep legacy-sync
```
Si se detecta algún identificador de proceso (PID) remanente tras 30 segundos de la orden de detención, finalice forzosamente el proceso mediante `kill -9 <PID>`.

#### Paso 3: Eliminación de archivo de bloqueo temporal
Cuando el daemon finaliza de manera anómala o sufre un bloqueo crítico, deja remanente un archivo de cerrojo temporal en el sistema de archivos que impide un nuevo arranque concurrente. Verifique y elimine dicho archivo de bloqueo:
```bash
rm -f /var/run/legacy/sync.lock
```
Asegúrese de contar con permisos suficientes de superusuario o membresía en el grupo `legacy-ops` para remover este descriptor.

#### Paso 4: Inicio del servicio
Una vez depurado el entorno y verificada la inexistencia de procesos concurrentes, proceda al levantamiento limpio del servicio de sincronización mediante el script de control:
```bash
/opt/legacy/bin/sync_ctl.sh start
# Alternativa mediante systemd:
systemctl start legacy-sync.service
```

#### Paso 5: Verificación en log
Supervise activamente el archivo de registro operativo para confirmar que el ciclo de inicialización concluyó de forma satisfactoria y que el hilo consumidor reanudó su tarea. Abra el flujo del log:
```bash
tail -f /var/log/legacy/sync.log
```
Debe comprobar la emisión explícita del mensaje "Sincronización reanudada exitosamente" en los registros inmediatos posteriores al arranque. De no observarse este mensaje en un lapso de dos minutos, escale al Administrador de Base de Datos y al Ingeniero de Infraestructura de guardia.

---

## 3. Códigos de Error Frecuentes y Acciones Correctivas

### 3.1 Error SYNC-901: Falla de Enlace de Red
El código de error `SYNC-901` indica pérdida de conectividad física o de enlace TLS con el bus corporativo. Compruebe la conectividad mediante `ping` y `curl -v https://bus.interno.corp:8443/health`. Si la red es estable, verifique la validez de los certificados locales en `/opt/legacy/ssl/client.crt`.

### 3.2 Error SYNC-902: Inconsistencia en Lote de Facturación
El código de error `SYNC-902` ocurre durante el procesamiento de lotes nocturnos de facturación tras cortes de fin de mes o desajustes en la numeración correlativa fiscal. Esta falla detiene la cola de facturación para evitar registros duplicados. Para mitigar, aplique el reinicio del servicio siguiendo el procedimiento de la sección 2.2 y ejecute la validación de integridad con `/opt/legacy/bin/validate_billing_batch.sh`.

---

## 4. Políticas de Contingencia y Contactos Operativos

En caso de que el procedimiento estándar no restablezca la operatividad en un lapso inferior a 30 minutos, se debe activar la contingencia nivel 2 notificando a la mesa de comando a través de los canales oficiales corporativos y escalando según la matriz de SLA documentada en las políticas organizacionales.
