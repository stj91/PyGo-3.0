import { supabase } from '../config/supabase.js';

export const registro = async (req, res) => {
  try {
    const { email, password, nombre, carrera_area_estudio, centro_universitario } = req.body;

    if (!email || !password || !nombre) {
      return res.status(400).json({ success: false, error: 'Campos obligatorios incompletos.' });
    }

    // 1. Crear usuario en Supabase Auth con confirmación automática
    const { data: authData, error: authError } = await supabase.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
      user_metadata: { nombre }
    });

    if (authError) throw authError;

    const userId = authData.user.id;

    // 2. Insertar en la tabla publica `usuarios` con nivel inicial Principiante
    const { data: usuario, error: dbError } = await supabase
      .from('usuarios')
      .insert([
        {
          id: userId,
          nombre,
          email,
          carrera_area_estudio,
          centro_universitario,
          nivel_asignado: 'Principiante'
        }
      ])
      .select()
      .single();

    if (dbError) throw dbError;

    // 3. Crear registro inicial de preferencias
    const { error: prefError } = await supabase
      .from('usuario_preferencias')
      .insert([{ usuario_id: userId, meta_diaria_minutos: 30, modo_oscuro: false }]);

    if (prefError) console.error('Error inicializando preferencias:', prefError);

    // 4. Iniciar sesión para generar token de sesión
    const { data: sessionData, error: loginError } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (loginError) throw loginError;

    return res.status(201).json({
      success: true,
      token: sessionData.session.access_token,
      usuario
    });
  } catch (error) {
    console.error('❌ ERROR DETALLADO EN REGISTRO:', error);
    return res.status(500).json({ success: false, error: error.message });
  }
};

export const login = async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ success: false, error: 'Email y contraseña requeridos.' });
    }

    // 1. Autenticar en Supabase Auth
    const { data: sessionData, error: authError } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (authError) {
      return res.status(401).json({ success: false, error: 'Credenciales inválidas.' });
    }

    // 2. Obtener perfil completo del usuario
    const { data: usuario, error: profileError } = await supabase
      .from('usuarios')
      .select('*, usuario_preferencias(*)')
      .eq('id', sessionData.user.id)
      .single();

    if (profileError) throw profileError;

    return res.json({
      success: true,
      token: sessionData.session.access_token,
      usuario
    });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
};