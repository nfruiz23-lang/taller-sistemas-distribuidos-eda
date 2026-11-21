"""
middleware.py - Patrones de Resiliencia: Rate Limiting, Circuit Breaker y Retry with Backoff
Taller 5 / LAB 11: Sistemas Distribuidos y Arquitectura de Software
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import httpx


# ─── 2. RATE LIMITER: Limitar las solicitudes ───────────────────────
class RateLimiter:
    """
    Controlador de Rate Limiting por IP usando ventana deslizante (Sliding Window).
    Evita que una misma IP realice más de 100 solicitudes en una ventana de 60 segundos.
    """
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        # 1. Revisar y eliminar las solicitudes con más de 60 segundos
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window_seconds
        ]

        # 2. Comprobar si ya alcanzó el límite permitido
        if len(self.requests[client_id]) >= self.max_requests:
            return False

        # 3. Registrar la marca de tiempo de la solicitud actual y permitir
        self.requests[client_id].append(now)
        return True


# Instancia global del Rate Limiter
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware HTTP para FastAPI:
    - Identifica la IP del cliente.
    - Bloquea con HTTP 429 Too Many Requests y Retry-After si excede el límite.
    - Continúa con call_next(request) si está permitida.
    """
    # Identificar la dirección IP del cliente
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Si supera el límite permitido
    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests"},
            headers={"Retry-After": "60"}
        )

    # Si la solicitud está permitida, continúa hacia la ruta correspondiente
    response = await call_next(request)
    return response


# ─── 3. CIRCUIT BREAKER: Proteger servicios externos ────────────────
class CircuitBreaker:
    """
    Implementación del patrón Circuit Breaker con máquina de 3 estados:
    - CLOSED: Funcionamiento normal, permite peticiones.
    - OPEN: Fallo detectado (>= 5 consecutivos). Cortocircuita llamadas inmediatamente.
    - HALF_OPEN: Periodo de recuperación cumplido (> 60s). Permite prueba controlada.
    """
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = self.STATE_CLOSED

    def can_execute(self) -> bool:
        """Determina si la solicitud al servicio externo está permitida."""
        if self.state == self.STATE_CLOSED:
            return True

        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                return True
            return False

        if self.state == self.STATE_HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Registra una respuesta exitosa, reseteando contadores y cerrando el circuito."""
        self.failure_count = 0
        self.state = self.STATE_CLOSED

    def record_failure(self):
        """Registra un fallo del servicio. Si alcanza el umbral, abre el circuito."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN


# Instancia global del Circuit Breaker para catalog-service
catalog_circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60
)


async def call_catalog_with_breaker(url: str) -> dict:
    """
    Realiza una petición HTTP asíncrona hacia el servicio de catálogo
    protegida por el Circuit Breaker con timeout estricto de 5 segundos.
    """
    if not catalog_circuit.can_execute():
        raise HTTPException(
            status_code=503,
            detail="Catalog service unavailable (Circuit Breaker OPEN)"
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                catalog_circuit.record_success()
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="Space not found in catalog")
            else:
                catalog_circuit.record_failure()
                raise HTTPException(
                    status_code=503,
                    detail=f"Catalog service error: {response.status_code}"
                )
    except httpx.RequestError as exc:
        catalog_circuit.record_failure()
        raise HTTPException(
            status_code=503,
            detail=f"Catalog service connection error: {str(exc)}"
        )
    except HTTPException:
        raise
    except Exception as exc:
        catalog_circuit.record_failure()
        raise HTTPException(
            status_code=503,
            detail=f"Catalog service error: {str(exc)}"
        )


# ─── 4. RETRY WITH BACKOFF: Reintentar operaciones ───────────────────
async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0
):
    """
    Reintenta la ejecución de una función asíncrona ante fallas transitorias,
    incrementando progresivamente el tiempo de espera exponencial (1s, 2s).
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"Retry {attempt + 1}/{max_retries} after {delay}s: {str(e)}")
                await asyncio.sleep(delay)

    raise last_exception

