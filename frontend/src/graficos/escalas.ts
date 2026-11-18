/** Escalas y marcas de ejes para los gráficos SVG. Funciones puras (solo presentación). */

/** Escala lineal: dominio → rango. */
export function escalaLineal(
  dominio: [number, number],
  rango: [number, number],
): (valor: number) => number {
  const [d0, d1] = dominio;
  const [r0, r1] = rango;
  const ancho = d1 - d0 || 1;
  return (valor) => r0 + ((valor - d0) / ancho) * (r1 - r0);
}

/** Escala logarítmica en base 10 (el dominio debe ser > 0). */
export function escalaLog(
  dominio: [number, number],
  rango: [number, number],
): (valor: number) => number {
  const lineal = escalaLineal([Math.log10(dominio[0]), Math.log10(dominio[1])], rango);
  return (valor) => lineal(Math.log10(valor));
}

/** Dominio logarítmico redondeado a décadas: [10^floor, 10^ceil]. */
export function dominioLog(minimo: number, maximo: number): [number, number] {
  const inferior = 10 ** Math.floor(Math.log10(minimo));
  let superior = 10 ** Math.ceil(Math.log10(maximo));
  if (superior <= inferior) {
    superior = inferior * 10;
  }
  return [inferior, superior];
}

/** Marcas 1-2-5 por década dentro del dominio logarítmico. */
export function marcasLog(dominio: [number, number]): number[] {
  const marcas: number[] = [];
  for (let decada = dominio[0]; decada <= dominio[1]; decada *= 10) {
    for (const multiplo of [1, 2, 5]) {
      const valor = decada * multiplo;
      if (valor >= dominio[0] && valor <= dominio[1]) {
        marcas.push(Number(valor.toPrecision(6)));
      }
    }
  }
  return marcas;
}

/** Marcas "redondas" (1, 2, 2.5, 5 × 10^k) para un eje lineal desde 0. */
export function marcasLineales(maximo: number, cantidad = 5): number[] {
  if (maximo <= 0) {
    return [0];
  }
  const bruto = maximo / cantidad;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? bruto;
  const marcas: number[] = [];
  for (let valor = 0; valor <= maximo + paso * 1e-9; valor += paso) {
    marcas.push(Number(valor.toPrecision(6)));
  }
  if (marcas[marcas.length - 1] < maximo) {
    marcas.push(Number((marcas[marcas.length - 1] + paso).toPrecision(6)));
  }
  return marcas;
}

/** Índice del punto cuyo x está más cerca del valor dado (lista ordenada o no). */
export function indiceMasCercano(valores: number[], objetivo: number): number {
  let mejor = 0;
  valores.forEach((valor, i) => {
    if (Math.abs(valor - objetivo) < Math.abs(valores[mejor] - objetivo)) {
      mejor = i;
    }
  });
  return mejor;
}
