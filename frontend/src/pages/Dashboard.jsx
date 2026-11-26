import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { SeccionRecomendaciones } from '../components/recomendaciones/SeccionRecomendaciones';
import {
  IconSparkles,
  IconCircleCheck,
  IconBook,
  IconChartBar,
  IconArrowRight,
  IconLoader2,
} from '@tabler/icons-react';

const MAX_CONCEPTOS = 5;

const esInscrito = (curso) => Boolean(curso.inscrito) || Number(curso.porcentaje_avance_global || 0) > 0;

const porcentaje = (valor) => Math.max(0, Math.min(100, Math.round(Number(valor) || 0)));

// Datos reales del tablero: avance por curso y perfil. Cada parte falla por
// separado, para que un error en una no oculte la otra.
const useDatosTablero = (usuarioId) => {
  const [datos, setDatos] = useState({ cargando: true, cursos: null, perfil: null });

  useEffect(() => {
    if (!usuarioId) {
      setDatos({ cargando: false, cursos: null, perfil: null });
      return undefined;
    }

    let vigente = true;
    setDatos({ cargando: true, cursos: null, perfil: null });
    Promise.allSettled([api.getCursos(usuarioId), api.getPerfil(usuarioId)]).then(([cursos, perfil]) => {
      if (!vigente) return;
      setDatos({
        cargando: false,
        cursos: cursos.status === 'fulfilled' && Array.isArray(cursos.value?.cursos) ? cursos.value.cursos : null,
        perfil: perfil.status === 'fulfilled' ? perfil.value?.perfil ?? null : null,
      });
    });

    return () => {
      vigente = false;
    };
  }, [usuarioId]);

  return datos;
};

const BannerBienvenida = ({ user, perfil }) => {
  const nombre = user?.nombre ? user.nombre.split(' ')[0] : null;
  const completados = perfil?.cursos_completados?.length ?? 0;
  const conceptos = perfil?.dominio?.length ?? 0;

  return (
    <div className="bg-slate-900 rounded-2xl p-8 text-white shadow-lg border border-slate-800">
      <div className="max-w-2xl space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 text-sky-400 border border-slate-700 text-xs font-semibold">
          <IconSparkles className="w-4 h-4" />
          <span>Nivel {user?.nivel}</span>
        </div>
        <h2 className="text-3xl font-bold tracking-tight">¡Hola de nuevo{nombre ? `, ${nombre}` : ''}!</h2>
        {perfil && (
          <p className="text-slate-300 text-sm leading-relaxed">
            {completados === 0 && conceptos === 0
              ? 'Empieza un curso para que PyCode pueda adaptar tu ruta.'
              : `Has completado ${completados} ${completados === 1 ? 'curso' : 'cursos'} y practicado ${conceptos} ${
                  conceptos === 1 ? 'concepto' : 'conceptos'
                }.`}
          </p>
        )}
      </div>
    </div>
  );
};

const TarjetaProgreso = ({ cursos }) => {
  const empezados = cursos.filter(esInscrito);
  const terminados = empezados.filter((c) => porcentaje(c.porcentaje_avance_global) === 100).length;

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <IconBook className="w-5 h-5 text-sky-500" />
          Tu progreso
        </h3>
        <span className="text-sm font-semibold text-slate-600">
          {terminados} de {cursos.length} cursos terminados
        </span>
      </div>

      {empezados.length === 0 ? (
        <p className="text-sm text-slate-500">
          Aún no has empezado ningún curso.{' '}
          <Link to="/cursos" className="font-semibold text-sky-700 hover:underline">
            Explora el catálogo
          </Link>
        </p>
      ) : (
        <ul className="space-y-3">
          {empezados.map((curso) => {
            const avance = porcentaje(curso.porcentaje_avance_global);
            return (
              <li key={curso.id}>
                <Link to={`/cursos/${curso.id}?origen=dashboard`} className="block space-y-1.5 group">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-800 group-hover:text-sky-700">
                      {curso.codigo_curso} · {curso.titulo}
                    </span>
                    <span className="flex items-center gap-1 font-semibold text-slate-600">
                      {avance === 100 && <IconCircleCheck className="w-4 h-4 text-emerald-600" />}
                      {avance}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${avance === 100 ? 'bg-emerald-500' : 'bg-sky-500'}`}
                      style={{ width: `${avance}%` }}
                    />
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

const TarjetaConceptos = ({ perfil }) => {
  const conceptos = [...(perfil.dominio ?? [])].sort((a, b) => b.dominio - a.dominio).slice(0, MAX_CONCEPTOS);

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
        <IconChartBar className="w-5 h-5 text-sky-500" />
        Lo que mejor dominas
      </h3>

      {conceptos.length === 0 ? (
        <p className="text-sm text-slate-500">Responde algunos ejercicios y aquí verás tus temas más fuertes.</p>
      ) : (
        <ul className="space-y-3">
          {conceptos.map((c) => {
            const valor = porcentaje(c.dominio * 100);
            return (
              <li key={c.clave} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-800">{c.nombre}</span>
                  <span className="text-slate-600">{valor}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div className="bg-sky-500 h-2 rounded-full" style={{ width: `${valor}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <Link to="/perfil" className="inline-flex items-center gap-1 text-sm font-semibold text-sky-700 hover:underline">
        Ver mi perfil completo
        <IconArrowRight className="w-4 h-4" />
      </Link>
    </div>
  );
};

export const Dashboard = () => {
  const { user } = useUser();
  const { cargando, cursos, perfil } = useDatosTablero(user?.id);

  return (
    <Layout>
      <div className="space-y-8">
        <BannerBienvenida user={user} perfil={perfil} />

        <SeccionRecomendaciones limite={3} />

        {cargando ? (
          <div className="flex items-center justify-center gap-2 py-10 text-slate-500">
            <IconLoader2 className="w-5 h-5 animate-spin text-sky-500" />
            <span className="text-sm font-medium">Cargando tu progreso...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2">{cursos && <TarjetaProgreso cursos={cursos} />}</div>
            <div>{perfil && <TarjetaConceptos perfil={perfil} />}</div>
          </div>
        )}
      </div>
    </Layout>
  );
};
