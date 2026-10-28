import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  IconLayoutDashboard,
  IconBook,
  IconListCheck,
  IconSettings,
  IconLogout,
  IconCode,
  IconHelpCircle
} from '@tabler/icons-react';

export const Sidebar = () => {
  const navigate = useNavigate();

  const navItems = [
    { label: 'Tablero Principal', path: '/dashboard', icon: IconLayoutDashboard },
    { label: 'Mis Cursos', path: '/cursos', icon: IconBook },
    { label: 'Temario y Módulos', path: '/cursos/1', icon: IconListCheck },
    { label: 'Configuración', path: '/configuracion', icon: IconSettings },
  ];

  const handleLogout = () => {
    localStorage.removeItem('pygo_token');
    localStorage.removeItem('pygo_user');
    navigate('/login');
  };

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col justify-between h-screen fixed left-0 top-0 z-30 border-r border-slate-800">
      <div>
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <div className="w-10 h-10 rounded-xl bg-sky-500 flex items-center justify-center text-slate-900 font-bold shadow-lg shadow-sky-500/20">
            <IconCode className="w-6 h-6 stroke-[2.5]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">PyGo</h1>
            <p className="text-xs text-slate-400 font-medium">Aprende Python Adaptativo</p>
          </div>
        </div>

        <nav className="p-4 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.label}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-colors ${
                    isActive
                      ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-slate-800 space-y-1">
        <button className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors">
          <IconHelpCircle className="w-5 h-5" />
          <span>Ayuda y Soporte</span>
        </button>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium text-rose-400 hover:bg-rose-500/10 transition-colors"
        >
          <IconLogout className="w-5 h-5" />
          <span>Cerrar Sesión</span>
        </button>
      </div>
    </aside>
  );
};