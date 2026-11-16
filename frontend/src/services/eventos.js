// Registro de eventos de aprendizaje desde el navegador (docs/motor/03-eventos-e-inscripcion.md §6).
// Todo es "dispara y olvida": nunca lanza ni hace esperar a la página. Usa api.registrarEvento
// (fetch con keepalive y el token), no navigator.sendBeacon, que no puede enviar Authorization.
// Las interacciones con recomendaciones no pasan por aquí: van a /api/retroalimentacion.

import { api } from './api';

const CLAVE_SESION = 'pygo_sesion_id';
const CLAVE_SESION_INICIADA = 'pygo_sesion_iniciada';

function leerSesion(clave) {
  try {
    return sessionStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardarSesion(clave, valor) {
  try {
    sessionStorage.setItem(clave, valor);
  } catch {
    // Sin sessionStorage (modo privado estricto): se sigue sin persistir.
  }
}

function haySesionDeUsuario() {
  try {
    return Boolean(localStorage.getItem('pygo_token'));
  } catch {
    return false;
  }
}

function sesionId() {
  const existente = leerSesion(CLAVE_SESION);
  if (existente) return existente;
  if (typeof crypto === 'undefined' || typeof crypto.randomUUID !== 'function') return null;
  const nuevo = crypto.randomUUID();
  guardarSesion(CLAVE_SESION, nuevo);
  return nuevo;
}

function entero(valor) {
  const numero = Number(valor);
  return Number.isInteger(numero) && numero > 0 ? numero : undefined;
}

function dispositivo() {
  const ancho = typeof window !== 'undefined' ? window.innerWidth : 0;
  if (ancho && ancho < 768) return 'movil';
  if (ancho && ancho < 1024) return 'tablet';
  return 'escritorio';
}

export function registrar(tipo, extra = {}) {
  try {
    if (!haySesionDeUsuario()) return;
    const id = sesionId();
    const evento = { ...extra, tipo, ...(id ? { sesion_id: id } : {}) };
    Promise.resolve(api.registrarEvento(evento)).catch(() => {});
  } catch {
    // La analítica nunca rompe una página.
  }
}

export function registrarVistaCurso(cursoId, origen, recomendacionId) {
  const id = entero(cursoId);
  if (id === undefined) return;
  const datos = {
    ...(origen ? { origen } : {}),
    ...(recomendacionId ? { recomendacion_id: recomendacionId } : {}),
  };
  registrar('curso_vista', { objeto_id: id, curso_id: id, datos });
}

export function iniciarSesionSiHaceFalta() {
  try {
    if (!haySesionDeUsuario() || leerSesion(CLAVE_SESION_INICIADA)) return;
    guardarSesion(CLAVE_SESION_INICIADA, '1');
    registrar('sesion_inicio', { datos: { dispositivo: dispositivo() } });
  } catch {
    // La analítica nunca rompe una página.
  }
}
