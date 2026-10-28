import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

import authRoutes from './routes/auth.routes.js';
import coldStartRoutes from './routes/coldStart.routes.js';
import cursosRoutes from './routes/cursos.routes.js';
import evaluacionesRoutes from './routes/evaluaciones.routes.js';
import adaptativoRoutes from './routes/adaptativo.routes.js';
import usuariosRoutes from './routes/usuarios.routes.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

// Configuración de Middlewares
app.use(cors({
  origin: 'http://localhost:5173',
  credentials: true
}));

app.use(express.json());

// Registro de Rutas de la API
app.use('/api/auth', authRoutes);
app.use('/api/cold-start', coldStartRoutes);
app.use('/api/cursos', cursosRoutes);
app.use('/api/lecciones', cursosRoutes); // Soporte alias para GET /api/lecciones/:id
app.use('/api/evaluaciones', evaluacionesRoutes);
app.use('/api/adaptativo', adaptativoRoutes);
app.use('/api/usuarios', usuariosRoutes);

// Endpoint Health Check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', server: 'PyGo Backend API running' });
});

// Middleware Global de Manejo de Errores
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ success: false, error: 'Error interno del servidor.' });
});

// Inicialización del Servidor
app.listen(PORT, () => {
  console.log(`🚀 Servidor backend PyGo ejecutándose en: http://localhost:${PORT}`);
});