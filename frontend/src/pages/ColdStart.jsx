import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { TextoConCodigo } from '../components/TextoConCodigo';
import { IconCheck, IconArrowRight, IconArrowLeft, IconCode, IconShieldCheck, IconAlertCircle, IconLoader2, IconRefresh } from '@tabler/icons-react';

const FAMILIARIDAD_NULA = 'No sé nada';

const OPCIONES_FAMILIARIDAD = [
  { title: FAMILIARIDAD_NULA, desc: 'Nunca he escrito una línea de código en Python' },
  { title: 'Apenas inicio', desc: 'Conozco variables y operaciones aritméticas básicas' },
  { title: 'Conozco estructuras condicionales', desc: 'Manejo if/else, bucles for/while y listas' },
  { title: 'Domino POO', desc: 'Escribo clases, métodos y módulos avanzados' },
];

const OPCIONES_OBJETIVO = [
  'Aprobar materia universitaria de programación',
  'Automatizar tareas o procesos cotidianos',
  'Análisis de datos y Ciencia de Datos',
  'Curiosidad personal y desarrollo profesional',
];

// Textos exactos: el backend (cold_start.metas_estudio) calcula las metas comparando con ellos.
const OPCIONES_DISPONIBILIDAD = [
  '5 a 10 minutos al día (Sesiones micro)',
  'Un par de horas a la semana',
  'Fines de semana exclusivamente',
  '1 hora diaria estructurada',
];

const CARGANDO = { estado: 'cargando', datos: [], error: '' };

const Consigna = ({ texto }) => (
  <TextoConCodigo texto={texto} className="space-y-4 text-lg font-bold text-slate-900" />
);

const Cargando = ({ texto }) => (
  <div className="flex flex-col items-center justify-center gap-3 py-10 text-slate-500">
    <IconLoader2 className="w-8 h-8 animate-spin text-sky-500" />
    <span className="text-sm">{texto}</span>
  </div>
);

const ErrorConReintento = ({ mensaje, onReintentar, deshabilitado = false }) => (
  <div className="p-4 rounded-xl border border-rose-200 bg-rose-50 text-rose-700 flex items-start gap-3">
    <IconAlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
    <div className="flex-1 space-y-3">
      <p className="text-sm">{mensaje}</p>
      <button
        onClick={onReintentar}
        disabled={deshabilitado}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-rose-200 text-sm font-medium hover:bg-rose-100 disabled:opacity-50"
      >
        <IconRefresh className="w-4 h-4" />
        <span>Reintentar</span>
      </button>
    </div>
  </div>
);

const BotonOpcion = ({ seleccionado, onClick, children }) => (
  <button
    onClick={onClick}
    className={`p-4 rounded-xl border text-left text-sm font-semibold transition-all flex items-center justify-between ${
      seleccionado ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 hover:border-slate-300 bg-white text-slate-700'
    }`}
  >
    {children}
    {seleccionado && <IconCheck className="w-5 h-5 text-sky-500" />}
  </button>
);

export const ColdStart = () => {
  const navigate = useNavigate();
  const { user, sincronizarEstadoAdaptativo, setNetworkError } = useUser();

  const [paso, setPaso] = useState(0);
  const [familiaridad, setFamiliaridad] = useState('');
  const [respuestasTecnicas, setRespuestasTecnicas] = useState({}); // {[ejercicio_id]: opcion_id}
  const [objetivo, setObjetivo] = useState('');
  const [intereses, setIntereses] = useState([]);
  const [disponibilidad, setDisponibilidad] = useState('');

  const [preguntas, setPreguntas] = useState(CARGANDO);
  const [areas, setAreas] = useState(CARGANDO);

  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState('');
  const [resultado, setResultado] = useState(null); // { nivel_asignado, aciertos, total }

  const cargarPreguntas = useCallback(async () => {
    setPreguntas(CARGANDO);
    try {
      const res = await api.getPreguntasColdStart();
      const lista = res?.preguntas ?? [];
      if (!lista.length) {
        setPreguntas({ estado: 'error', datos: [], error: 'No hay preguntas de diagnóstico disponibles.' });
        return;
      }
      setPreguntas({ estado: 'ok', datos: lista, error: '' });
    } catch (err) {
      if (err.isNetworkError) setNetworkError(true);
      setPreguntas({ estado: 'error', datos: [], error: 'No se pudieron cargar las preguntas del diagnóstico.' });
    }
  }, [setNetworkError]);

  const cargarAreas = useCallback(async () => {
    setAreas(CARGANDO);
    try {
      const res = await api.getAreas();
      setAreas({ estado: 'ok', datos: res?.areas ?? [], error: '' });
    } catch (err) {
      if (err.isNetworkError) setNetworkError(true);
      setAreas({ estado: 'error', datos: [], error: 'No se pudieron cargar las áreas de interés.' });
    }
  }, [setNetworkError]);

  useEffect(() => {
    cargarPreguntas();
    cargarAreas();
  }, [cargarPreguntas, cargarAreas]);

  const sinPrueba = familiaridad === FAMILIARIDAD_NULA;

  // Si las preguntas aún no están, un único paso de espera ocupa su lugar.
  const pasos = useMemo(() => {
    const pasosPreguntas = sinPrueba
      ? []
      : preguntas.estado === 'ok'
        ? preguntas.datos.map((p, indice) => ({ tipo: 'pregunta', pregunta: p, indice }))
        : [{ tipo: 'preguntas_pendientes' }];
    return [
      { tipo: 'familiaridad' },
      ...pasosPreguntas,
      { tipo: 'objetivo' },
      { tipo: 'intereses' },
      { tipo: 'disponibilidad' },
      { tipo: 'resultado' },
    ];
  }, [sinPrueba, preguntas]);

  const totalSteps = pasos.length;
  const actual = pasos[Math.min(paso, totalSteps - 1)];
  const totalPreguntas = preguntas.datos.length;
  const progressPercent = Math.round(((paso + 1) / totalSteps) * 100);

  const handleAnswerSelect = (ejercicioId, opcionId) => {
    setRespuestasTecnicas({ ...respuestasTecnicas, [ejercicioId]: opcionId });
  };

  const alternarInteres = (clave) => {
    setIntereses((prev) => (prev.includes(clave) ? prev.filter((c) => c !== clave) : [...prev, clave]));
  };

  const handleEnviarColdStart = async () => {
    setEnviando(true);
    setErrorEnvio('');
    const respuestasArray = sinPrueba
      ? []
      : preguntas.datos
          .filter((p) => respuestasTecnicas[p.id] !== undefined)
          .map((p) => ({ ejercicio_id: p.id, opcion_id: respuestasTecnicas[p.id] }));

    try {
      const res = await api.evaluarColdStart({
        usuario_id: user?.id,
        familiaridad,
        respuestas_tecnicas: respuestasArray,
        objetivo,
        disponibilidad,
        intereses,
      });
      if (!res?.success || !res.nivel_asignado) {
        throw new Error('No se pudo calcular tu nivel.');
      }
      setResultado({ nivel_asignado: res.nivel_asignado, aciertos: res.aciertos, total: res.total });
      if (user?.id) {
        await sincronizarEstadoAdaptativo(user.id);
      }
      setPaso((prev) => prev + 1);
    } catch (err) {
      if (err.isNetworkError) {
        setNetworkError(true);
        setErrorEnvio('No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.');
      } else {
        setErrorEnvio(err.message || 'No se pudo calcular tu nivel.');
      }
    } finally {
      setEnviando(false);
    }
  };

  const handleNext = () => {
    if (actual.tipo === 'disponibilidad') {
      handleEnviarColdStart();
      return;
    }
    setPaso((prev) => prev + 1);
  };

  const handlePrev = () => {
    setErrorEnvio('');
    setPaso((prev) => Math.max(prev - 1, 0));
  };

  const siguienteDeshabilitado =
    enviando ||
    (actual.tipo === 'familiaridad' && !familiaridad) ||
    actual.tipo === 'preguntas_pendientes' ||
    (actual.tipo === 'pregunta' && respuestasTecnicas[actual.pregunta.id] === undefined) ||
    (actual.tipo === 'objetivo' && !objetivo) ||
    (actual.tipo === 'intereses' && areas.estado !== 'ok') ||
    (actual.tipo === 'disponibilidad' && !disponibilidad);

  return (
    <div className="min-h-screen bg-slate-50 bg-dot-pattern flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-2xl bg-white border border-slate-200/80 rounded-2xl shadow-xl overflow-hidden">
        <div className="p-6 bg-slate-900 text-white">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <IconCode className="w-5 h-5 text-sky-400" />
              <span className="text-sm font-semibold text-slate-300">Diagnóstico de Entrada PyGo</span>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 bg-slate-800 text-sky-400 rounded-full border border-slate-700">
              Paso {paso + 1} de {totalSteps}
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2">
            <div className="bg-sky-500 h-2 rounded-full transition-all duration-300" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>

        <div className="p-8">
          {actual.tipo === 'familiaridad' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿Cuál es tu nivel actual de experiencia con Python?</h3>
                <p className="text-sm text-slate-500 mt-1">Esto ayuda a calibrar la dificultad inicial del material.</p>
              </div>
              <div className="grid gap-3">
                {OPCIONES_FAMILIARIDAD.map((item) => (
                  <BotonOpcion key={item.title} seleccionado={familiaridad === item.title} onClick={() => setFamiliaridad(item.title)}>
                    <div>
                      <p className="font-semibold text-sm">{item.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5 font-normal">{item.desc}</p>
                    </div>
                  </BotonOpcion>
                ))}
              </div>
            </div>
          )}

          {actual.tipo === 'preguntas_pendientes' && (
            <div className="space-y-6">
              {preguntas.estado === 'error' ? (
                <ErrorConReintento mensaje={preguntas.error} onReintentar={cargarPreguntas} />
              ) : (
                <Cargando texto="Cargando las preguntas del diagnóstico..." />
              )}
            </div>
          )}

          {actual.tipo === 'pregunta' && (
            <div className="space-y-6">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-sky-600 uppercase tracking-wider">
                  Evaluación Técnica • Ejercicio {actual.indice + 1} de {totalPreguntas}
                </span>
                <Consigna texto={actual.pregunta.consigna} />
              </div>
              <div className="grid gap-3">
                {(actual.pregunta.opciones ?? []).map((opcion) => (
                  <BotonOpcion
                    key={opcion.id}
                    seleccionado={respuestasTecnicas[actual.pregunta.id] === opcion.id}
                    onClick={() => handleAnswerSelect(actual.pregunta.id, opcion.id)}
                  >
                    <TextoConCodigo texto={opcion.texto_opcion} enLinea className="font-medium" />
                  </BotonOpcion>
                ))}
              </div>
            </div>
          )}

          {actual.tipo === 'objetivo' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿Cuál es tu objetivo principal con este curso?</h3>
                <p className="text-sm text-slate-500 mt-1">Adaptaremos las recomendaciones de proyectos según tu meta.</p>
              </div>
              <div className="grid gap-3">
                {OPCIONES_OBJETIVO.map((item) => (
                  <BotonOpcion key={item} seleccionado={objetivo === item} onClick={() => setObjetivo(item)}>
                    <span>{item}</span>
                  </BotonOpcion>
                ))}
              </div>
            </div>
          )}

          {actual.tipo === 'intereses' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿Qué te interesa?</h3>
                <p className="text-sm text-slate-500 mt-1">Elige las áreas que quieras (opcional). Las usaremos para recomendarte cursos.</p>
              </div>
              {areas.estado === 'cargando' && <Cargando texto="Cargando áreas..." />}
              {areas.estado === 'error' && <ErrorConReintento mensaje={areas.error} onReintentar={cargarAreas} />}
              {areas.estado === 'ok' && (
                <div className="flex flex-wrap gap-2">
                  {areas.datos.map((area) => {
                    const activa = intereses.includes(area.clave);
                    return (
                      <button
                        key={area.clave}
                        onClick={() => alternarInteres(area.clave)}
                        aria-pressed={activa}
                        className={`px-4 py-2 rounded-full border text-sm font-medium transition-all flex items-center gap-1.5 ${
                          activa ? 'border-sky-500 bg-sky-50 text-sky-700 ring-2 ring-sky-500/20' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        {activa && <IconCheck className="w-4 h-4" />}
                        <span>{area.nombre}</span>
                      </button>
                    );
                  })}
                  <button
                    onClick={() => setIntereses([])}
                    aria-pressed={intereses.length === 0}
                    className={`px-4 py-2 rounded-full border text-sm font-medium transition-all ${
                      intereses.length === 0 ? 'border-slate-500 bg-slate-100 text-slate-800' : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
                    }`}
                  >
                    Ninguna en particular
                  </button>
                </div>
              )}
            </div>
          )}

          {actual.tipo === 'disponibilidad' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿De cuánto tiempo dispones para estudiar?</h3>
                <p className="text-sm text-slate-500 mt-1">Ajustaremos la longitud diaria de tus sesiones.</p>
              </div>
              <div className="grid gap-3">
                {OPCIONES_DISPONIBILIDAD.map((item) => (
                  <BotonOpcion key={item} seleccionado={disponibilidad === item} onClick={() => setDisponibilidad(item)}>
                    <span>{item}</span>
                  </BotonOpcion>
                ))}
              </div>
              {enviando && <Cargando texto="Calculando tu nivel..." />}
              {errorEnvio && !enviando && (
                <ErrorConReintento mensaje={errorEnvio} onReintentar={handleEnviarColdStart} />
              )}
            </div>
          )}

          {actual.tipo === 'resultado' && resultado && (
            <div className="text-center space-y-6 py-4">
              <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-sm">
                <IconShieldCheck className="w-10 h-10" />
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-bold text-slate-900">¡Diagnóstico Completado!</h3>
                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  El motor adaptativo de PyGo ha procesado tus datos y ha determinado tu nivel de entrada.
                </p>
              </div>

              <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-6 text-left max-w-md mx-auto space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase">Nivel Asignado:</span>
                  <span className="px-3 py-1 bg-sky-500 text-slate-900 font-bold text-xs rounded-full">
                    {resultado.nivel_asignado.toUpperCase()}
                  </span>
                </div>
                {resultado.total > 0 && (
                  <div className="flex items-center justify-between text-xs text-slate-600 border-t border-slate-200 pt-2">
                    <span>Aciertos en la prueba técnica:</span>
                    <span className="font-semibold text-slate-800">{resultado.aciertos} de {resultado.total}</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-xs text-slate-600 border-t border-slate-200 pt-2">
                  <span>Objetivo principal:</span>
                  <span className="font-semibold text-slate-800">{objetivo}</span>
                </div>
              </div>

              <button
                onClick={() => navigate('/dashboard')}
                className="w-full max-w-md bg-slate-800 hover:bg-slate-900 text-white font-medium py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md mx-auto"
              >
                <span>Ir al Tablero Principal</span>
                <IconArrowRight className="w-5 h-5" />
              </button>
            </div>
          )}

          {actual.tipo !== 'resultado' && (
            <div className="flex items-center justify-between pt-6 mt-6 border-t border-slate-100">
              <button
                onClick={handlePrev}
                disabled={paso === 0 || enviando}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  paso === 0 ? 'text-slate-300 cursor-not-allowed' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <IconArrowLeft className="w-4 h-4" />
                <span>Anterior</span>
              </button>

              <button
                onClick={handleNext}
                disabled={siguienteDeshabilitado}
                className="bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 transition-all shadow-sm"
              >
                <span>{enviando ? 'Procesando...' : actual.tipo === 'disponibilidad' ? 'Ver Resultado' : 'Siguiente'}</span>
                {enviando ? <IconLoader2 className="w-4 h-4 animate-spin" /> : <IconArrowRight className="w-4 h-4" />}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
