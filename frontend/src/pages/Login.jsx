import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { IconCode, IconLock, IconMail, IconArrowRight, IconUserPlus, IconAlertCircle } from '@tabler/icons-react';

export const Login = () => {
  const navigate = useNavigate();
  const { loginUser, setNetworkError } = useUser();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      const res = await api.login({ email: formData.email, password: formData.password });
      if (res.success) {
        loginUser(res.usuario, res.token);
        if (res.usuario.nivel === 'Principiante' && res.usuario.esNuevoUsuario) {
          navigate('/cold-start');
        } else {
          navigate('/dashboard');
        }
      }
    } catch (err) {
      if (err.isNetworkError) {
        setNetworkError(true);
        setErrorMsg('No se pudo conectar con el servidor backend (http://127.0.0.1:5001).');
      } else {
        setErrorMsg(err.message || 'Credenciales incorrectas. Inténtalo de nuevo.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 bg-dot-pattern flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-slate-200/80 rounded-2xl shadow-xl p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-slate-800 text-sky-400 flex items-center justify-center mx-auto shadow-md">
            <IconCode className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Iniciar Sesión</h2>
          <p className="text-sm text-slate-500">Plataforma adaptativa de aprendizaje de Python para universitarios</p>
        </div>

        {errorMsg && (
          <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-rose-700 text-xs font-semibold">
            <IconAlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Correo Institucional o Personal
            </label>
            <div className="relative">
              <IconMail className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="email"
                required
                placeholder="estudiante@alumnos.udg.mx"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Contraseña
            </label>
            <div className="relative">
              <IconLock className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-medium py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md mt-2"
          >
            <span>{loading ? 'Ingresando...' : 'Ingresar a la Plataforma'}</span>
            <IconArrowRight className="w-5 h-5" />
          </button>
        </form>

        <div className="pt-4 border-t border-slate-100 text-center">
          <button
            onClick={() => navigate('/registro')}
            className="text-xs font-semibold text-sky-600 hover:text-sky-700 transition-colors inline-flex items-center gap-1.5"
          >
            <IconUserPlus className="w-4 h-4" />
            <span>¿Eres nuevo estudiante? Regístrate y realiza tu diagnóstico</span>
          </button>
        </div>
      </div>
    </div>
  );
};