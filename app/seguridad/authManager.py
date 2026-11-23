import logging
import os
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from app.errores.exceptionsSemanticos import NoAutenticado, SinPermiso

logger = logging.getLogger(__name__)

KEYCLOAK_CLAVE_PUBLICA = os.getenv("KEYCLOAK_JWKS_URL","http://keycloak-server:8080/realms/ds-2026-realm/protocol/openid-connect/certs",)

token_publico = PyJWKClient(KEYCLOAK_CLAVE_PUBLICA)
seguridad_segun_contrato = HTTPBearer(auto_error=False)


def validar_token_keycloak(credenciales: HTTPAuthorizationCredentials | None = Depends(seguridad_segun_contrato),) -> dict:
    if credenciales is None or not credenciales.credentials:
        logger.warning("Solicitud sin token Bearer en Authorization.")
        raise NoAutenticado(detail="Falta token de acceso Bearer.")  # 401

    token = credenciales.credentials
    try:
        clave = token_publico.get_signing_key_from_jwt(token)
        verificacion = jwt.decode(
            token,
            clave.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return verificacion

    except jwt.ExpiredSignatureError as e:
        logger.warning("Token JWT expirado.|Tipo: %s|Detalle: %s",type(e).__name__,e)
        raise NoAutenticado(detail="Certificado de acceso expirado.") from e # 401
    except jwt.PyJWTError as e:
        logger.warning("Token JWT inválido o corrupto|Tipo: %s|Detalle %s", type(e).__name__,e)
        raise NoAutenticado(detail="Certificado de acceso inválido o corrupto") from {e}  # 401


def verificar_roles(*roles_permitidos: str):
    permitidos = set(roles_permitidos)
    def dependencia_rol(verificacion: dict = Depends(validar_token_keycloak)) -> dict:
        roles_usuario = set(verificacion.get("realm_access", {}).get("roles", []))
        # Por si algún mapper del realm también inyecta roles en el claim raíz "roles"
        roles_usuario.update(verificacion.get("roles", []))

        if not roles_usuario.intersection(permitidos):
            cliente = verificacion.get("azp") or verificacion.get("client_id") or verificacion.get("sub")
            logger.warning("Acceso denegado (403)|Cliente=%s|Requeridos=%s|Presentes=%s",cliente,list(permitidos),list(roles_usuario),)
            raise SinPermiso()  # 403
        return verificacion
    return dependencia_rol