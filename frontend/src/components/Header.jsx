import React from 'react';
import { useUser } from '../context/UserContext';
import { IconSearch, IconBell, IconUser, IconShieldCheck } from '@tabler/icons-react';

export const Header = () => {
  const { user } = useUser();

  const getLevelBadgeStyle = (nivel) => {
    switch (nivel) {
      case 'Avanzado':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Intermedio':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      default:
        return 'bg-sky-50 text-sky-700 border-sky-200';
    }
  };

  return (
    <header className="h-20 bg-white border-b border-slate-200/80 px-8 flex items-center justify-between sticky top-0 z-20 shadow-sm">
      {/* Buscador */}
      <div className="relative w-96">
        <IconSearch className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Buscar temas, funciones, ejercicios..."
          className="w-full pl-11 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all"
        />
      </div>

      {/* Información del Usuario y Nivel */}
      <div className="flex items-center gap-5">
        {/* Badge de Nivel Adaptativo */}
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${getLevelBadgeStyle(user.nivel)}`}>
          <IconShieldCheck className="w-4 h-4" />
          <span>NIVEL: {user.nivel.toUpperCase()}</span>
        </div>

        {/* Notificaciones */}
        <button className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors relative">
          <IconBell className="w-5 h-5" />
          <span className="w-2 h-2 bg-sky-500 rounded-full absolute top-2 right-2 ring-2 ring-white"></span>
        </button>

        {/* Perfil */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
          <div className="w-9 h-9 rounded-xl bg-slate-800 text-white flex items-center justify-center font-semibold text-sm">
            <IconUser className="w-5 h-5" />
          </div>
          <div className="text-left hidden md:block">
            <p className="text-sm font-semibold text-slate-900 leading-tight">{user.nombre}</p>
            <p className="text-xs text-slate-500">{user.carrera}</p>
          </div>
        </div>
      </div>
    </header>
  );
};