import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import { 
  IconArrowLeft, 
  IconBook, 
  IconCheck, 
  IconX, 
  IconHelpCircle,
  IconChevronRight,
  IconLoader2 
} from '@tabler/icons-react';

export const DetalleCurso = () => {
  const { cursoId } = useParams();
  const navigate = useNavigate();
  const { user } = useUser();

  const [curso, setCurso] = useState(null);
  const [loading, setLoading] = useState(true);
  const [respuestas, setRespuestas] = useState({});
  const [resultados, setResultados] = useState({});

  useEffect(() => {
    const cargarCurso = async () => {
      setLoading(true);
      try {
        // Petición a la API / Supabase
        const response = await api.getCursoById(cursoId, user?.id);
        
        if (response && response.id) {
          setCurso(response);
        } else {
          // Fallback a mockCursos buscando de forma flexible (número o texto)
          const encontrado = mockCursos.find(
            (c) =>
              String(c.id) === String(cursoId) ||
              c.codigo_curso?.toLowerCase() === String(cursoId).toLowerCase() ||
              c.id === 'fundamentos-python' && (cursoId === '1' || cursoId === 'PY-101') ||
              c.id === 'estructuras-control' && (cursoId === '2' || cursoId === 'PY-201') ||
              c.id === 'poo' && (cursoId === '3' || cursoId === 'PY-301')
          );
          setCurso(encontrado || null);
        }
      } catch (err) {
        // Si la API falla, busca en mockCursos estático
        const encontrado = mockCursos.find(
          (c) =>
            String(c.id) === String(cursoId) ||
            c.id === 'fundamentos-python' && (cursoId === '1' || cursoId === 'PY-101') ||
            c.id === 'estructuras-control' && (cursoId === '2' || cursoId === 'PY-201') ||
            c.id === 'poo' && (cursoId === '3' || cursoId === 'PY-301')
        );
        setCurso(encontrado || mockCursos[0]);
      } finally {
        setLoading(false);
      }
    };

    cargarCurso();
  }, [cursoId, user?.id]);

  const seleccionarOpcion = (ejercicioId, opcionIndex) => {
    setRespuestas({ ...respuestas, [ejercicioId]: opcionIndex });
  };

  const verificarRespuesta = (ejercicioId, respuestaCorrecta) => {
    const seleccionada = respuestas[ejercicioId];
    if (seleccionada === undefined) return;

    const esCorrecta = seleccionada === respuestaCorrecta;
    setResultados({ ...resultados, [ejercicioId]: esCorrecta });
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <IconLoader2 className="w-8 h-8 animate-spin text-sky-500 mb-2" />
          <p className="text-sm font-medium">Cargando temario del curso...</p>
        </div>
      </Layout>
    );
  }

  if (!curso) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-center space-y-4">
          <h3 className="text-xl font-bold text-slate-800">No se encontró el curso solicitado</h3>
          <p className="text-sm text-slate-500">El curso con ID "{cursoId}" no está disponible actualmente.</p>
          <button
            onClick={() => navigate('/cursos')}
            className="flex items-center gap-2 bg-slate-800 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-slate-900 transition-all"
          >
            <IconArrowLeft className="w-4 h-4" />
            <span>Volver a Cursos</span>
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6 max-w-4xl mx-auto">
        {/* Encabezado del Curso */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/cursos')}
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors"
          >
            <IconArrowLeft className="w-4 h-4" />
            <span>Volver a Cursos</span>
          </button>
          <span className="px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-xs font-semibold">
            {curso.nivel || 'Principiante'}
          </span>
        </div>

        <div>
          <h2 className="text-2xl font-bold text-slate-900">{curso.titulo}</h2>
          <p className="text-sm text-slate-500 mt-1">{curso.descripcion}</p>
        </div>

        {/* Lista de Módulos y Temas */}
        <div className="space-y-6">
          {(curso.modulos || curso.temas || []).map((modulo, idx) => (
            <div key={modulo.id || idx} className="bg-white border border-slate-200/80 rounded-2xl overflow-hidden shadow-sm">
              <div className="p-5 bg-slate-50/70 border-b border-slate-200/80 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-slate-800 text-sky-400 flex items-center justify-center font-bold">
                    <IconBook className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{modulo.titulo}</h3>
                    <p className="text-xs text-slate-500">{modulo.descripcion || `${modulo.lecciones?.length || 2} lecciones`}</p>
                  </div>
                </div>
              </div>

              {/* Lecciones / Teoría y Ejercicios */}
              <div className="divide-y divide-slate-100 p-6 space-y-6">
                {(modulo.lecciones || [modulo]).map((leccion, lIdx) => (
                  <div key={leccion.id || lIdx} className="space-y-4 pt-2">
                    <h4 className="text-base font-bold text-slate-800 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                      {leccion.titulo || leccion.nombre}
                    </h4>

                    {/* Explicación Teórica Breve */}
                    {leccion.teoria && (
                      <div className="bg-sky-50/50 border border-sky-100 p-4 rounded-xl space-y-2 text-xs text-slate-700 leading-relaxed">
                        <p className="font-semibold text-sky-900">{leccion.teoria.introduccion}</p>
                        <p>{leccion.teoria.explicacion}</p>
                        {leccion.teoria.codigoEjemplo && (
                          <pre className="bg-slate-900 text-emerald-400 p-3 rounded-lg font-mono text-[11px] overflow-x-auto mt-2">
                            {leccion.teoria.codigoEjemplo}
                          </pre>
                        )}
                      </div>
                    )}

                    {/* Ejercicio Práctico de Opción Múltiple */}
                    {leccion.ejercicio && (
                      <div className="bg-white border border-slate-200 p-4 rounded-xl space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
                          <IconHelpCircle className="w-4 h-4 text-sky-600" />
                          <span>Ejercicio Práctico: {leccion.ejercicio.consigna}</span>
                        </div>

                        {leccion.ejercicio.codigo && (
                          <pre className="bg-slate-100 text-slate-800 p-2.5 rounded-lg font-mono text-[11px]">
                            {leccion.ejercicio.codigo}
                          </pre>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                          {leccion.ejercicio.opciones.map((opcion, oIdx) => {
                            const estaSeleccionada = respuestas[leccion.id] === oIdx;
                            return (
                              <button
                                key={oIdx}
                                onClick={() => seleccionarOpcion(leccion.id, oIdx)}
                                className={`p-2.5 rounded-lg text-xs font-medium text-left transition-all border ${
                                  estaSeleccionada
                                    ? 'bg-sky-50 border-sky-500 text-sky-900 font-semibold'
                                    : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700'
                                }`}
                              >
                                {opcion}
                              </button>
                            );
                          })}
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          <button
                            onClick={() => verificarRespuesta(leccion.id, leccion.ejercicio.respuestaCorrecta)}
                            disabled={respuestas[leccion.id] === undefined}
                            className="bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-all"
                          >
                            Verificar Respuesta
                          </button>

                          {resultados[leccion.id] !== undefined && (
                            <span className={`text-xs font-bold flex items-center gap-1 ${
                              resultados[leccion.id] ? 'text-emerald-600' : 'text-rose-600'
                            }`}>
                              {resultados[leccion.id] ? (
                                <>
                                  <IconCheck className="w-4 h-4" /> ¡Correcto!
                                </>
                              ) : (
                                <>
                                  <IconX className="w-4 h-4" /> Inténtalo de nuevo
                                </>
                              )}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
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