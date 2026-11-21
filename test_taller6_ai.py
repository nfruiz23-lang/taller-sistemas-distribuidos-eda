"""
test_taller6_ai.py
Suite de pruebas automatizadas completas para el LAB 12 / Taller 6:
- Validación de recommend_space() (JSON estructurado, matching de presupuesto y personas)
- Validación de generate_space_description() (Texto comercial con límite de tokens)
- Validación de analyze_booking_pattern() (Detección de peak_hours y underutilized_spaces)
- Manejo de ejecución asíncrona (AsyncOpenAI + await)
- Fallback y validación de prompts ante entradas incompletas (.get())
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

import ai_service.openai_client as ai_module


def run_coroutine(coro):
    """Ejecutor síncrono directo para evitar bloqueos de event loop en entornos restringidos."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


class TestTaller6OpenAIIntegration(unittest.TestCase):

    def setUp(self):
        """Mock del cliente OpenAI para pruebas unitarias deterministas."""
        self.mock_client = MagicMock()
        self.mock_completions = MagicMock()
        self.mock_client.chat.completions.create = AsyncMock()
        ai_module.client = self.mock_client

    # ─── 1. PRUEBAS DE RECOMMEND_SPACE ──────────────────────────────
    def test_01_recommend_space_valid_json_response(self):
        """Valida que recommend_space invoque gpt-4o-mini y retorne diccionario con claves esperadas."""
        mock_response_data = {
            "recommended_space_id": "ESP001",
            "confidence": 0.95,
            "reasoning": "Capacidad adecuada para 5 personas y dentro del presupuesto de $150.000.",
            "alternatives": ["ESP003"],
            "tips": ["Confirmar disponibilidad de proyector", "Reservar con anticipación"]
        }

        mock_openai_res = MagicMock()
        mock_openai_res.choices = [
            MagicMock(message=MagicMock(content=json.dumps(mock_response_data)))
        ]
        self.mock_client.chat.completions.create.return_value = mock_openai_res

        user_prefs = {"need": "Reunión", "hours": 3, "budget": 150000, "people": 5}
        spaces = [
            {"id": "ESP001", "name": "Sala Ejecutiva", "capacity": 6, "price_per_hour": 40000},
            {"id": "ESP002", "name": "Oficina Individual", "capacity": 1, "price_per_hour": 15000}
        ]

        result = run_coroutine(ai_module.recommend_space(user_prefs, spaces))

        self.assertIsInstance(result, dict)
        self.assertEqual(result["recommended_space_id"], "ESP001")
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertIn("reasoning", result)
        self.assertIn("alternatives", result)
        self.assertIn("tips", result)

        # Verificar parámetros de llamada a OpenAI
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini")
        self.assertEqual(call_kwargs["temperature"], 0.3)
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})
        print(" [PASS] 1. recommend_space() genera recomendación JSON estructurada y valida parámetros")

    def test_02_recommend_space_handles_missing_optional_preferences(self):
        """Valida que .get() maneje valores por defecto si el usuario no envía datos opcionales."""
        mock_response_data = {
            "recommended_space_id": "ESP002",
            "confidence": 0.8,
            "reasoning": "Espacio estándar para trabajo general",
            "alternatives": [],
            "tips": []
        }
        mock_openai_res = MagicMock()
        mock_openai_res.choices = [
            MagicMock(message=MagicMock(content=json.dumps(mock_response_data)))
        ]
        self.mock_client.chat.completions.create.return_value = mock_openai_res

        # Preferencias vacías
        empty_prefs = {}
        spaces = [{"id": "ESP002", "name": "Desk Flex", "capacity": 1, "price_per_hour": 20000}]

        result = run_coroutine(ai_module.recommend_space(empty_prefs, spaces))
        self.assertEqual(result["recommended_space_id"], "ESP002")

        # Verificar que el prompt contenga valores por defecto ('trabajo general', 2 horas, etc.)
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        prompt_content = call_kwargs["messages"][1]["content"]
        self.assertIn("trabajo general", prompt_content)
        self.assertIn("2 horas", prompt_content)
        print(" [PASS] 2. recommend_space() tolera campos ausentes usando valores fallback seguros")

    # ─── 2. PRUEBAS DE GENERATE_SPACE_DESCRIPTION ───────────────────
    def test_03_generate_space_description_returns_clean_text(self):
        """Valida que generate_space_description genere texto comercial con temperatura 0.7."""
        generated_text = (
            "La Sala Ejecutiva es un entorno elegante y productivo para reuniones de alto nivel. "
            "Con capacidad para 6 personas y excelente conectividad, optimiza tus sesiones colaborativas."
        )
        mock_openai_res = MagicMock()
        mock_openai_res.choices = [
            MagicMock(message=MagicMock(content=f"  {generated_text}\n\n"))
        ]
        self.mock_client.chat.completions.create.return_value = mock_openai_res

        space = {"name": "Sala Ejecutiva", "capacity": 6, "price_per_hour": 40000}
        result = run_coroutine(ai_module.generate_space_description(space))

        self.assertEqual(result, generated_text)
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini")
        self.assertEqual(call_kwargs["temperature"], 0.7)
        self.assertEqual(call_kwargs["max_tokens"], 150)
        print(" [PASS] 3. generate_space_description() genera texto comercial limpio y aplica max_tokens")

    # ─── 3. PRUEBAS DE ANALYZE_BOOKING_PATTERN ──────────────────────
    def test_04_analyze_booking_pattern_caps_to_20_records(self):
        """Valida que analyze_booking_pattern envíe solo hasta 20 registros y retorne JSON de análisis."""
        mock_analysis_data = {
            "peak_hours": [10, 11, 14],
            "underutilized_spaces": ["ESP002"],
            "recommendations": ["Ofrecer descuentos matutinos en ESP002"],
            "predicted_demand_next_week": "alta"
        }
        mock_openai_res = MagicMock()
        mock_openai_res.choices = [
            MagicMock(message=MagicMock(content=json.dumps(mock_analysis_data)))
        ]
        self.mock_client.chat.completions.create.return_value = mock_openai_res

        # Crear 50 registros de uso
        usage_data = [{"space_id": f"ESP{i:03d}", "hour": i % 24, "bookings": i} for i in range(50)]

        result = run_coroutine(ai_module.analyze_booking_pattern(usage_data))

        self.assertIsInstance(result, dict)
        self.assertEqual(result["peak_hours"], [10, 11, 14])
        self.assertEqual(result["predicted_demand_next_week"], "alta")

        # Verificar que en el prompt solo se hayan enviado 20 registros
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        prompt_content = call_kwargs["messages"][0]["content"]
        # Debe contener ESP019 (el número 20, 0-indexed), pero NO ESP025
        self.assertIn("ESP019", prompt_content)
        self.assertNotIn("ESP025", prompt_content)
        print(" [PASS] 4. analyze_booking_pattern() procesa patrones y limita estrictamente a 20 registros")

    # ─── 4. PRUEBA DE GESTIÓN DE ERROR SIN SDK ───────────────────────
    def test_05_client_none_raises_runtime_error(self):
        """Valida que si la librería openai no está presente se informe claramente."""
        with patch.object(ai_module, "AsyncOpenAI", None), patch.object(ai_module, "client", None):
            with self.assertRaises(RuntimeError) as ctx:
                run_coroutine(ai_module.generate_space_description({"name": "Test"}))
            self.assertIn("openai", str(ctx.exception))
        print(" [PASS] 5. Manejo defensivo: informa error explicativo si la librería openai no está instalada")


if __name__ == "__main__":
    unittest.main()
