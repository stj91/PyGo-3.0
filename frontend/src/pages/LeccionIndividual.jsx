import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import { normalizarLeccion } from '../data/normalizarLeccion';
import { explicacionPlegadaInicial } from '../adaptacion/presentacionLeccion';
import {
  IconArrowLeft,
  IconCheck,
  IconX,
  IconArrowRight,
  IconCode,
  IconLoader2,
  IconChevronDown,
} from '@tabler/icons-react';

export const LeccionIndividual = () => {
  const { cursoId, leccionId } = useParams();
  const navigate = useNavigate();
  const { user, nivelCargando, setNetworkError, sincronizarEstadoAdaptativo } = useUser();

  const [leccion, setLeccion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [respuestas, setRespuestas] = useState({}); // { [ejercicioId]: opcionId }
  const [errorEnvio, setErrorEnvio] = useState('');
  const inicioLeccion = useRef(Date.now());
  const [evaluando, setEvaluando] = useState(false);
  const [resultado, setResultado] = useState(null); // { aprobado, calificacion, porEjercicio: {[id]: {es_correcta, retroalimentacion}}, local }
  const [explicacionAbierta, setExplicacionAbierta] = useState(true);

  useEffect(() => {
    setExplicacionAbierta(!explicacionPlegadaInicial(user?.nivel));
  }, [leccionId, user?.nivel]);

  useEffect(() => {
    const cargarLeccion = async () => {
      setLoading(true);
      setRespuestas({});
      setResultado(null);
      setErrorEnvio('');
      try {
        const data = normalizarLeccion(await api.getLeccionPorId(leccionId));
        if (data) {
          setLeccion(data);
        } else {
          setLeccion(obtenerLeccionMock(cursoId, leccionId));
        }
      } catch (err) {
        if (err.isNetworkError) setNetworkError(true);
        setLeccion(obtenerLeccionMock(cursoId, leccionId));
      } finally {
        inicioLeccion.current = Date.now();
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

  const ejercicios = leccion?.ejercicios ?? [];
  const todasRespondidas = ejercicios.length > 0 && ejercicios.every((e) => respuestas[e.id] !== undefined);

  const elegirOpcion = (ejercicioId, opcionId) => {
    setRespuestas((prev) => ({ ...prev, [ejercicioId]: opcionId }));
    setResultado(null);
    setErrorEnvio('');
  };

  // Contenido de ejemplo (sin conexión): sus opciones no existen en la base de
  // datos, así que se corrige aquí y no se guarda nada.
  const corregirLocal = () => {
    const porEjercicio = Object.fromEntries(
      ejercicios.map((e) => {
        const esCorrecta = respuestas[e.id] === e.respuestaCorrecta;
        return [e.id, { es_correcta: esCorrecta, retroalimentacion: esCorrecta ? '¡Correcto!' : 'Respuesta incorrecta.' }];
      })
    );
    const aciertos = Object.values(porEjercicio).filter((r) => r.es_correcta).length;
    const calificacion = Math.round((aciertos / ejercicios.length) * 100);
    setResultado({ aprobado: calificacion >= 80, calificacion, porEjercicio, local: true });
  };

  const handleVerificarRespuesta = async () => {
    if (!todasRespondidas) return;
    setErrorEnvio('');

    if (leccion.local) {
      corregirLocal();
      return;
    }
    if (!user?.id) {
      setErrorEnvio('Inicia sesión para que se corrija y se guarde tu progreso.');
      return;
    }

    setEvaluando(true);
    try {
      const res = await api.evaluarModulo({
        usuario_id: user.id,
        tema_id: leccion.id,
        respuestas: ejercicios.map((e) => ({ ejercicio_id: e.id, opcion_id: respuestas[e.id] })),
        tiempo_resolucion_segundos: Math.round((Date.now() - inicioLeccion.current) / 1000),
      });

      const porEjercicio = Object.fromEntries(
        (res.retroalimentacion ?? []).map((r) => [r.ejercicio_id, r])
      );
      setResultado({ aprobado: Boolean(res.aprobado), calificacion: res.calificacion, porEjercicio, local: false });

      await sincronizarEstadoAdaptativo(user.id);
    } catch (err) {
      if (err.isNetworkError) {
        setNetworkError(true);
        setErrorEnvio('No se pudo enviar tu respuesta. Revisa tu conexión e inténtalo de nuevo.');
      } else {
        setErrorEnvio(err.message || 'No se pudo corregir tu respuesta.');
      }
    } finally {
      setEvaluando(false);
    }
  };

  if (loading || nivelCargando) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
          <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
          <p className="text-sm font-medium">Cargando lección y ejercicio práctico...</p>
        </div>
      </Layout>
    );
  }

  const contenidoTeoria = (
    <>
      <p className="text-sm text-slate-600">{leccion.teoria?.introduccion}</p>
      <p className="text-sm text-slate-600">{leccion.teoria?.explicacion}</p>
      {leccion.teoria?.codigoEjemplo && (
        <div className="bg-slate-900 text-sky-300 font-mono text-xs p-4 rounded-xl">
          <pre>{leccion.teoria.codigoEjemplo}</pre>
        </div>
      )}
    </>
  );

  const tarjetaExplicacion = (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-5">
      <button
        type="button"
        onClick={() => setExplicacionAbierta((v) => !v)}
        aria-expanded={explicacionAbierta}
        aria-controls="leccion-explicacion"
        className="w-full flex items-center justify-between gap-3 text-left"
      >
        <h2 className="text-2xl font-bold text-slate-900">{leccion.titulo}</h2>
        <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 shrink-0">
          {explicacionAbierta ? 'Ocultar explicación' : 'Ver explicación'}
          <IconChevronDown className={`w-4 h-4 transition-transform ${explicacionAbierta ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {explicacionAbierta && (
        <div id="leccion-explicacion" className="space-y-5">
          {contenidoTeoria}
        </div>
      )}
    </div>
  );

  return (
    <Layout>
      <div className="space-y-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <button onClick={() => navigate(`/cursos/${cursoId}`)} className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900">
            <IconArrowLeft className="w-4 h-4" />
            <span>Volver al Curso</span>
          </button>
        </div>

        <div className="max-w-3xl mx-auto space-y-6">
          {tarjetaExplicacion}

          {/* Columna Ejercicio */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-6">
            <h3 className="font-bold text-slate-900 flex items-center gap-2">
              <IconCode className="w-5 h-5 text-sky-500" />
              <span>Ejercicio Práctico</span>
            </h3>

            {ejercicios.length === 0 && (
              <p className="text-sm text-slate-500">Esta lección todavía no tiene ejercicios.</p>
            )}

            {ejercicios.map((ejercicio, eIdx) => {
              const corregido = resultado?.porEjercicio?.[ejercicio.id];
              return (
                <div key={ejercicio.id} className="space-y-3">
                  {ejercicios.length > 1 && (
                    <p className="text-xs font-semibold text-slate-400 uppercase">
                      Ejercicio {eIdx + 1} de {ejercicios.length}
                    </p>
                  )}
                  <p className="text-sm font-semibold text-slate-800">{ejercicio.consigna}</p>

                  {ejercicio.codigo && (
                    <div className="bg-slate-900 text-slate-100 p-3.5 rounded-xl font-mono text-xs">
                      <pre>{ejercicio.codigo}</pre>
                    </div>
                  )}

                  <div className="space-y-2.5">
                    {ejercicio.opciones.map((opcion) => {
                      const elegida = respuestas[ejercicio.id] === opcion.id;
                      return (
                        <button
                          key={opcion.id}
                          type="button"
                          onClick={() => elegirOpcion(ejercicio.id, opcion.id)}
                          aria-pressed={elegida}
                          className={`w-full p-3.5 rounded-xl border text-left text-sm font-medium transition-all ${
                            elegida ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 bg-white'
                          }`}
                        >
                          {opcion.texto}
                        </button>
                      );
                    })}
                  </div>

                  {corregido && (
                    <p className={`text-xs font-bold flex items-center gap-1 ${corregido.es_correcta ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {corregido.es_correcta ? <IconCheck className="w-4 h-4" /> : <IconX className="w-4 h-4" />}
                      <span>{corregido.retroalimentacion}</span>
                    </p>
                  )}
                </div>
              );
            })}

            <button
              onClick={handleVerificarRespuesta}
              disabled={!todasRespondidas || evaluando}
              className="w-full bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-medium py-3 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md"
            >
              <span>{evaluando ? 'Corrigiendo...' : ejercicios.length > 1 ? 'Verificar respuestas' : 'Verificar respuesta'}</span>
            </button>

            {errorEnvio && (
              <p className="text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3">{errorEnvio}</p>
            )}

            {resultado && resultado.aprobado && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-3 text-emerald-800">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <IconCheck className="w-5 h-5 text-emerald-600" />
                  <span>¡Excelente! Calificación: {resultado.calificacion}%</span>
                </div>
                {resultado.local && <p className="text-xs">Contenido de ejemplo: el resultado no se guarda.</p>}
                <button
                  onClick={() => navigate(`/cursos/${cursoId}`)}
                  className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-semibold py-2.5 rounded-xl text-xs flex items-center justify-center gap-2 shadow-sm"
                >
                  <span>Volver al temario</span>
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
                  {resultado.local
                    ? 'Contenido de ejemplo: el resultado no se guarda.'
                    : 'Necesitas 80 % para aprobar. Relee la explicación y vuelve a intentarlo.'}
                </p>
              </div>
            )}
          </div>

        </div>
      </div>
    </Layout>
  );
};