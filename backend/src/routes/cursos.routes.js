import { Router } from 'express';
import { getCursos, getCursoPorId, getLeccionPorId } from '../controllers/cursos.controller.js';

const router = Router();

router.get('/', getCursos);
router.get('/:id', getCursoPorId);
router.get('/lecciones/:id', getLeccionPorId);

export default router;