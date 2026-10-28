import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import { IconCheck, IconHourglass, IconLock, IconBook, IconArrowLeft, IconPlayerPlay, IconLoader2 } from '@tabler/icons-react';

export const DetalleCurso = () => {
  const { cursoId } = useParams();
  const navigate = useNavigate();
  const { user, setNetworkError } = useUser();
  const [curso, setCurso] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cargarDetalleCurso = async () => {
      setLoading(true);
      try {
        const data = await api.getCursoPorId(cursoId, user?.id);
        setCurso(data || mockCursos.find((c) => c.id === cursoId) || mockCursos[0]);
      } catch (err) {
        if (err.isNetworkError) setNetworkError(true);
        setCurso(mockCursos.find((c) => c.id === cursoId) || mockCursos[0]);
      } finally {
        setLoading(false);
      }
    };
    cargarDetalleCurso();
  }, [cursoId, user?.id]);

  if (loading) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
          <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
          <p className="text-sm font-medium">Cargando detalles del curso...</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-8 max-w-5xl mx-auto">
        <button onClick={() => navigate('/cursos')} className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 transition-colors">
          <IconArrowLeft className="w-4 h-4" />
          <span>Volver al Catálogo de Cursos</span>
        </button>

        <div className="bg-slate-900 text-white rounded-2xl p-8 border border-slate-800 shadow-lg space-y-4">
          <h2 className="text-3xl font-bold">{curso.titulo}</h2>
          <p className="text-slate-300 text-sm leading-relaxed">{curso.descripcion}</p>
        </div>

        <div className="space-y-6">
          {curso.modulos?.map((modulo) => (
            <div key={modulo.id} className="bg-white border border-slate-200/80 rounded-2xl overflow-hidden shadow-sm">
              <div className="p-5 bg-slate-50/60 border-b border-slate-200/80 flex items-center gap-3">
                <IconBook className="w-5 h-5 text-sky-500" />
                <h4 className="font-bold text-slate-900 text-base">{modulo.titulo}</h4>
              </div>
              <div className="divide-y divide-slate-100">
                {modulo.lecciones?.map((leccion) => (
                  <div key={leccion.id} className="p-5 flex items-center justify-between">
                    <span className="font-semibold text-slate-900 text-sm">{leccion.titulo}</span>
                    <button
                      onClick={() => navigate(`/cursos/${curso.id}/lecciones/${leccion.id}`)}
                      className="bg-slate-800 hover:bg-slate-900 text-white text-xs font-medium py-2 px-3.5 rounded-xl flex items-center gap-1.5 shadow-sm"
                    >
                      <span>Estudiar</span>
                      <IconPlayerPlay className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
};