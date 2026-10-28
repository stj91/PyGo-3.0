import React, { useState } from 'react';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { IconSchool, IconClock, IconAdjustmentsHorizontal, IconMoon, IconCheck, IconAlertCircle } from '@tabler/icons-react';

export const Configuracion = () => {
  const { user, updateUser, opcionesVisibles, setNetworkError } = useUser();
  const [formData, setFormData] = useState({
    nombre: user?.nombre || '',
    email: user?.email || '',
    carrera: user?.carrera || '',
    centro: user?.centro || '',
    metaDiariaMinutos: user?.metaDiariaMinutos || 30,
    dificultadAdaptativa: user?.dificultadAdaptativa || 'Normal',
    modoOscuro: user?.modoOscuro || false
  });

  const [toastMsg, setToastMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setToastMsg('');

    try {
      const res = await api.actualizarPerfil(user?.id, formData);
      if (res) {
        updateUser(formData);
        setToastMsg('Cambios guardados con éxito');
        setTimeout(() => setToastMsg(''), 3000);
      }
    } catch (err) {
      if (err.isNetworkError) setNetworkError(true);
      // Fallback local
      updateUser(formData);
      setToastMsg('Cambios guardados con éxito');
      setTimeout(() => setToastMsg(''), 3000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-8">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Configuración del Perfil</h2>
          <p className="text-sm text-slate-500 mt-1">Gestiona tus datos universitarios y preferencias de la plataforma.</p>
        </div>

        {toastMsg && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2 text-emerald-800 font-semibold text-sm shadow-sm transition-all">
            <IconCheck className="w-5 h-5 text-emerald-600" />
            <span>{toastMsg}</span>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-6">
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <IconSchool className="w-5 h-5 text-sky-500" />
              <span>Información Académica</span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Nombre Completo</label>
                <input
                  type="text"
                  value={formData.nombre}
                  onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                  className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Correo Electrónico</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                />
              </div>
            </div>
          </div>

          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <IconClock className="w-5 h-5 text-sky-500" />
              <span>Meta Diaria de Tiempo</span>
            </h3>

            <select
              value={formData.metaDiariaMinutos}
              onChange={(e) => setFormData({ ...formData, metaDiariaMinutos: Number(e.target.value) })}
              className="w-full md:w-64 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
            >
              <option value={15}>15 minutos al día</option>
              <option value={30}>30 minutos al día</option>
              <option value={45}>45 minutos al día</option>
              <option value={60}>60 minutos al día</option>
            </select>
          </div>

          {/* REGLA DE ADAPTABILIDAD STRICTA: Ocultación en el DOM si es Principiante */}
          {user?.nivel !== 'Principiante' && opcionesVisibles?.modo_oscuro_disponible !== false && (
            <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                <IconAdjustmentsHorizontal className="w-5 h-5 text-sky-500" />
                <span>Opciones Avanzadas e Interfaz (Nivel {user?.nivel})</span>
              </h3>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">Ajuste de Dificultad Dinámica</p>
                    <p className="text-xs text-slate-500">Aumenta la complejidad de los retos prácticos.</p>
                  </div>
                  <select
                    value={formData.dificultadAdaptativa}
                    onChange={(e) => setFormData({ ...formData, dificultadAdaptativa: e.target.value })}
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold"
                  >
                    <option value="Normal">Normal</option>
                    <option value="Desafiante">Desafiante</option>
                    <option value="Avanzado">Avanzado</option>
                  </select>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <div className="flex items-center gap-2">
                    <IconMoon className="w-4 h-4 text-slate-600" />
                    <p className="text-sm font-semibold text-slate-800">Modo Oscuro</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formData.modoOscuro}
                    onChange={(e) => setFormData({ ...formData, modoOscuro: e.target.checked })}
                    className="w-5 h-5 accent-sky-500 rounded cursor-pointer"
                  />
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={loading}
              className="bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-medium px-6 py-2.5 rounded-xl text-sm transition-all shadow-md flex items-center gap-2"
            >
              <IconCheck className="w-4 h-4" />
              <span>{loading ? 'Guardando...' : 'Guardar Preferencias'}</span>
            </button>
          </div>
        </form>
      </div>
    </Layout>
  );
};