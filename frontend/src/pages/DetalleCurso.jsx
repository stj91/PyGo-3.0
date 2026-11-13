import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { api } from '../services/api';
import { mockCursos } from '../data/mockCursos';
import {
  IconArrowLeft,
  IconBook,
  IconChevronRight,
  IconLoader2,
  IconWifiOff,
} from '@tabler/icons-react';

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

// Lecciones del contenido de ejemplo (sin conexión): módulos -> lecciones.
const leccionesMock = (curso) =>
  (curso.modulos || []).flatMap((modulo) =>
    (modulo.lecciones || []).map((leccion) => ({
      id: leccion.id,
      titulo: leccion.titulo,
      descripcion: leccion.teoria?.introduccion,
      ejercicios: leccion.ejercicio ? 1 : 0,
    }))
  );

const MOCK_POR_ID = { 1: 'fundamentos-python', 2: 'estructuras-control', 3: 'poo' };

const buscarMock = (cursoId) =>
  mockCursos.find((c) => c.id === cursoId || c.id === MOCK_POR_ID[cursoId]) || null;

export const DetalleCurso = () => {
  const { cursoId } = useParams();
  const navigate = useNavigate();

  const [curso, setCurso] = useState(null);
  const [lecciones, setLecciones] = useState([]);
  const [sinConexion, setSinConexion] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cargarCurso = async () => {
      setLoading(true);
      setError('');
      setSinConexion(false);
      try {
        const { curso: encontrado } = await api.getCursoPorId(cursoId);
        setCurso(encontrado || null);
        setLecciones(encontrado ? leccionesReales(encontrado) : []);
      } catch (err) {
        if (err.isNetworkError) {
          const mock = buscarMock(cursoId);
          setSinConexion(true);
          setCurso(mock);
          setLecciones(mock ? leccionesMock(mock) : []);
        } else {
          setCurso(null);
          setLecciones([]);
          setError(err.message || 'No se pudo cargar el curso.');
        }
      } finally {
        setLoading(false);
      }
    };

    cargarCurso();
  }, [cursoId]);

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
          <p className="text-sm text-slate-500">{error || `El curso con ID "${cursoId}" no está disponible actualmente.`}</p>
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

        {sinConexion && (
          <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3 text-xs font-medium">
            <IconWifiOff className="w-4 h-4" />
            <span>Sin conexión: mostrando contenido de ejemplo.</span>
          </div>
        )}

        <div>
          <h2 className="text-2xl font-bold text-slate-900">{curso.titulo}</h2>
          <p className="text-sm text-slate-500 mt-1">{curso.descripcion}</p>
        </div>

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
