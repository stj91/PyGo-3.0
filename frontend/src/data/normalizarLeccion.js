// Convierte una lección a la forma que usa LeccionIndividual:
//   { id, titulo, teoria: {introduccion, explicacion, codigoEjemplo}, local,
//     ejercicios: [{ id, titulo, consigna, codigo, opciones: [{id, texto}],
//                    respuestaCorrecta?, explicacionRespuesta? }] }
//
// Acepta la respuesta de GET /lecciones/:id ({ success, leccion }) y las
// lecciones de mockCursos.js. `local: true` marca el contenido de ejemplo: sus
// opciones no existen en la base de datos y sólo pueden corregirse en el navegador.
export const normalizarLeccion = (data) => {
  if (!data) return null;
  if ('success' in data && !data.leccion) return null;
  const raw = data.leccion ?? data;
  if (!raw || typeof raw !== 'object') return null;

  if (raw.teoria || raw.ejercicio) return normalizarMock(raw);

  return {
    id: raw.id,
    titulo: raw.titulo,
    local: false,
    teoria: { introduccion: '', explicacion: raw.descripcion ?? '', codigoEjemplo: '' },
    ejercicios: (raw.ejercicios ?? []).map((ejercicio) => ({
      id: ejercicio.id,
      titulo: ejercicio.titulo,
      consigna: ejercicio.consigna,
      codigo: '',
      opciones: [...(ejercicio.opciones_ejercicios ?? [])]
        .sort((a, b) => (a.orden ?? 0) - (b.orden ?? 0))
        .map((o) => ({ id: o.id, texto: o.texto_opcion })),
    })),
  };
};

const normalizarMock = (raw) => ({
  id: raw.id,
  titulo: raw.titulo,
  local: true,
  teoria: raw.teoria ?? {},
  ejercicios: raw.ejercicio
    ? [
        {
          id: `${raw.id}-ejercicio`,
          titulo: raw.titulo,
          consigna: raw.ejercicio.consigna,
          codigo: raw.ejercicio.codigo,
          opciones: (raw.ejercicio.opciones ?? []).map((texto, idx) => ({ id: idx, texto })),
          respuestaCorrecta: raw.ejercicio.respuestaCorrecta,
          explicacionRespuesta: raw.ejercicio.explicacionRespuesta,
        },
      ]
    : [],
});
