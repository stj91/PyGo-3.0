import { supabase } from '../config/supabase.js';

export const getEstadoAdaptativo = async (req, res) => {
  try {
    const { usuario_id } = req.params;

    const { data: usuario, error } = await supabase
      .from('usuarios')
      .select('nivel_asignado')
      .eq('id', usuario_id)
      .single();

    if (error || !usuario) {
      return res.status(404).json({ success: false, error: 'Usuario no encontrado.' });
    }

    const nivel = usuario.nivel_asignado || 'Principiante';

    // Reglas adaptativas de visibilidad en UI
    const configuracionUI = {
      nivel_activo: nivel,
      modo_oscuro_disponible: nivel !== 'Principiante',
      ajuste_dificultad_disponible: nivel !== 'Principiante',
      certificaciones_disponibles: nivel === 'Avanzado'
    };

    return res.json({
      success: true,
      configuracion: configuracionUI
    });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};