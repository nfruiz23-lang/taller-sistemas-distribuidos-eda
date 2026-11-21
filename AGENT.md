# AGENT.md

## Proyecto

Taller de Sistemas Distribuidos y Arquitectura de Software
- **Parte 1 (Labs 1-5):** Microservicios con FastAPI, Docker Compose y Chaos Engineering.
- **Parte 2 (Labs 6-10):** Migración Serverless y Event-Driven Architecture (EDA) con AWS Lambda, API Gateway, EventBridge y SQS.

## Objetivo del proyecto

Evolucionar un sistema de microservicios síncronos de reservas de coworking hacia una arquitectura distribuida inteligente, desacoplada y resiliente mediante eventos asíncronos y funciones serverless, resolviendo los puntos de falla detectados durante los experimentos de Chaos Engineering.

## Estructura del proyecto

```text
taller/
├── catalog-service/             # [Taller 1] Microservicio FastAPI de catálogo original
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── orders-service/              # [Taller 1 & 2] Microservicio de órdenes con caché resiliente EDA
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── lambda-catalog/              # [Taller 2 - LAB 6] Lambda Serverless de catálogo con EventBridge
│   ├── handler.py
│   └── requirements.txt
├── lambda-consumer/             # [Taller 2 - LAB 7] Lambda consumidora de SQS
│   ├── handler.py
│   └── requirements.txt
├── scripts/
│   ├── init-localstack.sh       # Inicialización de colas y reglas en LocalStack
│   └── simulate_event_flow.py   # Demostración interactiva en consola
├── template.yaml                # [Taller 2 - LAB 8] Especificación completa AWS SAM
├── docker-compose.yml           # [Taller 1] Orquestación de microservicios contenedores
├── docker-compose.serverless.yml# [Taller 2] Emulación local con LocalStack
├── test_serverless_pipeline.py  # [Taller 2 - LAB 10] Suite de pruebas automatizadas (5/5 PASS)
├── chaos-test.sh                # [Taller 1] Script de Chaos Engineering
├── chaos-test.ps1               # [Taller 1] Script PowerShell de Chaos Engineering
├── chaos-report.md              # [Taller 1] Informe de resultados de caos
├── Parte 2.docx                 # [Taller 2] Documento Word completado y formateado
├── PARTE_2.md                   # [Taller 2] Documentación completa en Markdown
└── taller 1.docx                # [Taller 1] Documento original de la Parte 1
```

## Stack tecnológico

- **Lenguaje:** Python 3.11+
- **Framework Web:** FastAPI 0.104.1 + Uvicorn 0.24.0
- **Modelos:** Pydantic 2.5.0
- **Cliente HTTP:** httpx 0.25.2
- **SDK Cloud:** boto3 1.34.0+ (Amazon EventBridge, SQS, Lambda)
- **Infraestructura Serverless:** AWS SAM (Serverless Application Model)
- **Contenedores y Emulación:** Docker, Docker Compose, LocalStack

## Labs completados

### Parte 1: Microservicios y Caos
- [x] LAB 1: catalog-service con FastAPI (puerto 8001)
- [x] LAB 2: orders-service que consulta al catálogo (puerto 8002)
- [x] LAB 3: Docker Compose con red compartida
- [x] LAB 4: Chaos Engineering - apagar el catálogo
- [x] LAB 5: Chaos Engineering - romper contrato de API + chaos-report.md

### Parte 2: Serverless & Event-Driven Architecture (EDA)
- [x] LAB 6: Lambda catalog-service con API Gateway y publicación a EventBridge (`lambda-catalog/`)
- [x] LAB 7: Consumer Lambda con suscripción a SQS y soporte para batching (`lambda-consumer/`)
- [x] LAB 8: Infraestructura como Código con AWS SAM (`template.yaml` + Dead Letter Queue)
- [x] LAB 9: Resiliencia en orders-service (Event-Carried State Transfer + Fallback ante caídas)
- [x] LAB 10 (Serverless): Pruebas unitarias, de integración y simulación interactiva (`test_serverless_pipeline.py` & `simulate_event_flow.py`)

### Taller 4: Backend Avanzado FastAPI
- [x] LAB 10 (Auth & Resiliencia): Autenticación JWT + RBAC (`orders-service/auth.py`)
- [x] Cifrado de contraseñas con bcrypt (`passlib` + `bcrypt`)
- [x] Persistencia de usuarios en PostgreSQL AWS RDS (`UserModel` + Migración Alembic `8f5e47c59a2f`)
- [x] Control de Acceso Basado en Roles (`user: 1 < admin: 2 < superadmin: 3`)
- [x] Patrón Circuit Breaker para llamadas a dependencias síncronas (`orders-service/resilience.py`)
- [x] Patrón Rate Limiting con Sliding Window y headers HTTP estándar
- [x] Suite de pruebas automatizadas completa 12/12 PASS (`test_taller4_auth.py`)
- [x] Documentación técnica en Markdown (`TALLER_4.md`) y Word (`Taller 4 - Reporte Tecnico.docx`)

### Taller 5: Resiliencia y Estabilidad en APIs Distribuidas
- [x] LAB 11: Rate Limiting + Circuit Breaker + Retry with Backoff (`orders-service/middleware.py`)
- [x] Rate Limiting con ventana deslizante (100 req / 60s por IP) y respuesta HTTP 429 con cabecera `Retry-After: 60`
- [x] Circuit Breaker con máquina de estados (`closed`, `open`, `half_open`), umbral de 5 fallos y 60s de recuperación
- [x] Conexión protegida con Circuit Breaker hacia `catalog-service` con timeout de 5.0 segundos (`call_catalog_with_breaker`)
- [x] Mecanismo de Retry with Exponential Backoff (3 intentos con retrasos progresivos de 1s y 2s)
- [x] Integración del middleware en FastAPI mediante `app.middleware("http")(rate_limit_middleware)` en `orders-service/main.py`
- [x] Suite de pruebas automatizadas completa 14/14 PASS (`test_taller5_middleware.py`)
- [x] Documentación técnica completa en Markdown (`TALLER_5.md`)

### Taller 6: Integración de APIs de Inteligencia Artificial
- [x] LAB 12: Integración de OpenAI API (GPT-4o-mini) en `ai_service/openai_client.py`
- [x] Función `recommend_space()` con salida estructurada JSON (`recommended_space_id`, `confidence`, `reasoning`, `alternatives`, `tips`)
- [x] Función `generate_space_description()` para redacción comercial (temperatura 0.7, max 100 palabras)
- [x] Función `analyze_booking_pattern()` con recorte a 20 registros para analítica de demanda y horas pico
- [x] Corrección asíncrona oficial mediante `AsyncOpenAI` y `await` nativo
- [x] Script de prueba en vivo `test_ai.py` con datos de demostración
- [x] Suite de pruebas automatizadas completas 5/5 PASS (`test_taller6_ai.py`)
- [x] Documentación técnica completa en Markdown (`TALLER_6.md`)

## Convenciones del proyecto

- **EventBridge Event:**
  - `Source`: `coworking.catalog`
  - `DetailType`: `SpaceChanged`
- **SQS Queue:** `catalog-events` (con DLQ `catalog-events-dlq` y `maxReceiveCount: 3`)
- **API Gateway Paths:** `/spaces`, `/spaces/{id}`, `/spaces/{id}/availability`, `/health`
- **Webhook de Órdenes:** `POST /events/space-changed`
- **Tolerant Reader:** Soporta intercambiablemente `price_per_hour` y `hourly_rate` para prevenir rupturas de contrato.
