"""Herramienta operativa para el cálculo determinista de severidad y SLA de incidentes.

Implementa la política cuantitativa de clasificación técnica (D10) evaluando el volumen
de usuarios afectados y la condición de misión crítica del servicio para determinar
el nivel de severidad ('critical', 'high', 'medium', 'low'), el SLA en horas y la
necesidad de escalamiento inmediato.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.models.ticket import Priority


def evaluate_incident_severity(
    affected_users: int, is_critical_service: bool = False, service_name: str = ""
) -> dict[str, Any]:
    """Evalúa de forma determinista la severidad, SLA y requerimiento de escalamiento.

    Args:
        affected_users: cantidad estimada de usuarios o clientes afectados.
        is_critical_service: indica si la plataforma afectada es de misión crítica.
        service_name: nombre del sistema o componente impactado.

    Returns:
        Diccionario con severity, sla_hours, requires_escalation, rationale,
        service_name, affected_users e is_critical_service.
    """
    safe_users = max(0, affected_users)

    if safe_users >= 500 or is_critical_service:
        severity = Priority.CRITICAL.value
        sla_hours = 1
        requires_escalation = True
        rationale = "Servicio crítico o afectación masiva (>= 500 usuarios)."
    elif safe_users >= 100:
        severity = Priority.HIGH.value
        sla_hours = 4
        requires_escalation = True
        rationale = "Impacto alto (100 a 499 usuarios afectados)."
    elif safe_users >= 10:
        severity = Priority.MEDIUM.value
        sla_hours = 8
        requires_escalation = False
        rationale = "Impacto moderado (10 a 99 usuarios afectados)."
    else:
        severity = Priority.LOW.value
        sla_hours = 24
        requires_escalation = False
        rationale = "Impacto bajo (< 10 usuarios afectados)."

    return {
        "severity": severity,
        "sla_hours": sla_hours,
        "requires_escalation": requires_escalation,
        "rationale": rationale,
        "service_name": service_name.strip(),
        "affected_users": safe_users,
        "is_critical_service": is_critical_service,
    }


@tool("calculate_incident_priority")
def calculate_incident_priority(
    affected_users: int,
    is_critical_service: bool = False,
    service_name: str = "",
) -> dict[str, Any]:
    """Calcula deterministamente la severidad, SLA de resolución y escalamiento de un incidente.

    Invoca esta herramienta cuando el usuario reporte una caída, falla o degradación
    operativa y proporcione información de usuarios afectados o criticidad del servicio,
    o solicite clasificar la prioridad o calcular el SLA de atención del incidente.

    Args:
        affected_users: número estimado de usuarios impactados por la falla (ej. 500).
        is_critical_service: True si el servicio es considerado de misión crítica corporativa.
        service_name: nombre opcional del servicio o infraestructura afectada.

    Returns:
        Diccionario con severity, sla_hours, requires_escalation, rationale y datos asociados.
    """
    return evaluate_incident_severity(
        affected_users=affected_users,
        is_critical_service=is_critical_service,
        service_name=service_name,
    )


__all__ = [
    "calculate_incident_priority",
    "evaluate_incident_severity",
]
