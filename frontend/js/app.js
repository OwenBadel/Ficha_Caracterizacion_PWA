/**
 * app.js — Controlador de la Interfaz PWA y Sincronización
 * Digitalizador de Fichas de Caracterización y Pre/Post Test — Owen Badel Hooker
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------
  // ESTADO DE LA APLICACIÓN
  // -------------------------------------------------------------
  const state = {
    mode: 'ficha',         // 'ficha', 'anexo4', 'anexo17'
    currentStep: 1,        // Ficha/Anexo17: 1 (Pág 1), 2 (Pág 2), 3 (Lista). Anexo4: 1 (Foto), 2 (Lista)
    
    // Fotos Ficha
    foto1Blob: null,
    foto2Blob: null,
    foto1Mime: 'image/jpeg',
    foto2Mime: 'image/jpeg',

    // Foto Test (Hoja Única)
    fotoTestBlob: null,
    fotoTestMime: 'image/jpeg',
    tipoEvaluacion: 'AUTO', // 'AUTO', 'PRE-TEST', 'POST-TEST'

    // Municipios Anexo 17 dinámicos (Santa Catalina, Turbana, etc.)
    anexo17Municipios: ['SANTA CATALINA', 'TURBANA'],
    anexo17MunicipioActivo: 'SANTA CATALINA',

    isSyncing: false,
    drawerOpen: false,
    queueFilter: 'all' // 'all', 'pending', 'error', 'synced'
  };

  // -------------------------------------------------------------
  // REFERENCIAS DOM
  // -------------------------------------------------------------
  // Header y Modos
  const tabModoFicha = document.getElementById('tabModoFicha');
  const tabModoAnexo4 = document.getElementById('tabModoAnexo4');
  const tabModoAnexo17 = document.getElementById('tabModoAnexo17');
  const testPlaceholderMain = document.getElementById('testPlaceholderMain');
  const testPlaceholderSub = document.getElementById('testPlaceholderSub');
  const netStatusBadge = document.getElementById('netStatusBadge');
  const netStatusText = document.getElementById('netStatusText');
  const brandSubtitle = document.getElementById('brandSubtitle');
  const btnToggleTheme = document.getElementById('btnToggleTheme');

  // Selector Tipo de Test
  const testTypeBar = document.getElementById('testTypeBar');
  const pillBtns = document.querySelectorAll('.pill-btn');

  // Selector y Gestión de Municipio Anexo 17
  const anexo17MunicipioBar = document.getElementById('anexo17MunicipioBar');
  const selectMunicipioAnexo17 = document.getElementById('selectMunicipioAnexo17');
  const btnGestionarMunicipiosAnexo17 = document.getElementById('btnGestionarMunicipiosAnexo17');
  const municipiosBackdrop = document.getElementById('municipiosBackdrop');
  const modalGestionMunicipios = document.getElementById('modalGestionMunicipios');
  const btnCloseMunicipiosModal = document.getElementById('btnCloseMunicipiosModal');
  const inputNuevoMunicipio = document.getElementById('inputNuevoMunicipio');
  const btnGuardarNuevoMunicipio = document.getElementById('btnGuardarNuevoMunicipio');
  const listaMunicipiosChips = document.getElementById('listaMunicipiosChips');
  const btnRestaurarMunicipiosDefault = document.getElementById('btnRestaurarMunicipiosDefault');

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
  const labelPlaceholder1 = document.getElementById('labelPlaceholder1');
  const labelPlaceholder2 = document.getElementById('labelPlaceholder2');
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
  const syncProgressBar = document.getElementById('syncProgressBar');
  const queueCountBadge = document.getElementById('queueCountBadge');
  const queueLabel = document.getElementById('queueLabel');
  const queueSubLabel = document.getElementById('queueSubLabel');
  const btnSyncAllNow = document.getElementById('btnSyncAllNow');
  const btnSyncIcon = document.getElementById('btnSyncIcon');
  const btnSyncText = document.getElementById('btnSyncText');
  const btnOpenDrawer = document.getElementById('btnOpenDrawer');

  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const drawerContainer = document.getElementById('drawerContainer');
  const btnCloseDrawer = document.getElementById('btnCloseDrawer');
  const drawerQueueList = document.getElementById('drawerQueueList');
  const btnLimpiarCompletadas = document.getElementById('btnLimpiarCompletadas');
  const btnSyncAllFromDrawer = document.getElementById('btnSyncAllFromDrawer');

  // Chips de estado en el drawer
  const chipPending = document.getElementById('chipPending');
  const chipSynced = document.getElementById('chipSynced');
  const chipError = document.getElementById('chipError');

  // Filtros de estado en el drawer
  const filterAll = document.getElementById('filterAll');
  const filterPending = document.getElementById('filterPending');
  const filterError = document.getElementById('filterError');
  const filterSynced = document.getElementById('filterSynced');

  /**
   * Asegura que un Blob o File tenga tipo MIME de imagen válido y nombre de archivo consistente.
   * Evita errores 400 Bad Request por Content-Type 'application/octet-stream' desde IndexedDB.
   */
  function normalizarBlobParaEnvio(blob, defaultNombre = 'captura.jpg') {
    if (!blob) return null;
    let mime = 'image/jpeg';
    if (blob.type && (blob.type.startsWith('image/') || blob.type === 'application/pdf')) {
      mime = blob.type;
    }
    return new File([blob], defaultNombre, { type: mime });
  }



  // Modal Procesamiento y Toasts
  const processingModal = document.getElementById('processingModal');
  const procTitle = document.getElementById('procTitle');
  const procDesc = document.getElementById('procDesc');
  const toastContainer = document.getElementById('toastContainer');

  // -------------------------------------------------------------
  // CONTROLADOR DE TEMA CLARO / OSCURO (ALTO CONTRASTE AL SOL)
  // -------------------------------------------------------------
  function aplicarTema(tema) {
    document.documentElement.setAttribute('data-theme', tema);
    try {
      localStorage.setItem('app-theme', tema);
    } catch (_) {}
    if (btnToggleTheme) {
      const sun = btnToggleTheme.querySelector('.icon-theme-sun');
      const moon = btnToggleTheme.querySelector('.icon-theme-moon');
      if (sun && moon) {
        if (tema === 'light') {
          sun.style.display = 'none';
          moon.style.display = 'inline-block';
        } else {
          sun.style.display = 'inline-block';
          moon.style.display = 'none';
        }
      }
    }
  }

  const temaGuardado = (() => {
    try {
      return localStorage.getItem('app-theme') || 'dark';
    } catch (_) {
      return 'dark';
    }
  })();
  aplicarTema(temaGuardado);

  if (btnToggleTheme) {
    btnToggleTheme.addEventListener('click', () => {
      const actual = document.documentElement.getAttribute('data-theme') || 'dark';
      const nuevo = actual === 'dark' ? 'light' : 'dark';
      aplicarTema(nuevo);
      showToast(nuevo === 'light' ? 'Modo Claro activado (Alto Contraste)' : 'Modo Oscuro activado', 'info');
    });
  }

  // Función de escape HTML seguro para prevenir XSS
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // -------------------------------------------------------------
  // TOASTS DE NOTIFICACIÓN MONOCROMÁTICOS (SIN EMOJIS)
  // -------------------------------------------------------------
  function showToast(message, type = 'success') {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'error') {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    // Sanitizar cualquier emoji residual de textos heredados
    const cleanMessage = String(message).replace(/[📋📝🌟🏛️🤖🔄📸⚡📦🗑️⏳✅❌🧹⚠️ℹ️✨📭📁🛡️🕒📍]/g, '').trim();

    toast.innerHTML = `
      ${iconSvg}
      <span>${escapeHtml(cleanMessage)}</span>
    `;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-8px)';
      setTimeout(() => toast.remove(), 250);
    }, 4200);
  }

  // -------------------------------------------------------------
  // GESTIÓN DINÁMICA DE MUNICIPIOS (ANEXO 17)
  // -------------------------------------------------------------
  const MUNICIPIOS_DEFAULT_ANEXO17 = ['SANTA CATALINA', 'TURBANA'];

  function cargarMunicipiosAnexo17DesdeStorage() {
    try {
      const raw = localStorage.getItem('anexo17_municipios');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          state.anexo17Municipios = parsed.map(m => String(m).trim().toUpperCase()).filter(Boolean);
        }
      }
    } catch (_) {}

    try {
      const activo = localStorage.getItem('anexo17_municipio_activo');
      if (activo && state.anexo17Municipios.includes(activo.trim().toUpperCase())) {
        state.anexo17MunicipioActivo = activo.trim().toUpperCase();
      } else {
        state.anexo17MunicipioActivo = state.anexo17Municipios[0] || 'SANTA CATALINA';
      }
    } catch (_) {
      state.anexo17MunicipioActivo = state.anexo17Municipios[0] || 'SANTA CATALINA';
    }
  }

  function guardarMunicipiosAnexo17EnStorage() {
    try {
      localStorage.setItem('anexo17_municipios', JSON.stringify(state.anexo17Municipios));
      localStorage.setItem('anexo17_municipio_activo', state.anexo17MunicipioActivo);
    } catch (_) {}
  }

  function actualizarSelectMunicipiosAnexo17() {
    if (!selectMunicipioAnexo17) return;
    selectMunicipioAnexo17.innerHTML = '';
    state.anexo17Municipios.forEach(mun => {
      const opt = document.createElement('option');
      opt.value = mun;
      opt.textContent = mun;
      if (mun === state.anexo17MunicipioActivo) opt.selected = true;
      selectMunicipioAnexo17.appendChild(opt);
    });
  }

  function renderizarChipsGestionMunicipios() {
    if (!listaMunicipiosChips) return;
    listaMunicipiosChips.innerHTML = '';

    state.anexo17Municipios.forEach(mun => {
      const chip = document.createElement('div');
      const esActivo = mun === state.anexo17MunicipioActivo;
      chip.className = `mun-tag-chip${esActivo ? ' active-mun' : ''}`;

      const btnSelect = document.createElement('button');
      btnSelect.type = 'button';
      btnSelect.className = 'mun-chip-select-btn';
      btnSelect.title = `Seleccionar ${mun}`;
      btnSelect.innerHTML = `
        <span>${escapeHtml(mun)}</span>
        ${esActivo ? '<span style="font-size:0.65rem;">(Activo)</span>' : ''}
      `;
      btnSelect.addEventListener('click', () => {
        state.anexo17MunicipioActivo = mun;
        guardarMunicipiosAnexo17EnStorage();
        actualizarSelectMunicipiosAnexo17();
        renderizarChipsGestionMunicipios();
        if (state.mode === 'anexo17') {
          brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${mun})`;
          setStepFicha(state.currentStep || 1);
        }
        showToast(`Municipio activo: ${mun}`, 'info');
      });

      chip.appendChild(btnSelect);

      // Botón para eliminar (solo si hay más de 1 municipio en la lista)
      if (state.anexo17Municipios.length > 1) {
        const btnDel = document.createElement('button');
        btnDel.type = 'button';
        btnDel.className = 'mun-chip-del-btn';
        btnDel.title = `Eliminar ${mun}`;
        btnDel.innerHTML = `
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        `;
        btnDel.addEventListener('click', (e) => {
          e.stopPropagation();
          eliminarMunicipioAnexo17(mun);
        });
        chip.appendChild(btnDel);
      }

      listaMunicipiosChips.appendChild(chip);
    });
  }

  function abrirModalMunicipios() {
    renderizarChipsGestionMunicipios();
    if (inputNuevoMunicipio) inputNuevoMunicipio.value = '';
    if (municipiosBackdrop) {
      municipiosBackdrop.style.display = 'block';
      municipiosBackdrop.classList.add('active');
    }
    if (modalGestionMunicipios) {
      modalGestionMunicipios.style.display = 'block';
      modalGestionMunicipios.classList.add('active');
    }
    setTimeout(() => {
      if (inputNuevoMunicipio) inputNuevoMunicipio.focus();
    }, 100);
  }

  function cerrarModalMunicipios() {
    if (municipiosBackdrop) {
      municipiosBackdrop.style.display = 'none';
      municipiosBackdrop.classList.remove('active');
    }
    if (modalGestionMunicipios) {
      modalGestionMunicipios.style.display = 'none';
      modalGestionMunicipios.classList.remove('active');
    }
  }

  function agregarNuevoMunicipioAnexo17(nuevoNombre) {
    const limpio = (nuevoNombre || '').trim().toUpperCase().replace(/[^A-ZÁÉÍÓÚÑ\s]/g, '');
    if (!limpio || limpio.length < 3) {
      showToast('Ingresa un nombre de municipio válido (mínimo 3 letras).', 'error');
      return;
    }
    if (state.anexo17Municipios.includes(limpio)) {
      showToast(`El municipio "${limpio}" ya está en la lista.`, 'info');
      state.anexo17MunicipioActivo = limpio;
      guardarMunicipiosAnexo17EnStorage();
      actualizarSelectMunicipiosAnexo17();
      renderizarChipsGestionMunicipios();
      if (state.mode === 'anexo17') {
        brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${limpio})`;
        setStepFicha(state.currentStep || 1);
      }
      return;
    }

    state.anexo17Municipios.push(limpio);
    state.anexo17MunicipioActivo = limpio;
    guardarMunicipiosAnexo17EnStorage();
    actualizarSelectMunicipiosAnexo17();
    renderizarChipsGestionMunicipios();
    if (inputNuevoMunicipio) inputNuevoMunicipio.value = '';
    if (state.mode === 'anexo17') {
      brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${limpio})`;
      setStepFicha(state.currentStep || 1);
    }
    showToast(`Municipio "${limpio}" agregado y seleccionado.`, 'success');
  }

  function eliminarMunicipioAnexo17(munAEliminar) {
    if (state.anexo17Municipios.length <= 1) {
      showToast('Debe haber al menos un municipio registrado.', 'error');
      return;
    }
    state.anexo17Municipios = state.anexo17Municipios.filter(m => m !== munAEliminar);
    if (state.anexo17MunicipioActivo === munAEliminar) {
      state.anexo17MunicipioActivo = state.anexo17Municipios[0];
    }
    guardarMunicipiosAnexo17EnStorage();
    actualizarSelectMunicipiosAnexo17();
    renderizarChipsGestionMunicipios();
    if (state.mode === 'anexo17') {
      brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${state.anexo17MunicipioActivo})`;
      setStepFicha(state.currentStep || 1);
    }
    showToast(`Municipio "${munAEliminar}" eliminado.`, 'info');
  }

  function restaurarMunicipiosPredeterminadosAnexo17() {
    state.anexo17Municipios = [...MUNICIPIOS_DEFAULT_ANEXO17];
    state.anexo17MunicipioActivo = 'SANTA CATALINA';
    guardarMunicipiosAnexo17EnStorage();
    actualizarSelectMunicipiosAnexo17();
    renderizarChipsGestionMunicipios();
    if (state.mode === 'anexo17') {
      brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${state.anexo17MunicipioActivo})`;
      setStepFicha(state.currentStep || 1);
    }
    showToast('Municipios restablecidos a SANTA CATALINA y TURBANA.', 'success');
  }

  // Listeners de Municipio Anexo 17
  if (selectMunicipioAnexo17) {
    selectMunicipioAnexo17.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val) {
        state.anexo17MunicipioActivo = val;
        guardarMunicipiosAnexo17EnStorage();
        if (state.mode === 'anexo17') {
          brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${val})`;
          setStepFicha(state.currentStep || 1);
        }
        showToast(`Municipio: ${val}`, 'info');
      }
    });
  }

  if (btnGestionarMunicipiosAnexo17) {
    btnGestionarMunicipiosAnexo17.addEventListener('click', abrirModalMunicipios);
  }
  if (btnCloseMunicipiosModal) {
    btnCloseMunicipiosModal.addEventListener('click', cerrarModalMunicipios);
  }
  if (municipiosBackdrop) {
    municipiosBackdrop.addEventListener('click', cerrarModalMunicipios);
  }
  if (btnGuardarNuevoMunicipio) {
    btnGuardarNuevoMunicipio.addEventListener('click', () => {
      if (inputNuevoMunicipio) agregarNuevoMunicipioAnexo17(inputNuevoMunicipio.value);
    });
  }
  if (inputNuevoMunicipio) {
    inputNuevoMunicipio.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        agregarNuevoMunicipioAnexo17(inputNuevoMunicipio.value);
      }
    });
  }
  if (btnRestaurarMunicipiosDefault) {
    btnRestaurarMunicipiosDefault.addEventListener('click', restaurarMunicipiosPredeterminadosAnexo17);
  }

  // -------------------------------------------------------------
  // CAMBIO DE MODO: FICHA VS ANEXO 4 VS ANEXO 17
  // -------------------------------------------------------------
  if (tabModoFicha) tabModoFicha.addEventListener('click', () => cambiarModo('ficha'));
  if (tabModoAnexo4) tabModoAnexo4.addEventListener('click', () => cambiarModo('anexo4'));
  if (tabModoAnexo17) tabModoAnexo17.addEventListener('click', () => cambiarModo('anexo17'));

  function cambiarModo(nuevoModo) {
    if (state.mode === nuevoModo) return;
    state.mode = nuevoModo;

    if (nuevoModo === 'ficha') {
      tabModoFicha.classList.add('active');
      if (tabModoAnexo4) tabModoAnexo4.classList.remove('active');
      if (tabModoAnexo17) tabModoAnexo17.classList.remove('active');
      if (btnOpenMasterModal) btnOpenMasterModal.style.display = 'none';
      testTypeBar.style.display = 'none';
      if (anexo17MunicipioBar) anexo17MunicipioBar.style.display = 'none';
      photosGridFicha.style.display = 'grid';
      photosSingleTest.style.display = 'none';
      brandSubtitle.textContent = 'Anexo 10 — Fichas de Caracterización (2 Páginas)';
      if (labelPlaceholder1) labelPlaceholder1.innerHTML = 'Página 1<br>(Anverso)';
      if (labelPlaceholder2) labelPlaceholder2.innerHTML = 'Página 2<br>(Reverso)';
      resetFichaForm();
    } else if (nuevoModo === 'anexo4') {
      if (tabModoAnexo4) tabModoAnexo4.classList.add('active');
      tabModoFicha.classList.remove('active');
      if (tabModoAnexo17) tabModoAnexo17.classList.remove('active');
      if (btnOpenMasterModal) btnOpenMasterModal.style.display = 'inline-flex';
      testTypeBar.style.display = 'flex';
      if (anexo17MunicipioBar) anexo17MunicipioBar.style.display = 'none';
      photosGridFicha.style.display = 'none';
      photosSingleTest.style.display = 'flex';
      brandSubtitle.textContent = 'Pre/Post Test — Anexo 4 (SSR ITS)';
      if (testPlaceholderMain) testPlaceholderMain.textContent = 'Pre o Post Test';
      if (testPlaceholderSub) testPlaceholderSub.textContent = '(Anexo 4 SSR ITS — 9 Preguntas)';
      resetTestForm();
      actualizarEtiquetaTest();
    } else if (nuevoModo === 'anexo17') {
      if (tabModoAnexo17) tabModoAnexo17.classList.add('active');
      tabModoFicha.classList.remove('active');
      if (tabModoAnexo4) tabModoAnexo4.classList.remove('active');
      if (btnOpenMasterModal) btnOpenMasterModal.style.display = 'inline-flex';
      testTypeBar.style.display = 'flex';
      if (anexo17MunicipioBar) anexo17MunicipioBar.style.display = 'flex';
      photosGridFicha.style.display = 'grid'; // ¡Anexo 17 utiliza 2 páginas físicas!
      photosSingleTest.style.display = 'none';
      brandSubtitle.textContent = `Pre/Post Test — Anexo 17 (${state.anexo17MunicipioActivo})`;
      if (labelPlaceholder1) labelPlaceholder1.innerHTML = 'Página 1<br>(Datos y Preg. 1-5)';
      if (labelPlaceholder2) labelPlaceholder2.innerHTML = 'Página 2<br>(Preg. 6-10)';
      resetFichaForm();
      setStepFicha(1);
    }
  }

  // Selección de tipo de evaluación (AUTO / PRE-TEST / POST-TEST)
  pillBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      pillBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.tipoEvaluacion = btn.getAttribute('data-type');
      if (state.mode === 'anexo17') {
        setStepFicha(state.currentStep || 1);
      } else {
        actualizarEtiquetaTest();
      }
    });
  });

  function actualizarEtiquetaTest() {
    if (state.mode !== 'anexo4') return;
    const anexoLabel = 'Anexo 4';
    const tipo = state.tipoEvaluacion;
    if (state.fotoTestBlob) {
      stepTag.textContent = tipo === 'AUTO' ? `${anexoLabel} Listo (Auto IA)` : `${anexoLabel} ${tipo} Listo`;
      shutterLabel.textContent = 'Listo para procesar';
    } else {
      stepTag.textContent = tipo === 'AUTO' ? `Hoja Única (${anexoLabel})` : `Hoja Única (${anexoLabel} ${tipo})`;
      stepTitle.textContent = tipo === 'AUTO' ? `Tomar Foto ${anexoLabel}` : `Tomar Foto ${anexoLabel} (${tipo})`;
      stepDesc.textContent = `Enfoca la hoja física del ${anexoLabel} asegurando buena luz.`;
      shutterLabel.textContent = tipo === 'AUTO' ? `Tomar Foto ${anexoLabel}` : `Tomar Foto ${tipo}`;
    }
  }

  // -------------------------------------------------------------
  // DISPARADOR DE CÁMARA ERGONÓMICO
  // -------------------------------------------------------------
  function dispararCamara() {
    try {
      if (state.mode === 'ficha' || state.mode === 'anexo17') {
        if (state.currentStep === 1) {
          if (cameraInput1) { cameraInput1.value = ''; cameraInput1.click(); }
        } else if (state.currentStep === 2) {
          if (cameraInput2) { cameraInput2.value = ''; cameraInput2.click(); }
        } else {
          showToast('Fotos listas. Elige "Sincronizar Ahora" o "Mandar a la Cola" abajo.', 'info');
        }
      } else {
        // Modo Anexo 4 (Hoja Única)
        if (!state.fotoTestBlob) {
          if (cameraInputTest) { cameraInputTest.value = ''; cameraInputTest.click(); }
        } else {
          showToast('Foto lista. Elige "Sincronizar Ahora" o "Mandar a la Cola" abajo.', 'info');
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
  // GESTIÓN DE SCREEN WAKE LOCK & CONECTIVIDAD AL SERVIDOR LOCAL
  // -------------------------------------------------------------
  let wakeLockSentinel = null;

  async function solicitarWakeLock() {
    try {
      if ('wakeLock' in navigator && !wakeLockSentinel) {
        wakeLockSentinel = await navigator.wakeLock.request('screen');
        wakeLockSentinel.addEventListener('release', () => {
          wakeLockSentinel = null;
        });
        console.log('Screen Wake Lock activo (impidiendo suspensión de pantalla/Wi-Fi).');
      }
    } catch (err) {
      console.warn('Wake Lock no disponible o denegado:', err);
    }
  }

  async function liberarWakeLock() {
    try {
      if (wakeLockSentinel) {
        await wakeLockSentinel.release();
        wakeLockSentinel = null;
        console.log('Screen Wake Lock liberado.');
      }
    } catch (err) {
      console.warn('Error al liberar Wake Lock:', err);
    }
  }

  async function verificarConexionServidor() {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      const res = await fetch('/api/health', {
        method: 'GET',
        signal: controller.signal,
        cache: 'no-store'
      });
      clearTimeout(timeoutId);
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  // -------------------------------------------------------------
  // ORIENTACIÓN VERTICAL AUTOMÁTICA Y RESOLUCIÓN OPTIMIZADA (1600px @ 82%)
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

  async function procesarYOrientarImagen(fileOrBlob, maxDimension = 1600, quality = 0.82, forceRotate90 = false) {
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

  // -------------------------------------------------------------
  // GESTIÓN DE CICLO DE VIDA DE MEMORIA Y OBJECT URLS (ANTI-LEAKS)
  // -------------------------------------------------------------
  const activePreviewUrls = new Map();
  let activeDrawerObjectUrls = [];

  function setPreviewBlob(imgElement, blob) {
    if (!imgElement) return '';
    if (activePreviewUrls.has(imgElement)) {
      try {
        URL.revokeObjectURL(activePreviewUrls.get(imgElement));
      } catch (_) {}
    }
    if (!blob) {
      activePreviewUrls.delete(imgElement);
      imgElement.src = '';
      return '';
    }
    const url = URL.createObjectURL(blob);
    activePreviewUrls.set(imgElement, url);
    imgElement.src = url;
    return url;
  }

  function revokePreviewBlob(imgElement) {
    if (!imgElement) return;
    if (activePreviewUrls.has(imgElement)) {
      try {
        URL.revokeObjectURL(activePreviewUrls.get(imgElement));
      } catch (_) {}
      activePreviewUrls.delete(imgElement);
    }
    imgElement.src = '';
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
      const rotatedBlob = await procesarYOrientarImagen(currentBlob, 1600, 0.82, true);
      setPreviewBlob(previewEl, rotatedBlob);

      if (tipo === 1) {
        state.foto1Blob = rotatedBlob;
        if (window.surveyDB && typeof window.surveyDB.guardarBorradorActivo === 'function') {
          window.surveyDB.guardarBorradorActivo(state.mode, rotatedBlob, 'image/jpeg', {
            tipoEvaluacion: state.tipoEvaluacion
          }).catch(() => {});
        }
      } else if (tipo === 2) {
        state.foto2Blob = rotatedBlob;
      } else if (tipo === 'test') {
        state.fotoTestBlob = rotatedBlob;
      }

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
      const verticalBlob = await procesarYOrientarImagen(file, 1600, 0.82, false);
      setPreviewBlob(imgPreview1, verticalBlob);

      imgPreview1.style.display = 'block';
      placeholderFoto1.style.display = 'none';
      badgeCheck1.style.display = 'flex';
      if (slotActions1) slotActions1.style.display = 'flex';
      slotFoto1.classList.remove('active-slot');
      slotFoto1.classList.add('completed');

      state.foto1Blob = verticalBlob;
      state.foto1Mime = 'image/jpeg';

      // Persistir de inmediato en IndexedDB para blindar contra suspensión de RAM al abrir la cámara de Foto 2
      if (window.surveyDB && typeof window.surveyDB.guardarBorradorActivo === 'function') {
        window.surveyDB.guardarBorradorActivo(state.mode, verticalBlob, 'image/jpeg', {
          tipoEvaluacion: state.tipoEvaluacion
        }).catch(err => console.warn('Aviso guardando borrador activo:', err));
      }

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
      const verticalBlob = await procesarYOrientarImagen(file, 1600, 0.82, false);
      setPreviewBlob(imgPreview2, verticalBlob);

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
    const esAnexo17 = state.mode === 'anexo17';

    if (step === 1) {
      stepTag.textContent = esAnexo17 ? `Paso 1 de 2 • Anexo 17 (${state.tipoEvaluacion})` : 'Paso 1 de 2';
      stepTitle.textContent = esAnexo17 ? 'Foto 1: Página 1 (Datos y Preg. 1 a 5)' : 'Foto 1: Anverso (Frente)';
      stepDesc.textContent = esAnexo17 ? `Enfoca la primera hoja con el nombre y preguntas 1 a 5 (${state.anexo17MunicipioActivo}).` : 'Enfoca la cara frontal de la ficha con buena iluminación.';
      stepBadge.textContent = '1/2';
      shutterLabel.textContent = esAnexo17 ? 'Tomar Foto Pág. 1 (Anexo 17)' : 'Tomar Foto 1 (Anverso)';
      slotFoto1.classList.add('active-slot');
      slotFoto2.classList.remove('active-slot');
      cameraTriggerSection.style.display = 'flex';
      readyActionBox.style.display = 'none';
    } else if (step === 2) {
      stepTag.textContent = esAnexo17 ? `Paso 2 de 2 • Anexo 17 (${state.tipoEvaluacion})` : 'Paso 2 de 2';
      stepTitle.textContent = esAnexo17 ? 'Foto 2: Página 2 (Preguntas 6 a 10)' : 'Foto 2: Reverso (Atrás)';
      stepDesc.textContent = esAnexo17 ? 'Enfoca la segunda hoja con las preguntas 6 a 10.' : 'Gira la ficha y fotografía la parte posterior.';
      stepBadge.textContent = '2/2';
      shutterLabel.textContent = esAnexo17 ? 'Tomar Foto Pág. 2 (Anexo 17)' : 'Tomar Foto 2 (Reverso)';
      slotFoto2.classList.add('active-slot');
      slotFoto1.classList.remove('active-slot');
      cameraTriggerSection.style.display = 'flex';
      readyActionBox.style.display = 'none';
    } else if (step === 3) {
      stepTag.textContent = '¡Fotos Listas!';
      stepTitle.textContent = esAnexo17 ? `Anexo 17 Completo (${state.tipoEvaluacion})` : 'Encuesta Completa (2/2 Fotos)';
      stepDesc.textContent = esAnexo17 ? 'Verifica las 2 páginas y elige cómo registrarla.' : 'Verifica las fotos y elige cómo registrarla.';
      stepBadge.textContent = '✔';
      readyIcon.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
      readyTitle.textContent = esAnexo17 ? 'Fotos Listas (2/2) — Anexo 17' : 'Fotos Listas (2/2)';
      readySubtitle.textContent = esAnexo17 ? 'Página 1 y Página 2 listas para procesar con IA:' : 'Selecciona la acción para esta ficha:';
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

    revokePreviewBlob(imgPreview1);
    imgPreview1.style.display = 'none';
    placeholderFoto1.style.display = 'flex';
    badgeCheck1.style.display = 'none';
    if (slotActions1) slotActions1.style.display = 'none';
    slotFoto1.className = 'photo-slot active-slot';

    revokePreviewBlob(imgPreview2);
    imgPreview2.style.display = 'none';
    placeholderFoto2.style.display = 'flex';
    badgeCheck2.style.display = 'none';
    if (slotActions2) slotActions2.style.display = 'none';
    slotFoto2.className = 'photo-slot';

    if (window.surveyDB && typeof window.surveyDB.limpiarBorradorActivo === 'function') {
      window.surveyDB.limpiarBorradorActivo().catch(() => {});
    }

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
      const verticalBlob = await procesarYOrientarImagen(file, 1600, 0.82, false);
      setPreviewBlob(imgPreviewTest, verticalBlob);

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
    const anexoLabel = state.mode === 'anexo17' ? 'Anexo 17' : 'Anexo 4';
    const tipo = state.tipoEvaluacion === 'AUTO' ? `${anexoLabel}` : `${anexoLabel} (${state.tipoEvaluacion})`;
    stepTag.textContent = '¡Foto Lista!';
    stepTitle.textContent = `${tipo} (Hoja Única)`;
    stepDesc.textContent = 'Verifica la nitidez y selecciona una acción.';
    stepBadge.textContent = '✔';

    readyIcon.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    readyTitle.textContent = `${anexoLabel} Listo (1/1 Foto)`;
    readySubtitle.textContent = `Evaluación: ${state.tipoEvaluacion}. Elige la acción:`;

    cameraTriggerSection.style.display = 'none';
    readyActionBox.style.display = 'flex';
    readyActionBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function resetTestForm() {
    state.fotoTestBlob = null;
    cameraInputTest.value = '';

    revokePreviewBlob(imgPreviewTest);
    imgPreviewTest.style.display = 'none';
    placeholderFotoTest.style.display = 'flex';
    badgeCheckTest.style.display = 'none';
    if (slotActionsTest) slotActionsTest.style.display = 'none';
    slotFotoTest.className = 'photo-slot photo-slot-single active-slot';

    const anexoLabel = state.mode === 'anexo17' ? 'Anexo 17' : 'Anexo 4';
    stepTag.textContent = 'Hoja Única';
    stepTitle.textContent = `Tomar Foto ${anexoLabel}`;
    stepDesc.textContent = `Enfoca la hoja completa del Pre-Test o Post-Test (${anexoLabel}) con buena luz.`;
    stepBadge.textContent = '1/1';
    shutterLabel.textContent = `Tomar Foto ${anexoLabel}`;

    cameraTriggerSection.style.display = 'flex';
    readyActionBox.style.display = 'none';
    actualizarEtiquetaTest();
  }

  // -------------------------------------------------------------
  // BOTONES DE ACCIÓN (SINCRONIZAR, GUARDAR EN COLA, DESCARTAR)
  // -------------------------------------------------------------
  btnCancelarEncuesta.addEventListener('click', () => {
    if (confirm('¿Deseas descartar la captura actual?')) {
      if (state.mode === 'ficha' || state.mode === 'anexo17') resetFichaForm();
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
  // ENVÍO EN MODO INMEDIATO (GUARDADO PREVIO EN IDB + SYNC INMEDIATO)
  // -------------------------------------------------------------
  async function ejecutarEnvioInmediato() {
    // 1. Validaciones previas de fotos tomadas
    if (state.mode === 'ficha') {
      if (!state.foto1Blob || !state.foto2Blob) {
        showToast('Debes tomar ambas fotos de la ficha antes de enviar.', 'error');
        return;
      }
    } else if (state.mode === 'anexo17') {
      if (!state.foto1Blob) {
        showToast('Debes tomar al menos la foto de la Página 1 de Anexo 17 antes de enviar.', 'error');
        return;
      }
    } else {
      if (!state.fotoTestBlob) {
        showToast('Debes tomar la foto del test antes de enviar.', 'error');
        return;
      }
    }

    // 2. Guardar PRIMERO en IndexedDB para tener un ID permanente e inmutable ante cortes
    let itemGuardado = null;
    try {
      if (state.mode === 'ficha') {
        itemGuardado = await window.surveyDB.guardarEncuesta(
          state.foto1Blob,
          state.foto2Blob,
          state.foto1Mime,
          state.foto2Mime
        );
        resetFichaForm();
      } else if (state.mode === 'anexo17') {
        itemGuardado = await window.surveyDB.guardarAnexo17(
          state.foto1Blob,
          state.foto2Blob,
          state.foto1Mime,
          state.foto2Mime,
          state.tipoEvaluacion,
          state.anexo17MunicipioActivo || 'SANTA CATALINA'
        );
        resetFichaForm();
      } else {
        itemGuardado = await window.surveyDB.guardarTest(
          state.fotoTestBlob,
          state.fotoTestMime,
          state.tipoEvaluacion
        );
        resetTestForm();
      }

      await actualizarContadorCola();
      if (state.drawerOpen) await renderizarListaDrawer();
    } catch (errDb) {
      console.error('Error guardando en IDB previo a sincronizar:', errDb);
      showToast('Error al persistir registro en el teléfono: ' + errDb.message, 'error');
      return;
    }

    if (!itemGuardado) return;

    // 3. Sincronizar inmediatamente el registro con su ID único permanente
    showToast('Registro asegurado localmente. Sincronizando con el servidor...', 'info');
    await sincronizarItemIndividual(itemGuardado.id, true);
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
      } else if (state.mode === 'anexo17') {
        if (!state.foto1Blob) {
          showToast('Debes tomar al menos la foto de la Página 1.', 'error');
          return;
        }
        await window.surveyDB.guardarAnexo17(
          state.foto1Blob,
          state.foto2Blob,
          state.foto1Mime,
          state.foto2Mime,
          state.tipoEvaluacion,
          state.anexo17MunicipioActivo || 'SANTA CATALINA'
        );
        resetFichaForm();
      } else {
        if (!state.fotoTestBlob) {
          showToast('Debes tomar la foto del test Anexo 4.', 'error');
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
      if (state.drawerOpen) await renderizarListaDrawer();
      const count = await window.surveyDB.contarPendientes();

      if (state.isSyncing) {
        showToast(`Registro agregado al final de la cola activa (${count} en proceso).`, 'success');
      } else {
        showToast(`Registro guardado en cola (${count} pendientes).`, 'success');
        if (navigator.onLine) {
          // Iniciar sincronización en segundo plano automáticamente de forma no bloqueante
          iniciarSincronizacionSegundoPlano(false);
        }
      }
    } catch (err) {
      console.error('Error guardando en IDB:', err);
      showToast('Error al guardar en el dispositivo: ' + err.message, 'error');
    }
  }

  // -------------------------------------------------------------
  // SINCRONIZACIÓN EN SEGUNDO PLANO (CONTINUOUS FIFO BACKGROUND WORKER)
  // -------------------------------------------------------------
  btnSyncAllNow.addEventListener('click', () => {
    iniciarSincronizacionSegundoPlano(true);
  });

  function actualizarBarraSincronizacionUI(estaSincronizando, textoDetalle = '') {
    if (estaSincronizando) {
      if (syncProgressBar) syncProgressBar.style.display = 'block';
      if (queueCountBadge) queueCountBadge.classList.add('syncing');
      if (queueLabel) queueLabel.textContent = textoDetalle || 'Sincronizando en segundo plano...';
      if (queueSubLabel) queueSubLabel.textContent = 'Segundo plano activo • Toca para ver cola';
      if (btnSyncAllNow) {
        btnSyncAllNow.disabled = true;
        btnSyncAllNow.style.opacity = '0.9';
      }
      if (btnSyncText) btnSyncText.textContent = 'En proceso...';
      if (btnSyncIcon) btnSyncIcon.innerHTML = '<span class="spinner-inline"></span>';
    } else {
      if (syncProgressBar) syncProgressBar.style.display = 'none';
      if (queueCountBadge) queueCountBadge.classList.remove('syncing');
      if (queueSubLabel) queueSubLabel.textContent = 'Toca para ver la cola';
      if (btnSyncText) btnSyncText.textContent = 'Sincronizar';
      if (btnSyncIcon) {
        btnSyncIcon.innerHTML = `
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 12v-3a3 3 0 0 1 3 -3h13m-3 -3l3 3l-3 3" />
            <path d="M20 12v3a3 3 0 0 1 -3 3h-13m3 3l-3 -3l3 -3" />
          </svg>
        `;
      }
      actualizarContadorCola();
    }
  }

  async function iniciarSincronizacionSegundoPlano(iniciadoManualmente = false) {
    if (!navigator.onLine) {
      if (iniciadoManualmente) {
        showToast('No tienes conexión de red activa en el dispositivo.', 'error');
      }
      return;
    }

    if (state.isSyncing) {
      if (iniciadoManualmente) {
        showToast('La sincronización en segundo plano ya está en curso.', 'info');
      }
      return;
    }

    const iniciales = await window.surveyDB.obtenerPendientes();
    if (iniciales.length === 0) {
      if (iniciadoManualmente) {
        showToast('No hay registros pendientes en la cola.', 'info');
      }
      return;
    }

    // Verificación real de alcance al servidor en PC (evita falsos positivos con 4G)
    const servidorAlcanzable = await verificarConexionServidor();
    if (!servidorAlcanzable) {
      if (iniciadoManualmente) {
        showToast('El servidor en el PC no responde. Verifica que estés conectado a la misma red Wi-Fi.', 'error');
      }
      return;
    }

    state.isSyncing = true;
    await solicitarWakeLock();
    actualizarBarraSincronizacionUI(true, `Iniciando sincronización (${iniciales.length} pendientes)...`);
    if (iniciadoManualmente) {
      showToast(`Sincronización en segundo plano activa (${iniciales.length} registros). Puedes seguir capturando fotos libremente.`, 'info');
    }

    let exitosas = 0;
    let fallidas = 0;
    const fallidosEnEstaSesion = new Set();

    try {
      while (state.isSyncing) {
        if (!navigator.onLine) {
          showToast('Conexión perdida. Pausando sincronización en segundo plano.', 'error');
          break;
        }

        // Consultar la cola viva en IndexedDB en orden cronológico FIFO (el más antiguo primero)
        const todosPendientes = await window.surveyDB.obtenerPendientes();
        const pendientes = todosPendientes.filter(it => !fallidosEnEstaSesion.has(it.id));

        if (pendientes.length === 0) {
          // Cola totalmente procesada
          break;
        }

        const item = pendientes[0];
        const esAnexo17 = item.tipo === 'anexo17';
        const esAnexo4 = item.tipo === 'anexo4' || item.tipo === 'test';
        const restantes = pendientes.length;

        let labelTipo = 'Ficha';
        if (esAnexo17) labelTipo = 'Anexo 17';
        else if (esAnexo4) labelTipo = 'Anexo 4';

        actualizarBarraSincronizacionUI(true, `Sincronizando ${labelTipo} (${restantes} en cola)...`);
        await window.surveyDB.actualizarEstado(item.id, 'syncing');
        await actualizarContadorCola();
        if (state.drawerOpen) await renderizarListaDrawer();

        try {
          let resp;
          if (esAnexo17) {
            const formData = new FormData();
            formData.append('foto_anverso', normalizarBlobParaEnvio(item.anversoBlob || item.fotoBlob, 'anexo17_pag1.jpg'), 'anexo17_pag1.jpg');
            if (item.reversoBlob) {
              formData.append('foto_reverso', normalizarBlobParaEnvio(item.reversoBlob, 'anexo17_pag2.jpg'), 'anexo17_pag2.jpg');
            }
            if (item.tipoEvaluacion && item.tipoEvaluacion !== 'AUTO') {
              formData.append('tipo_evaluacion', item.tipoEvaluacion);
            }
            if (item.municipio) {
              formData.append('municipio', item.municipio);
            } else if (state.anexo17MunicipioActivo) {
              formData.append('municipio', state.anexo17MunicipioActivo);
            }
            formData.append('modo', 'batch');
            formData.append('client_item_id', item.id);
            formData.append('ya_orientada', 'true');

            resp = await fetch('/api/process-anexo17', {
              method: 'POST',
              body: formData
            });
          } else if (esAnexo4) {
            const formData = new FormData();
            formData.append('foto_test', normalizarBlobParaEnvio(item.anversoBlob || item.fotoBlob, 'test.jpg'), 'test.jpg');
            if (item.tipoEvaluacion && item.tipoEvaluacion !== 'AUTO') {
              formData.append('tipo_evaluacion', item.tipoEvaluacion);
            }
            formData.append('modo', 'batch');
            formData.append('client_item_id', item.id);
            formData.append('ya_orientada', 'true');

            resp = await fetch('/api/process-test', {
              method: 'POST',
              body: formData
            });
          } else {
            const formData = new FormData();
            formData.append('foto_anverso', normalizarBlobParaEnvio(item.anversoBlob, 'anverso.jpg'), 'anverso.jpg');
            formData.append('foto_reverso', normalizarBlobParaEnvio(item.reversoBlob, 'reverso.jpg'), 'reverso.jpg');
            formData.append('modo', 'batch');
            formData.append('client_item_id', item.id);
            formData.append('ya_orientada', 'true');

            resp = await fetch('/api/process-survey', {
              method: 'POST',
              body: formData
            });
          }

          const resData = await resp.json();

          if (resp.ok && resData.success) {
            const esDedup = Boolean(resData.deduplicated);
            await window.surveyDB.actualizarEstado(item.id, 'synced', {
              extractedData: resData.datos_extraidos,
              sheetsResult: resData.sheets_result,
              deduplicated: esDedup,
              errorMsg: null
            });
            exitosas++;
            if (esDedup) {
              showToast(`🛡️ ${labelTipo} sincronizada (Deduplicada en servidor)`, 'info');
            } else {
              showToast(`${labelTipo} sincronizada (${restantes - 1} restantes)`, 'success');
            }
          } else {
            throw new Error(resData.detail || resData.error || 'Error de servidor');
          }
        } catch (err) {
          console.error(`Error sincronizando item ${item.id}:`, err);
          fallidosEnEstaSesion.add(item.id);
          await window.surveyDB.actualizarEstado(item.id, 'error', { errorMsg: err.message });
          fallidas++;
          showToast(`Error sincronizando ${labelTipo}: ${err.message}`, 'error');
        }

        await actualizarContadorCola();
        if (state.drawerOpen) await renderizarListaDrawer();
        cargarResumenParticipantes();

        // Pausa ligera optimizada de 500ms (evita saturación y permite respuesta inmediata)
        const pendientesPost = (await window.surveyDB.obtenerPendientes()).filter(it => !fallidosEnEstaSesion.has(it.id));
        if (pendientesPost.length > 0) {
          actualizarBarraSincronizacionUI(true, `Encolando siguiente registro (${pendientesPost.length} pendientes)...`);
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
    } finally {
      state.isSyncing = false;
      await liberarWakeLock();
      actualizarBarraSincronizacionUI(false);
      await actualizarContadorCola();
      if (state.drawerOpen) await renderizarListaDrawer();
      cargarResumenParticipantes();

      if (exitosas > 0 && fallidas === 0) {
        showToast(`🚀 ¡Completado! Se sincronizaron los ${exitosas} registros en segundo plano.`, 'success');
      } else if (exitosas > 0 && fallidas > 0) {
        showToast(`Sincronización en segundo plano: ${exitosas} exitosas, ${fallidas} con error.`, 'info');
      }
    }
  }

  // -------------------------------------------------------------
  // CONTADOR Y DRAWER DE LA COLA LOCAL
  // -------------------------------------------------------------
  async function actualizarContadorCola() {
    try {
      if (window.surveyDB) {
        const count = await window.surveyDB.contarPendientes();
        if (queueCountBadge) queueCountBadge.textContent = count;
        if (!state.isSyncing) {
          if (queueLabel) queueLabel.textContent = `${count} ${count === 1 ? 'registro pendiente' : 'registros pendientes'}`;
          if (queueSubLabel) queueSubLabel.textContent = 'Toca para ver la cola';
          if (btnSyncAllNow) btnSyncAllNow.disabled = (count === 0 || !navigator.onLine);
        }
      }
    } catch (err) {
      console.error('Error consultando cola:', err);
    }
  }
  actualizarContadorCola();
  cargarResumenParticipantes();

  btnOpenDrawer.addEventListener('click', async () => {
    state.drawerOpen = true;
    await renderizarListaDrawer();
    if (drawerBackdrop) {
      drawerBackdrop.style.display = 'block';
      drawerBackdrop.classList.add('active');
    }
    if (drawerContainer) {
      drawerContainer.style.display = 'flex';
      drawerContainer.classList.add('open');
    }
  });

  btnCloseDrawer.addEventListener('click', cerrarDrawer);
  drawerBackdrop.addEventListener('click', cerrarDrawer);

  function cerrarDrawer() {
    state.drawerOpen = false;
    if (drawerBackdrop) {
      drawerBackdrop.style.display = 'none';
      drawerBackdrop.classList.remove('active');
    }
    if (drawerContainer) {
      drawerContainer.style.display = 'none';
      drawerContainer.classList.remove('open');
    }
  }

  // -------------------------------------------------------------
  // REINTENTO / SINCRONIZACIÓN INDIVIDUAL POR ÍTEM (SEGURO Y DEDUPLICADO)
  // -------------------------------------------------------------
  async function sincronizarItemIndividual(id, conModal = false) {
    if (!navigator.onLine) {
      showToast('No tienes conexión de red para sincronizar este registro.', 'error');
      return;
    }

    // Prevenir colisiones con el background worker activo
    if (state.isSyncing) {
      showToast('Hay una sincronización general activa. El registro se procesará automáticamente.', 'info');
      return;
    }

    const items = await window.surveyDB.obtenerTodas();
    const item = items.find(it => it.id === id);
    if (!item) {
      showToast('Registro no encontrado en el dispositivo.', 'error');
      return;
    }

    if (item.status === 'syncing') {
      showToast('Este registro ya se encuentra en proceso de sincronización.', 'info');
      return;
    }

    // Verificar alcance real con el servidor antes de empezar
    const servidorAlcanzable = await verificarConexionServidor();
    if (!servidorAlcanzable) {
      showToast('El servidor en el PC no responde (revisa tu red Wi-Fi o si el PC está activo).', 'error');
      await window.surveyDB.actualizarEstado(item.id, 'error', { errorMsg: 'Servidor no alcanzable' });
      await actualizarContadorCola();
      if (state.drawerOpen) await renderizarListaDrawer();
      return;
    }

    await window.surveyDB.actualizarEstado(item.id, 'syncing');
    await actualizarContadorCola();
    await renderizarListaDrawer();
    await solicitarWakeLock();

    const esAnexo17 = item.tipo === 'anexo17';
    const esAnexo4 = item.tipo === 'anexo4' || item.tipo === 'test';
    const labelTipo = esAnexo17 ? 'Anexo 17' : (esAnexo4 ? 'Anexo 4' : 'Ficha');

    if (conModal) {
      mostrarModalProcesamiento(`Digitalizando ${labelTipo} con IA`, 'Extrayendo datos forenses y sincronizando con el servidor...');
    } else {
      showToast(`Sincronizando ${labelTipo} individualmente...`, 'info');
    }

    try {
      let resp;
      if (esAnexo17) {
        const formData = new FormData();
        formData.append('foto_anverso', normalizarBlobParaEnvio(item.anversoBlob || item.fotoBlob, 'anexo17_pag1.jpg'), 'anexo17_pag1.jpg');
        if (item.reversoBlob) {
          formData.append('foto_reverso', normalizarBlobParaEnvio(item.reversoBlob, 'anexo17_pag2.jpg'), 'anexo17_pag2.jpg');
        }
        if (item.tipoEvaluacion && item.tipoEvaluacion !== 'AUTO') {
          formData.append('tipo_evaluacion', item.tipoEvaluacion);
        }
        if (item.municipio) {
          formData.append('municipio', item.municipio);
        } else if (state.anexo17MunicipioActivo) {
          formData.append('municipio', state.anexo17MunicipioActivo);
        }
        formData.append('modo', 'inmediato');
        formData.append('client_item_id', item.id);
        formData.append('ya_orientada', 'true');

        resp = await fetch('/api/process-anexo17', {
          method: 'POST',
          body: formData
        });
      } else if (esAnexo4) {
        const formData = new FormData();
        formData.append('foto_test', normalizarBlobParaEnvio(item.anversoBlob || item.fotoBlob, 'test.jpg'), 'test.jpg');
        if (item.tipoEvaluacion && item.tipoEvaluacion !== 'AUTO') {
          formData.append('tipo_evaluacion', item.tipoEvaluacion);
        }
        formData.append('modo', 'inmediato');
        formData.append('client_item_id', item.id);
        formData.append('ya_orientada', 'true');

        resp = await fetch('/api/process-test', {
          method: 'POST',
          body: formData
        });
      } else {
        const formData = new FormData();
        formData.append('foto_anverso', normalizarBlobParaEnvio(item.anversoBlob, 'anverso.jpg'), 'anverso.jpg');
        formData.append('foto_reverso', normalizarBlobParaEnvio(item.reversoBlob, 'reverso.jpg'), 'reverso.jpg');
        formData.append('modo', 'inmediato');
        formData.append('client_item_id', item.id);
        formData.append('ya_orientada', 'true');

        resp = await fetch('/api/process-survey', {
          method: 'POST',
          body: formData
        });
      }

      const resData = await resp.json();

      if (resp.ok && resData.success) {
        const esDedup = Boolean(resData.deduplicated);
        await window.surveyDB.actualizarEstado(item.id, 'synced', {
          extractedData: resData.datos_extraidos,
          sheetsResult: resData.sheets_result,
          deduplicated: esDedup,
          errorMsg: null
        });
        if (esDedup) {
          showToast(`🛡️ ${labelTipo} sincronizado (Deduplicado: ya existía registro en Sheets)`, 'info');
        } else {
          showToast(`${labelTipo} sincronizado con éxito (${resData.participante || 'Participante'})`, 'success');
        }
      } else {
        throw new Error(resData.detail || resData.error || 'Error al procesar en el servidor');
      }
    } catch (err) {
      console.error(`Error en sincronización individual de item ${item.id}:`, err);
      await window.surveyDB.actualizarEstado(item.id, 'error', { errorMsg: err.message });
      showToast(`Error al sincronizar ${labelTipo}: ${err.message}`, 'error');
    } finally {
      if (conModal) ocultarModalProcesamiento();
      await liberarWakeLock();
      await actualizarContadorCola();
      await renderizarListaDrawer();
      cargarResumenParticipantes();
    }
  }

  // -------------------------------------------------------------
  // FILTROS Y ACCIONES GLOBALES DEL DRAWER
  // -------------------------------------------------------------
  const filterBtns = [
    { el: filterAll, val: 'all' },
    { el: filterPending, val: 'pending' },
    { el: filterError, val: 'error' },
    { el: filterSynced, val: 'synced' }
  ];

  filterBtns.forEach(({ el, val }) => {
    if (!el) return;
    el.addEventListener('click', () => {
      filterBtns.forEach(f => f.el && f.el.classList.remove('active'));
      el.classList.add('active');
      state.queueFilter = val;
      renderizarListaDrawer();
    });
  });

  if (btnSyncAllFromDrawer) {
    btnSyncAllFromDrawer.addEventListener('click', () => {
      iniciarSincronizacionSegundoPlano(true);
    });
  }

  // -------------------------------------------------------------
  // RENDERIZADO VISUAL ENRIQUECIDO DE LA COLA LOCAL
  // -------------------------------------------------------------
  async function renderizarListaDrawer() {
    activeDrawerObjectUrls.forEach(u => {
      try {
        URL.revokeObjectURL(u);
      } catch (_) {}
    });
    activeDrawerObjectUrls = [];

    drawerQueueList.innerHTML = '';
    const items = await window.surveyDB.obtenerTodas();

    // Actualizar métricas en tiempo real de los chips
    const totalPending = items.filter(it => it.status === 'pending' || it.status === 'syncing').length;
    const totalSynced = items.filter(it => it.status === 'synced').length;
    const totalError = items.filter(it => it.status === 'error').length;

    if (chipPending) chipPending.textContent = `${totalPending} pendientes`;
    if (chipSynced) chipSynced.textContent = `${totalSynced} listos`;
    if (chipError) {
      chipError.textContent = `${totalError} errores`;
      chipError.style.display = totalError > 0 ? 'inline-flex' : 'none';
    }

    // Actualizar números en los botones de filtro
    if (filterAll) filterAll.textContent = `Todos (${items.length})`;
    if (filterPending) filterPending.textContent = `Pendientes (${totalPending})`;
    if (filterError) filterError.textContent = `Errores (${totalError})`;
    if (filterSynced) filterSynced.textContent = `Sincronizados (${totalSynced})`;

    if (btnSyncAllFromDrawer) {
      if (state.isSyncing) {
        btnSyncAllFromDrawer.disabled = true;
        btnSyncAllFromDrawer.innerHTML = '<span class="spinner-inline"></span> Sincronizando...';
      } else {
        btnSyncAllFromDrawer.disabled = (totalPending === 0 || !navigator.onLine);
        btnSyncAllFromDrawer.innerHTML = `
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          <span>Sincronizar Cola (${totalPending})</span>
        `;
      }
    }

    // Filtrar según la pestaña activa
    let itemsFiltrados = items;
    if (state.queueFilter === 'pending') {
      itemsFiltrados = items.filter(it => it.status === 'pending' || it.status === 'syncing');
    } else if (state.queueFilter === 'error') {
      itemsFiltrados = items.filter(it => it.status === 'error');
    } else if (state.queueFilter === 'synced') {
      itemsFiltrados = items.filter(it => it.status === 'synced');
    }

    if (itemsFiltrados.length === 0) {
      let emptyMsg = 'No tienes registros en la cola local.';
      if (state.queueFilter === 'pending') emptyMsg = 'No hay registros pendientes por sincronizar.';
      else if (state.queueFilter === 'error') emptyMsg = 'No hay registros con error.';
      else if (state.queueFilter === 'synced') emptyMsg = 'Aún no se han sincronizado registros.';

      drawerQueueList.innerHTML = `
        <div class="queue-empty-state" style="text-align: center; padding: 32px 16px; color: var(--text-tertiary);">
          <div style="font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 4px;">${emptyMsg}</div>
          <div style="font-size: 0.72rem;">Las capturas se almacenan de forma segura en el almacenamiento local.</div>
        </div>
      `;
      return;
    }

    itemsFiltrados.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = `queue-card-rich card-status-${item.status}`;

      const esAnexo17 = item.tipo === 'anexo17';
      const esAnexo4 = item.tipo === 'anexo4' || item.tipo === 'test';
      const fecha = new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // Badges de tipo sobrios sin emojis
      let typeBadge = '';
      if (esAnexo17) {
        typeBadge = `<span class="badge-item-type badge-type-anexo17">Anexo 17 · ${item.tipoEvaluacion || 'AUTO'}</span>`;
      } else if (esAnexo4) {
        typeBadge = `<span class="badge-item-type badge-type-test">Anexo 4 · ${item.tipoEvaluacion || 'AUTO'}</span>`;
      } else {
        typeBadge = `<span class="badge-item-type badge-type-ficha">Anexo 10 · Ficha</span>`;
      }

      // Píldora de estado funcional
      let statusPill = '';
      if (item.status === 'pending') {
        statusPill = `<span class="status-pill status-pending">Pendiente</span>`;
      } else if (item.status === 'syncing') {
        statusPill = `<span class="status-pill status-pending"><span class="spinner-inline"></span> Sincronizando</span>`;
      } else if (item.status === 'synced') {
        if (item.deduplicated) {
          statusPill = `<span class="status-pill status-synced" style="background-color: var(--color-info); color: #ffffff;">Deduplicado</span>`;
        } else {
          statusPill = `<span class="status-pill status-synced">Sincronizado</span>`;
        }
      } else if (item.status === 'error') {
        statusPill = `<span class="status-pill status-error">Error</span>`;
      }

      // Miniaturas de documentos
      let thumbsHtml = '';
      if (item.anversoBlob || item.fotoBlob) {
        const u1 = URL.createObjectURL(item.anversoBlob || item.fotoBlob);
        activeDrawerObjectUrls.push(u1);
        const lbl1 = esAnexo17 ? 'Pág 1' : (esAnexo4 ? 'Test' : 'Anverso');
        thumbsHtml += `
          <div class="rich-thumb-box">
            <img class="rich-thumb-img" src="${u1}" alt="${lbl1}" />
            <span class="rich-thumb-label">${lbl1}</span>
          </div>
        `;
      }
      if (item.reversoBlob) {
        const u2 = URL.createObjectURL(item.reversoBlob);
        activeDrawerObjectUrls.push(u2);
        const lbl2 = esAnexo17 ? 'Pág 2' : 'Reverso';
        thumbsHtml += `
          <div class="rich-thumb-box">
            <img class="rich-thumb-img" src="${u2}" alt="${lbl2}" />
            <span class="rich-thumb-label">${lbl2}</span>
          </div>
        `;
      }

      // Información de participante y municipio
      let metaTitulo = `Registro #${items.length - index}`;
      let metaMunicipio = esAnexo17 ? (item.municipio || state.anexo17MunicipioActivo || 'SANTA CATALINA') : '';
      let metaDocumento = '';

      if (item.extractedData) {
        const ed = item.extractedData;
        const nombreExt = ed['NOMBRE'] || ed['Nombre completo del participante'] || ed.nombres_apellidos || ed.NOMBRE_COMPLETO || ed.nombre || '';
        if (nombreExt) metaTitulo = nombreExt;
        const muniExt = ed['MUNICIPIO'] || ed['Municipio'] || ed.municipio || '';
        if (muniExt) metaMunicipio = muniExt;
        metaDocumento = ed['Numero de documento identidad'] || ed['numero_documento'] || ed.documento || '';
      }

      // Caja de error
      let errorBoxHtml = '';
      if (item.status === 'error' && item.errorMsg) {
        errorBoxHtml = `
          <div class="rich-error-box" style="padding: 6px 8px; background-color: var(--color-danger-subtle); border-radius: var(--radius-sm); border: 1px solid rgba(239, 68, 68, 0.2); font-size: 0.68rem; color: var(--color-danger);">
            <strong>Fallo:</strong> ${escapeHtml(item.errorMsg)}
          </div>
        `;
      }

      // Generar vista expandible con datos de IA para auditoría
      let extractedDataHtml = '';
      if (item.extractedData && typeof item.extractedData === 'object') {
        const entries = Object.entries(item.extractedData).filter(([k, v]) => v !== null && v !== '' && v !== undefined);
        if (entries.length > 0) {
          const rows = entries.slice(0, 16).map(([k, v]) => {
            const valStr = typeof v === 'object' ? JSON.stringify(v) : String(v);
            return `
              <div class="rich-extracted-row">
                <span class="rich-extracted-key">${escapeHtml(k)}</span>
                <span class="rich-extracted-val" title="${escapeHtml(valStr)}">${escapeHtml(valStr)}</span>
              </div>
            `;
          }).join('');
          extractedDataHtml = `
            <button class="btn-toggle-extracted" type="button" data-id="${item.id}">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
              <span>Ver datos extraídos (${entries.length})</span>
            </button>
            <div id="extractedBox-${item.id}" class="rich-extracted-table" style="display: none;">
              ${rows}
            </div>
          `;
        }
      }

      // Botón de sincronización individual
      let btnSyncHtml = '';
      if (item.status !== 'synced') {
        const btnText = item.status === 'error' ? 'Reintentar' : 'Sincronizar';
        const isThisSyncing = item.status === 'syncing';
        btnSyncHtml = `
          <button class="btn-card-sync" data-id="${item.id}" ${isThisSyncing ? 'disabled' : ''}>
            ${isThisSyncing ? '<span class="spinner-inline"></span> Enviando...' : btnText}
          </button>
        `;
      }

      card.innerHTML = `
        <div class="rich-card-header">
          ${typeBadge}
          ${statusPill}
        </div>
        <div class="rich-card-body">
          <div class="rich-thumbs-wrapper">
            ${thumbsHtml}
          </div>
          <div class="rich-details">
            <div class="rich-meta-title">${escapeHtml(metaTitulo)}</div>
            <div class="rich-meta-sub">
              <span>${fecha}</span>
              ${metaMunicipio ? `<span>· ${escapeHtml(metaMunicipio)}</span>` : ''}
            </div>
            ${metaDocumento ? `
              <div class="rich-meta-detail">Doc: ${escapeHtml(metaDocumento)}</div>
            ` : ''}
            ${item.deduplicated ? `
              <div class="rich-meta-detail" style="color: var(--color-info); font-weight: 500; font-size: 0.68rem; margin-top: 2px;">
                Existía previamente (Deduplicado)
              </div>
            ` : ''}
            ${extractedDataHtml}
          </div>
        </div>
        ${errorBoxHtml}
        <div class="rich-card-actions">
          ${btnSyncHtml}
          <button class="btn-card-delete" data-id="${item.id}" title="Eliminar de la cola">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            <span>Eliminar</span>
          </button>
        </div>
      `;

      // Evento alternar datos extraídos
      const toggleBtn = card.querySelector('.btn-toggle-extracted');
      if (toggleBtn) {
        toggleBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const targetBox = card.querySelector(`#extractedBox-${item.id}`);
          if (targetBox) {
            const isHidden = targetBox.style.display === 'none';
            targetBox.style.display = isHidden ? 'flex' : 'none';
            const numKeys = Object.keys(item.extractedData || {}).length;
            toggleBtn.querySelector('span').textContent = isHidden ? 'Ocultar datos extraídos' : `Ver datos extraídos (${numKeys})`;
          }
        });
      }

      // Evento reintentar / sincronizar individual
      const syncBtn = card.querySelector('.btn-card-sync');
      if (syncBtn) {
        syncBtn.addEventListener('click', async (e) => {
          const id = e.currentTarget.getAttribute('data-id');
          await sincronizarItemIndividual(id);
        });
      }

      // Evento eliminar individual
      const delBtn = card.querySelector('.btn-card-delete');
      if (delBtn) {
        delBtn.addEventListener('click', async (e) => {
          const id = e.currentTarget.getAttribute('data-id');
          if (confirm('¿Eliminar este registro de la cola local? Esta acción no se puede deshacer.')) {
            await window.surveyDB.eliminarEncuesta(id);
            await actualizarContadorCola();
            await renderizarListaDrawer();
            showToast('Registro eliminado de la cola.', 'info');
          }
        });
      }

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
    actualizarContadorCola();
    if (isOnline) {
      // Reanudar sincronización de la cola automáticamente en segundo plano si hay pendientes
      iniciarSincronizacionSegundoPlano(false);
    } else {
      showToast('Estás sin conexión. Las capturas se guardarán en cola local.', 'error');
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
  // CONSULTA DE RESUMEN DE PARTICIPANTES EN CACHÉ Y ESTADO MOTOR
  // -------------------------------------------------------------
  async function cargarResumenParticipantes() {
    try {
      if (!navigator.onLine) return;
      const res = await fetch('/api/health');
      if (res.ok) {
        const h = await res.json();
        const maestroCount = h.patron_maestro_participantes || 0;
        if (netStatusText) {
          netStatusText.textContent = `Gemini Online`;
          netStatusText.title = `Motor: Google Gemini | Patrón Maestro: ${maestroCount} registros`;
        }
        if (masterCacheCount) {
          masterCacheCount.textContent = maestroCount;
        }
      }
    } catch (err) {
      console.warn('No se pudo consultar el catálogo de participantes:', err);
    }
  }

  // -------------------------------------------------------------
  // GESTIÓN DEL PATRÓN MAESTRO DE PARTICIPANTES (JARO-WINKLER)
  // EXCLUSIVO PARA PRE Y POST TEST (ANEXO 4 Y ANEXO 17) VIA EXCEL
  // -------------------------------------------------------------
  const btnOpenMasterModal = document.getElementById('btnOpenMasterModal');
  const btnCloseMasterModal = document.getElementById('btnCloseMasterModal');
  const masterBackdrop = document.getElementById('masterBackdrop');
  const masterModal = document.getElementById('masterModal');
  const masterCacheCount = document.getElementById('masterCacheCount');
  const statTotalParticipantes = document.getElementById('statTotalParticipantes');
  const statTotalMunicipios = document.getElementById('statTotalMunicipios');
  const participantsBreakdown = document.getElementById('participantsBreakdown');
  const inputMasterExcel = document.getElementById('inputMasterExcel');
  const btnUploadMasterExcel = document.getElementById('btnUploadMasterExcel');

  async function actualizarEstadisticasPatronMaestro() {
    try {
      if (!navigator.onLine) return;
      const res = await fetch('/api/participants/stats');
      if (!res.ok) return;
      const data = await res.json();
      if (!data.success || !data.stats) return;

      const total = data.stats.total || 0;
      const porMun = data.stats.por_municipio || {};
      const numMunicipios = Object.keys(porMun).length;

      if (masterCacheCount) masterCacheCount.textContent = total;
      if (statTotalParticipantes) statTotalParticipantes.textContent = total;
      if (statTotalMunicipios) statTotalMunicipios.textContent = numMunicipios;

      if (participantsBreakdown) {
        participantsBreakdown.innerHTML = '';
        const sortedMuns = Object.entries(porMun).sort((a, b) => b[1] - a[1]);
        if (sortedMuns.length === 0) {
          participantsBreakdown.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted); display:block; padding:8px 4px;">Sin participantes en memoria aún. Adjunta un archivo Excel (.xlsx o .csv).</span>';
        } else {
          sortedMuns.forEach(([mun, count]) => {
            const row = document.createElement('div');
            row.className = 'mun-row';
            row.innerHTML = `<span class="mun-name">${mun}</span><span class="mun-count">${count}</span>`;
            participantsBreakdown.appendChild(row);
          });
        }
      }
    } catch (e) {
      console.warn('Error obteniendo stats de patrón maestro:', e);
    }
  }

  function abrirModalPatronMaestro() {
    actualizarEstadisticasPatronMaestro();
    if (masterBackdrop) {
      masterBackdrop.style.display = 'block';
      masterBackdrop.classList.add('active');
    }
    if (masterModal) {
      masterModal.style.display = 'flex';
      masterModal.classList.add('open');
    }
  }

  function cerrarModalPatronMaestro() {
    if (masterBackdrop) {
      masterBackdrop.style.display = 'none';
      masterBackdrop.classList.remove('active');
    }
    if (masterModal) {
      masterModal.style.display = 'none';
      masterModal.classList.remove('open');
    }
  }

  if (btnOpenMasterModal) btnOpenMasterModal.addEventListener('click', abrirModalPatronMaestro);
  if (btnCloseMasterModal) btnCloseMasterModal.addEventListener('click', cerrarModalPatronMaestro);
  if (masterBackdrop) masterBackdrop.addEventListener('click', cerrarModalPatronMaestro);

  if (btnUploadMasterExcel) {
    btnUploadMasterExcel.addEventListener('click', async () => {
      if (!inputMasterExcel || !inputMasterExcel.files || inputMasterExcel.files.length === 0) {
        showToast('Selecciona un archivo Excel (.xlsx) o CSV primero.', 'error');
        return;
      }
      const file = inputMasterExcel.files[0];
      const formData = new FormData();
      formData.append('file', file);

      btnUploadMasterExcel.disabled = true;
      btnUploadMasterExcel.textContent = 'Cargando...';
      try {
        const res = await fetch('/api/participants/upload-file', {
          method: 'POST',
          body: formData
        });
        const result = await res.json();
        if (result.success) {
          showToast(`Ingestados ${result.total_cargados} participantes del archivo.`, 'success');
          actualizarEstadisticasPatronMaestro();
          cargarResumenParticipantes();
          inputMasterExcel.value = '';
        } else {
          showToast(result.detail || result.error || 'Error al procesar archivo.', 'error');
        }
      } catch (err) {
        showToast('Error al subir archivo: ' + err.message, 'error');
      } finally {
        btnUploadMasterExcel.disabled = false;
        btnUploadMasterExcel.textContent = 'Cargar Archivo Excel';
      }
    });
  }

  const btnResetMaster = document.getElementById('btnResetMaster');
  if (btnResetMaster) {
    btnResetMaster.addEventListener('click', async () => {
      if (!confirm('¿Seguro que deseas vaciar la memoria de participantes a 0? Podrás sincronizar de nuevo en cualquier momento.')) {
        return;
      }
      btnResetMaster.disabled = true;
      btnResetMaster.textContent = 'Vaciando...';
      try {
        const res = await fetch('/api/participants/clear', { method: 'POST' });
        const result = await res.json();
        if (result.success) {
          showToast('Memoria de participantes reiniciada a 0.', 'info');
          actualizarEstadisticasPatronMaestro();
          cargarResumenParticipantes();
        } else {
          showToast('Error al vaciar memoria.', 'error');
        }
      } catch (err) {
        showToast('Error de conexión: ' + err.message, 'error');
      } finally {
        btnResetMaster.disabled = false;
        btnResetMaster.textContent = 'Vaciar Memoria (Reiniciar Catálogo)';
      }
    });
  }

  // Llamar al inicio
  cargarMunicipiosAnexo17DesdeStorage();
  actualizarSelectMunicipiosAnexo17();
  cargarResumenParticipantes();
  actualizarEstadisticasPatronMaestro();

  // Auto-recuperación de Foto 1 si Android/iOS recargó la pestaña al usar la cámara
  async function restaurarBorradorActivoSiExiste() {
    try {
      if (!window.surveyDB || typeof window.surveyDB.obtenerBorradorActivo !== 'function') return;
      const draft = await window.surveyDB.obtenerBorradorActivo();
      if (draft && draft.foto1Blob && !state.foto1Blob) {
        console.log('[Auto-Recovery] Restaurando borrador de Foto 1 desde IndexedDB...');
        // 1. Cambiar el modo PRIMERO si es distinto (antes de asignar foto1Blob, porque cambiarModo limpia el formulario)
        if (draft.tipo && (draft.tipo === 'ficha' || draft.tipo === 'anexo17') && state.mode !== draft.tipo) {
          cambiarModo(draft.tipo);
        }
        if (draft.extra && draft.extra.tipoEvaluacion) {
          state.tipoEvaluacion = draft.extra.tipoEvaluacion;
        }

        // 2. Restaurar el blob en el estado y volver a persistir el borrador
        state.foto1Blob = draft.foto1Blob;
        state.foto1Mime = draft.foto1Mime || 'image/jpeg';
        await window.surveyDB.guardarBorradorActivo(state.mode, state.foto1Blob, state.foto1Mime, {
          tipoEvaluacion: state.tipoEvaluacion
        });

        setPreviewBlob(imgPreview1, draft.foto1Blob);
        imgPreview1.style.display = 'block';
        placeholderFoto1.style.display = 'none';
        badgeCheck1.style.display = 'flex';
        if (slotActions1) slotActions1.style.display = 'flex';
        slotFoto1.classList.remove('active-slot');
        slotFoto1.classList.add('completed');

        setStepFicha(2);
        showToast('Foto 1 recuperada automáticamente tras recarga de memoria.', 'info');
      }
    } catch (err) {
      console.warn('Aviso al verificar borrador activo en inicio:', err);
    }
  }

  restaurarBorradorActivoSiExiste();

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
