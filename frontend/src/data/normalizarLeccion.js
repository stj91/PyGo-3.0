// Convierte la respuesta de GET /lecciones/:id ({ success, leccion }) a la forma
// que usa LeccionIndividual:
//   { id, titulo, teoria: {introduccion, explicacion, codigoEjemplo},
//     ejercicios: [{ id, titulo, consigna, codigo, opciones: [{id, texto}] }] }
export const normalizarLeccion = (data) => {
  if (!data) return null;
  if ('success' in data && !data.leccion) return null;
  const raw = data.leccion ?? data;
  if (!raw || typeof raw !== 'object') return null;

  return {
    id: raw.id,
    titulo: raw.titulo,
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
