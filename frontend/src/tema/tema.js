// Tema de la interfaz (modo claro / oscuro).
// La preferencia vive en la base de datos (`usuario_preferencias.tema_interfaz`);
// localStorage solo la recuerda en este navegador para pintar la página con el
// tema correcto antes de cargar nada (lo lee el script de index.html).

export const CLAVE_TEMA = 'pygo_tema';
const OSCURO = 'oscuro';

/** Aplica el tema a la página y lo recuerda en este navegador. */
export const aplicarTema = (oscuro) => {
  document.documentElement.classList.toggle('dark', Boolean(oscuro));
  try {
    localStorage.setItem(CLAVE_TEMA, oscuro ? OSCURO : 'claro');
  } catch {
    // Sin localStorage el tema dura hasta recargar.
  }
};

export const temaActualEsOscuro = () => document.documentElement.classList.contains('dark');

/** `true`/`false` según las preferencias del perfil, o `null` si no las trae. */
export const oscuroDesdePerfil = (usuario) => {
  const prefs = Array.isArray(usuario?.usuario_preferencias)
    ? usuario.usuario_preferencias[0]
    : usuario?.usuario_preferencias;
  if (!prefs?.tema_interfaz) return null;
  return prefs.tema_interfaz === 'modo_oscuro';
};

/** Mismo criterio que Configuración: el modo oscuro se desbloquea desde Intermedio. */
export const modoOscuroDisponible = (user, opcionesVisibles) =>
  Boolean(user) && user.nivel !== 'Principiante' && opcionesVisibles?.modo_oscuro_disponible !== false;
