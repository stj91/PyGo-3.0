import { supabase } from '../config/supabase.js';

export const evaluarModulo = async (req, res) => {
  try {
    const { usuario_id, tema_id, respuestas = [], tiempo_resolucion_segundos = 0 } = req.body;

    if (!usuario_id || !tema_id || respuestas.length === 0) {
      return res.status(400).json({ success: false, error: 'Faltan parámetros requeridos para la evaluación.' });
    }

    const opcionesIds = respuestas.map(r => r.opcion_id);

    // Consulta de las opciones correctas
    const { data: opcionesCorrectas, error: opError } = await supabase
      .from('opciones_ejercicios')
      .select('id, ejercicio_id, es_correcta, retroalimentacion')
      .in('id', opcionesIds);

    if (opError) throw opError;

    let aciertos = 0;
    const retroalimentacion = [];

    respuestas.forEach(r => {
      const match = opcionesCorrectas.find(op => op.id === r.opcion_id);
      const esCorrecta = match ? match.es_correcta : false;
      if (esCorrecta) aciertos++;

      retroalimentacion.push({
        ejercicio_id: r.ejercicio_id,
        opcion_id: r.opcion_id,
        es_correcta: esCorrecta,
        retroalimentacion: match?.retroalimentacion || (esCorrecta ? '¡Correcto!' : 'Respuesta incorrecta.')
      });
    });

    const calificacion = Math.round((aciertos / respuestas.length) * 100);
    const requiereRefuerzo = calificacion < 70;
    const aprobado = calificacion >= 80;

    // Registrar intento en intentos_ejercicios
    await supabase.from('intentos_ejercicios').insert({
      usuario_id,
      tema_id,
      puntaje_obtenido: calificacion,
      tiempo_resolucion_segundos,
      requiere_refuerzo
    });

    // Lógica Adaptativa
    if (requiereRefuerzo) {
      // Marcar estado de refuerzo
      await supabase
        .from('usuario_temas')
        .upsert({ usuario_id, tema_id, estado: 'actividades_de_refuerzo' });
    } else if (aprobado) {
      // 1. Marcar tema como completado
      await supabase
        .from('usuario_temas')
        .upsert({ usuario_id, tema_id, estado: 'completado' });

      // 2. Desbloquear el siguiente tema en el orden
      const { data: temaActual } = await supabase.from('temas').select('orden, curso_id').eq('id', tema_id).single();

      if (temaActual) {
        const { data: siguienteTema } = await supabase
          .from('temas')
          .select('id')
          .eq('curso_id', temaActual.curso_id)
          .eq('orden', temaActual.orden + 1)
          .single();

        if (siguienteTema) {
          await supabase
            .from('usuario_temas')
            .upsert({ usuario_id, tema_id: siguienteTema.id, estado: 'desbloqueado' });
        }
      }

      // 3. Recalcular avance del curso
      await recalcularAvanceCurso(usuario_id, temaActual?.curso_id);
    }

    return res.json({
      calificacion,
      aprobado,
      requiere_refuerzo: requiereRefuerzo,
      retroalimentacion
    });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};

// Función auxiliar para recalcular el porcentaje global de avance
async function recalcularAvanceCurso(usuario_id, curso_id) {
  if (!curso_id) return;

  const { data: temasCurso } = await supabase.from('temas').select('id').eq('curso_id', curso_id);
  if (!temasCurso || temasCurso.length === 0) return;

  const temaIds = temasCurso.map(t => t.id);

  const { data: temasCompletados } = await supabase
    .from('usuario_temas')
    .select('id')
    .eq('usuario_id', usuario_id)
    .eq('estado', 'completado')
    .in('tema_id', temaIds);

  const porcentaje = Math.round(((temasCompletados?.length || 0) / temasCurso.length) * 100);

  await supabase
    .from('usuario_cursos')
    .upsert({ usuario_id, curso_id, porcentaje_avance_global: porcentaje });
}