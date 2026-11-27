import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { IconSearch, IconUser, IconShieldCheck, IconMoon, IconSun } from '@tabler/icons-react';

export const Header = () => {
  const { user, temaOscuro, temaDisponible, cambiarTema } = useUser();
  const navigate = useNavigate();
  const [busqueda, setBusqueda] = useState('');

  // La búsqueda se resuelve en el catálogo, que filtra por título y descripción.
  const buscar = (e) => {
    e.preventDefault();
    const texto = busqueda.trim();
    navigate(texto ? `/cursos?q=${encodeURIComponent(texto)}` : '/cursos');
  };

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
      <form onSubmit={buscar} className="relative w-96" role="search">
        <IconSearch className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar cursos"
          placeholder="Buscar cursos..."
          className="w-full pl-11 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all"
        />
      </form>

      {/* Información del Usuario y Nivel */}
      <div className="flex items-center gap-5">
        {/* Badge de Nivel Adaptativo */}
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${getLevelBadgeStyle(user.nivel)}`}>
          <IconShieldCheck className="w-4 h-4" />
          <span>NIVEL: {user.nivel.toUpperCase()}</span>
        </div>

        {temaDisponible && (
          <button
            type="button"
            onClick={() => cambiarTema(!temaOscuro).catch(() => {})}
            aria-label={temaOscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            title={temaOscuro ? 'Modo claro' : 'Modo oscuro'}
            className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors"
          >
            {temaOscuro ? <IconSun className="w-5 h-5" /> : <IconMoon className="w-5 h-5" />}
          </button>
        )}

        {/* Perfil */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
          <div className="w-9 h-9 rounded-xl bg-slate-800 text-white flex items-center justify-center font-semibold text-sm">
            <IconUser className="w-5 h-5" />
          </div>
          <div className="text-left hidden md:block">
            <p className="text-sm font-semibold text-slate-900 leading-tight">{user.nombre}</p>
            <p className="text-xs text-slate-500">{user.carreras?.nombre || user.carrera}</p>
          </div>
        </div>
      </div>
    </header>
  );
};