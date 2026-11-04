const BASE_URL = 'http://127.0.0.1:5001/api';

/**
 * Función auxiliar para realizar peticiones HTTP con manejo de token y errores de red
 */
async function request(endpoint, options = {}) {
  const token = localStorage.getItem('pygo_token');

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.mensaje || errorData.error || `Error ${response.status}: Solicitud fallida`);
    }

    return await response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      // Error de conexión física / Servidor caído
      const customError = new Error('ERROR_CONEXION_RED');
      customError.isNetworkError = true;
      throw customError;
    }
    throw error;
  }
}

export const api = {
  // Autenticación
  login: (credenciales) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credenciales),
    }),

  registro: (datosUsuario) =>
    request('/auth/registro', {
      method: 'POST',
      body: JSON.stringify(datosUsuario),
    }),

  // Cold Start / Diagnóstico
  evaluarColdStart: (datosColdStart) =>
    request('/cold-start/evaluar', {
      method: 'POST',
      body: JSON.stringify(datosColdStart),
    }),

  // Cursos y Temario
  getCursos: (usuarioId) =>
    request(`/cursos${usuarioId ? `?usuario_id=${usuarioId}` : ''}`, {
      method: 'GET',
    }),

  getCursoPorId: (id, usuarioId) =>
    request(`/cursos/${id}${usuarioId ? `?usuario_id=${usuarioId}` : ''}`, {
      method: 'GET',
    }),

  getLeccionPorId: (id) =>
    request(`/lecciones/${id}`, {
      method: 'GET',
    }),

  // Evaluaciones y Motor Adaptativo
  evaluarModulo: (datosEvaluacion) =>
    request('/evaluaciones/evaluar-modulo', {
      method: 'POST',
      body: JSON.stringify(datosEvaluacion),
    }),

  getEstadoAdaptativo: (usuarioId) =>
    request(`/adaptativo/estado/${usuarioId}`, {
      method: 'GET',
    }),

  // Perfil de Usuario
  actualizarPerfil: (usuarioId, datosPerfil) =>
    request(`/usuarios/configuracion/${usuarioId}`, {
      method: 'PUT',
      body: JSON.stringify(datosPerfil),
    }),
};