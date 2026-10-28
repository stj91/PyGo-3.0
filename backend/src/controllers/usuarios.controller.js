import { supabase } from '../config/supabase.js';

export const actualizarConfiguracion = async (req, res) => {
  try {
    const { id } = req.params;
    const { carrera_area_estudio, meta_diaria_minutos, modo_oscuro, dificultad_adaptativa } = req.body;

    // Actualizar datos de usuario
    if (carrera_area_estudio) {
      await supabase
        .from('usuarios')
        .update({ carrera_area_estudio })
        .eq('id', id);
    }

    // Actualizar preferencias
    const prefData = {};
    if (meta_diaria_minutos !== undefined) prefData.meta_diaria_minutos = meta_diaria_minutos;
    if (modo_oscuro !== undefined) prefData.modo_oscuro = modo_oscuro;
    if (dificultad_adaptativa !== undefined) prefData.dificultad_adaptativa = dificultad_adaptativa;

    if (Object.keys(prefData).length > 0) {
      await supabase
        .from('usuario_preferencias')
        .upsert({ usuario_id: id, ...prefData });
    }

    return res.json({
      success: true,
      mensaje: 'Configuración de usuario actualizada correctamente.'
    });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};