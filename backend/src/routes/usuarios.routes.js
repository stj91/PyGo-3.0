import { Router } from 'express';
import { actualizarConfiguracion } from '../controllers/usuarios.controller.js';

const router = Router();

router.put('/configuracion/:id', actualizarConfiguracion);

export default router;