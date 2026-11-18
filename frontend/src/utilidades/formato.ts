const BYTES_POR_MB = 1024 * 1024;
const BYTES_POR_KB = 1024;

/** dd/mm/aaaa en hora local. */
export function formatearFecha(iso: string): string {
  const fecha = new Date(iso);
  const dia = String(fecha.getDate()).padStart(2, "0");
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  return `${dia}/${mes}/${fecha.getFullYear()}`;
}

export function formatearTamano(bytes: number): string {
  if (bytes >= BYTES_POR_MB) {
    return `${(bytes / BYTES_POR_MB).toFixed(1).replace(".", ",")} MB`;
  }
  return `${Math.max(1, Math.round(bytes / BYTES_POR_KB))} KB`;
}
