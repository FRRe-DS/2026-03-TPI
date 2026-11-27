// Etapa 1b: cliente HTTP con problem+json, panel de logs y panel de salud.
// Las pantallas de negocio (mapa, estado, cercanos, reservas, ruta y
// geocodificación) se agregan en las etapas siguientes.
import { ConfigPanel } from './config/ConfigPanel'
import { HealthPanel } from './ui/HealthPanel'
import { RequestLogPanel } from './ui/RequestLogPanel'

export default function App() {
  return (
    <main className="app">
      <header>
        <h1>Simulador M4 — Ubicación y Disponibilidad</h1>
        <p className="etapa">Etapa 1b: cliente HTTP, panel de logs y panel de salud.</p>
      </header>
      <ConfigPanel />
      <HealthPanel />
      <RequestLogPanel />
    </main>
  )
}
