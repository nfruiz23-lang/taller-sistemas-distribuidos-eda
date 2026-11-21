"""
test_ai.py - Archivo de ejecución y prueba del LAB 12
Invocación de las 3 funciones de IA con datos de prueba del documento.
"""

import os
import sys
import json
import asyncio

# Asegurar que se reconozca ai_service
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from ai_service.openai_client import (
    recommend_space,
    generate_space_description,
    analyze_booking_pattern
)


async def main():
    print("=" * 60)
    print("🚀 EJECUTANDO PRUEBAS DEL LAB 12 (OPENAI API)")
    print("=" * 60)

    # 1. Datos del usuario
    preferences = {
        "need": "Sala de reuniones",
        "hours": 3,
        "budget": 150000,
        "people": 5,
        "notes": "Buena conexión a internet y ambiente tranquilo"
    }

    # 2. Espacios disponibles
    spaces = [
        {
            "id": "ESP001",
            "name": "Sala Ejecutiva",
            "capacity": 6,
            "price_per_hour": 40000,
            "wifi": True
        },
        {
            "id": "ESP002",
            "name": "Oficina Privada",
            "capacity": 2,
            "price_per_hour": 25000,
            "wifi": True
        },
        {
            "id": "ESP003",
            "name": "Sala de Conferencias",
            "capacity": 10,
            "price_per_hour": 60000,
            "wifi": True
        }
    ]

    # Probar recomendación
    print("\n--- 1. RECOMENDACIÓN INTELIGENTE ---")
    recommendation = await recommend_space(preferences, spaces)
    print("RECOMENDACIÓN:")
    print(json.dumps(recommendation, indent=2, ensure_ascii=False) if isinstance(recommendation, dict) else recommendation)

    # Probar descripción comercial
    print("\n--- 2. GENERACIÓN DE DESCRIPCIÓN COMERCIAL ---")
    description = await generate_space_description(spaces[0])
    print("DESCRIPCIÓN:")
    print(description)

    # Probar análisis de reservas
    print("\n--- 3. ANÁLISIS DE PATRONES DE RESERVA ---")
    usage = [
        {"space_id": "ESP001", "hour": 10, "bookings": 8},
        {"space_id": "ESP001", "hour": 14, "bookings": 5},
        {"space_id": "ESP002", "hour": 10, "bookings": 1},
        {"space_id": "ESP002", "hour": 11, "bookings": 0},
        {"space_id": "ESP003", "hour": 9, "bookings": 7}
    ]
    analysis = await analyze_booking_pattern(usage)
    print("ANÁLISIS:")
    print(json.dumps(analysis, indent=2, ensure_ascii=False) if isinstance(analysis, dict) else analysis)

    print("\n" + "=" * 60)
    print("✅ PRUEBAS COMPLETADAS CON ÉXITO")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
