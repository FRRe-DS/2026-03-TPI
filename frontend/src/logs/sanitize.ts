// RF-4.7: las URLs con coordenadas en el query string nunca se registran ni
// se muestran. Esta función es la única puerta de entrada de rutas al panel
// de logs: devuelve siempre la ruta sin query.
export function rutaSinQuery(ruta: string): string {
  const indice = ruta.indexOf('?')
  return indice === -1 ? ruta : ruta.slice(0, indice)
}
