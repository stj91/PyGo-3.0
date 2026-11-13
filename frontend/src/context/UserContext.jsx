import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const UserContext = createContext();

// El nivel nunca se guarda en el navegador: la única fuente es la base de datos
// (usuarios.nivel_asignado), que llega en el login y en /api/adaptativo/estado.
const sinNivel = (datos) => {
  if (!datos) return datos;
  const { nivel: _nivel, nivel_asignado: _nivelAsignado, ...resto } = datos;
  return resto;
};

const guardarSesion = (datos) => localStorage.setItem('pygo_user', JSON.stringify(sinNivel(datos)));

export const UserProvider = ({ children }) => {
  const [usuario, setUsuario] = useState(() => {
    const savedUser = localStorage.getItem('pygo_user');
    return savedUser ? sinNivel(JSON.parse(savedUser)) : null;
  });

  const [nivel, setNivel] = useState(null);
  const [nivelCargando, setNivelCargando] = useState(() => Boolean(usuario?.id));

  const [token, setToken] = useState(() => localStorage.getItem('pygo_token') || null);
  const [opcionesVisibles, setOpcionesVisibles] = useState({
    modo_oscuro_disponible: false,
    ajuste_dificultad_disponible: false,
    certificaciones_disponibles: false,
  });
  const [networkError, setNetworkError] = useState(false);

  // Al recargar la página (F5) el nivel se vuelve a pedir al backend.
  useEffect(() => {
    if (usuario?.id) {
      sincronizarEstadoAdaptativo(usuario.id);
    }
  }, []);

  const sincronizarEstadoAdaptativo = async (usuarioId) => {
    setNivelCargando(true);
    try {
      setNetworkError(false);
      const { configuracion } = (await api.getEstadoAdaptativo(usuarioId)) || {};
      if (configuracion) {
        setNivel(configuracion.nivel_activo || null);
        setOpcionesVisibles({
          modo_oscuro_disponible: Boolean(configuracion.modo_oscuro_disponible),
          ajuste_dificultad_disponible: Boolean(configuracion.ajuste_dificultad_disponible),
          certificaciones_disponibles: Boolean(configuracion.certificaciones_disponibles),
        });
      }
    } catch (err) {
      if (err.isNetworkError) {
        setNetworkError(true);
      }
    } finally {
      setNivelCargando(false);
    }
  };

  const loginUser = (userData, userToken) => {
    setUsuario(sinNivel(userData));
    setNivel(userData?.nivel_asignado || null);
    setToken(userToken);
    guardarSesion(userData);
    localStorage.setItem('pygo_token', userToken);
    if (userData?.id) {
      sincronizarEstadoAdaptativo(userData.id);
    }
  };

  const logoutUser = () => {
    setUsuario(null);
    setNivel(null);
    setToken(null);
    localStorage.removeItem('pygo_user');
    localStorage.removeItem('pygo_token');
  };

  const updateUser = (data) => {
    setUsuario((prev) => {
      const updated = { ...prev, ...sinNivel(data) };
      guardarSesion(updated);
      return updated;
    });
  };

  // `user.nivel` siempre es un texto: el Header llama a toUpperCase() sin comprobarlo.
  const user = usuario ? { ...usuario, nivel: nivel || 'Principiante' } : null;

  return (
    <UserContext.Provider
      value={{
        user,
        token,
        nivelCargando,
        opcionesVisibles,
        networkError,
        setNetworkError,
        loginUser,
        logoutUser,
        updateUser,
        sincronizarEstadoAdaptativo,
      }}
    >
      {children}
    </UserContext.Provider>
  );
};

export const useUser = () => useContext(UserContext);
