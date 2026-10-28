import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import { IconSearch, IconChevronRight, IconShieldCheck, IconLoader2 } from '@tabler/icons-react';

export const CatalogoCursos = () => {
  const navigate = useNavigate();
  const { user, setNetworkError } = useUser();
  const [cursos, setCursos] = useState([]);
  const [busqueda, setBusqueda] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cargarCursos = async () => {
      setLoading(true);
      try {
        const data = await api.getCursos(user?.id);
        setCursos(data && data.length > 0 ? data : mockCursos);
      } catch (err) {
        if (err.isNetworkError) setNetworkError(true);
        setCursos(mockCursos);
      } finally {
        setLoading(false);
      }
    };
    cargarCursos();
  }, [user?.id]);

  const cursosFiltrados = cursos.filter(
    (c) =>
      c.titulo?.toLowerCase().includes(busqueda.toLowerCase()) ||
      c.descripcion?.toLowerCase().includes(busqueda.toLowerCase())
  );

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Cursos de Python</h2>
            <p className="text-sm text-slate-500 mt-1">Explora los módulos estructurados y continúa tu ruta.</p>
          </div>
          <div className="relative w-full md:w-80">
            <IconSearch className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Buscar curso por título..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              className="w-full pl-11 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
            <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
            <p className="text-sm font-medium">Cargando catálogo de cursos...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cursosFiltrados.map((curso) => (
              <div key={curso.id} className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-xs font-semibold flex items-center gap-1">
                      <IconShieldCheck className="w-3.5 h-3.5" />
                      {curso.nivel}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">{curso.titulo}</h3>
                  <p className="text-xs text-slate-500">{curso.descripcion}</p>
                </div>

                <button
                  onClick={() => navigate(`/cursos/${curso.id}`)}
                  className="w-full bg-slate-800 hover:bg-slate-900 text-white rounded-xl py-2.5 px-4 text-sm font-medium flex items-center justify-center gap-2 transition-all shadow-sm"
                >
                  <span>Ver Temario / Continuar</span>
                  <IconChevronRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};