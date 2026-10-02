/**
 * app.js — Controlador de la Interfaz PWA y Sincronización
 * Digitalizador de Fichas de Caracterización y Pre/Post Test — Owen Badel Hooker
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------
  // ESTADO DE LA APLICACIÓN
  // -------------------------------------------------------------
  const state = {
    mode: 'ficha',         // 'ficha' o 'test'
    currentStep: 1,        // Ficha: 1 (Anverso), 2 (Reverso), 3 (Lista). Test: 1 (Foto), 2 (Lista)
    
    // Fotos Ficha
    foto1Blob: null,
    foto2Blob: null,
    foto1Mime: 'image/jpeg',
    foto2Mime: 'image/jpeg',

    // Foto Test (Hoja Única)
    fotoTestBlob: null,
    fotoTestMime: 'image/jpeg',
    tipoEvaluacion: 'AUTO', // 'AUTO', 'PRE-TEST', 'POST-TEST'

    isSyncing: false
  };

  // -------------------------------------------------------------
  // REFERENCIAS DOM
  // -------------------------------------------------------------
  // Header y Modos
  const tabModoFicha = document.getElementById('tabModoFicha');
  const tabModoTest = document.getElementById('tabModoTest');
  const btnOpenParticipants = document.getElementById('btnOpenParticipants');
  const headerParticipantsCount = document.getElementById('headerParticipantsCount');
  const netStatusBadge = document.getElementById('netStatusBadge');
  const netStatusText = document.getElementById('netStatusText');
  const brandSubtitle = document.getElementById('brandSubtitle');

  // Selector Tipo de Test
  const testTypeBar = document.getElementById('testTypeBar');
  const pillBtns = document.querySelectorAll('.pill-btn');

  // Banner
  const stepTag = document.getElementById('stepTag');
  const stepTitle = document.getElementById('stepTitle');
  const stepDesc = document.getElementById('stepDesc');
  const stepBadge = document.getElementById('stepCounterBadge');

  // Visores de Fotos
  const photosGridFicha = document.getElementById('photosGridFicha');
  const slotFoto1 = document.getElementById('slotFoto1');
  const slotFoto2 = document.getElementById('slotFoto2');
  const placeholderFoto1 = document.getElementById('placeholderFoto1');
  const placeholderFoto2 = document.getElementById('placeholderFoto2');
  const imgPreview1 = document.getElementById('imgPreview1');
  const imgPreview2 = document.getElementById('imgPreview2');
  const badgeCheck1 = document.getElementById('badgeCheck1');
  const badgeCheck2 = document.getElementById('badgeCheck2');
  const slotActions1 = document.getElementById('slotActions1');
  const slotActions2 = document.getElementById('slotActions2');
  const btnRotate1 = document.getElementById('btnRotate1');
  const btnRotate2 = document.getElementById('btnRotate2');
  const btnRetake1 = document.getElementById('btnRetake1');
  const btnRetake2 = document.getElementById('btnRetake2');

  const photosSingleTest = document.getElementById('photosSingleTest');
  const slotFotoTest = document.getElementById('slotFotoTest');
  const placeholderFotoTest = document.getElementById('placeholderFotoTest');
  const imgPreviewTest = document.getElementById('imgPreviewTest');
  const badgeCheckTest = document.getElementById('badgeCheckTest');
  const slotActionsTest = document.getElementById('slotActionsTest');
  const btnRotateTest = document.getElementById('btnRotateTest');
  const btnRetakeTest = document.getElementById('btnRetakeTest');

  // Disparador de Cámara
  const cameraTriggerSection = document.getElementById('cameraTriggerSection');
  const btnMainCamera = document.getElementById('btnMainCamera');
  const shutterLabel = document.getElementById('shutterLabel');
  const cameraInput1 = document.getElementById('cameraInput1');
  const cameraInput2 = document.getElementById('cameraInput2');
  const cameraInputTest = document.getElementById('cameraInputTest');

  // Caja de Acción
  const readyActionBox = document.getElementById('readyActionBox');
  const readyIcon = document.getElementById('readyIcon');
  const readyTitle = document.getElementById('readyTitle');
  const readySubtitle = document.getElementById('readySubtitle');
  const btnEnviarAhora = document.getElementById('btnEnviarAhora');
  const btnGuardarEnCola = document.getElementById('btnGuardarEnCola');
  const btnCancelarEncuesta = document.getElementById('btnCancelarEncuesta');

  // Barra de Cola y Drawer
  const bottomQueueBar = document.getElementById('bottomQueueBar');
  const queueCountBadge = document.getElementById('queueCountBadge');
  const queueLabel = document.getElementById('queueLabel');
  const btnSyncAllNow = document.getElementById('btnSyncAllNow');
  const btnOpenDrawer = document.getElementById('btnOpenDrawer');

  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const drawerContainer = document.getElementById('drawerContainer');
  const btnCloseDrawer = document.getElementById('btnCloseDrawer');
  const drawerQueueList = document.getElementById('drawerQueueList');
  const btnLimpiarCompletadas = document.getElementById('btnLimpiarCompletadas');

  // Modal Participantes
  const participantsBackdrop = document.getElementById('participantsBackdrop');
  const participantsModal = document.getElementById('participantsModal');
  const btnCloseParticipants = document.getElementById('btnCloseParticipants');
  const csvFileInput = document.getElementById('csvFileInput');
  const btnUploadCsv = document.getElementById('btnUploadCsv');
  const statTotalParticipantes = document.getElementById('statTotalParticipantes');
  const statTotalMunicipios = document.getElementById('statTotalMunicipios');
  const participantsBreakdown = document.getElementById('participantsBreakdown');

  // Modal Procesamiento y Toasts
  const processingModal = document.getElementById('processingModal');
  const procTitle = document.getElementById('procTitle');
  const procDesc = document.getElementById('procDesc');
  const toastContainer = document.getElementById('toastContainer');

  // -------------------------------------------------------------
  // TOASTS DE NOTIFICACIÓN
  // -------------------------------------------------------------
  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span>${type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️')}</span>
      <span>${message}</span>
    `;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  // -------------------------------------------------------------
  // CAMBIO DE MODO: FICHA VS TEST
  // -------------------------------------------------------------
  tabModoFicha.addEventListener('click', () => cambiarModo('ficha'));
  tabModoTest.addEventListener('click', () => cambiarModo('test'));

  function cambiarModo(nuevoModo) {
    if (state.mode === nuevoModo) return;
    state.mode = nuevoModo;

    if (nuevoModo === 'ficha') {
      tabModoFicha.classList.add('active');
      tabModoTest.classList.remove('active');
      testTypeBar.style.display = 'none';
      photosGridFicha.style.display = 'grid';
      photosSingleTest.style.display = 'none';
      brandSubtitle.textContent = 'Fichas de Caracterización';
      resetFichaForm();
    } else {
      tabModoTest.classList.add('active');
      tabModoFicha.classList.remove('active');
      testTypeBar.style.display = 'flex';
      photosGridFicha.style.display = 'none';
      photosSingleTest.style.display = 'flex';
      brandSubtitle.textContent = 'Pre-Test y Post-Test (Anexo 4)';
      resetTestForm();
    }
  }

  // Selección de tipo de evaluación (AUTO / PRE-TEST / POST-TEST)
  pillBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      pillBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.tipoEvaluacion = btn.getAttribute('data-type');
      actualizarEtiquetaTest();
    });
  });

  function actualizarEtiquetaTest() {
    if (state.mode !== 'test') return;
    const tipo = state.tipoEvaluacion;
    if (state.fotoTestBlob) {
      stepTag.textContent = tipo === 'AUTO' ? 'Test Listo (Auto IA)' : `${tipo} Listo`;
      shutterLabel.textContent = 'Listo para procesar';
    } else {
      stepTag.textContent = tipo === 'AUTO' ? 'Hoja Única (Auto IA)' : `Hoja Única (${tipo})`;
      shutterLabel.textContent = tipo === 'AUTO' ? 'Tomar Foto del Test' : `Tomar Foto ${tipo}`;
    }
  }

  // -------------------------------------------------------------
  // DISPARADOR DE CÁMARA ERGONÓMICO
  // -------------------------------------------------------------
  function dispararCamara() {
    try {
      if (state.mode === 'ficha') {
        if (state.currentStep === 1) {
          if (cameraInput1) { cameraInput1.value = ''; cameraInput1.click(); }
        } else if (state.currentStep === 2) {
          if (cameraInput2) { cameraInput2.value = ''; cameraInput2.click(); }
        } else {
          showToast('Fotos listas. Elige "Sincronizar Ahora" o "Mandar a la Cola" abajo.', 'info');
        }
      } else {
        // Modo Test
        if (!state.fotoTestBlob) {
          if (cameraInputTest) { cameraInputTest.value = ''; cameraInputTest.click(); }
        } else {
          showToast('Foto del test lista. Elige "Sincronizar Ahora" o "Mandar a la Cola" abajo.', 'info');
        }
      }
    } catch (err) {
      console.error('Error al abrir la cámara:', err);
      showToast('Error al abrir la cámara: ' + err.message, 'error');
    }
  }

  if (btnMainCamera) {
    btnMainCamera.addEventListener('click', (e) => {
      e.preventDefault();
      dispararCamara();
    });
  }

  // Clicks directos en slots (solo abren cámara si aún no hay foto capturada)
  if (slotFoto1) slotFoto1.addEventListener('click', (e) => {
    if (e.target.closest('.slot-actions')) return;
    if (!state.foto1Blob && cameraInput1) { cameraInput1.value = ''; cameraInput1.click(); }
  });
  if (slotFoto2) slotFoto2.addEventListener('click', (e) => {
    if (e.target.closest('.slot-actions')) return;
    if (!state.foto2Blob && cameraInput2) { cameraInput2.value = ''; cameraInput2.click(); }
  });
  if (slotFotoTest) slotFotoTest.addEventListener('click', (e) => {
    if (e.target.closest('.slot-actions')) return;
    if (!state.fotoTestBlob && cameraInputTest) { cameraInputTest.value = ''; cameraInputTest.click(); }
  });

  if (btnRetake1) btnRetake1.addEventListener('click', (e) => { e.stopPropagation(); if (cameraInput1) { cameraInput1.value = ''; cameraInput1.click(); } });
  if (btnRetake2) btnRetake2.addEventListener('click', (e) => { e.stopPropagation(); if (cameraInput2) { cameraInput2.value = ''; cameraInput2.click(); } });
  if (btnRetakeTest) btnRetakeTest.addEventListener('click', (e) => { e.stopPropagation(); if (cameraInputTest) { cameraInputTest.value = ''; cameraInputTest.click(); } });

  if (btnRotate1) btnRotate1.addEventListener('click', (e) => { e.stopPropagation(); rotarFoto(1); });
  if (btnRotate2) btnRotate2.addEventListener('click', (e) => { e.stopPropagation(); rotarFoto(2); });
  if (btnRotateTest) btnRotateTest.addEventListener('click', (e) => { e.stopPropagation(); rotarFoto('test'); });

  // -------------------------------------------------------------
  // ORIENTACIÓN VERTICAL AUTOMÁTICA Y RESOLUCIÓN ULTRA ALTA (3200px)
  // -------------------------------------------------------------
  async function cargarImagenElemento(fileOrBlob) {
    if (typeof createImageBitmap === 'function') {
      try {
        const bmp = await createImageBitmap(fileOrBlob, { imageOrientation: 'from-image' });
        return {
          source: bmp,
          width: bmp.width,
          height: bmp.height,
          close: () => bmp.close()
        };
      } catch (err) {
        console.warn('createImageBitmap no disponible o falló, usando Image fallback:', err);
      }
    }
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(fileOrBlob);
      img.onload = () => {
        resolve({
          source: img,
          width: img.naturalWidth || img.width,
          height: img.naturalHeight || img.height,
          close: () => URL.revokeObjectURL(url)
        });
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e);
      };
      img.src = url;
    });
  }

  async function procesarYOrientarImagen(fileOrBlob, maxDimension = 3200, quality = 0.95, forceRotate90 = false) {
    if (!fileOrBlob) return fileOrBlob;

    const imgData = await cargarImagenElemento(fileOrBlob);
    const srcW = imgData.width;
    const srcH = imgData.height;

    // Si la imagen es horizontal (ancho > alto), se orienta automáticamente a vertical rotando 90° en sentido horario.
    // También se rota 90° si forceRotate90 es true (botón manual de rotación).
    const esHorizontal = srcW > srcH;
    const debeRotar = forceRotate90 || esHorizontal;

    // Si rota 90°, se intercambian ancho y alto
    let targetW = debeRotar ? srcH : srcW;
    let targetH = debeRotar ? srcW : srcH;

    // Escalar si sobrepasa la dimensión máxima manteniendo nitidez forense
    if (Math.max(targetW, targetH) > maxDimension) {
      if (targetW > targetH) {
        targetH = Math.round((targetH * maxDimension) / targetW);
        targetW = maxDimension;
      } else {
        targetW = Math.round((targetW * maxDimension) / targetH);
        targetH = maxDimension;
      }
    }

    const canvas = document.createElement('canvas');
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';

    if (debeRotar) {
      // Rotar 90° en sentido horario
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate(90 * Math.PI / 180);
      const scale = targetW / srcH;
      const drawW = srcW * scale;
      const drawH = srcH * scale;
      ctx.drawImage(imgData.source, -drawW / 2, -drawH / 2, drawW, drawH);
    } else {
      ctx.drawImage(imgData.source, 0, 0, targetW, targetH);
    }

    if (typeof imgData.close === 'function') {
      imgData.close();
    }

    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        resolve(blob || fileOrBlob);
      }, 'image/jpeg', quality);
    });
  }

  // Rotación manual asistida de 90° en cualquier ranura
  async function rotarFoto(tipo) {
    let currentBlob = null;
    let previewEl = null;

    if (tipo === 1) {
      currentBlob = state.foto1Blob;
      previewEl = imgPreview1;
    } else if (tipo === 2) {
      currentBlob = state.foto2Blob;
      previewEl = imgPreview2;
    } else if (tipo === 'test') {
      currentBlob = state.fotoTestBlob;
      previewEl = imgPreviewTest;
    }

    if (!currentBlob || !previewEl) return;

    try {
      showToast('Rotando 90°...', 'info');
      const rotatedBlob = await procesarYOrientarImagen(currentBlob, 3200, 0.95, true);
      const newUrl = URL.createObjectURL(rotatedBlob);
      previewEl.src = newUrl;

      if (tipo === 1) state.foto1Blob = rotatedBlob;
      else if (tipo === 2) state.foto2Blob = rotatedBlob;
      else if (tipo === 'test') state.fotoTestBlob = rotatedBlob;

      showToast('Foto rotada 90° exitosamente.', 'success');
    } catch (err) {
      console.error('Error al rotar foto:', err);
      showToast('Error al rotar foto: ' + err.message, 'error');
    }
  }

  // -------------------------------------------------------------
  // PROCESAMIENTO DE FOTOS: MODO FICHA
  // -------------------------------------------------------------
  cameraInput1.addEventListener('change', async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    try {
      showToast('Procesando foto 1...', 'info');
      const verticalBlob = await procesarYOrientarImagen(file, 3200, 0.95, false);
      const previewUrl = URL.createObjectURL(verticalBlob);

      imgPreview1.src = previewUrl;
      imgPreview1.style.display = 'block';
      placeholderFoto1.style.display = 'none';
      badgeCheck1.style.display = 'flex';
      if (slotActions1) slotActions1.style.display = 'flex';
      slotFoto1.classList.remove('active-slot');
      slotFoto1.classList.add('completed');

      state.foto1Blob = verticalBlob;
      state.foto1Mime = 'image/jpeg';

      if (!state.foto2Blob) setStepFicha(2);
      else setStepFicha(3);
    } catch (err) {
      console.error('Error procesando foto 1:', err);
      showToast('Error procesando foto: ' + err.message, 'error');
    }
  });

  cameraInput2.addEventListener('change', async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    try {
      showToast('Procesando foto 2...', 'info');
      const verticalBlob = await procesarYOrientarImagen(file, 3200, 0.95, false);
      const previewUrl = URL.createObjectURL(verticalBlob);

      imgPreview2.src = previewUrl;
      imgPreview2.style.display = 'block';
      placeholderFoto2.style.display = 'none';
      badgeCheck2.style.display = 'flex';
      if (slotActions2) slotActions2.style.display = 'flex';
      slotFoto2.classList.remove('active-slot');
      slotFoto2.classList.add('completed');

      state.foto2Blob = verticalBlob;
      state.foto2Mime = 'image/jpeg';

      if (state.foto1Blob) setStepFicha(3);
      else setStepFicha(1);
    } catch (err) {
      console.error('Error procesando foto 2:', err);
      showToast('Error procesando foto: ' + err.message, 'error');
    }
  });

  function setStepFicha(step) {
    state.currentStep = step;
    if (step === 1) {
      stepTag.textContent = 'Paso 1 de 2';
      stepTitle.textContent = 'Foto 1: Anverso (Frente)';
      stepDesc.textContent = 'Enfoca la cara frontal de la ficha con buena iluminación.';
      stepBadge.textContent = '1/2';
      shutterLabel.textContent = 'Tomar Foto 1 (Anverso)';
      slotFoto1.classList.add('active-slot');
      slotFoto2.classList.remove('active-slot');
      cameraTriggerSection.style.display = 'flex';
      readyActionBox.style.display = 'none';
    } else if (step === 2) {
      stepTag.textContent = 'Paso 2 de 2';
      stepTitle.textContent = 'Foto 2: Reverso (Atrás)';
      stepDesc.textContent = 'Gira la ficha y fotografía la parte posterior.';
      stepBadge.textContent = '2/2';
      shutterLabel.textContent = 'Tomar Foto 2 (Reverso)';
      slotFoto2.classList.add('active-slot');
      slotFoto1.classList.remove('active-slot');
      cameraTriggerSection.style.display = 'flex';
      readyActionBox.style.display = 'none';
    } else if (step === 3) {
      stepTag.textContent = '¡Fotos Listas!';
      stepTitle.textContent = 'Encuesta Completa (2/2 Fotos)';
      stepDesc.textContent = 'Verifica las fotos y elige cómo registrarla.';
      stepBadge.textContent = '✔';
      readyIcon.textContent = '📋';
      readyTitle.textContent = 'Fotos Listas (2/2)';
      readySubtitle.textContent = 'Selecciona la acción para esta ficha:';
      cameraTriggerSection.style.display = 'none';
      readyActionBox.style.display = 'flex';
      readyActionBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function resetFichaForm() {
    state.foto1Blob = null;
    state.foto2Blob = null;
    cameraInput1.value = '';
    cameraInput2.value = '';

    imgPreview1.src = '';
    imgPreview1.style.display = 'none';
    placeholderFoto1.style.display = 'flex';
    badgeCheck1.style.display = 'none';
    if (slotActions1) slotActions1.style.display = 'none';
    slotFoto1.className = 'photo-slot active-slot';

    imgPreview2.src = '';
    imgPreview2.style.display = 'none';
    placeholderFoto2.style.display = 'flex';
    badgeCheck2.style.display = 'none';
    if (slotActions2) slotActions2.style.display = 'none';
    slotFoto2.className = 'photo-slot';

    cameraTriggerSection.style.display = 'flex';
    readyActionBox.style.display = 'none';
    setStepFicha(1);
  }

  // -------------------------------------------------------------
  // PROCESAMIENTO DE FOTOS: MODO TEST (1 SOLA FOTO)
  // -------------------------------------------------------------
  cameraInputTest.addEventListener('change', async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    try {
      showToast('Procesando test...', 'info');
      const verticalBlob = await procesarYOrientarImagen(file, 3200, 0.95, false);
      const previewUrl = URL.createObjectURL(verticalBlob);

      imgPreviewTest.src = previewUrl;
      imgPreviewTest.style.display = 'block';
      placeholderFotoTest.style.display = 'none';
      badgeCheckTest.style.display = 'flex';
      if (slotActionsTest) slotActionsTest.style.display = 'flex';
      slotFotoTest.classList.remove('active-slot');
      slotFotoTest.classList.add('completed');

      state.fotoTestBlob = verticalBlob;
      state.fotoTestMime = 'image/jpeg';

      setStepTestReady();
    } catch (err) {
      console.error('Error procesando test:', err);
      showToast('Error procesando test: ' + err.message, 'error');
    }
  });

  function setStepTestReady() {
    const tipo = state.tipoEvaluacion === 'AUTO' ? 'Pre/Post Test' : state.tipoEvaluacion;
    stepTag.textContent = '¡Foto Lista!';
    stepTitle.textContent = `${tipo} (Hoja Única)`;
    stepDesc.textContent = 'Verifica la nitidez y selecciona una acción.';
    stepBadge.textContent = '✔';

    readyIcon.textContent = '📝';
    readyTitle.textContent = 'Test Listo (1/1 Foto)';
    readySubtitle.textContent = `Evaluación: ${state.tipoEvaluacion}. Elige la acción:`;

    cameraTriggerSection.style.display = 'none';
    readyActionBox.style.display = 'flex';
    readyActionBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function resetTestForm() {
    state.fotoTestBlob = null;
    cameraInputTest.value = '';

    imgPreviewTest.src = '';
    imgPreviewTest.style.display = 'none';
    placeholderFotoTest.style.display = 'flex';
    badgeCheckTest.style.display = 'none';
    if (slotActionsTest) slotActionsTest.style.display = 'none';
    slotFotoTest.className = 'photo-slot photo-slot-single active-slot';

    stepTag.textContent = 'Hoja Única';
    stepTitle.textContent = 'Tomar Foto del Test';
    stepDesc.textContent = 'Enfoca la hoja completa del Pre-Test o Post-Test con buena luz.';
    stepBadge.textContent = '1/1';
    shutterLabel.textContent = 'Tomar Foto del Test';

    cameraTriggerSection.style.display = 'flex';
    readyActionBox.style.display = 'none';
    actualizarEtiquetaTest();
  }

  // -------------------------------------------------------------
  // BOTONES DE ACCIÓN (SINCRONIZAR, GUARDAR EN COLA, DESCARTAR)
  // -------------------------------------------------------------
  btnCancelarEncuesta.addEventListener('click', () => {
    if (confirm('¿Deseas descartar la captura actual?')) {
      if (state.mode === 'ficha') resetFichaForm();
      else resetTestForm();
      showToast('Captura descartada.', 'info');
    }
  });

  btnEnviarAhora.addEventListener('click', () => {
    ejecutarEnvioInmediato();
  });

  btnGuardarEnCola.addEventListener('click', () => {
    ejecutarGuardadoEnCola();
  });

  // -------------------------------------------------------------
  // ENVÍO EN MODO INMEDIATO
  // -------------------------------------------------------------
  async function ejecutarEnvioInmediato() {
    if (state.mode === 'ficha') {
      if (!state.foto1Blob || !state.foto2Blob) {
        showToast('Debes tomar ambas fotos de la ficha antes de enviar.', 'error');
        return;
      }
    } else {
      if (!state.fotoTestBlob) {
        showToast('Debes tomar la foto del test antes de enviar.', 'error');
        return;
      }
    }

    if (!navigator.onLine) {
      showToast('Sin conexión a Internet. Guardando automáticamente en Modo Cola.', 'error');
      await ejecutarGuardadoEnCola();
      return;
    }

    if (state.mode === 'ficha') {
      mostrarModalProcesamiento('Extrayendo Ficha con IA', 'Analizando 43 variables, checkboxes manuscritos y subiendo a Google Sheets...');
      try {
        const formData = new FormData();
        formData.append('foto_anverso', state.foto1Blob, 'anverso.jpg');
        formData.append('foto_reverso', state.foto2Blob, 'reverso.jpg');
        formData.append('modo', 'inmediato');

        const response = await fetch('/api/process-survey', {
          method: 'POST',
          body: formData
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(data.detail || data.error || 'Error en el servidor');
        }

        ocultarModalProcesamiento();
        showToast(`¡Éxito! Registrada ficha de: ${data.participante || 'Participante'}`, 'success');
        resetFichaForm();
        cargarResumenParticipantes();

      } catch (error) {
        console.error('Error en envío inmediato de ficha:', error);
        ocultarModalProcesamiento();
        showToast(`Error al procesar: ${error.message}. Se guardará en cola local.`, 'error');
        await ejecutarGuardadoEnCola();
      }

    } else {
      // Modo Test
      mostrarModalProcesamiento('Extrayendo Pre/Post Test con IA', 'Digitalizando respuestas, reconciliando con base de participantes y subiendo a Google Sheets...');
      try {
        const formData = new FormData();
        formData.append('foto_test', state.fotoTestBlob, 'test.jpg');
        if (state.tipoEvaluacion && state.tipoEvaluacion !== 'AUTO') {
          formData.append('tipo_evaluacion', state.tipoEvaluacion);
        }
        formData.append('modo', 'inmediato');

        const response = await fetch('/api/process-test', {
          method: 'POST',
          body: formData
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(data.detail || data.error || 'Error en el servidor');
        }

        ocultarModalProcesamiento();
        showToast(`¡Éxito! ${data.tipo_evaluacion} registrado: ${data.participante} (${data.municipio})`, 'success');
        resetTestForm();

      } catch (error) {
        console.error('Error en envío inmediato de test:', error);
        ocultarModalProcesamiento();
        showToast(`Error al procesar: ${error.message}. Se guardará en cola local.`, 'error');
        await ejecutarGuardadoEnCola();
      }
    }
  }

  // -------------------------------------------------------------
  // GUARDADO EN MODO COLA (INDEXEDDB)
  // -------------------------------------------------------------
  async function ejecutarGuardadoEnCola() {
    try {
      if (state.mode === 'ficha') {
        if (!state.foto1Blob || !state.foto2Blob) {
          showToast('Debes tomar ambas fotos de la ficha.', 'error');
          return;
        }
        await window.surveyDB.guardarEncuesta(
          state.foto1Blob,
          state.foto2Blob,
          state.foto1Mime,
          state.foto2Mime
        );
        resetFichaForm();
      } else {
        if (!state.fotoTestBlob) {
          showToast('Debes tomar la foto del test.', 'error');
          return;
        }
        await window.surveyDB.guardarTest(
          state.fotoTestBlob,
          state.fotoTestMime,
          state.tipoEvaluacion
        );
        resetTestForm();
      }

      await actualizarContadorCola();
      const count = await window.surveyDB.contarPendientes();
      showToast(`📦 Registro guardado en la cola local (${count} pendientes).`, 'success');
    } catch (err) {
      console.error('Error guardando en IDB:', err);
      showToast('Error al guardar en el dispositivo: ' + err.message, 'error');
    }
  }

  // -------------------------------------------------------------
  // SINCRONIZAR TODA LA COLA (BATCH MULTI-FORMATO)
  // -------------------------------------------------------------
  btnSyncAllNow.addEventListener('click', sincronizarColaCompleta);

  async function sincronizarColaCompleta() {
    if (!navigator.onLine) {
      showToast('No tienes conexión a Internet para sincronizar.', 'error');
      return;
    }

    const pendientes = await window.surveyDB.obtenerPendientes();
    if (pendientes.length === 0) {
      showToast('No hay registros pendientes en la cola.', 'info');
      return;
    }

    state.isSyncing = true;
    btnSyncAllNow.disabled = true;

    let exitosas = 0;
    let fallidas = 0;
    const total = pendientes.length;

    mostrarModalProcesamiento('Sincronizando Lote en Cola', `Procesando registro 1 de ${total}...`);

    for (let i = 0; i < total; i++) {
      const item = pendientes[i];
      const esTest = item.tipo === 'test';
      procDesc.textContent = `Procesando ${esTest ? 'Test' : 'Ficha'} ${i + 1} de ${total}... (IA + Google Sheets)`;

      try {
        await window.surveyDB.actualizarEstado(item.id, 'syncing');

        let resp;
        if (esTest) {
          const formData = new FormData();
          formData.append('foto_test', item.anversoBlob || item.fotoBlob, 'test.jpg');
          if (item.tipoEvaluacion && item.tipoEvaluacion !== 'AUTO') {
            formData.append('tipo_evaluacion', item.tipoEvaluacion);
          }
          formData.append('modo', 'batch');

          resp = await fetch('/api/process-test', {
            method: 'POST',
            body: formData
          });
        } else {
          const formData = new FormData();
          formData.append('foto_anverso', item.anversoBlob, 'anverso.jpg');
          formData.append('foto_reverso', item.reversoBlob, 'reverso.jpg');
          formData.append('modo', 'batch');

          resp = await fetch('/api/process-survey', {
            method: 'POST',
            body: formData
          });
        }

        const resData = await resp.json();

        if (resp.ok && resData.success) {
          await window.surveyDB.actualizarEstado(item.id, 'synced', {
            extractedData: resData.datos_extraidos,
            sheetsResult: resData.sheets_result
          });
          exitosas++;
        } else {
          throw new Error(resData.detail || resData.error || 'Error de servidor');
        }
      } catch (err) {
        console.error(`Error sincronizando item ${item.id}:`, err);
        await window.surveyDB.actualizarEstado(item.id, 'error', { errorMsg: err.message });
        fallidas++;
      }
    }

    state.isSyncing = false;
    ocultarModalProcesamiento();
    await actualizarContadorCola();
    await renderizarListaDrawer();
    cargarResumenParticipantes();

    if (fallidas === 0) {
      showToast(`🚀 ¡Completado! Se sincronizaron los ${exitosas} registros con Google Sheets.`, 'success');
    } else {
      showToast(`Sincronización terminada: ${exitosas} exitosas, ${fallidas} con error.`, 'error');
    }
  }

  // -------------------------------------------------------------
  // CONTADOR Y DRAWER DE LA COLA LOCAL
  // -------------------------------------------------------------
  async function actualizarContadorCola() {
    try {
      if (window.surveyDB) {
        const count = await window.surveyDB.contarPendientes();
        queueCountBadge.textContent = count;
        queueLabel.textContent = `${count} ${count === 1 ? 'registro pendiente' : 'registros pendientes'}`;
        btnSyncAllNow.disabled = (count === 0 || !navigator.onLine || state.isSyncing);
      }
    } catch (err) {
      console.error('Error consultando cola:', err);
    }
  }
  actualizarContadorCola();

  btnOpenDrawer.addEventListener('click', async () => {
    await renderizarListaDrawer();
    drawerBackdrop.style.display = 'block';
    drawerContainer.style.display = 'flex';
  });

  btnCloseDrawer.addEventListener('click', cerrarDrawer);
  drawerBackdrop.addEventListener('click', cerrarDrawer);

  function cerrarDrawer() {
    drawerBackdrop.style.display = 'none';
    drawerContainer.style.display = 'none';
  }

  async function renderizarListaDrawer() {
    drawerQueueList.innerHTML = '';
    const items = await window.surveyDB.obtenerTodas();

    if (items.length === 0) {
      drawerQueueList.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 24px 0;">
          No tienes registros en la cola local.
        </div>
      `;
      return;
    }

    items.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = 'queue-item-card';

      const esTest = item.tipo === 'test';
      const url1 = URL.createObjectURL(item.anversoBlob || item.fotoBlob);
      const url2 = item.reversoBlob ? URL.createObjectURL(item.reversoBlob) : null;
      const fecha = new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      let statusBadge = '';
      if (item.status === 'pending') statusBadge = '<span style="color: #f59e0b;">⏳ Pendiente</span>';
      else if (item.status === 'syncing') statusBadge = '<span style="color: #06b6d4;">🔄 Sincronizando</span>';
      else if (item.status === 'synced') statusBadge = '<span style="color: #10b981;">✅ Sincronizado</span>';
      else if (item.status === 'error') statusBadge = `<span style="color: #ef4444;" title="${item.errorMsg || ''}">❌ Error</span>`;

      const typeBadge = esTest 
        ? `<span class="badge-item-type badge-type-test">📝 Test (${item.tipoEvaluacion || 'AUTO'})</span>`
        : `<span class="badge-item-type badge-type-ficha">📋 Ficha (2 Fotos)</span>`;

      card.innerHTML = `
        <div class="queue-item-left">
          <div class="item-thumb-pair">
            <img class="item-thumb" src="${url1}" alt="Foto 1">
            ${url2 ? `<img class="item-thumb" src="${url2}" alt="Foto 2">` : ''}
          </div>
          <div class="item-meta">
            ${typeBadge}
            <span>#${items.length - index} • ${fecha}</span>
            <small>${statusBadge}</small>
          </div>
        </div>
        <button class="btn-delete-item" data-id="${item.id}" title="Eliminar de cola">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 7l16 0" /><path d="M10 11l0 6" /><path d="M14 11l0 6" />
            <path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12" />
            <path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3" />
          </svg>
        </button>
      `;

      card.querySelector('.btn-delete-item').addEventListener('click', async (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        if (confirm('¿Eliminar este registro de la cola local?')) {
          await window.surveyDB.eliminarEncuesta(id);
          await actualizarContadorCola();
          await renderizarListaDrawer();
          showToast('Registro eliminado de la cola.', 'info');
        }
      });

      drawerQueueList.appendChild(card);
    });
  }

  btnLimpiarCompletadas.addEventListener('click', async () => {
    const borradas = await window.surveyDB.limpiarSincronizadas();
    await actualizarContadorCola();
    await renderizarListaDrawer();
    showToast(`Se eliminaron ${borradas} registros ya sincronizados.`, 'info');
  });

  // -------------------------------------------------------------
  // MODAL DE BASE DE DATOS DE PARTICIPANTES (IMPORTACIÓN CSV)
  // -------------------------------------------------------------
  btnOpenParticipants.addEventListener('click', async () => {
    await cargarResumenParticipantes();
    participantsBackdrop.style.display = 'block';
    participantsModal.classList.add('open');
  });

  btnCloseParticipants.addEventListener('click', cerrarModalParticipantes);
  participantsBackdrop.addEventListener('click', cerrarModalParticipantes);

  function cerrarModalParticipantes() {
    participantsBackdrop.style.display = 'none';
    participantsModal.classList.remove('open');
  }

  async function cargarResumenParticipantes() {
    try {
      const resp = await fetch('/api/participants');
      if (!resp.ok) return;
      const data = await resp.json();

      headerParticipantsCount.textContent = data.total || 0;
      statTotalParticipantes.textContent = data.total || 0;

      const porMun = data.por_municipio || {};
      const numMuns = Object.keys(porMun).length;
      statTotalMunicipios.textContent = numMuns;

      participantsBreakdown.innerHTML = '';
      if (numMuns === 0) {
        participantsBreakdown.innerHTML = `
          <div style="font-size: 0.72rem; color: var(--text-muted); text-align: center; padding: 10px;">
            Aún no hay participantes en memoria. Sube tu CSV de Google Sheets arriba.
          </div>
        `;
      } else {
        for (const [mun, count] of Object.entries(porMun)) {
          const row = document.createElement('div');
          row.className = 'mun-row';
          row.innerHTML = `
            <span class="mun-name">📍 ${mun}</span>
            <span class="mun-count">${count}</span>
          `;
          participantsBreakdown.appendChild(row);
        }
      }
    } catch (e) {
      console.warn('Error cargando participantes:', e);
    }
  }
  cargarResumenParticipantes();

  btnUploadCsv.addEventListener('click', async () => {
    const file = csvFileInput.files && csvFileInput.files[0];
    if (!file) {
      showToast('Por favor selecciona un archivo .csv para importar.', 'error');
      return;
    }

    mostrarModalProcesamiento('Importando Participantes', 'Indexando nombres, edades, municipios y EPS para coincidencia difusa...');
    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp = await fetch('/api/participants/import', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json();

      ocultarModalProcesamiento();
      if (resp.ok && data.success) {
        showToast(data.message, 'success');
        csvFileInput.value = '';
        await cargarResumenParticipantes();
      } else {
        throw new Error(data.error || 'Error al importar archivo CSV');
      }
    } catch (err) {
      ocultarModalProcesamiento();
      console.error('Error importando CSV:', err);
      showToast('Error al importar CSV: ' + err.message, 'error');
    }
  });

  // -------------------------------------------------------------
  // MONITOREO DE RED (ONLINE / OFFLINE)
  // -------------------------------------------------------------
  function updateNetworkStatus() {
    const isOnline = navigator.onLine;
    if (netStatusBadge && netStatusText) {
      if (isOnline) {
        netStatusBadge.className = 'badge-network';
        netStatusText.textContent = 'Online';
      } else {
        netStatusBadge.className = 'badge-network offline';
        netStatusText.textContent = 'Offline';
      }
    }
    if (!isOnline) {
      showToast('⚠️ Estás sin conexión. Las capturas se guardarán en cola local.', 'error');
    }
  }
  window.addEventListener('online', updateNetworkStatus);
  window.addEventListener('offline', updateNetworkStatus);
  updateNetworkStatus();

  // -------------------------------------------------------------
  // REGISTRO DE SERVICE WORKER (PWA OFFLINE)
  // -------------------------------------------------------------
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
      .then(() => console.log('Service Worker registrado correctamente'))
      .catch((e) => console.warn('Fallo registrando Service Worker:', e));
  }

  // -------------------------------------------------------------
  // MODAL DE PROCESAMIENTO
  // -------------------------------------------------------------
  function mostrarModalProcesamiento(titulo, desc) {
    procTitle.textContent = titulo;
    procDesc.textContent = desc;
    processingModal.style.display = 'flex';
  }

  function ocultarModalProcesamiento() {
    processingModal.style.display = 'none';
  }
});
