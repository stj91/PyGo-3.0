import React, { useEffect, useState } from 'react';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { IconCheck, IconHourglass, IconLock, IconBell, IconCalendar, IconArrowRight, IconSparkles, IconClock, IconLoader2 } from '@tabler/icons-react';

export const Dashboard = () => {
  const { user, setNetworkError } = useUser();
  const [temasUnidad, setTemasUnidad] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cargarDatosDashboard = async () => {
      setLoading(true);
      try {
        const cursos = await api.getCursos(user?.id);
        if (cursos && cursos.length > 0 && cursos[0].modulos?.[0]?.lecciones) {
          setTemasUnidad(cursos[0].modulos[0].lecciones);
        } else {
          setTemasUnidad([
            { id: 1, titulo: 'Sintaxis Básica y Tipos de Datos', estado: 'Completado', duracion: '20 min' },
            { id: 2, titulo: 'Estructuras Condicionales (if / else)', estado: 'En Curso', duracion: '35 min' },
            { id: 3, titulo: 'Bucles e Iteraciones (for / while)', estado: 'Bloqueado', duracion: '45 min' },
            { id: 4, titulo: 'Funciones y Alcance de Variables', estado: 'Bloqueado', duracion: '50 min' }
          ]);
        }
      } catch (err) {
        if (err.isNetworkError) setNetworkError(true);
      } finally {
        setLoading(false);
      }
    };

    cargarDatosDashboard();
  }, [user?.id]);

  const getStatusBadge = (estado) => {
    switch (estado) {
      case 'Completado':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <IconCheck className="w-3.5 h-3.5" /> Completado
          </span>
        );
      case 'En Curso':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <IconHourglass className="w-3.5 h-3.5" /> En Curso
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-400 border border-slate-200">
            <IconLock className="w-3.5 h-3.5" /> Bloqueado
          </span>
        );
    }
  };

  return (
    <Layout>
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
          <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
          <p className="text-sm font-medium">Cargando tablero personalizado...</p>
        </div>
      ) : (
        <div className="space-y-8">
          <div className="bg-slate-900 rounded-2xl p-8 text-white relative overflow-hidden shadow-lg border border-slate-800">
            <div className="relative z-10 max-w-2xl space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 text-sky-400 border border-slate-700 text-xs font-semibold">
                <IconSparkles className="w-4 h-4" />
                <span>Ruta Adaptativa Activa</span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight">
                ¡Hola de nuevo, {user?.nombre ? user.nombre.split(' ')[0] : 'Estudiante'}!
              </h2>
              <p className="text-slate-300 text-sm leading-relaxed">
                Tu ruta está optimizada para el nivel <strong className="text-sky-400">{user?.nivel || 'Principiante'}</strong>. Completa tus ejercicios para mantener tu racha.
              </p>
            </div>
          </div>

          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Progreso Global de la Unidad</h3>
                <p className="text-xs text-slate-500">Fundamentos de Programación en Python</p>
              </div>
              <span className="text-2xl font-extrabold text-slate-900">{user?.progresoGlobal || 35}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-3">
              <div className="bg-sky-500 h-3 rounded-full transition-all duration-500" style={{ width: `${user?.progresoGlobal || 35}%` }}></div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Temas de la Unidad</h3>
              <div className="space-y-3">
                {temasUnidad.map((tema) => (
                  <div key={tema.id} className="bg-white border border-slate-200/80 rounded-2xl p-5 flex items-center justify-between hover:shadow-md transition-all">
                    <div className="space-y-1">
                      <p className="font-semibold text-slate-900 text-sm">{tema.titulo}</p>
                      <span className="flex items-center gap-1 text-xs text-slate-500">
                        <IconClock className="w-3.5 h-3.5" />
                        {tema.duracion || '25 min'}
                      </span>
                    </div>
                    <div>{getStatusBadge(tema.estado)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                  <IconBell className="w-5 h-5 text-sky-500" />
                  <h4 className="font-bold text-slate-900 text-sm">Notificaciones</h4>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/60 space-y-1 text-xs">
                  <p className="font-semibold text-slate-800">Evaluación Activa</p>
                  <p className="text-slate-500">Completa el test de condicionales esta semana.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};