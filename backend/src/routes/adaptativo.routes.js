import { Router } from 'express';
import { getEstadoAdaptativo } from '../controllers/adaptativo.controller.js';

const router = Router();

router.get('/estado/:usuario_id', getEstadoAdaptativo);

export default router;