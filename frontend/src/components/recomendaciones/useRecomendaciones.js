import { useCallback, useEffect, useState } from 'react';
import { useUser } from '../../context/UserContext';
import { api } from '../../services/api';

const OCULTO = { estado: 'oculto', recomendaciones: [], continuar: [] };
const CARGANDO = { estado: 'cargando', recomendaciones: [], continuar: [] };

const listo = (respuesta) => ({
  estado: 'listo',
  recomendaciones: respuesta.recomendaciones,
  continuar: Array.isArray(respuesta.continuar) ? respuesta.continuar : [],
});

/**
 * Recomendaciones del usuario actual, pedidas una vez por montaje.
 * Cualquier fallo del endpoint deja el estado en 'oculto': la sección no se muestra.
 * El orden es el recibido; el backend se encarga de que la lista sea estable.
 */
export const useRecomendaciones = (limite = 3) => {
  const { user } = useUser();
  const usuarioId = user?.id;
  const [datos, setDatos] = useState(() => (usuarioId ? CARGANDO : OCULTO));

  useEffect(() => {
    if (!usuarioId) {
      setDatos(OCULTO);
      return undefined;
    }

    let vigente = true;
    setDatos(CARGANDO);
    api
      .getRecomendaciones(usuarioId, limite)
      .then((respuesta) => {
        if (!vigente) return;
        setDatos(respuesta && Array.isArray(respuesta.recomendaciones) ? listo(respuesta) : OCULTO);
      })
      .catch(() => {
        if (vigente) setDatos(OCULTO);
      });

    return () => {
      vigente = false;
    };
  }, [usuarioId, limite]);

  const quitar = useCallback((recomendacionId) => {
    setDatos((previo) => ({
      ...previo,
      recomendaciones: previo.recomendaciones.filter((r) => r.recomendacion_id !== recomendacionId),
    }));
  }, []);

  return { ...datos, quitar };
};
