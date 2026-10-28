import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import { 
  IconSearch, 
  IconChevronRight, 
  IconShieldCheck, 
  IconLoader2, 
  IconBook, 
  IconBookOff, 
  IconPlayerPlay 
} from '@tabler/icons-react';

export const CatalogoCursos = () => {
  const navigate = useNavigate();
  const { user, setNetworkError } = useUser();
  
  const [cursos, setCursos] = useState([]);
  const [busqueda, setBusqueda] = useState('');
  const [loading, setLoading] = useState(true);
  const [tabActiva, setTabActiva] = useState('mis-cursos'); // 'mis-cursos' | 'catalogo'

  useEffect(() => {
    const cargarCursos = async () => {
      setLoading(true);
      try {
        const response = await api.getCursos(user?.id);
        
        // Extrae la lista de cursos verificando si viene como { success: true, cursos: [...] } o Array directo
        let listaValida = [];
        if (Array.isArray(response)) {
          listaValida = response;
        } else if (response && Array.isArray(response.cursos)) {
          listaValida = response.cursos;
        } else {
          listaValida = mockCursos;
        }

        setCursos(listaValida);
      } catch (err) {
        if (err?.isNetworkError && setNetworkError) setNetworkError(true);
        setCursos(mockCursos);
      } finally {
        setLoading(false);
      }
    };

    cargarCursos();
  }, [user?.id]);

  // Filtrado de la pestaña "Mis Cursos" (solo cursos con avance > 0 o inscritos)
  const misCursos = Array.isArray(cursos) 
    ? cursos.filter((c) => Number(c.porcentaje_avance_global || 0) > 0 || c.inscrito) 
    : [];

  const cursosMostrados = tabActiva === 'mis-cursos' ? misCursos : (Array.isArray(cursos) ? cursos : []);

  // Filtrado final por la barra de búsqueda
  const cursosFiltrados = cursosMostrados.filter(
    (c) =>
      c.titulo?.toLowerCase().includes(busqueda.toLowerCase()) ||
      c.descripcion?.toLowerCase().includes(busqueda.toLowerCase())
  );

  return (
    <Layout>
      <div className="space-y-6">
        {/* Encabezado y Barra de Búsqueda */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Módulos y Cursos de Python</h2>
            <p className="text-sm text-slate-500 mt-1">
              Administra tus inscripciones y explora nuevas unidades de aprendizaje.
            </p>
          </div>
          <div className="relative w-full md:w-80">
            <IconSearch className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Buscar por título o tema..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              className="w-full pl-11 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 transition-all"
            />
          </div>
        </div>

        {/* Pestañas de Navegación (Mis Cursos vs Catálogo) */}
        <div className="flex items-center space-x-2 border-b border-slate-200 pb-2">
          <button
            onClick={() => setTabActiva('mis-cursos')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              tabActiva === 'mis-cursos'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <IconBook className="w-4 h-4" />
            <span>Mis Cursos</span>
            {misCursos.length > 0 && (
              <span className={`ml-1.5 px-2 py-0.5 rounded-full text-xs ${
                tabActiva === 'mis-cursos' ? 'bg-sky-700 text-white' : 'bg-slate-200 text-slate-700'
              }`}>
                {misCursos.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setTabActiva('catalogo')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              tabActiva === 'catalogo'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <span>Catálogo de Cursos</span>
          </button>
        </div>

        {/* Estado de Carga */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
            <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
            <p className="text-sm font-medium">Cargando información de cursos...</p>
          </div>
        ) : (
          <>
            {/* ESTADO VACÍO (Empty State) para "Mis Cursos" */}
            {tabActiva === 'mis-cursos' && misCursos.length === 0 ? (
              <div className="bg-white border border-slate-200/80 rounded-2xl p-8 text-center space-y-5 max-w-md mx-auto my-6 shadow-sm">
                <div className="w-16 h-16 bg-sky-50 text-sky-600 rounded-full flex items-center justify-center mx-auto">
                  <IconBookOff className="w-8 h-8" />
                </div>
                <div className="space-y-2">
                  <span className="px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-xs font-semibold tracking-wide uppercase">
                    NIVEL ASIGNADO: {user?.nivel || 'PRINCIPIANTE'}
                  </span>
                  <h3 className="text-xl font-bold text-slate-900 pt-2">Aún no has iniciado ningún curso</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Comienza tu ruta personalizada según el diagnóstico obtenido para desbloquear las lecciones.
                  </p>
                </div>
                <button
                  onClick={() => setTabActiva('catalogo')}
                  className="w-full bg-sky-600 hover:bg-sky-700 text-white font-medium py-2.5 px-4 rounded-xl shadow-sm transition-all text-sm flex items-center justify-center gap-2"
                >
                  <IconPlayerPlay className="w-4 h-4" />
                  <span>Comenzar primer curso</span>
                </button>
              </div>
            ) : (
              /* GRID DE CURSOS */
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {cursosFiltrados.map((curso) => {
                  const tieneAvance = Number(curso.porcentaje_avance_global || 0) > 0;

                  return (
                    <div
                      key={curso.id}
                      className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all flex flex-col justify-between space-y-4"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-xs font-semibold flex items-center gap-1">
                            <IconShieldCheck className="w-3.5 h-3.5" />
                            {curso.nivel || 'Principiante'}
                          </span>
                          {tieneAvance && (
                            <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                              {curso.porcentaje_avance_global}% Avance
                            </span>
                          )}
                        </div>
                        <h3 className="text-lg font-bold text-slate-900">{curso.titulo}</h3>
                        <p className="text-xs text-slate-500 line-clamp-3 leading-relaxed">
                          {curso.descripcion}
                        </p>
                      </div>

                      <button
                        onClick={() => navigate(`/cursos/${curso.id}`)}
                        className={`w-full rounded-xl py-2.5 px-4 text-sm font-medium flex items-center justify-center gap-2 transition-all shadow-sm ${
                          tieneAvance
                            ? 'bg-amber-500 hover:bg-amber-600 text-white'
                            : 'bg-slate-800 hover:bg-slate-900 text-white'
                        }`}
                      >
                        <span>{tieneAvance ? 'Continuar Lección' : 'Ver Temario / Iniciar'}</span>
                        <IconChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
};