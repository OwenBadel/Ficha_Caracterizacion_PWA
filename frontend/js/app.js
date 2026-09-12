/**
 * app.js — Controlador de la Interfaz PWA y Sincronización
 * Digitalizador de Fichas de Caracterización (Lemon Fábrica)
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------
  // ESTADO DE LA APLICACIÓN
  // -------------------------------------------------------------
  const state = {
    currentStep: 1,    // 1: Foto Anverso, 2: Foto Reverso, 3: Completa
    foto1Blob: null,
    foto2Blob: null,
    foto1Mime: 'image/jpeg',
    foto2Mime: 'image/jpeg',
    isSyncing: false
  };

  // -------------------------------------------------------------
  // REFERENCIAS DOM
  // -------------------------------------------------------------
  const stepTag = document.getElementById('stepTag');
  const stepTitle = document.getElementById('stepTitle');
  const stepDesc = document.getElementById('stepDesc');
  const stepBadge = document.getElementById('stepCounterBadge');

  const slotFoto1 = document.getElementById('slotFoto1');
  const slotFoto2 = document.getElementById('slotFoto2');
  const placeholderFoto1 = document.getElementById('placeholderFoto1');
  const placeholderFoto2 = document.getElementById('placeholderFoto2');
  const imgPreview1 = document.getElementById('imgPreview1');
  const imgPreview2 = document.getElementById('imgPreview2');
  const badgeCheck1 = document.getElementById('badgeCheck1');
  const badgeCheck2 = document.getElementById('badgeCheck2');
  const btnRetake1 = document.getElementById('btnRetake1');
  const btnRetake2 = document.getElementById('btnRetake2');

  const cameraTriggerSection = document.getElementById('cameraTriggerSection');
  const btnMainCamera = document.getElementById('btnMainCamera');
  const shutterLabel = document.getElementById('shutterLabel');
  const cameraInput1 = document.getElementById('cameraInput1');
  const cameraInput2 = document.getElementById('cameraInput2');

  const readyActionBox = document.getElementById('readyActionBox');
  const btnEnviarAhora = document.getElementById('btnEnviarAhora');
  const btnGuardarEnCola = document.getElementById('btnGuardarEnCola');
  const btnCancelarEncuesta = document.getElementById('btnCancelarEncuesta');

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

  const processingModal = document.getElementById('processingModal');
  const procTitle = document.getElementById('procTitle');
  const procDesc = document.getElementById('procDesc');

  const netStatusBadge = document.getElementById('netStatusBadge');
  const netStatusText = document.getElementById('netStatusText');
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
    }, 4000);
  }

  // -------------------------------------------------------------
  // DISPARADOR DE CÁMARA ROBUSTO (SINCRÓNICO E INMEDIATO)
  // -------------------------------------------------------------
  function dispararCamara() {
    try {
      if (state.currentStep === 1) {
        if (cameraInput1) {
          cameraInput1.value = '';
          cameraInput1.click();
        }
      } else if (state.currentStep === 2) {
        if (cameraInput2) {
          cameraInput2.value = '';
          cameraInput2.click();
        }
      } else {
        showToast('Fotos listas. Elige "Sincronizar Ahora" o "Mandar a la Cola" abajo.', 'info');
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

  if (slotFoto1) {
    slotFoto1.addEventListener('click', () => {
      if (cameraInput1) {
        cameraInput1.value = '';
        cameraInput1.click();
      }
    });
  }

  if (slotFoto2) {
    slotFoto2.addEventListener('click', () => {
      if (cameraInput2) {
        cameraInput2.value = '';
        cameraInput2.click();
      }
    });
  }

  if (btnRetake1) {
    btnRetake1.addEventListener('click', (e) => {
      e.stopPropagation();
      if (cameraInput1) {
        cameraInput1.value = '';
        cameraInput1.click();
      }
    });
  }

  if (btnRetake2) {
    btnRetake2.addEventListener('click', (e) => {
      e.stopPropagation();
      if (cameraInput2) {
        cameraInput2.value = '';
        cameraInput2.click();
      }
    });
  }

  // -------------------------------------------------------------
  // MONITOREO DE RED (ONLINE / OFFLINE)
  // -------------------------------------------------------------
  function updateNetworkStatus() {
    const isOnline = navigator.onLine;
    if (isOnline) {
      netStatusBadge.className = 'badge-network';
      netStatusText.textContent = 'Online';
    } else {
      netStatusBadge.className = 'badge-network offline';
      netStatusText.textContent = 'Offline';
      showToast('⚠️ Estás sin conexión. Las encuestas se guardarán en cola local.', 'error');
    }
  }
  window.addEventListener('online', updateNetworkStatus);
  window.addEventListener('offline', updateNetworkStatus);
  updateNetworkStatus();

  // -------------------------------------------------------------
  // REGISTRO DE SERVICE WORKER (PWA OFFLINE - EN SEGUNDO PLANO)
  // -------------------------------------------------------------
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
      .then(() => console.log('Service Worker registrado correctamente'))
      .catch((e) => console.warn('Fallo registrando Service Worker:', e));
  }

  // -------------------------------------------------------------
  // ACTUALIZACIÓN DE LA COLA LOCAL (INDEXEDDB - EN SEGUNDO PLANO)
  // -------------------------------------------------------------
  async function actualizarContadorCola() {
    try {
      if (window.surveyDB) {
        const count = await window.surveyDB.contarPendientes();
        queueCountBadge.textContent = count;
        queueLabel.textContent = `${count} ${count === 1 ? 'encuesta pendiente' : 'encuestas pendientes'}`;
        btnSyncAllNow.disabled = (count === 0 || !navigator.onLine || state.isSyncing);
      }
    } catch (err) {
      console.error('Error consultando cola:', err);
    }
  }
  actualizarContadorCola();

  // Procesamiento Foto 1 (Anverso)
  cameraInput1.addEventListener('change', async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    state.foto1Blob = file;
    state.foto1Mime = file.type || 'image/jpeg';

    const url = URL.createObjectURL(file);
    imgPreview1.src = url;
    imgPreview1.style.display = 'block';
    placeholderFoto1.style.display = 'none';
    badgeCheck1.style.display = 'flex';
    btnRetake1.style.display = 'flex';
    slotFoto1.classList.remove('active-slot');
    slotFoto1.classList.add('completed');

    // Avanzar a Paso 2 si la foto 2 no está tomada
    if (!state.foto2Blob) {
      setStep(2);
    } else {
      setStep(3);
    }
  });

  // Procesamiento Foto 2 (Reverso)
  cameraInput2.addEventListener('change', async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    state.foto2Blob = file;
    state.foto2Mime = file.type || 'image/jpeg';

    const url = URL.createObjectURL(file);
    imgPreview2.src = url;
    imgPreview2.style.display = 'block';
    placeholderFoto2.style.display = 'none';
    badgeCheck2.style.display = 'flex';
    btnRetake2.style.display = 'flex';
    slotFoto2.classList.remove('active-slot');
    slotFoto2.classList.add('completed');

    // Si ambas están listas, pasar al paso 3 sin auto-disparar
    if (state.foto1Blob) {
      setStep(3);
    } else {
      setStep(1);
    }
  });

  function setStep(step) {
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
      shutterLabel.textContent = 'Selecciona una acción abajo';
      slotFoto1.classList.remove('active-slot');
      slotFoto2.classList.remove('active-slot');
      cameraTriggerSection.style.display = 'none';
      readyActionBox.style.display = 'flex';
      readyActionBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // -------------------------------------------------------------
  // REINICIAR FORMULARIO TRAS GUARDAR / ENVIAR
  // -------------------------------------------------------------
  function resetForm() {
    state.foto1Blob = null;
    state.foto2Blob = null;
    cameraInput1.value = '';
    cameraInput2.value = '';

    imgPreview1.src = '';
    imgPreview1.style.display = 'none';
    placeholderFoto1.style.display = 'flex';
    badgeCheck1.style.display = 'none';
    btnRetake1.style.display = 'none';
    slotFoto1.className = 'photo-slot active-slot';

    imgPreview2.src = '';
    imgPreview2.style.display = 'none';
    placeholderFoto2.style.display = 'flex';
    badgeCheck2.style.display = 'none';
    btnRetake2.style.display = 'none';
    slotFoto2.className = 'photo-slot';

    cameraTriggerSection.style.display = 'flex';
    readyActionBox.style.display = 'none';

    setStep(1);
  }

  btnCancelarEncuesta.addEventListener('click', () => {
    if (confirm('¿Deseas descartar las dos fotos actuales?')) {
      resetForm();
      showToast('Encuesta descartada.', 'info');
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
    if (!state.foto1Blob || !state.foto2Blob) {
      showToast('Debes tomar ambas fotos antes de enviar.', 'error');
      return;
    }

    if (!navigator.onLine) {
      showToast('Sin conexión a Internet. Guardando automáticamente en Modo Cola.', 'error');
      await ejecutarGuardadoEnCola();
      return;
    }

    mostrarModalProcesamiento('Extrayendo Datos con IA', 'Analizando checkboxes, campos manuscritos y convirtiendo a MAYÚSCULAS...');

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
      resetForm();

    } catch (error) {
      console.error('Error en envío inmediato:', error);
      ocultarModalProcesamiento();
      showToast(`Error al procesar: ${error.message}. Se guardará en cola local para no perder los datos.`, 'error');
      await ejecutarGuardadoEnCola();
    }
  }

  // -------------------------------------------------------------
  // GUARDADO EN MODO COLA (INDEXEDDB)
  // -------------------------------------------------------------
  async function ejecutarGuardadoEnCola() {
    if (!state.foto1Blob || !state.foto2Blob) {
      showToast('Debes tomar ambas fotos.', 'error');
      return;
    }

    try {
      await window.surveyDB.guardarEncuesta(
        state.foto1Blob,
        state.foto2Blob,
        state.foto1Mime,
        state.foto2Mime
      );

      await actualizarContadorCola();
      const count = await window.surveyDB.contarPendientes();
      showToast(`📦 Encuesta guardada en la cola local (${count} pendientes).`, 'success');
      resetForm();
    } catch (err) {
      console.error('Error guardando en IDB:', err);
      showToast('Error al guardar en el dispositivo: ' + err.message, 'error');
    }
  }

  // -------------------------------------------------------------
  // SINCRONIZAR TODAS LAS ENCUESTAS DE LA COLA (BATCH)
  // -------------------------------------------------------------
  btnSyncAllNow.addEventListener('click', sincronizarColaCompleta);

  async function sincronizarColaCompleta() {
    if (!navigator.onLine) {
      showToast('No tienes conexión a Internet para sincronizar.', 'error');
      return;
    }

    const pendientes = await window.surveyDB.obtenerPendientes();
    if (pendientes.length === 0) {
      showToast('No hay encuestas pendientes en la cola.', 'info');
      return;
    }

    state.isSyncing = true;
    btnSyncAllNow.disabled = true;

    let exitosas = 0;
    let fallidas = 0;
    const total = pendientes.length;

    mostrarModalProcesamiento('Sincronizando Lote en Cola', `Procesando encuesta 1 de ${total}...`);

    for (let i = 0; i < total; i++) {
      const item = pendientes[i];
      procDesc.textContent = `Procesando encuesta ${i + 1} de ${total}... (IA de Visión + Sheets)`;

      try {
        await window.surveyDB.actualizarEstado(item.id, 'syncing');

        const formData = new FormData();
        formData.append('foto_anverso', item.anversoBlob, 'anverso.jpg');
        formData.append('foto_reverso', item.reversoBlob, 'reverso.jpg');
        formData.append('modo', 'batch');

        const resp = await fetch('/api/process-survey', {
          method: 'POST',
          body: formData
        });

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

    if (fallidas === 0) {
      showToast(`🚀 ¡Completado! Se sincronizaron las ${exitosas} encuestas con Google Sheets.`, 'success');
    } else {
      showToast(`Sincronización terminada: ${exitosas} exitosas, ${fallidas} con error.`, 'error');
    }
  }

  // -------------------------------------------------------------
  // GESTIÓN DEL DRAWER DE COLA
  // -------------------------------------------------------------
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
          No tienes encuestas en la cola local.
        </div>
      `;
      return;
    }

    items.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = 'queue-item-card';

      const url1 = URL.createObjectURL(item.anversoBlob);
      const url2 = URL.createObjectURL(item.reversoBlob);
      const fecha = new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      let statusBadge = '';
      if (item.status === 'pending') statusBadge = '<span style="color: #f59e0b;">⏳ Pendiente</span>';
      else if (item.status === 'syncing') statusBadge = '<span style="color: #06b6d4;">🔄 Sincronizando</span>';
      else if (item.status === 'synced') statusBadge = '<span style="color: #10b981;">✅ Sincronizada</span>';
      else if (item.status === 'error') statusBadge = `<span style="color: #ef4444;" title="${item.errorMsg || ''}">❌ Error</span>`;

      card.innerHTML = `
        <div class="queue-item-left">
          <div class="item-thumb-pair">
            <img class="item-thumb" src="${url1}" alt="Anverso">
            <img class="item-thumb" src="${url2}" alt="Reverso">
          </div>
          <div class="item-meta">
            <span>Encuesta #${items.length - index} • ${fecha}</span>
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
        if (confirm('¿Eliminar esta encuesta de la cola local?')) {
          await window.surveyDB.eliminarEncuesta(id);
          await actualizarContadorCola();
          await renderizarListaDrawer();
          showToast('Encuesta eliminada de la cola.', 'info');
        }
      });

      drawerQueueList.appendChild(card);
    });
  }

  btnLimpiarCompletadas.addEventListener('click', async () => {
    const borradas = await window.surveyDB.limpiarSincronizadas();
    await actualizarContadorCola();
    await renderizarListaDrawer();
    showToast(`Se eliminaron ${borradas} encuestas ya sincronizadas.`, 'info');
  });

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
