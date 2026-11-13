# 🧰 Keycloak en Docker con Cliente Preconfigurado (JWT)

Este proyecto permite levantar **Keycloak** en un contenedor Docker, con un **cliente OIDC (OpenID Connect)** preconfigurado, listo para solicitar **tokens JWT** mediante el flujo de *Client Credentials*.

---

## 🚀 Requisitos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/)

---

## ⚙️ Iniciar el servicio

```bash
docker compose up -d
```

Acceder a la consola de administración:

👉 http://localhost:8080

Usuario: admin
Credenciales de administrador: ds2026

## Obtener un token JWT

Por ejemplo para el Grupo 1

```bash
curl --location 'http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/token' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--data-urlencode 'grant_type=client_credentials' \
--data-urlencode 'client_id=grupo-01' \
--data-urlencode 'client_secret=68230b9a-f540-4e16-9f56-19180f303676'
```

y como resultado

```json
{
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJmdXlRZ3o1Yy1JM29VdUdoT3RzOGxqTl8wX0Ewbm5IQjlhd1dhOC1WMWx3In0.eyJleHAiOjE3NTk5NjYyNTYsImlhdCI6MTc1OTk2NTk1NiwianRpIjoiYzc3MzdjYmEtNDIxYS00N2IzLTk5YzQtZjdmNTBiZjUwOTMzIiwiaXNzIjoiaHR0cDovL2xvY2FsaG9zdDo4MDgwL3JlYWxtcy9kcy0yMDI1LXJlYWxtIiwiYXVkIjoiYWNjb3VudCIsInN1YiI6IjEwYmNiYjMyLTRhYjQtNGJmNy1iYjVjLTQ0ZDMxMzA0ODM0MiIsInR5cCI6IkJlYXJlciIsImF6cCI6Imdyb3VwXzAxIiwiYWNyIjoiMSIsInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIiwiZGVmYXVsdC1yb2xlcy1kcy0yMDI1LXJlYWxtIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJlbWFpbCBwcm9maWxlIiwiY2xpZW50SG9zdCI6IjE5Mi4xNjguNjUuMSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoic2VydmljZS1hY2NvdW50LWdyb3VwXzAxIiwiY2xpZW50QWRkcmVzcyI6IjE5Mi4xNjguNjUuMSIsImNsaWVudF9pZCI6Imdyb3VwXzAxIn0.PKx-qlEl98_F-modzU_5Bx7HekA9YOM_Mgdv_w32dIsWILjR8MkfSMtF3HI-uKpSRJSfQuw9fJAniIYohWtv7pKeCd-STjxQ2lhzGeVq_FJoN8y_72RlFXvzQ0INoxU7j6Ku5zUWvQElkmmfPxLaDN6E_DI_5dbxDY2974hiE0m03LuO_lgWN96o_HYQuPB-Yx826T1tuwNYRpZg1kcynrWS3Rm1ItdqlfCny2UboTpGvhclrTdHyUvLUw6SGrPkSVbIQgTMH2pNSJt_ude5mvAicyQk4pK7mP6lZ9mVdBTCkFmIdyO90THrh1S_uycsUjKUMq6SCuCgpjgUGADJ0w",
    "expires_in": 300,
    "refresh_expires_in": 0,
    "token_type": "Bearer",
    "not-before-policy": 0,
    "scope": "email profile"
}
```

## Ejemplo de Configuración de Spring Boot

### application.yml

```yaml
server:
  port: 8081 # clualquier otro que no sea el 8080 que se lo otorgamos a keycloack

spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: http://localhost:8080/realms/ds-2026-realm
          # http://${KC_HOSTNAME}:${KC_PORT}/realms/${MI_REALM}
```

Podemos obtener la configuración OIDC en la URL: [.well-known/openid-configuration](http://localhost:8080/realms/ds-2026-realm/.well-known/openid-configuration)

Podemos obtener las JSON Web Key Set en la URL: [JWKS](http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/certs)

---

## 🔧 Solución de Problemas de Sincronización

### Problema: Los cambios en el archivo realm no se aplican

Si modificas el archivo `realm-config/ds-2026-realm.json` pero los cambios no se reflejan en Keycloak, sigue estos pasos:


#### 1. Reinicio Completo con Limpieza

Para aplicar los cambios en el archivo realm, necesitas hacer un reinicio completo que limpie los datos persistentes:

```bash
# Detener contenedores
docker-compose down

# Eliminar volúmenes (esto borrará todos los datos)
docker volume rm keycloak_postgres_data

# Limpiar sistema Docker
docker system prune -f

# Reiniciar
docker-compose up -d
```

#### 2. Verificar la Configuración

Después del reinicio, verifica que:

1. **Default Client Scopes del Realm**: Ve a `Realm Settings > Client Scopes` y verifica que aparezcan todos los scopes definidos en `defaultDefaultClientScopes`

2. **Client Scopes de los Clientes**: Ve a cada cliente (ej: `grupo-03`) y verifica que tenga los `defaultClientScopes` correctos

3. **Acceso a la Consola**: http://localhost:8080 con las credenciales del archivo `.env`

### Client Scopes Disponibles

El realm ahora incluye todos estos client scopes:

- `usuarios:read` / `usuarios:write`
- `compras:read` / `compras:write`
- `stock:read` / `stock:write`
- `productos:read` / `productos:write`
- `categorias:read` / `categorias:write`
- `reservas:read` / `reservas:write`
- `envios:read` / `envios:write`

