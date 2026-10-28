import { supabase } from '../config/supabase.js';

export const getCursos = async (req, res) => {
  try {
    const { usuario_id } = req.query;

    const { data: cursos, error: cursosError } = await supabase
      .from('cursos')
      .select('*')
      .order('id', { ascending: true });

    if (cursosError) throw cursosError;

    if (usuario_id) {
      const { data: avances } = await supabase
        .from('usuario_cursos')
        .select('curso_id, porcentaje_avance_global')
        .eq('usuario_id', usuario_id);

      const cursosConAvance = cursos.map(curso => {
        const avance = avances?.find(a => a.curso_id === curso.id);
        return {
          ...curso,
          porcentaje_avance_global: avance ? avance.porcentaje_avance_global : 0
        };
      });

      return res.json({ success: true, cursos: cursosConAvance });
    }

    return res.json({ success: true, cursos });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};

export const getCursoPorId = async (req, res) => {
  try {
    const { id } = req.params;

    const { data: curso, error: cursoError } = await supabase
      .from('cursos')
      .select(`
        *,
        temas (
          id,
          titulo,
          orden,
          bloqueado,
          lecciones (
            id,
            titulo,
            orden
          )
        )
      `)
      .eq('id', id)
      .single();

    if (cursoError) throw cursoError;

    return res.json({ success: true, curso });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};

export const getLeccionPorId = async (req, res) => {
  try {
    const { id } = req.params;

    // Obtener consigna teórica y sus ejercicios
    const { data: leccion, error: leccionError } = await supabase
      .from('lecciones')
      .select(`
        id,
        titulo,
        contenido_teorico,
        tema_id,
        ejercicios (
          id,
          enunciado,
          codigo_base,
          opciones_ejercicios (
            id,
            texto_opcion
          )
        )
      `)
      .eq('id', id)
      .single();

    if (leccionError) throw leccionError;

    return res.json({ success: true, leccion });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};