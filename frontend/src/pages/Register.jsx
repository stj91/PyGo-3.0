import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { IconCode, IconUser, IconMail, IconLock, IconSchool, IconBuildingStore, IconArrowRight, IconLogin, IconAlertCircle, IconChevronDown, IconLoader2, IconRefresh } from '@tabler/icons-react';

export const Register = () => {
  const navigate = useNavigate();
  const { loginUser, setNetworkError } = useUser();
  const [formData, setFormData] = useState({
    nombre: '',
    email: '',
    password: '',
    // Ids, no texto: la carrera y el centro son claves ajenas a sus catálogos.
    // Vacío de partida para obligar a elegir en vez de dejar un valor por
    // defecto que la mayoría enviaría sin leer.
    carrera_id: '',
    centro_id: ''
  });
  const [carreras, setCarreras] = useState([]);
  const [centros, setCentros] = useState([]);
  const [cargandoCatalogos, setCargandoCatalogos] = useState(true);
  const [errorCatalogos, setErrorCatalogos] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const cargarCatalogos = useCallback(async () => {
    setCargandoCatalogos(true);
    setErrorCatalogos('');
    try {
      // En paralelo: son dos lecturas independientes y así el formulario se
      // habilita en un viaje de red en lugar de dos.
      const [resCarreras, resCentros] = await Promise.all([
        api.getCarreras(),
        api.getCentros()
      ]);
      setCarreras(resCarreras?.carreras ?? []);
      setCentros(resCentros?.centros ?? []);
    } catch (err) {
      if (err.isNetworkError) setNetworkError(true);
      // No se cae a campos de texto libre: es justo lo que generó los datos
      // inconsistentes que estos desplegables vienen a corregir.
      setErrorCatalogos('No se pudieron cargar las carreras y los centros.');
      setCarreras([]);
      setCentros([]);
    } finally {
      setCargandoCatalogos(false);
    }
  }, [setNetworkError]);

  useEffect(() => {
    cargarCatalogos();
  }, [cargarCatalogos]);

  const catalogosListos = carreras.length > 0 && centros.length > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      const res = await api.registro({
        email: formData.email,
        password: formData.password,
        nombre: formData.nombre,
        carrera_id: Number(formData.carrera_id),
        centro_id: Number(formData.centro_id)
      });

      if (res.success) {
        loginUser(res.usuario, res.token);
        navigate('/cold-start');
      }
    } catch (err) {
      if (err.isNetworkError) {
        setNetworkError(true);
        setErrorMsg('Error de red al intentar registrar la cuenta.');
      } else {
        setErrorMsg(err.message || 'No se pudo completar el registro. Verifica los datos.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 bg-dot-pattern flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white border border-slate-200/80 rounded-2xl shadow-xl p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-slate-800 text-sky-400 flex items-center justify-center mx-auto shadow-md">
            <IconCode className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Crear Cuenta en PyGo</h2>
          <p className="text-sm text-slate-500">Regístrate para iniciar tu ruta adaptativa en Python</p>
        </div>

        {errorMsg && (
          <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-rose-700 text-xs font-semibold">
            <IconAlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">Nombre Completo</label>
            <div className="relative">
              <IconUser className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                required
                placeholder="Carlos Ramírez"
                value={formData.nombre}
                onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">Correo Electrónico</label>
            <div className="relative">
              <IconMail className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="email"
                required
                placeholder="estudiante@alumnos.udg.mx"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">Contraseña</label>
            <div className="relative">
              <IconLock className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
          </div>

          {errorCatalogos && (
            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs space-y-2">
              <div className="flex items-center gap-2 font-semibold">
                <IconAlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorCatalogos}</span>
              </div>
              <button
                type="button"
                onClick={cargarCatalogos}
                className="inline-flex items-center gap-1.5 font-semibold text-amber-900 hover:text-amber-950 underline underline-offset-2"
              >
                <IconRefresh className="w-3.5 h-3.5" />
                <span>Reintentar</span>
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="carrera" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">Carrera</label>
              <div className="relative">
                <IconSchool className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <select
                  id="carrera"
                  required
                  disabled={cargandoCatalogos || carreras.length === 0}
                  value={formData.carrera_id}
                  onChange={(e) => setFormData({ ...formData, carrera_id: e.target.value })}
                  className="w-full pl-10 pr-9 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm appearance-none disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                >
                  <option value="" disabled>
                    {cargandoCatalogos ? 'Cargando...' : 'Selecciona tu carrera'}
                  </option>
                  {carreras.map((carrera) => (
                    <option key={carrera.id} value={carrera.id}>
                      {carrera.nombre}
                    </option>
                  ))}
                </select>
                {cargandoCatalogos ? (
                  <IconLoader2 className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 animate-spin" />
                ) : (
                  <IconChevronDown className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                )}
              </div>
            </div>

            <div>
              <label htmlFor="centro" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">Centro Universitario</label>
              <div className="relative">
                <IconBuildingStore className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <select
                  id="centro"
                  required
                  disabled={cargandoCatalogos || centros.length === 0}
                  value={formData.centro_id}
                  onChange={(e) => setFormData({ ...formData, centro_id: e.target.value })}
                  className="w-full pl-10 pr-9 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm appearance-none disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                >
                  <option value="" disabled>
                    {cargandoCatalogos ? 'Cargando...' : 'Selecciona tu centro'}
                  </option>
                  {centros.map((centro) => (
                    <option key={centro.id} value={centro.id}>
                      {centro.nombre}
                    </option>
                  ))}
                </select>
                {cargandoCatalogos ? (
                  <IconLoader2 className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 animate-spin" />
                ) : (
                  <IconChevronDown className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                )}
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !catalogosListos}
            className="w-full bg-slate-800 hover:bg-slate-900 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md mt-2"
          >
            <span>{loading ? 'Creando cuenta...' : 'Crear Cuenta e Iniciar Diagnóstico'}</span>
            <IconArrowRight className="w-5 h-5" />
          </button>
        </form>

        <div className="pt-4 border-t border-slate-100 text-center">
          <button
            onClick={() => navigate('/login')}
            className="text-xs font-semibold text-sky-600 hover:text-sky-700 transition-colors inline-flex items-center gap-1.5"
          >
            <IconLogin className="w-4 h-4" />
            <span>¿Ya tienes una cuenta? Inicia Sesión</span>
          </button>
        </div>
      </div>
    </div>
  );
};