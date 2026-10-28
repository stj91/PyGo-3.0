import { Router } from 'express';
import { evaluarColdStart } from '../controllers/coldStart.controller.js';

const router = Router();

router.post('/evaluar', evaluarColdStart);

export default router;