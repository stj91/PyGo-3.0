import { supabase } from '../config/supabase.js';

export const evaluarColdStart = async (req, res) => {
  try {
    const { usuario_id, familiaridad, respuestas_tecnicas = [], objetivo, disponibilidad } = req.body;

    if (!usuario_id) {
      return res.status(400).json({ success: false, error: 'usuario_id es requerido.' });
    }

    let nivelAsignado = 'Principiante';
    let aciertos = 0;

    // Evaluacion según lógica Cold Start
    if (familiaridad === 'No sé nada' || respuestas_tecnicas.length === 0) {
      nivelAsignado = 'Principiante';
    } else {
      const opcionesIds = respuestas_tecnicas.map(r => r.opcion_id);

      // Consultar opciones correctas
      const { data: opcionesCorrectas, error: opError } = await supabase
        .from('opciones_ejercicios')
        .select('id')
        .in('id', opcionesIds)
        .eq('es_correcta', true);

      if (opError) throw opError;

      aciertos = opcionesCorrectas ? opcionesCorrectas.length : 0;

      if (aciertos <= 1) {
        nivelAsignado = 'Principiante';
      } else if (aciertos <= 3) {
        nivelAsignado = 'Intermedio';
      } else {
        nivelAsignado = 'Avanzado';
      }
    }

    // Actualizar usuario
    const { error: userUpdateError } = await supabase
      .from('usuarios')
      .update({
        nivel_asignado: nivelAsignado,
        objetivo_aprendizaje: objetivo || null
      })
      .eq('id', usuario_id);

    if (userUpdateError) throw userUpdateError;

    // Actualizar disponibilidad si se envió
    if (disponibilidad) {
      await supabase
        .from('usuario_preferencias')
        .upsert({ usuario_id, meta_diaria_minutos: parseInt(disponibilidad) || 30 });
    }

    return res.json({
      success: true,
      nivel_asignado: nivelAsignado,
      aciertos
    });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};