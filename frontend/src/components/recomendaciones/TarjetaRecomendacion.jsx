import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { IconSparkles, IconChevronRight, IconX } from '@tabler/icons-react';
import { enviarRetroalimentacion, MOTIVOS_DESCARTE } from './retroalimentacion';

// Mismo tamaño para la tarjeta y su esqueleto de carga, para que el diseño no salte.
export const CLASE_TARJETA =
  'bg-white border border-slate-200/80 rounded-2xl p-5 shadow-sm min-h-[13rem] flex flex-col justify-between gap-4';

// "Mostrada" se envía una sola vez por recomendación en cada carga de la página.
const yaMostradas = new Set();

export const TarjetaRecomendacion = ({ rec, onDescartar }) => {
  const navigate = useNavigate();
  const tarjetaRef = useRef(null);
  const menuRef = useRef(null);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const id = rec.recomendacion_id;

  useEffect(() => {
    const nodo = tarjetaRef.current;
    if (!nodo || yaMostradas.has(id) || typeof IntersectionObserver === 'undefined') return undefined;

    const observador = new IntersectionObserver(
      (entradas) => {
        const visible = entradas.some((e) => e.isIntersecting && e.intersectionRatio >= 0.5);
        if (!visible || yaMostradas.has(id)) return;
        yaMostradas.add(id);
        enviarRetroalimentacion({ recomendacion_id: id, accion: 'mostrada' });
        observador.disconnect();
      },
      { threshold: 0.5 }
    );
    observador.observe(nodo);
    return () => observador.disconnect();
  }, [id]);

  useEffect(() => {
    if (!menuAbierto) return undefined;
    const alPulsarTecla = (e) => {
      if (e.key === 'Escape') setMenuAbierto(false);
    };
    const alPulsarFuera = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuAbierto(false);
    };
    document.addEventListener('keydown', alPulsarTecla);
    document.addEventListener('mousedown', alPulsarFuera);
    return () => {
      document.removeEventListener('keydown', alPulsarTecla);
      document.removeEventListener('mousedown', alPulsarFuera);
    };
  }, [menuAbierto]);

  const verCurso = () => {
    enviarRetroalimentacion({ recomendacion_id: id, accion: 'clic' });
    navigate(`/cursos/${rec.curso_id}?origen=recomendacion&rid=${encodeURIComponent(id)}`);
  };

  const descartar = (motivo) => {
    setMenuAbierto(false);
    enviarRetroalimentacion({ recomendacion_id: id, accion: 'descartada', motivo });
    onDescartar(id);
  };

  return (
    <article ref={tarjetaRef} className={CLASE_TARJETA}>
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
              <IconSparkles className="w-3.5 h-3.5" aria-hidden="true" />
              Recomendado
            </span>
            {rec.codigo_curso && (
              <span className="text-xs font-semibold text-slate-400">{rec.codigo_curso}</span>
            )}
          </div>

          <div ref={menuRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuAbierto((abierto) => !abierto)}
              aria-label={`No me interesa: ${rec.titulo}`}
              aria-haspopup="menu"
              aria-expanded={menuAbierto}
              title="No me interesa"
              className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <IconX className="w-4 h-4" aria-hidden="true" />
            </button>
            {menuAbierto && (
              <div
                role="menu"
                aria-label="Motivo para descartar"
                className="absolute right-0 top-8 z-20 w-44 bg-white border border-slate-200 rounded-xl shadow-lg py-1"
              >
                {MOTIVOS_DESCARTE.map((motivo) => (
                  <button
                    key={motivo.valor}
                    type="button"
                    role="menuitem"
                    onClick={() => descartar(motivo.valor)}
                    className="w-full text-left px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    {motivo.texto}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <h4 className="font-bold text-slate-900">{rec.titulo}</h4>
        <p className="text-xs text-slate-600 leading-relaxed">{rec.explicacion}</p>
      </div>

      <button
        type="button"
        onClick={verCurso}
        className="w-full rounded-xl py-2 px-4 text-sm font-medium flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-900 text-white shadow-sm transition-all"
      >
        <span>Ver curso</span>
        <IconChevronRight className="w-4 h-4" aria-hidden="true" />
      </button>
    </article>
  );
};
