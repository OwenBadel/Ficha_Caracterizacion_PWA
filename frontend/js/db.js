/**
 * db.js — Capa de Persistencia Local Offline (IndexedDB)
 * Almacena encuestas en lotes (fotografías como Blobs y metadatos)
 * permitiendo trabajo de campo sin conexión.
 */

const DB_NAME = 'FichaCaracterizacionDB';
const DB_VERSION = 1;
const STORE_NAME = 'encuestas';

class LocalSurveyDB {
  constructor() {
    this.db = null;
  }

  async init() {
    if (this.db) return this.db;

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          store.createIndex('status', 'status', { unique: false });
          store.createIndex('createdAt', 'createdAt', { unique: false });
        }
      };

      request.onsuccess = (event) => {
        this.db = event.target.result;
        resolve(this.db);
      };

      request.onerror = (event) => {
        console.error('Error abriendo IndexedDB:', event.target.error);
        reject(event.target.error);
      };
    });
  }

  /**
   * Guarda una encuesta en la cola local
   * @param {Blob} anversoBlob
   * @param {Blob} reversoBlob
   * @param {string} anversoMime
   * @param {string} reversoMime
   */
  async guardarEncuesta(anversoBlob, reversoBlob, anversoMime = 'image/jpeg', reversoMime = 'image/jpeg') {
    await this.init();
    const id = 'encuesta_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7);
    const item = {
      id,
      anversoBlob,
      reversoBlob,
      anversoMime,
      reversoMime,
      createdAt: new Date().toISOString(),
      status: 'pending', // 'pending', 'syncing', 'synced', 'error'
      errorMsg: null,
      extractedData: null
    };

    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([STORE_NAME], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.add(item);

      req.onsuccess = () => resolve(item);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Retorna todas las encuestas pendientes o con error
   */
  async obtenerPendientes() {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([STORE_NAME], 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();

      req.onsuccess = () => {
        const items = req.result || [];
        const pendientes = items.filter(it => it.status === 'pending' || it.status === 'error');
        pendientes.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt));
        resolve(pendientes);
      };
      req.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Retorna todas las encuestas almacenadas
   */
  async obtenerTodas() {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([STORE_NAME], 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();

      req.onsuccess = () => {
        const items = req.result || [];
        items.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
        resolve(items);
      };
      req.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Conteo de encuestas pendientes
   */
  async contarPendientes() {
    const pendientes = await this.obtenerPendientes();
    return pendientes.length;
  }

  /**
   * Actualiza el estado de una encuesta
   */
  async actualizarEstado(id, status, extra = {}) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([STORE_NAME], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const getReq = store.get(id);

      getReq.onsuccess = () => {
        const data = getReq.result;
        if (!data) {
          return reject(new Error('Encuesta no encontrada en IDB: ' + id));
        }
        data.status = status;
        if (extra.errorMsg !== undefined) data.errorMsg = extra.errorMsg;
        if (extra.extractedData !== undefined) data.extractedData = extra.extractedData;
        if (extra.sheetsResult !== undefined) data.sheetsResult = extra.sheetsResult;
        data.updatedAt = new Date().toISOString();

        const putReq = store.put(data);
        putReq.onsuccess = () => resolve(data);
        putReq.onerror = (e) => reject(e.target.error);
      };

      getReq.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Elimina una encuesta por ID
   */
  async eliminarEncuesta(id) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([STORE_NAME], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(id);

      req.onsuccess = () => resolve(true);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Elimina todas las encuestas ya sincronizadas para liberar espacio
   */
  async limpiarSincronizadas() {
    await this.init();
    const todas = await this.obtenerTodas();
    const sincronizadas = todas.filter(it => it.status === 'synced');
    for (const item of sincronizadas) {
      await this.eliminarEncuesta(item.id);
    }
    return sincronizadas.length;
  }
}

// Exportar instancia singleton
window.surveyDB = new LocalSurveyDB();
