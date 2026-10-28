import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  IconCode,
  IconSchool,
  IconLogin,
  IconUserPlus,
  IconAdjustmentsHorizontal,
  IconChecklist,
  IconShieldCheck,
  IconArrowRight
} from '@tabler/icons-react';

export const LandingPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 bg-dot-pattern flex flex-col justify-between">
      {/* Navbar Superior */}
      <header className="bg-white border-b border-slate-200/80 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          {/* Logo y Badge Universitario */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-slate-800 text-sky-400 flex items-center justify-center font-bold shadow-md">
                <IconCode className="w-6 h-6" />
              </div>
              <span className="text-xl font-extrabold text-slate-900 tracking-tight">PyGo</span>
            </div>
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 text-xs font-semibold">
              <IconSchool className="w-4 h-4 text-slate-500" />
              <span>CUCEI / UdG</span>
            </div>
          </div>

          {/* Botones Únicos de Acción */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 text-sm font-medium transition-colors"
            >
              <IconLogin className="w-4 h-4" />
              <span>Iniciar Sesión</span>
            </button>
            <button
              onClick={() => navigate('/registro')}
              className="flex items-center gap-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl py-2.5 px-4 text-sm font-medium transition-all shadow-sm"
            >
              <IconUserPlus className="w-4 h-4" />
              <span>Registrarse</span>
            </button>
          </div>
        </div>
      </header>

      {/* Sección Hero */}
      <main className="max-w-7xl mx-auto px-6 py-16 flex-1 flex flex-col justify-center">
        <div className="max-w-3xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200 text-xs font-semibold">
            <IconShieldCheck className="w-4 h-4" />
            <span>Sistema de Aprendizaje Adaptativo para Universitarios</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight tracking-tight">
            Aprende Python a tu propio ritmo con un sistema adaptativo
          </h1>

          <p className="text-base sm:text-lg text-slate-500 max-w-2xl mx-auto leading-relaxed">
            Plataforma interactiva diseñada para la comunidad universitaria de CUCEI. Evalúa tu nivel actual, recibe ejercicios personalizados y domina la programación estructurada y orientada a objetos.
          </p>

          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => navigate('/registro')}
              className="w-full sm:w-auto bg-slate-800 hover:bg-slate-900 text-white rounded-xl py-3 px-6 font-medium text-sm flex items-center justify-center gap-2 shadow-md transition-all"
            >
              <span>Comenzar Ahora</span>
              <IconArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => navigate('/login')}
              className="w-full sm:w-auto bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-xl py-3 px-6 font-medium text-sm flex items-center justify-center gap-2 shadow-sm transition-all"
            >
              <span>Ingresar a mi Cuenta</span>
            </button>
          </div>
        </div>

        {/* Tarjetas Informativas Secundarias */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-200 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center">
              <IconAdjustmentsHorizontal className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900">Diagnóstico Inteligente</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Inicia con una prueba de entrada que calibra la dificultad de la plataforma automáticamente según tus conocimientos previos.
            </p>
          </div>

          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-200 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <IconChecklist className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900">Retroalimentación Inmediata</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Resuelve ejercicios de código interactivos y recibe explicaciones detalladas al instante para consolidar tus conceptos.
            </p>
          </div>

          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-200 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <IconShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900">Adaptabilidad por Nivel</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              La interfaz y las funciones avanzadas se adaptan a tu perfil: Principiante, Intermedio o Avanzado.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200/80 py-6 text-center text-xs text-slate-500">
        <p>PyGo — Plataforma Adaptativa de Aprendizaje de Python. Universidad de Guadalajara / CUCEI.</p>
      </footer>
    </div>
  );
};