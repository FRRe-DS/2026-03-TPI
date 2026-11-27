// Campos de conexión en memoria: token JWT y URL base del API.
// Restricción: el token NUNCA se persiste (sin localStorage/sessionStorage);
// al recargar la página hay que pegarlo de nuevo.
import { avisoUrlBase, setConfigApi, useConfigApi } from './apiConfig'

export function ConfigPanel() {
  const { token, urlBase } = useConfigApi()
  const aviso = avisoUrlBase(urlBase)

  return (
    <section className="panel">
      <h2>Conexión</h2>
      <div className="campo">
        <label htmlFor="token">Token JWT (en memoria)</label>
        <input
          id="token"
          type="password"
          autoComplete="off"
          placeholder="Pegar el access_token (contra Prism alcanza cualquier string)"
          value={token}
          onChange={(e) => setConfigApi({ token: e.target.value })}
        />
        <p className="nota">
          No se guarda en ningún lado: al recargar la página hay que pegarlo de nuevo. Contra el
          backend real vence a los 5 minutos.
        </p>
      </div>
      <div className="campo">
        <label htmlFor="url-base">URL base del API</label>
        <input
          id="url-base"
          type="text"
          autoComplete="off"
          placeholder="(vacío = proxy de Vite → VITE_PROXY_TARGET)"
          value={urlBase}
          onChange={(e) => setConfigApi({ urlBase: e.target.value })}
          aria-invalid={aviso !== null}
        />
        {aviso !== null && (
          <p className="aviso" role="alert">
            {aviso}
          </p>
        )}
        <p className="nota">
          Vacío usa el proxy de Vite (Prism, <code>http://localhost:4010</code>, por defecto).
          Backend real: <code>http://localhost:8000</code>.
        </p>
      </div>
    </section>
  )
}
