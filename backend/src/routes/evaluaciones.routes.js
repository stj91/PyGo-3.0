import { Router } from 'express';
import { evaluarModulo } from '../controllers/evaluaciones.controller.js';

const router = Router();

router.post('/evaluar-modulo', evaluarModulo);

export default router;