import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { registrarVistaCurso } from '../services/eventos';
import {
  IconArrowLeft,
  IconBook,
  IconChevronRight,
  IconCircleCheck,
  IconLoader2,
  IconPlayerPlay,
  IconRefresh,
} from '@tabler/icons-react';

// Valores de `origen` que acepta el registro de eventos (docs/motor/03 §1, `curso_vista`).
const ORIGENES = ['catalogo', 'recomendacion', 'dashboard', 'busqueda', 'ruta'];

const esNoImplementado = (err) => err?.status === 501 || err?.code === 'NOT_IMPLEMENTED';

const INSCRIPCION_INICIAL = { estado: 'disponible', error: '' }; // disponible | enviando | inscrito | ya_inscrito | oculto

// Lecciones de un curso real: cada `tema` de la base de datos es una lección.
const leccionesReales = (curso) =>
  [...(curso.temas || [])]
    .sort((a, b) => (a.orden ?? 0) - (b.orden ?? 0))
    .map((tema) => ({
      id: tema.id,
      titulo: tema.titulo,
      descripcion: tema.descripcion,
      ejercicios: (tema.ejercicios || []).length,
    }));

export const DetalleCurso = () => {
  const { cursoId } = useParams();
  const navigate = useNavigate();
  const { user } = useUser();
  const [searchParams] = useSearchParams();
  const origenParam = searchParams.get('origen');
  const origen = ORIGENES.includes(origenParam) ? origenParam : 'catalogo';
  const rid = searchParams.get('rid') || undefined;

  const [curso, setCurso] = useState(null);
  const [lecciones, setLecciones] = useState([]);
  const [recarga, setRecarga] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [inscripcion, setInscripcion] = useState(INSCRIPCION_INICIAL);
  const vistaRegistrada = useRef(null);

  // Una vista por id de curso.
  useEffect(() => {
    const id = Number(cursoId);
    if (!Number.isInteger(id) || vistaRegistrada.current === id) return;
    vistaRegistrada.current = id;
    registrarVistaCurso(id, origen, rid);
  }, [cursoId, origen, rid]);

  const empezarCurso = async () => {
    setInscripcion({ estado: 'enviando', error: '' });
    try {
      const respuesta = await api.inscribirse(cursoId, { origen, recomendacion_id: rid });
      setInscripcion({
        estado: respuesta?.nueva === false ? 'ya_inscrito' : 'inscrito',
        error: '',
      });
    } catch (err) {
      if (esNoImplementado(err)) {
        setInscripcion({ estado: 'oculto', error: '' });
      } else {
        setInscripcion({
          estado: 'disponible',
          error: err.isNetworkError
            ? 'No se pudo conectar con el servidor. Inténtalo de nuevo.'
            : err.message || 'No se pudo completar la inscripción.',
        });
      }
    }
  };

  useEffect(() => {
    const cargarCurso = async () => {
      setLoading(true);
      setError('');
      setInscripcion(INSCRIPCION_INICIAL);
      try {
        const { curso: encontrado } = await api.getCursoPorId(cursoId);
        setCurso(encontrado || null);
        setLecciones(encontrado ? leccionesReales(encontrado) : []);
      } catch (err) {
        setCurso(null);
        setLecciones([]);
        setError(
          err.isNetworkError
            ? 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.'
            : err.message || 'No se pudo cargar el curso.'
        );
      } finally {
        setLoading(false);
      }
    };

    cargarCurso();
  }, [cursoId, recarga]);

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
          <h3 className="text-xl font-bold text-slate-800">{error ? 'No se pudo cargar el curso' : 'No se encontró el curso solicitado'}</h3>
          <p className="text-sm text-slate-500">{error || `El curso con ID "${cursoId}" no está disponible actualmente.`}</p>
          {error && (
            <button
              onClick={() => setRecarga((n) => n + 1)}
              className="flex items-center gap-2 border border-slate-300 text-slate-700 px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-slate-50 transition-all"
            >
              <IconRefresh className="w-4 h-4" />
              <span>Reintentar</span>
            </button>
          )}
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
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/cursos')}
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors"
          >
            <IconArrowLeft className="w-4 h-4" />
            <span>Volver a Cursos</span>
          </button>
          {curso.codigo_curso && (
            <span className="px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-xs font-semibold">
              {curso.codigo_curso}
            </span>
          )}
        </div>

        <div>
          <h2 className="text-2xl font-bold text-slate-900">{curso.titulo}</h2>
          <p className="text-sm text-slate-500 mt-1">{curso.descripcion}</p>
        </div>

        {/* Inscripción: orientativa, las lecciones siguen accesibles igualmente. */}
        {user?.id && inscripcion.estado !== 'oculto' && (
          <div className="space-y-2">
            {inscripcion.estado === 'inscrito' || inscripcion.estado === 'ya_inscrito' ? (
              <span
                role="status"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
              >
                <IconCircleCheck className="w-4 h-4" />
                {inscripcion.estado === 'inscrito' ? 'Inscrito' : 'Ya estás inscrito'}
              </span>
            ) : (
              <button
                onClick={empezarCurso}
                disabled={inscripcion.estado === 'enviando'}
                className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-70 text-white px-5 py-2.5 rounded-xl text-sm font-medium shadow-sm transition-all"
              >
                {inscripcion.estado === 'enviando' ? (
                  <IconLoader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <IconPlayerPlay className="w-4 h-4" />
                )}
                <span>Empezar curso</span>
              </button>
            )}
            {inscripcion.error && (
              <p role="alert" className="text-xs font-medium text-rose-600">
                {inscripcion.error}
              </p>
            )}
          </div>
        )}

        {lecciones.length === 0 ? (
          <p className="text-sm text-slate-500">Este curso todavía no tiene lecciones.</p>
        ) : (
          <ol className="space-y-3">
            {lecciones.map((leccion, idx) => (
              <li key={leccion.id}>
                <button
                  onClick={() => navigate(`/cursos/${curso.id}/lecciones/${leccion.id}`)}
                  className="w-full text-left bg-white border border-slate-200/80 rounded-2xl p-5 shadow-sm hover:border-sky-300 hover:shadow transition-all flex items-center gap-4"
                >
                  <div className="w-10 h-10 shrink-0 rounded-xl bg-slate-800 text-sky-400 flex items-center justify-center">
                    <IconBook className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Lección {idx + 1}</p>
                    <h3 className="font-bold text-slate-900">{leccion.titulo}</h3>
                    {leccion.descripcion && (
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">{leccion.descripcion}</p>
                    )}
                    <p className="text-xs text-slate-400 mt-1">
                      {leccion.ejercicios} {leccion.ejercicios === 1 ? 'ejercicio' : 'ejercicios'}
                    </p>
                  </div>
                  <span className="flex items-center gap-1 text-xs font-semibold text-sky-700">
                    Abrir lección
                    <IconChevronRight className="w-4 h-4" />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </Layout>
  );
};
