import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { IconCheck, IconArrowRight, IconArrowLeft, IconCode, IconShieldCheck, IconAlertCircle } from '@tabler/icons-react';

const PREGUNTAS_TECNICAS = [
  { id: 1, pregunta: '¿Cuál es la salida del siguiente código en Python?', codigo: 'print("5" + "5")', opciones: ['10', '55', 'TypeError', '"10"'], correcta: 1 },
  { id: 2, pregunta: '¿Qué palabra clave se utiliza para definir una función en Python?', codigo: '___ mi_funcion():\n    return "Hola"', opciones: ['function', 'def', 'func', 'void'], correcta: 1 },
  { id: 3, pregunta: '¿Qué resultado produce la expresión len([10, 20, 30])?', codigo: 'numeros = [10, 20, 30]\nprint(len(numeros))', opciones: ['30', '2', '3', 'Error de índice'], correcta: 2 },
  { id: 4, pregunta: '¿Cuál es la salida del siguiente bucle for?', codigo: 'for i in range(3):\n    print(i, end=" ")', opciones: ['1 2 3', '0 1 2', '0 1 2 3', '1 2'], correcta: 1 },
  { id: 5, pregunta: '¿Qué estructura de datos es inmutable en Python?', codigo: 'a = (1, 2, 3)', opciones: ['Lista', 'Diccionario', 'Tupla', 'Conjunto (Set)'], correcta: 2 }
];

export const ColdStart = () => {
  const navigate = useNavigate();
  const { user, updateUser, sincronizarEstadoAdaptativo, setNetworkError } = useUser();

  const [step, setStep] = useState(1);
  const [familiaridad, setFamiliaridad] = useState('');
  const [respuestasTecnicas, setRespuestasTecnicas] = useState({});
  const [objetivo, setObjetivo] = useState('');
  const [disponibilidad, setDisponibilidad] = useState('');
  const [loading, setLoading] = useState(false);
  const [nivelCalculado, setNivelCalculado] = useState('');

  const totalSteps = 9;
  const progressPercent = Math.round((step / totalSteps) * 100);

  const handleAnswerSelect = (questionIndex, selectedOptionIndex) => {
    setRespuestasTecnicas({ ...respuestasTecnicas, [questionIndex]: selectedOptionIndex });
  };

  const handleNext = () => {
    if (step === 1 && familiaridad === 'No sé nada') {
      setStep(7);
      return;
    }
    setStep((prev) => prev + 1);
  };

  const handlePrev = () => {
    if (step === 7 && familiaridad === 'No sé nada') {
      setStep(1);
      return;
    }
    setStep((prev) => prev - 1);
  };

  const handleEnviarColdStart = async () => {
    setLoading(true);
    const respuestasArray = Object.keys(respuestasTecnicas).map((qIdx) => ({
      ejercicio_id: PREGUNTAS_TECNICAS[qIdx].id,
      opcion_id: respuestasTecnicas[qIdx],
    }));

    try {
      const res = await api.evaluarColdStart({
        usuario_id: user?.id,
        familiaridad,
        respuestas_tecnicas: respuestasArray,
        objetivo,
        disponibilidad,
      });

      if (res.success) {
        setNivelCalculado(res.nivel_asignado);
        updateUser({ nivel: res.nivel_asignado, esNuevoUsuario: false });
        if (user?.id) {
          await sincronizarEstadoAdaptativo(user.id);
        }
      }
    } catch (err) {
      if (err.isNetworkError) setNetworkError(true);
      setNivelCalculado(familiaridad === 'No sé nada' ? 'Principiante' : 'Intermedio');
    } finally {
      setLoading(false);
    }
  };

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
              Paso {step} de {totalSteps}
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2">
            <div className="bg-sky-500 h-2 rounded-full transition-all duration-300" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>

        <div className="p-8">
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿Cuál es tu nivel actual de experiencia con Python?</h3>
                <p className="text-sm text-slate-500 mt-1">Esto ayuda a calibrar la dificultad inicial del material.</p>
              </div>
              <div className="grid gap-3">
                {[
                  { title: 'No sé nada', desc: 'Nunca he escrito una línea de código en Python' },
                  { title: 'Apenas inicio', desc: 'Conozco variables y operaciones aritméticas básicas' },
                  { title: 'Conozco estructuras condicionales', desc: 'Manejo if/else, bucles for/while y listas' },
                  { title: 'Domino POO', desc: 'Escribo clases, métodos y módulos avanzados' }
                ].map((item) => (
                  <button
                    key={item.title}
                    onClick={() => setFamiliaridad(item.title)}
                    className={`p-4 rounded-xl border text-left transition-all flex items-center justify-between ${
                      familiaridad === item.title ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div>
                      <p className="font-semibold text-sm">{item.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
                    </div>
                    {familiaridad === item.title && <IconCheck className="w-5 h-5 text-sky-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step >= 2 && step <= 6 && (
            <div className="space-y-6">
              {(() => {
                const qIdx = step - 2;
                const pregunta = PREGUNTAS_TECNICAS[qIdx];
                return (
                  <>
                    <div>
                      <span className="text-xs font-semibold text-sky-600 uppercase tracking-wider">
                        Evaluación Técnica • Ejercicio {qIdx + 1} de 5
                      </span>
                      <h3 className="text-lg font-bold text-slate-900 mt-1">{pregunta.pregunta}</h3>
                    </div>
                    {pregunta.codigo && (
                      <div className="bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-sm border border-slate-800">
                        <pre>{pregunta.codigo}</pre>
                      </div>
                    )}
                    <div className="grid gap-3">
                      {pregunta.opciones.map((opcion, idx) => (
                        <button
                          key={opcion}
                          onClick={() => handleAnswerSelect(qIdx, idx)}
                          className={`p-4 rounded-xl border text-left text-sm font-medium transition-all flex items-center justify-between ${
                            respuestasTecnicas[qIdx] === idx ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 hover:border-slate-300 bg-white text-slate-700'
                          }`}
                        >
                          <span>{opcion}</span>
                          {respuestasTecnicas[qIdx] === idx && <IconCheck className="w-5 h-5 text-sky-500" />}
                        </button>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>
          )}

          {step === 7 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿Cuál es tu objetivo principal con este curso?</h3>
                <p className="text-sm text-slate-500 mt-1">Adaptaremos las recomendaciones de proyectos según tu meta.</p>
              </div>
              <div className="grid gap-3">
                {['Aprobar materia universitaria de programación', 'Automatizar tareas o procesos cotidianos', 'Análisis de datos y Ciencia de Datos', 'Curiosidad personal y desarrollo profesional'].map((item) => (
                  <button
                    key={item}
                    onClick={() => setObjetivo(item)}
                    className={`p-4 rounded-xl border text-left text-sm font-semibold transition-all flex items-center justify-between ${
                      objetivo === item ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 hover:border-slate-300 bg-white text-slate-700'
                    }`}
                  >
                    <span>{item}</span>
                    {objetivo === item && <IconCheck className="w-5 h-5 text-sky-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 8 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900">¿De cuánto tiempo dispones para estudiar?</h3>
                <p className="text-sm text-slate-500 mt-1">Ajustaremos la longitud diaria de tus sesiones.</p>
              </div>
              <div className="grid gap-3">
                {['5 a 10 minutos al día (Sesiones micro)', 'Un par de horas a la semana', 'Fines de semana exclusivamente', '1 hora diaria estructurada'].map((item) => (
                  <button
                    key={item}
                    onClick={() => setDisponibilidad(item)}
                    className={`p-4 rounded-xl border text-left text-sm font-semibold transition-all flex items-center justify-between ${
                      disponibilidad === item ? 'border-sky-500 bg-sky-50/50 text-slate-900 ring-2 ring-sky-500/20' : 'border-slate-200 hover:border-slate-300 bg-white text-slate-700'
                    }`}
                  >
                    <span>{item}</span>
                    {disponibilidad === item && <IconCheck className="w-5 h-5 text-sky-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 9 && (
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
                    {(nivelCalculado || user?.nivel || 'Principiante').toUpperCase()}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-slate-600 border-t border-slate-200 pt-2">
                  <span>Objetivo principal:</span>
                  <span className="font-semibold text-slate-800">{objetivo || 'Aprobar materia'}</span>
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

          {step < 9 && (
            <div className="flex items-center justify-between pt-6 mt-6 border-t border-slate-100">
              <button
                onClick={handlePrev}
                disabled={step === 1}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  step === 1 ? 'text-slate-300 cursor-not-allowed' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <IconArrowLeft className="w-4 h-4" />
                <span>Anterior</span>
              </button>

              <button
                onClick={() => {
                  if (step === 8) {
                    handleEnviarColdStart();
                    handleNext();
                  } else {
                    handleNext();
                  }
                }}
                disabled={
                  loading ||
                  (step === 1 && !familiaridad) ||
                  (step >= 2 && step <= 6 && respuestasTecnicas[step - 2] === undefined) ||
                  (step === 7 && !objetivo) ||
                  (step === 8 && !disponibilidad)
                }
                className="bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 transition-all shadow-sm"
              >
                <span>{loading ? 'Procesando...' : step === 8 ? 'Ver Resultado' : 'Siguiente'}</span>
                <IconArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};