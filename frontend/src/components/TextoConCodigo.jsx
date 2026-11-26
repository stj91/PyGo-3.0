import React from 'react';

// Contenido de los cursos con dos marcas (migración 0010):
//   `código`               -> código dentro de la frase
//   ```python … ```        -> bloque de código de varias líneas
// Todo se construye como elementos de React, nunca como HTML: el texto que
// llega de la base de datos no se interpreta.

const BLOQUE = /```[\w-]*\n?([\s\S]*?)```/g;
const EN_LINEA = /`([^`\n]+)`/g;

const CLASE_EN_LINEA = 'font-mono text-[0.9em] bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded-md';
const CLASE_BLOQUE = 'bg-slate-900 text-slate-100 font-mono font-normal text-xs p-3.5 rounded-xl overflow-x-auto my-2';

/** Divide un texto en trozos `{ tipo: 'texto' | 'bloque', valor }`. Pura. */
export const trozosDeBloques = (texto) => {
  const fuente = String(texto ?? '');
  const trozos = [];
  let ultimo = 0;
  for (const coincidencia of fuente.matchAll(BLOQUE)) {
    trozos.push({ tipo: 'texto', valor: fuente.slice(ultimo, coincidencia.index) });
    trozos.push({ tipo: 'bloque', valor: coincidencia[1].replace(/\n$/, '') });
    ultimo = coincidencia.index + coincidencia[0].length;
  }
  trozos.push({ tipo: 'texto', valor: fuente.slice(ultimo) });
  return trozos.filter((t) => t.tipo === 'bloque' || t.valor.trim() !== '');
};

const ConCodigoEnLinea = ({ texto }) => {
  const partes = texto.split(EN_LINEA);
  // split con un grupo intercala: [texto, código, texto, código, …]
  return partes.map((parte, i) =>
    i % 2 === 1 ? (
      <code key={i} className={CLASE_EN_LINEA}>
        {parte}
      </code>
    ) : (
      <React.Fragment key={i}>{parte}</React.Fragment>
    )
  );
};

/**
 * Muestra un texto del curso con su código formateado.
 * `enLinea`: para usar dentro de un <p>, un botón o una lista; un bloque se
 * muestra entonces como código en línea, porque un <pre> no cabe ahí.
 */
export const TextoConCodigo = ({ texto, enLinea = false, className = '' }) => {
  if (!texto) return null;

  if (enLinea) {
    const plano = trozosDeBloques(texto)
      .map((t) => (t.tipo === 'bloque' ? `\`${t.valor.replace(/\s*\n\s*/g, ' ')}\`` : t.valor))
      .join(' ');
    return (
      <span className={className}>
        <ConCodigoEnLinea texto={plano} />
      </span>
    );
  }

  return (
    <div className={className}>
      {trozosDeBloques(texto).map((trozo, i) =>
        trozo.tipo === 'bloque' ? (
          <pre key={i} className={CLASE_BLOQUE}>
            <code>{trozo.valor}</code>
          </pre>
        ) : (
          <p key={i} className="whitespace-pre-line">
            <ConCodigoEnLinea texto={trozo.valor.trim()} />
          </p>
        )
      )}
    </div>
  );
};
