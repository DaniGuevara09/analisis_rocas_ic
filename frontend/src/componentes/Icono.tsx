/** Iconos de trazo (24×24, color del texto). Las rutas SVG son geometría, no estilos. */
const RUTAS = {
  cursor: ["M4 4l7.07 17 2.51-7.39L21 11.07z"],
  lapiz: ["M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z", "M15 5l4 4"],
  pincel: [
    "M15 4V2",
    "M15 16v-2",
    "M8 9h2",
    "M20 9h2",
    "M17.8 11.8L19 13",
    "M15 9h.01",
    "M17.8 6.2L19 5",
    "M3 21l9-9",
    "M12.2 6.2L11 5",
  ],
  tijeras: [
    "M9 6a3 3 0 1 1-6 0a3 3 0 1 1 6 0",
    "M9 18a3 3 0 1 1-6 0a3 3 0 1 1 6 0",
    "M20 4L8.12 15.88",
    "M14.47 14.48L20 20",
    "M8.12 8.12L12 12",
  ],
  unir: ["M8 6l4-4 4 4", "M12 2v10.3a4 4 0 0 1-1.17 2.87L4 22", "M20 22l-5-5"],
  papelera: [
    "M3 6h18",
    "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6",
    "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
    "M10 11v6",
    "M14 11v6",
  ],
  deshacer: ["M9 14L4 9l5-5", "M4 9h10.5a5.5 5.5 0 0 1 0 11H11"],
  rehacer: ["M15 14l5-5-5-5", "M20 9H9.5a5.5 5.5 0 0 0 0 11H13"],
  acercar: ["M18 11a7 7 0 1 1-14 0a7 7 0 1 1 14 0", "M21 21l-4.3-4.3", "M8 11h6", "M11 8v6"],
  alejar: ["M18 11a7 7 0 1 1-14 0a7 7 0 1 1 14 0", "M21 21l-4.3-4.3", "M8 11h6"],
  ajustar: ["M8 3H5a2 2 0 0 0-2 2v3", "M21 8V5a2 2 0 0 0-2-2h-3", "M3 16v3a2 2 0 0 0 2 2h3", "M16 21h3a2 2 0 0 0 2-2v-3"],
  mas: ["M12 5v14", "M5 12h14"],
  anterior: ["M19 12H5", "M11 18l-6-6 6-6"],
  siguiente: ["M5 12h14", "M13 6l6 6-6 6"],
  descargar: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M7 10l5 5 5-5", "M12 15V3"],
  subir: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M17 8l-5-5-5 5", "M12 3v12"],
  hecho: ["M20 6L9 17l-5-5"],
  info: ["M22 12a10 10 0 1 1-20 0a10 10 0 1 1 20 0", "M12 16v-4", "M12 8h.01"],
  ajustes: [
    "M12 15a3 3 0 1 0 0-6a3 3 0 0 0 0 6z",
    "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
  ],
} as const;

export type NombreIcono = keyof typeof RUTAS;

export function Icono({ nombre }: { nombre: NombreIcono }) {
  return (
    <svg
      className="icono"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {RUTAS[nombre].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
