import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import { IconArrowLeft, IconCheck, IconX, IconArrowRight, IconCode, IconLoader2 } from '@tabler/icons-react';

export const LeccionIndividual = () => {
  const { cursoId, leccionId } = useParams();
  const navigate = useNavigate();
  const { user, setNetworkError, sincronizarEstadoAdaptativo } = useUser();

  const [leccion, setLeccion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [opcionSeleccionada, setOpcionSeleccionada] = useState(null);
  const [evaluando, setEvaluando] = useState(false);
  const [resultado, setResultado] = useState(null); // { aprobado: boolean, calificacion: number, explicacion: string }

  useEffect(() => {
    const cargarLeccion = async () => {
      setLoading(true);
      try {
        const data = await api.getLeccionPorId(leccionId);
        if (data) {
          setLeccion(data);
        } else {
          setLeccion(obtenerLeccionMock(cursoId, leccionId));
        }
      } catch (err) {
        if (err.isNetworkError) setNetworkError(true);
        setLeccion(obtenerLeccionMock(cursoId, leccionId));
      } finally {
        setLoading(false);
      }
    };
    cargarLeccion();
  }, [leccionId, cursoId]);

  const obtenerLeccionMock = (cId, lId) => {
    const cursoMock = mockCursos.find((c) => c.id === cId) || mockCursos[0];
    for (const mod of cursoMock.modulos) {
      const l = mod.lecciones.find((lec) => lec.id === lId);
      if (l) return l;
    }
    return cursoMock.modulos[0].lecciones[0];
  };

  const handleVerificarRespuesta = async () => {
    if (opcionSeleccionada === null) return;
    setEvaluando(true);

    try {
      const res = await api.evaluarModulo({
        usuario_id: user?.id,
        tema_id: leccionId,
        respuestas: [{ ejercicio_id: leccion.ejercicio?.id || 1, opcion_id: opcionSeleccionada }],
        tiempo_resolucion_segundos: 120,
      });

      if (res) {
        const esAprobado = res.promedio >= 80;
        setResultado({
          aprobado: esAprobado,
          calificacion: res.promedio,
          requiereRefuerzo: res.requiere_refuerzo,
          explicacion: leccion.ejercicio?.explicacionRespuesta || 'Procesado por el motor adaptativo de PyGo.',
        });

        if (user?.id) {
          await sincronizarEstadoAdaptativo(user.id);
        }
      }
    } catch (err) {
      if (err.isNetworkError) setNetworkError(true);
      const esCorrecto = opcionSeleccionada === leccion.ejercicio?.respuestaCorrecta;
      setResultado({
        aprobado: esCorrecto,
        calificacion: esCorrecto ? 100 : 50,
        requiereRefuerzo: !esCorrecto,
        explicacion: leccion.ejercicio?.explicacionRespuesta || 'Revisa la sintaxis en Python.',
      });
    } finally {
      setEvaluando(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
          <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
          <p className="text-sm font-medium">Cargando lección y ejercicio práctico...</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <button onClick={() => navigate(`/cursos/${cursoId}`)} className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900">
            <IconArrowLeft className="w-4 h-4" />
            <span>Volver al Curso</span>
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          {/* Columna Izquierda: Teórica */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-5">
            <h2 className="text-2xl font-bold text-slate-900">{leccion.titulo}</h2>
            <p className="text-sm text-slate-600">{leccion.teoria?.introduccion}</p>
            <p className="text-sm text-slate-600">{leccion.teoria?.explicacion}</p>
            {leccion.teoria?.codigoEjemplo && (
              <div className="bg-slate-900 text-sky-300 font-mono text-xs p-4 rounded-xl">
                <pre>{leccion.teoria.codigoEjemplo}</pre>
              </div>
            )}
          </div>

          {/* Columna Derecha: Ejercicio */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-6">
            <h3 className="font-bold text-slate-900 flex items-center gap-2">
              <IconCode className="w-5 h-5 text-sky-500" />
              <span>Ejercicio Práctico</span>
            </h3>

            <p className="text-sm font-semibold text-slate-800">{leccion.ejercicio?.consigna}</p>

            {leccion.ejercicio?.codigo && (
              <div className="bg-slate-900 text-slate-100 p-3.5 rounded-xl font-mono text-xs">
                <pre>{leccion.ejercicio.codigo}</pre>
              </div>
            )}

            <div className="space-y-2.5">
              {leccion.ejercicio?.opciones?.map((opcion, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setOpcionSeleccionada(idx);
                    setResultado(null);
                  }}
                  className={`w-full p-3.5 rounded-xl border text-left text-sm font-medium transition-all ${
                    opcionSeleccionada === idx ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 bg-white'
                  }`}
                >
                  {opcion}
                </button>
              ))}
            </div>

            <button
              onClick={handleVerificarRespuesta}
              disabled={opcionSeleccionada === null || evaluando}
              className="w-full bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-medium py-3 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md"
            >
              <span>{evaluando ? 'Evaluando en Supabase...' : 'Verificar Respuesta'}</span>
            </button>

            {/* Banners de Retroalimentación */}
            {resultado && resultado.aprobado && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-3 text-emerald-800">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <IconCheck className="w-5 h-5 text-emerald-600" />
                  <span>¡Excelente! Respuesta Correcta ({resultado.calificacion}%)</span>
                </div>
                <p className="text-xs">{resultado.explicacion}</p>
                <button
                  onClick={() => navigate(`/cursos/${cursoId}`)}
                  className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-semibold py-2.5 rounded-xl text-xs flex items-center justify-center gap-2 shadow-sm"
                >
                  <span>Siguiente Lección</span>
                  <IconArrowRight className="w-4 h-4" />
                </button>
              </div>
            )}

            {resultado && !resultado.aprobado && (
              <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 space-y-2 text-rose-800">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <IconX className="w-5 h-5 text-rose-600" />
                  <span>Inténtalo de nuevo (Calificación: {resultado.calificacion}%)</span>
                </div>
                <p className="text-xs text-rose-700">
                  {resultado.explicacion || 'Se requieren actividades de refuerzo. Intenta nuevamente sin congelar tus opciones.'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};