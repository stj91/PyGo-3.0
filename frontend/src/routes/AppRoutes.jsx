import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Vistas Previas Existentes
import { Login } from '../pages/Login';
import { ColdStart } from '../pages/ColdStart';
import { Dashboard } from '../pages/Dashboard';
import { Configuracion } from '../pages/Configuracion';
import { Temario } from '../pages/Temario';

// Vistas Nuevas Integradas
import { LandingPage } from '../pages/LandingPage';
import { Register } from '../pages/Register';
import { CatalogoCursos } from '../pages/CatalogoCursos';
import { DetalleCurso } from '../pages/DetalleCurso';
import { LeccionIndividual } from '../pages/LeccionIndividual';

export const AppRoutes = () => {
  return (
    <Routes>
      {/* Ruta Principal Landing */}
      <Route path="/" element={<LandingPage />} />

      {/* Autenticación y Onboarding */}
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Register />} />
      <Route path="/cold-start" element={<ColdStart />} />

      {/* Aplicación / Tablero */}
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/configuracion" element={<Configuracion />} />
      <Route path="/temario" element={<Temario />} />

      {/* Catálogo de Cursos, Detalle y Lección Individual */}
      <Route path="/cursos" element={<CatalogoCursos />} />
      <Route path="/cursos/:cursoId" element={<DetalleCurso />} />
      <Route path="/cursos/:cursoId/lecciones/:leccionId" element={<LeccionIndividual />} />

      {/* Redirección por defecto */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};