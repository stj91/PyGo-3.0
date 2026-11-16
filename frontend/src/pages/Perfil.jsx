import React, { useCallback, useEffect, useState } from 'react';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import {
  IconUserCircle,
  IconShieldCheck,
  IconHeart,
  IconCheck,
  IconChartBar,
  IconTrophy,
  IconLock,
  IconLoader2,
  IconRefresh,
  IconAlertCircle,
} from '@tabler/icons-react';

const MAX_INTERESES = 4;

// Agrupa el dominio por área conservando el orden recibido (área y luego nombre).
const agruparPorArea = (dominio) =>
  dominio.reduce((grupos, concepto) => {
    const clave = concepto.area || '';
    const existente = grupos.find((g) => g.clave === clave);
    return existente
      ? grupos.map((g) => (g === existente ? { ...g, conceptos: [...g.conceptos, concepto] } : g))
      : [...grupos, { clave, conceptos: [concepto] }];
  }, []);

const porcentaje = (valor) => Math.max(0, Math.min(100, Math.round((Number(valor) || 0) * 100)));

const Tarjeta = ({ icono: Icono, titulo, children }) => (
  <section className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
    <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
      <Icono className="w-5 h-5 text-sky-500" aria-hidden="true" />
      <h3 className="font-bold text-slate-900">{titulo}</h3>
    </div>
    {children}
  </section>
);

export const Perfil = () => {
  const { user } = useUser();
  const usuarioId = user?.id;

  const [estado, setEstado] = useState('cargando'); // cargando | listo | error
  const [perfil, setPerfil] = useState(null);
  const [areas, setAreas] = useState([]);
  const [seleccion, setSeleccion] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null); // { tipo: 'ok' | 'error', texto }

  const cargar = useCallback(async () => {
    if (!usuarioId) return;
    setEstado('cargando');
    setAviso(null);
    try {
      const [respuestaPerfil, respuestaAreas] = await Promise.all([api.getPerfil(usuarioId), api.getAreas()]);
      const datos = respuestaPerfil?.perfil;
      if (!datos) throw new Error('Perfil vacío');
      setPerfil(datos);
      setAreas(Array.isArray(respuestaAreas?.areas) ? respuestaAreas.areas : []);
      setSeleccion(Array.isArray(datos.intereses_declarados) ? datos.intereses_declarados : []);
      setEstado('listo');
    } catch {
      setEstado('error');
    }
  }, [usuarioId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const alternarInteres = (clave) => {
    setAviso(null);
    setSeleccion((previa) =>
      previa.includes(clave)
        ? previa.filter((c) => c !== clave)
        : previa.length < MAX_INTERESES
          ? [...previa, clave]
          : previa
    );
  };

  const guardarIntereses = async () => {
    setGuardando(true);
    setAviso(null);
    try {
      const respuesta = await api.guardarIntereses(usuarioId, seleccion);
      if (Array.isArray(respuesta?.intereses)) setSeleccion(respuesta.intereses);
      setAviso({ tipo: 'ok', texto: 'Intereses guardados.' });
    } catch (err) {
      setAviso({
        tipo: 'error',
        texto: err.isNetworkError
          ? 'No se pudo conectar con el servidor. Inténtalo de nuevo.'
          : err.message || 'No se pudieron guardar tus intereses.',
      });
    } finally {
      setGuardando(false);
    }
  };

  if (!usuarioId) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-center space-y-2">
          <IconUserCircle className="w-10 h-10 text-slate-400" />
          <p className="text-sm text-slate-500">Inicia sesión para ver lo que PyGo sabe de ti.</p>
        </div>
      </Layout>
    );
  }

  if (estado === 'cargando') {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <IconLoader2 className="w-8 h-8 animate-spin text-sky-500 mb-2" />
          <p className="text-sm font-medium">Cargando tu perfil...</p>
        </div>
      </Layout>
    );
  }

  if (estado === 'error') {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 text-center space-y-4 max-w-md mx-auto">
          <IconAlertCircle className="w-10 h-10 text-slate-400" />
          <h3 className="text-xl font-bold text-slate-800">No pudimos cargar tu perfil</h3>
          <p className="text-sm text-slate-500">
            Puede que esta sección aún no esté disponible o que haya un problema de conexión. Prueba de nuevo en
            unos minutos.
          </p>
          <button
            onClick={cargar}
            className="flex items-center gap-2 bg-slate-800 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-slate-900 transition-all"
          >
            <IconRefresh className="w-4 h-4" />
            <span>Reintentar</span>
          </button>
        </div>
      </Layout>
    );
  }

  const nivel = perfil.nivel || user.nivel;
  const nivelCambiado =
    perfil.nivel_inferido && perfil.nivel_asignado && perfil.nivel_inferido !== perfil.nivel_asignado;
  const nombreArea = Object.fromEntries(areas.map((a) => [a.clave, a.nombre]));
  const dominio = (Array.isArray(perfil.dominio) ? perfil.dominio : []).filter((c) => Number(c.evidencias) > 0);
  const grupos = agruparPorArea(dominio);
  const completados = Array.isArray(perfil.cursos_completados) ? perfil.cursos_completados : [];
  const limiteAlcanzado = seleccion.length >= MAX_INTERESES;

  return (
    <Layout>
      <div className="space-y-6 max-w-4xl mx-auto">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Lo que PyGo sabe de ti</h2>
          <p className="text-sm text-slate-500 mt-1">
            Así te vemos para recomendarte cursos. Si algo no encaja, corrígelo.
          </p>
        </div>

        <Tarjeta icono={IconShieldCheck} titulo="Tu nivel">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-sky-50 text-sky-700 border border-sky-200 rounded-full text-sm font-semibold">
            <IconShieldCheck className="w-4 h-4" aria-hidden="true" />
            {nivel}
          </span>
          {nivelCambiado && (
            <p className="text-sm text-slate-600">
              Tu nivel inicial fue {perfil.nivel_asignado}; por tu progreso, ahora te consideramos {nivel}.
            </p>
          )}
        </Tarjeta>

        <Tarjeta icono={IconHeart} titulo="Tus intereses">
          <p className="text-xs text-slate-500">Elige hasta {MAX_INTERESES} áreas.</p>
          <div className="flex flex-wrap gap-2">
            {areas.map((area) => {
              const activa = seleccion.includes(area.clave);
              const bloqueada = !activa && limiteAlcanzado;
              return (
                <button
                  key={area.clave}
                  type="button"
                  onClick={() => alternarInteres(area.clave)}
                  disabled={bloqueada}
                  aria-pressed={activa}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                    activa
                      ? 'bg-sky-600 text-white border-sky-600'
                      : bloqueada
                        ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                        : 'bg-white text-slate-600 border-slate-200 hover:border-sky-300'
                  }`}
                >
                  {activa && <IconCheck className="w-3.5 h-3.5" aria-hidden="true" />}
                  {area.nombre}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={guardarIntereses}
              disabled={guardando}
              className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-70 text-white px-4 py-2 rounded-xl text-sm font-medium shadow-sm transition-all"
            >
              {guardando && <IconLoader2 className="w-4 h-4 animate-spin" />}
              <span>Guardar intereses</span>
            </button>
            {aviso && (
              <p
                role={aviso.tipo === 'error' ? 'alert' : 'status'}
                className={`text-xs font-medium flex items-center gap-1 ${
                  aviso.tipo === 'error' ? 'text-rose-600' : 'text-emerald-700'
                }`}
              >
                {aviso.tipo === 'error' ? (
                  <IconAlertCircle className="w-3.5 h-3.5" aria-hidden="true" />
                ) : (
                  <IconCheck className="w-3.5 h-3.5" aria-hidden="true" />
                )}
                {aviso.texto}
              </p>
            )}
          </div>
        </Tarjeta>

        <Tarjeta icono={IconChartBar} titulo="Dominio por concepto">
          {grupos.length === 0 ? (
            <p className="text-sm text-slate-500">Aún no hay suficiente actividad para estimarlo.</p>
          ) : (
            <div className="space-y-5">
              {grupos.map((grupo) => (
                <div key={grupo.clave || 'sin-area'} className="space-y-3">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase">
                    {grupo.clave ? nombreArea[grupo.clave] || grupo.clave : 'Otros conceptos'}
                  </h4>
                  <ul className="space-y-3">
                    {grupo.conceptos.map((concepto) => {
                      const valor = porcentaje(concepto.dominio);
                      const evidencias = Number(concepto.evidencias);
                      return (
                        <li key={concepto.clave} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-medium text-slate-800">{concepto.nombre}</span>
                            <span className="font-semibold text-slate-600">{valor}%</span>
                          </div>
                          <div
                            className="w-full bg-slate-100 rounded-full h-2"
                            role="progressbar"
                            aria-valuenow={valor}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-label={`Dominio de ${concepto.nombre}`}
                          >
                            <div className="bg-sky-500 h-2 rounded-full" style={{ width: `${valor}%` }} />
                          </div>
                          <p className="text-xs text-slate-400">
                            basado en {evidencias} {evidencias === 1 ? 'actividad' : 'actividades'}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </Tarjeta>

        <Tarjeta icono={IconTrophy} titulo="Cursos completados">
          {completados.length === 0 ? (
            <p className="text-sm text-slate-500">Todavía no has completado ningún curso.</p>
          ) : (
            <ul className="space-y-2">
              {completados.map((curso) => (
                <li key={curso.curso_id} className="flex items-center gap-2 text-sm text-slate-800">
                  <IconCheck className="w-4 h-4 text-emerald-600" aria-hidden="true" />
                  {curso.codigo_curso && (
                    <span className="text-xs font-semibold text-slate-400">{curso.codigo_curso}</span>
                  )}
                  <span className="font-medium">{curso.titulo}</span>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>

        <p className="flex items-start gap-2 text-xs text-slate-500">
          <IconLock className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>PyGo usa tus respuestas y tu avance para recomendarte cursos. No compartimos estos datos.</span>
        </p>
      </div>
    </Layout>
  );
};
