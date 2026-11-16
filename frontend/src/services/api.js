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
      const error = new Error(errorData.mensaje || errorData.error || `Error ${response.status}: Solicitud fallida`);
      error.status = response.status;
      error.code = errorData.code;
      throw error;
    }

    // 204 No Content: no hay cuerpo que parsear.
    if (response.status === 204) {
      return null;
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

  // Catálogos académicos (públicos: alimentan los desplegables del registro)
  getCentros: () =>
    request('/centros', {
      method: 'GET',
    }),

  getCarreras: () =>
    request('/carreras', {
      method: 'GET',
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

  // Motor de recomendación
  getAreas: () => request('/motor/areas', { method: 'GET' }),

  getPreguntasColdStart: () => request('/cold-start/preguntas', { method: 'GET' }),

  registrarEvento: (evento) =>
    request('/eventos', { method: 'POST', body: JSON.stringify(evento), keepalive: true }),

  inscribirse: (cursoId, datos = {}) =>
    request(`/cursos/${cursoId}/inscripcion`, { method: 'POST', body: JSON.stringify(datos) }),

  getPerfil: (usuarioId) => request(`/perfil/${usuarioId}`, { method: 'GET' }),

  guardarIntereses: (usuarioId, areas) =>
    request(`/perfil/${usuarioId}/intereses`, { method: 'PUT', body: JSON.stringify({ areas }) }),

  getRecomendaciones: (usuarioId, limite = 3) =>
    request(`/recomendaciones/cursos?usuario_id=${usuarioId}&limite=${limite}`, { method: 'GET' }),

  enviarRetroalimentacion: (datos) =>
    request('/retroalimentacion', { method: 'POST', body: JSON.stringify(datos) }),
};