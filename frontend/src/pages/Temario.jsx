import React from 'react';
import { Layout } from '../components/Layout';
import { IconCheck, IconHourglass, IconLock, IconBook, IconChevronRight } from '@tabler/icons-react';

export const Temario = () => {
  const modulos = [
    {
      id: 1,
      titulo: 'Módulo 1: Fundamentos de Sintaxis y Tipos de Datos',
      progreso: 100,
      lecciones: [
        { nombre: 'Variables, Enteros y Flotantes', estado: 'Completado' },
        { nombre: 'Cadenas de Texto (Strings) y Operaciones', estado: 'Completado' }
      ]
    },
    {
      id: 2,
      titulo: 'Módulo 2: Estructuras de Control y Lógica',
      progreso: 50,
      lecciones: [
        { nombre: 'Operadores Lógicos y Relacionales', estado: 'Completado' },
        { nombre: 'Condicionales Anidadas (if / elif / else)', estado: 'En Curso' },
        { nombre: 'Bucles for y range()', estado: 'Bloqueado' }
      ]
    },
    {
      id: 3,
      titulo: 'Módulo 3: Funciones y Estructuras Compuestas',
      progreso: 0,
      lecciones: [
        { nombre: 'Definición de Funciones y Parámetros', estado: 'Bloqueado' },
        { nombre: 'Listas, Tuplas y Diccionarios', estado: 'Bloqueado' }
      ]
    }
  ];

  return (
    <Layout>
      <div className="space-y-6 max-w-4xl mx-auto">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Temario del Curso</h2>
          <p className="text-sm text-slate-500 mt-1">
            Estructura jerárquica de contenidos adaptada a tu ritmo de estudio.
          </p>
        </div>

        <div className="space-y-6">
          {modulos.map((modulo) => (
            <div key={modulo.id} className="bg-white border border-slate-200/80 rounded-2xl overflow-hidden shadow-sm">
              <div className="p-6 bg-slate-50/50 border-b border-slate-200/80 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-slate-800 text-sky-400 flex items-center justify-center font-bold">
                    <IconBook className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{modulo.titulo}</h3>
                    <p className="text-xs text-slate-500">{modulo.lecciones.length} lecciones en este módulo</p>
                  </div>
                </div>
                <span className="text-xs font-bold px-3 py-1 bg-white border border-slate-200 rounded-full text-slate-700">
                  {modulo.progreso}% Completado
                </span>
              </div>

              <div className="divide-y divide-slate-100">
                {modulo.lecciones.map((leccion, idx) => (
                  <div key={idx} className="p-4 px-6 flex items-center justify-between hover:bg-slate-50/80 transition-colors">
                    <span className="text-sm font-medium text-slate-800">{leccion.nombre}</span>
                    <div className="flex items-center gap-3">
                      {leccion.estado === 'Completado' && (
                        <span className="flex items-center gap-1 text-xs font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                          <IconCheck className="w-3.5 h-3.5" /> Completado
                        </span>
                      )}
                      {leccion.estado === 'En Curso' && (
                        <span className="flex items-center gap-1 text-xs font-semibold text-amber-600 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200">
                          <IconHourglass className="w-3.5 h-3.5" /> En Curso
                        </span>
                      )}
                      {leccion.estado === 'Bloqueado' && (
                        <span className="flex items-center gap-1 text-xs font-semibold text-slate-400 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
                          <IconLock className="w-3.5 h-3.5" /> Bloqueado
                        </span>
                      )}
                      <IconChevronRight className="w-4 h-4 text-slate-400" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
};