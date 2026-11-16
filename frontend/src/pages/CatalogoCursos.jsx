import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { useRecomendaciones } from '../components/recomendaciones/useRecomendaciones';
import { ListaRecomendaciones } from '../components/recomendaciones/SeccionRecomendaciones';
import {
  IconSearch,
  IconChevronRight,
  IconShieldCheck,
  IconLoader2,
  IconBook,
  IconBookOff,
  IconPlayerPlay,
  IconSparkles,
  IconGauge
} from '@tabler/icons-react';

// La dificultad solo se muestra si el curso la trae (columna de la migración 0005).
const dificultadValida = (valor) => {
  if (valor === null || valor === undefined || valor === '') return null;
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : null;
};

// Inscrito según el backend (`inscrito`, aunque el avance sea 0) o con avance.
const esInscrito = (curso) => Boolean(curso.inscrito) || Number(curso.porcentaje_avance_global || 0) > 0;

export const CatalogoCursos = () => {
  const navigate = useNavigate();
  const { user, setNetworkError } = useUser();
  const datosRecomendaciones = useRecomendaciones(8);
  const { recomendaciones } = datosRecomendaciones;

  // Recomendación por id de curso; sin respuesta del motor queda vacío y no se marca nada.
  const recomendacionPorCurso = new Map(recomendaciones.map((r) => [String(r.curso_id), r]));

  const [cursos, setCursos] = useState([]);
  const [searchParams] = useSearchParams();
  const consulta = searchParams.get('q') || '';
  const [busqueda, setBusqueda] = useState(consulta);
  const [loading, setLoading] = useState(true);
  const [tabActiva, setTabActiva] = useState('mis-cursos'); // 'mis-cursos' | 'catalogo'
  const [errorCarga, setErrorCarga] = useState('');
  const [recarga, setRecarga] = useState(0);

  // Búsqueda desde la cabecera (?q=): se busca en todo el catálogo.
  useEffect(() => {
    if (!consulta) return;
    setBusqueda(consulta);
    setTabActiva('catalogo');
  }, [consulta]);

  useEffect(() => {
    const cargarCursos = async () => {
      setLoading(true);
      setErrorCarga('');
      try {
        const response = await api.getCursos(user?.id);
        
        // Extrae la lista de cursos verificando si viene como { success: true, cursos: [...] } o Array directo
        let listaValida = [];
        if (Array.isArray(response)) {
          listaValida = response;
        } else if (response && Array.isArray(response.cursos)) {
          listaValida = response.cursos;
        }

        setCursos(listaValida);
        // Sin cursos inscritos no hay nada en "Mis Cursos": se abre el catálogo.
        if (consulta || !listaValida.some(esInscrito)) setTabActiva('catalogo');
      } catch (err) {
        if (err?.isNetworkError && setNetworkError) setNetworkError(true);
        setCursos([]);
        setErrorCarga(
          err?.isNetworkError
            ? 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.'
            : err?.message || 'No se pudo cargar el catálogo.'
        );
      } finally {
        setLoading(false);
      }
    };

    cargarCursos();
  }, [user?.id, recarga]);

  const misCursos = Array.isArray(cursos) ? cursos.filter(esInscrito) : [];

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

        <ListaRecomendaciones {...datosRecomendaciones} maxTarjetas={3} mostrarContinuar={false} />

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
        ) : errorCarga ? (
          <div className="bg-white border border-slate-200/80 rounded-2xl p-8 text-center space-y-4 max-w-md mx-auto my-6 shadow-sm">
            <h3 className="text-lg font-bold text-slate-900">No se pudo cargar el catálogo</h3>
            <p className="text-sm text-slate-500">{errorCarga}</p>
            <button
              onClick={() => setRecarga((n) => n + 1)}
              className="border border-slate-300 text-slate-700 px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-slate-50"
            >
              Reintentar
            </button>
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
                  const recomendacion = recomendacionPorCurso.get(String(curso.id));
                  const dificultad = dificultadValida(curso.dificultad);
                  const destino = recomendacion
                    ? `/cursos/${curso.id}?origen=recomendacion&rid=${encodeURIComponent(recomendacion.recomendacion_id)}`
                    : `/cursos/${curso.id}?origen=catalogo`;

                  return (
                    <div
                      key={curso.id}
                      className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all flex flex-col justify-between space-y-4"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {curso.nivel && (
                              <span className="px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-xs font-semibold flex items-center gap-1">
                                <IconShieldCheck className="w-3.5 h-3.5" />
                                {curso.nivel}
                              </span>
                            )}
                            {dificultad !== null && (
                              <span className="px-3 py-1 bg-slate-50 text-slate-600 border border-slate-200 rounded-full text-xs font-semibold flex items-center gap-1">
                                <IconGauge className="w-3.5 h-3.5" />
                                Dificultad {dificultad}/5
                              </span>
                            )}
                            {recomendacion && (
                              <span className="px-3 py-1 bg-sky-600 text-white border border-sky-600 rounded-full text-xs font-semibold flex items-center gap-1">
                                <IconSparkles className="w-3.5 h-3.5" />
                                Recomendado
                              </span>
                            )}
                          </div>
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
                        {recomendacion && (
                          <p className="text-xs text-sky-700 leading-relaxed flex items-start gap-1.5">
                            <IconSparkles className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span>{recomendacion.explicacion}</span>
                          </p>
                        )}
                      </div>

                      <button
                        onClick={() => navigate(destino)}
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