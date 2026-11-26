# Simulador M4 — Ubicación y Disponibilidad (frontend)

Simulador web para ejercitar la API del Módulo 4 sin depender de que M3 y M5
estén listos. Consumidor visual del contrato `openapi.yml` de la raíz del repo.

## Requisitos

- Node.js 20 o superior (probado con Node 26).
- No requiere Docker: el entorno principal de desarrollo es **Prism**.

## Instalación

```bash
cd frontend
npm install
```

## Tipos desde el contrato

Los tipos de TypeScript se generan desde `../openapi.yml` (fuente única de
verdad). El front **no** define a mano ningún tipo que exista en el contrato:

```bash
npm run gen:types
```

Salida: `src/api/generated/schema.ts` (commiteada; regenerar cuando cambie el
contrato). `openapi-typescript` requiere `typescript@^5.x` (instalado como
devDependency).

## Correr contra Prism (entorno principal)

Prism levanta un mock que valida requests y responde según los `examples` del
contrato, en el puerto 4010:

```bash
npm run mock        # terminal 1 → http://localhost:4010
npm run dev         # terminal 2 → http://localhost:5173
```

Abrir <http://localhost:5173>. El proxy de Vite redirige `/api` y `/health`
hacia `VITE_PROXY_TARGET` (por defecto `http://localhost:4010`).

Notas sobre Prism:

- Exige `Authorization: Bearer <cualquier string>` en los endpoints de
  negocio (está declarado `bearerAuth` en el contrato); sin token responde 401.
- `/health/live` y `/health/ready` no requieren token.
- Responde con los `examples` del YAML: por ejemplo, la búsqueda de cercanos
  sin candidatos devuelve `radio_aplicado_km: 9.5`.

## Apuntar a un backend real

1. Copiar el archivo de variables:

   ```bash
   cp .env.example .env
   ```

2. En `.env`, cambiar el destino del proxy:

   ```bash
   VITE_PROXY_TARGET=http://localhost:8000
   ```

3. Levantar el backend del repo (desde la raíz):

   ```bash
   docker-compose up -d
   docker-compose exec api python -m app.seed   # semilla: 50 conductores
   ```

4. Obtener un JWT (Keycloak local, realm `ds-2026-realm`) y pegarlo en el
   campo "Token" de la UI (queda solo en memoria, no se persiste):

   ```bash
   curl -s 'http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/token' \
     -H 'Content-Type: application/x-www-form-urlencoded' \
     -d 'grant_type=client_credentials' \
     -d 'client_id=grupo-03' \
     -d 'client_secret=<client_secret>' | jq -r .access_token
   ```

   - `grupo-03` (rol `ubicacion-be`): ubicación, estado operativo, cercanos,
     estimación de ruta y geocodificación.
   - `grupo-04` (rol `solicitud-be`): necesario para `POST .../reserva`.
   - El token vence a los 5 minutos (`expires_in: 300`); si expira, la API
     responde 401 y hay que regenerarlo.

> Si el backend corre fuera de Docker, exportar `KEYCLOAK_JWKS_URL` apuntando a
> `http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/certs`.

## Scripts

| Script             | Qué hace                                              |
| ------------------ | ----------------------------------------------------- |
| `npm run dev`      | Servidor de desarrollo con proxy (Vite)                |
| `npm run build`    | Type-check (`tsc -b`) y build de producción           |
| `npm run gen:types`| Genera `src/api/generated/schema.ts` desde el contrato|
| `npm run mock`     | Levanta Prism sobre `../openapi.yml` en el puerto 4010|

## Variables de entorno

| Variable            | Default                   | Descripción                       |
| ------------------- | ------------------------- | --------------------------------- |
| `VITE_PROXY_TARGET` | `http://localhost:4010`   | Destino del proxy `/api` y `/health` (Prism). Para backend real: `http://localhost:8000` |

## Notas de privacidad (RF-4.7)

- El panel de logs **nunca** muestra URLs completas con coordenadas en el
  query string: se registra solo la ruta, sin query.
- Las coordenadas de los conductores simulados viven únicamente en el cliente:
  la API no expone un listado de ubicaciones.
