import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const UserContext = createContext();

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('pygo_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });

  const [token, setToken] = useState(() => localStorage.getItem('pygo_token') || null);
  const [opcionesVisibles, setOpcionesVisibles] = useState({
    modo_oscuro_disponible: false,
    ajuste_dificultad_disponible: false,
    certificaciones_disponibles: false,
  });
  const [networkError, setNetworkError] = useState(false);

  // Sincronización automática de sesión al recargar la página (F5)
  useEffect(() => {
    if (user?.id) {
      sincronizarEstadoAdaptativo(user.id);
    }
  }, []);

  const sincronizarEstadoAdaptativo = async (usuarioId) => {
    try {
      setNetworkError(false);
      const res = await api.getEstadoAdaptativo(usuarioId);
      if (res) {
        setUser((prev) => {
          const updated = {
            ...prev,
            nivel: res.nivel_asignado || prev?.nivel || 'Principiante',
            progresoGlobal: res.porcentaje_avance_global ?? prev?.progresoGlobal ?? 0,
            requiereRefuerzo: res.requiere_refuerzo ?? false,
          };
          localStorage.setItem('pygo_user', JSON.stringify(updated));
          return updated;
        });

        if (res.opciones_visibles) {
          setOpcionesVisibles(res.opciones_visibles);
        }
      }
    } catch (err) {
      if (err.isNetworkError) {
        setNetworkError(true);
      }
    }
  };

  const loginUser = (userData, userToken) => {
    setUser(userData);
    setToken(userToken);
    localStorage.setItem('pygo_user', JSON.stringify(userData));
    localStorage.setItem('pygo_token', userToken);
    if (userData.id) {
      sincronizarEstadoAdaptativo(userData.id);
    }
  };

  const logoutUser = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('pygo_user');
    localStorage.removeItem('pygo_token');
  };

  const updateUser = (data) => {
    setUser((prev) => {
      const updated = { ...prev, ...data };
      localStorage.setItem('pygo_user', JSON.stringify(updated));
      return updated;
    });
  };

  return (
    <UserContext.Provider
      value={{
        user,
        token,
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