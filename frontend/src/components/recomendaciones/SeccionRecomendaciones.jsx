import React from 'react';
import { Link } from 'react-router-dom';
import { IconSparkles, IconPlayerPlay, IconChevronRight } from '@tabler/icons-react';
import { useRecomendaciones } from './useRecomendaciones';
import { TarjetaRecomendacion, CLASE_TARJETA } from './TarjetaRecomendacion';

const Titulo = () => (
  <div className="flex items-center gap-2">
    <IconSparkles className="w-5 h-5 text-sky-500" aria-hidden="true" />
    <h3 className="text-lg font-bold text-slate-900">Recomendado para ti</h3>
  </div>
);

const Esqueleto = () => (
  <div className={`${CLASE_TARJETA} animate-pulse`} aria-hidden="true">
    <div className="space-y-3">
      <div className="h-4 w-24 bg-slate-100 rounded-full" />
      <div className="h-5 w-3/4 bg-slate-100 rounded" />
      <div className="h-3 w-full bg-slate-100 rounded" />
      <div className="h-3 w-2/3 bg-slate-100 rounded" />
    </div>
    <div className="h-9 w-full bg-slate-100 rounded-xl" />
  </div>
);

const Continuar = ({ cursos }) => (
  <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-sm space-y-3">
    <div className="flex items-center gap-2">
      <IconPlayerPlay className="w-4 h-4 text-amber-500" aria-hidden="true" />
      <h4 className="font-bold text-slate-900 text-sm">Continúa donde lo dejaste</h4>
    </div>
    <ul className="space-y-3">
      {cursos.map((curso) => {
        const avance = Math.max(0, Math.min(100, Math.round(Number(curso.porcentaje_avance_global) || 0)));
        return (
          <li key={curso.curso_id} className="flex items-center gap-4">
            <div className="flex-1 min-w-0 space-y-1.5">
              <p className="text-sm font-semibold text-slate-800 truncate">{curso.titulo}</p>
              <div className="flex items-center gap-3">
                <div
                  className="flex-1 bg-slate-100 rounded-full h-2"
                  role="progressbar"
                  aria-valuenow={avance}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Avance en ${curso.titulo}`}
                >
                  <div className="bg-sky-500 h-2 rounded-full" style={{ width: `${avance}%` }} />
                </div>
                <span className="text-xs font-semibold text-slate-600 w-10 text-right">{avance}%</span>
              </div>
            </div>
            <Link
              to={`/cursos/${curso.curso_id}?origen=dashboard`}
              className="flex items-center gap-1 text-xs font-semibold text-sky-700 hover:text-sky-900 shrink-0"
            >
              Continuar
              <IconChevronRight className="w-4 h-4" aria-hidden="true" />
            </Link>
          </li>
        );
      })}
    </ul>
  </div>
);

/**
 * Presentación de "Recomendado para ti" (y, si `mostrarContinuar`, "Continúa
 * donde lo dejaste") a partir de los datos de `useRecomendaciones`. Si no hay
 * nada que mostrar no renderiza nada (nunca un mensaje de error).
 */
export const ListaRecomendaciones = ({
  estado,
  recomendaciones,
  continuar = [],
  quitar,
  maxTarjetas = 3,
  mostrarContinuar = true,
}) => {
  if (estado === 'oculto') return null;

  if (estado === 'cargando') {
    return (
      <section className="space-y-4" aria-busy="true">
        <Titulo />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: Math.min(maxTarjetas, 3) }, (_, i) => (
            <Esqueleto key={i} />
          ))}
        </div>
      </section>
    );
  }

  const tarjetas = recomendaciones.slice(0, maxTarjetas);
  const filas = mostrarContinuar ? continuar : [];
  if (tarjetas.length === 0 && filas.length === 0) return null;

  return (
    <section className="space-y-4">
      {tarjetas.length > 0 && (
        <>
          <Titulo />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {tarjetas.map((rec) => (
              <TarjetaRecomendacion key={rec.recomendacion_id} rec={rec} onDescartar={quitar} />
            ))}
          </div>
        </>
      )}
      {filas.length > 0 && <Continuar cursos={filas} />}
    </section>
  );
};

/** "Recomendado para ti" + "Continúa donde lo dejaste", con su propia petición. */
export const SeccionRecomendaciones = ({ limite = 3 }) => {
  const datos = useRecomendaciones(limite);
  return <ListaRecomendaciones {...datos} maxTarjetas={limite} />;
};
