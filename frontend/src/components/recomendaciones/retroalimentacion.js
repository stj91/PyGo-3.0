import { api } from '../../services/api';

// Envía la interacción con una recomendación sin esperar la respuesta: un fallo
// (501, red, 4xx/5xx) nunca llega a la interfaz.
export const enviarRetroalimentacion = (datos) => {
  api.enviarRetroalimentacion(datos).catch(() => {});
};

export const MOTIVOS_DESCARTE = [
  { valor: 'ya_lo_conozco', texto: 'Ya lo conozco' },
  { valor: 'no_me_interesa', texto: 'No me interesa' },
  { valor: 'no_es_mi_nivel', texto: 'No es mi nivel' },
  { valor: 'otro', texto: 'Otro motivo' },
];
