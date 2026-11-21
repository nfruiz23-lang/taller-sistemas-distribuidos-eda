"""
test_taller5_middleware.py
Suite de pruebas automatizadas completas para el Taller 5 / LAB 11:
- Rate Limiter (Ventana deslizante de 100 solicitudes / 60 segundos por IP)
- Middleware de Rate Limiting (HTTP 429 + Headers Retry-After)
- Circuit Breaker (Estados CLOSED, OPEN, HALF_OPEN tras 5 fallos y 60s recuperación)
- Llamada protegida al catálogo (HTTP 503 ante fallas y cortocircuitos)
- Retry with Exponential Backoff (3 intentos, backoff progresivo 1s, 2s)
"""

import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Asegurar path para importar orders-service
_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_dir, "orders-service"))

from middleware import (
    RateLimiter,
    rate_limiter,
    rate_limit_middleware,
    CircuitBreaker,
    catalog_circuit,
    call_catalog_with_breaker,
    retry_with_backoff,
)
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse


def run_coroutine(coro):
    """
    Ejecuta una corrutina de forma síncrona/directa mediante paso de iteración,
    evitando bloqueos de sockets o proactor en entornos restringidos.
    """
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


class TestTaller5ResiliencePatterns(unittest.TestCase):

    def setUp(self):
        """Reinicia el estado de las instancias globales antes de cada prueba."""
        rate_limiter.requests.clear()
        catalog_circuit.state = CircuitBreaker.STATE_CLOSED
        catalog_circuit.failure_count = 0
        catalog_circuit.last_failure_time = 0

    # ─── 1. PRUEBAS DE RATE LIMITER ─────────────────────────────────
    def test_01_rate_limiter_allows_up_to_limit(self):
        """Valida que una IP pueda realizar hasta 100 solicitudes permitidas."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        client_ip = "192.168.1.10"

        for i in range(100):
            allowed = limiter.is_allowed(client_ip)
            self.assertTrue(allowed, f"La solicitud {i + 1} debió ser permitida")

        self.assertEqual(len(limiter.requests[client_ip]), 100)
        print(" [PASS] 1. RateLimiter permite exactamente las primeras 100 solicitudes de la IP")

    def test_02_rate_limiter_blocks_request_101(self):
        """Valida que la solicitud 101 sea bloqueada dentro de la ventana de 60s."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        client_ip = "192.168.1.10"

        for _ in range(100):
            limiter.is_allowed(client_ip)

        blocked = limiter.is_allowed(client_ip)
        self.assertFalse(blocked, "La solicitud 101 debe ser bloqueada (False)")
        print(" [PASS] 2. RateLimiter bloquea exitosamente la solicitud 101 al alcanzar el límite")

    def test_03_rate_limiter_independent_ips(self):
        """Valida que el conteo de solicitudes sea independiente por dirección IP."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        ip_a = "192.168.1.10"
        ip_b = "192.168.1.20"

        # Saturar IP A
        for _ in range(100):
            limiter.is_allowed(ip_a)

        self.assertFalse(limiter.is_allowed(ip_a))
        # IP B debe seguir permitida con registro independiente
        self.assertTrue(limiter.is_allowed(ip_b))
        self.assertEqual(len(limiter.requests[ip_b]), 1)
        print(" [PASS] 3. RateLimiter mantiene registros y contadores aislados por cada dirección IP")

    def test_04_rate_limiter_expires_old_requests(self):
        """Valida que las marcas de tiempo mayores a 60 segundos sean eliminadas."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        client_ip = "192.168.1.50"

        now = time.time()
        # Inyectar 100 solicitudes con más de 65 segundos de antigüedad
        limiter.requests[client_ip] = [now - 65 for _ in range(100)]

        # Al consultar is_allowed, debe limpiar las viejas y permitir la nueva
        allowed = limiter.is_allowed(client_ip)
        self.assertTrue(allowed)
        self.assertEqual(len(limiter.requests[client_ip]), 1)
        print(" [PASS] 4. RateLimiter depura automáticamente solicitudes fuera de la ventana de 60s")

    # ─── 2. PRUEBAS DEL MIDDLEWARE HTTP (FASTAPI) ───────────────────
    def test_05_rate_limit_middleware_allows_normal_request(self):
        """Valida que el middleware permita la solicitud y llame a call_next si está bajo el límite."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        async def mock_call_next(req):
            return JSONResponse(status_code=200, content={"status": "ok"})

        response = run_coroutine(rate_limit_middleware(mock_request, mock_call_next))
        self.assertEqual(response.status_code, 200)
        print(" [PASS] 5. Middleware HTTP permite peticiones dentro del límite y delega a call_next")

    def test_06_rate_limit_middleware_blocks_exceeded_requests(self):
        """Valida que el middleware intercepte y retorne HTTP 429 + Retry-After si excede límite."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Simular que la IP ya consumió sus 100 cupos
        rate_limiter.requests["192.168.1.100"] = [time.time() for _ in range(100)]

        async def mock_call_next(req):
            return JSONResponse(status_code=200, content={"status": "ok"})

        response = run_coroutine(rate_limit_middleware(mock_request, mock_call_next))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers.get("Retry-After"), "60")
        print(" [PASS] 6. Middleware HTTP bloquea peticiones excedidas con HTTP 429 y header Retry-After: 60")

    # ─── 3. PRUEBAS DE CIRCUIT BREAKER ──────────────────────────────
    def test_07_circuit_breaker_initial_state_closed(self):
        """Valida que el Circuit Breaker inicie en CLOSED y permita llamadas."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self.assertEqual(cb.state, CircuitBreaker.STATE_CLOSED)
        self.assertTrue(cb.can_execute())
        print(" [PASS] 7. CircuitBreaker inicializa en estado 'closed' permitiendo peticiones")

    def test_08_circuit_breaker_transitions_to_open_after_5_failures(self):
        """Valida transición de CLOSED a OPEN tras exactamente 5 fallos consecutivos."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        # Registrar 4 fallos consecutivos: debe seguir CLOSED
        for i in range(4):
            cb.record_failure()
            self.assertEqual(cb.state, CircuitBreaker.STATE_CLOSED)
            self.assertTrue(cb.can_execute())

        # 5to fallo: debe abrir el circuito
        cb.record_failure()
        self.assertEqual(cb.failure_count, 5)
        self.assertEqual(cb.state, CircuitBreaker.STATE_OPEN)
        self.assertFalse(cb.can_execute())
        print(" [PASS] 8. CircuitBreaker transiciona a 'open' y bloquea llamadas al alcanzar 5 fallos")

    def test_09_circuit_breaker_recovery_to_half_open_and_closed(self):
        """Valida transición de OPEN a HALF_OPEN tras 60s, y cierre a CLOSED tras éxito."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        # Provocar apertura
        for _ in range(5):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitBreaker.STATE_OPEN)

        # Simular que transcurrieron 65 segundos (> recovery_timeout=60)
        cb.last_failure_time = time.time() - 65

        # can_execute debe transicionar a HALF_OPEN y permitir una prueba
        can_retry = cb.can_execute()
        self.assertTrue(can_retry)
        self.assertEqual(cb.state, CircuitBreaker.STATE_HALF_OPEN)

        # Registrar éxito en prueba: debe resetear fallos y cerrar circuito
        cb.record_success()
        self.assertEqual(cb.failure_count, 0)
        self.assertEqual(cb.state, CircuitBreaker.STATE_CLOSED)
        self.assertTrue(cb.can_execute())
        print(" [PASS] 9. CircuitBreaker recupera servicio: OPEN -> HALF_OPEN (60s) -> CLOSED")

    # ─── 4. PRUEBAS DE LLAMADA PROTEGIDA AL CATÁLOGO ─────────────────
    def test_10_call_catalog_with_breaker_when_open_raises_503(self):
        """Valida que call_catalog_with_breaker rechace con 503 inmediato si el circuito está abierto."""
        catalog_circuit.state = CircuitBreaker.STATE_OPEN
        catalog_circuit.last_failure_time = time.time()

        with self.assertRaises(HTTPException) as ctx:
            run_coroutine(call_catalog_with_breaker("http://catalog-service:8001/spaces/1"))

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Circuit Breaker OPEN", ctx.exception.detail)
        print(" [PASS] 10. call_catalog_with_breaker cortocircuita y devuelve 503 sin peticiones HTTP")

    def test_11_call_catalog_with_breaker_records_failure_on_error(self):
        """Valida que ante fallo de red se incremente el conteo y devuelva HTTP 503."""
        import httpx

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            with self.assertRaises(HTTPException) as ctx:
                run_coroutine(call_catalog_with_breaker("http://catalog-service:8001/spaces/1"))

            self.assertEqual(ctx.exception.status_code, 503)
            self.assertEqual(catalog_circuit.failure_count, 1)
        print(" [PASS] 11. Fallo de red capturado, registra error en CircuitBreaker y responde HTTP 503")

    # ─── 5. PRUEBAS DE RETRY WITH BACKOFF ────────────────────────────
    def test_12_retry_with_backoff_success_first_try(self):
        """Valida que una función exitosa en el primer intento no aplique reintentos ni retardos."""
        call_count = [0]
        async def dummy_op():
            call_count[0] += 1
            return {"status": "ok", "data": "item"}

        result = run_coroutine(retry_with_backoff(dummy_op, max_retries=3, base_delay=0.01))
        self.assertEqual(result, {"status": "ok", "data": "item"})
        self.assertEqual(call_count[0], 1)
        print(" [PASS] 12. retry_with_backoff retorna resultado inmediato en el primer intento exitoso")

    def test_13_retry_with_backoff_eventual_success(self):
        """Valida que la función se reintente ante fallos transitorios hasta tener éxito."""
        attempts = [0]
        delays_seen = []

        async def flaky_op():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ConnectionError(f"Fallo transitorio {attempts[0]}")
            return {"status": "recovered", "attempts": attempts[0]}

        async def mock_sleep(d):
            delays_seen.append(d)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            result = run_coroutine(retry_with_backoff(flaky_op, max_retries=3, base_delay=1.0))

        self.assertEqual(result, {"status": "recovered", "attempts": 3})
        self.assertEqual(attempts[0], 3)
        # Retardos exponenciales esperados: intento 1 (1.0s) e intento 2 (2.0s)
        self.assertEqual(delays_seen, [1.0, 2.0])
        print(" [PASS] 13. retry_with_backoff reintenta con backoff exponencial (1s, 2s) y recupera operación")

    def test_14_retry_with_backoff_exhausts_and_raises(self):
        """Valida que tras agotar los 3 intentos se propague la última excepción capturada."""
        attempts = [0]
        async def always_failing():
            attempts[0] += 1
            raise ValueError(f"Fallo irrecuperable en intento {attempts[0]}")

        with patch("asyncio.sleep", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                run_coroutine(retry_with_backoff(always_failing, max_retries=3, base_delay=0.01))

        self.assertEqual(attempts[0], 3)
        self.assertIn("Fallo irrecuperable en intento 3", str(ctx.exception))
        print(" [PASS] 14. retry_with_backoff propaga la última excepción tras agotar los 3 intentos")


if __name__ == "__main__":
    unittest.main()
