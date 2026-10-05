<<<<<<< HEAD
'use strict';

/**
 * llm-config.js — Gestión API LLM (frontend)
 * Sincroniza localStorage (llm_configs, llm_active) con backend /api/v1/llm
 * Compatible: ES Module (import) y global (window.LLMConfig)
 */

const LLM_API = '/api/v1/llm';
const LS_KEY = 'llm_configs';
const LS_ACTIVE = 'llm_active';

// Helpers localStorage con try/catch
function lsGet(k, fallback) {
  try {
    const v = localStorage.getItem(k);
    return v ? JSON.parse(v) : fallback;
  } catch (_) {
    return fallback;
  }
}
function lsSet(k, v) {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch (_) {
    console.warn('localStorage set failed', k);
  }
}
function lsGetStr(k) {
  try { return localStorage.getItem(k); } catch (_) { return null; }
}
function lsSetStr(k, v) {
  try {
    if (v === null || v === undefined) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch (_) {}
}

// Fetch helper con manejo de errores
async function apiFetch(url, opts = {}) {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!r.ok) {
    const txt = await r.text().catch(() => r.statusText);
    throw new Error(txt || `HTTP ${r.status}`);
  }
  // 204 No Content
  if (r.status === 204) return null;
  return r.json();
}

// Backend sync (opcional, fallback a localStorage si backend no disponible)
export async function fetchLLMs() {
  try {
    const list = await apiFetch(`${LLM_API}/config`);
    // Sincroniza a localStorage (sin exponer api_key real, solo masked_key)
    // Mantiene copia local para UI offline
    if (Array.isArray(list) && list.length) {
      const local = lsGet(LS_KEY, []);
      // Si backend tiene más, actualiza local (merge por id)
      const merged = [...local];
      for (const b of list) {
        if (!merged.find((l) => l.id === b.id)) {
          merged.push({
            id: b.id,
            provider: b.provider,
            name: b.name,
            model: b.model,
            base_url: b.base_url || '',
            temperature: b.temperature ?? 0.7,
            max_tokens: b.max_tokens ?? 2048,
            timeout: b.timeout ?? 30000,
            api_key: `••••${(b.masked_key || '').slice(-4)}`, // no exponer real
            is_active: b.is_active,
          });
        }
      }
      lsSet(LS_KEY, merged);
      const active = list.find((c) => c.is_active);
      if (active) lsSetStr(LS_ACTIVE, active.id);
    }
    return list;
  } catch (e) {
    console.warn('fetchLLMs backend fallo, usando localStorage', e.message);
    return lsGet(LS_KEY, []);
  }
}

export async function saveLLM(payload) {
  // payload: {provider, name, api_key, model, base_url, temperature, max_tokens, timeout}
  if (!payload || !payload.api_key || payload.api_key.length < 8) {
    throw new Error('API Key inválida (mín 8 chars)');
  }
  try {
    const saved = await apiFetch(`${LLM_API}/config`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    // Actualiza localStorage
    const local = lsGet(LS_KEY, []);
    local.push({
      id: saved.id,
      provider: saved.provider,
      name: saved.name,
      model: saved.model,
      base_url: saved.base_url || '',
      temperature: saved.temperature,
      max_tokens: saved.max_tokens,
      timeout: saved.timeout,
      api_key: payload.api_key, // guarda real solo local
      is_active: saved.is_active,
    });
    lsSet(LS_KEY, local);
    if (saved.is_active) lsSetStr(LS_ACTIVE, saved.id);
    return saved;
  } catch (e) {
    // Fallback local si backend no disponible (demo)
    console.warn('saveLLM backend fallo, guardando solo local', e.message);
    const id = `llm_${Date.now()}`;
    const rec = { id, ...payload, is_active: lsGet(LS_KEY, []).length === 0 };
    const local = lsGet(LS_KEY, []);
    local.push({ ...rec, api_key: payload.api_key });
    lsSet(LS_KEY, local);
    if (rec.is_active) lsSetStr(LS_ACTIVE, id);
    return { id, ...payload, masked_key: `••••${payload.api_key.slice(-4)}`, is_active: rec.is_active };
  }
}

export async function testLLM(payload) {
  // payload: {provider, api_key, model, base_url}
  return apiFetch(`${LLM_API}/test`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function activateLLM(id) {
  if (!id) throw new Error('id requerido');
  try {
    const res = await apiFetch(`${LLM_API}/config/${id}/activate`, { method: 'POST' });
    lsSetStr(LS_ACTIVE, id);
    // Actualiza flag local
    const local = lsGet(LS_KEY, []);
    local.forEach((c) => { c.is_active = c.id === id; });
    lsSet(LS_KEY, local);
    return res;
  } catch (e) {
    // Fallback local
    console.warn('activateLLM backend fallo, solo local', e.message);
    lsSetStr(LS_ACTIVE, id);
    const local = lsGet(LS_KEY, []);
    local.forEach((c) => { c.is_active = c.id === id; });
    lsSet(LS_KEY, local);
    return { id, activated: true, local: true };
  }
}

export async function deleteLLM(id) {
  if (!id) throw new Error('id requerido');
  try {
    await apiFetch(`${LLM_API}/config/${id}`, { method: 'DELETE' });
  } catch (e) {
    console.warn('deleteLLM backend fallo', e.message);
  }
  const local = lsGet(LS_KEY, []).filter((c) => c.id !== id);
  lsSet(LS_KEY, local);
  if (lsGetStr(LS_ACTIVE) === id) {
    const next = local[0]?.id || null;
    lsSetStr(LS_ACTIVE, next);
  }
  return { deleted: id };
}

export function getActiveLocal() {
  const activeId = lsGetStr(LS_ACTIVE);
  const list = lsGet(LS_KEY, []);
  return list.find((c) => c.id === activeId) || list[0] || null;
}

// Exponer global para scripts no-module
if (typeof window !== 'undefined') {
  window.LLMConfig = { fetchLLMs, saveLLM, testLLM, activateLLM, deleteLLM, getActiveLocal, LLM_API };
}
=======
/*
 * ============================================================
 * llm-config.js
 * ============================================================
 * AGENT-REACT
 *
 * Compatible con:
 *
 *   <script src="/llm-config.js"></script>
 *
 * NO requiere type="module".
 *
 * Expone:
 *
 *   window.LLMConfig
 *
 * API:
 *
 *   LLMConfig.fetchLLMs()
 *   LLMConfig.saveLLM(payload)
 *   LLMConfig.testLLM(payload)
 *   LLMConfig.activateLLM(id)
 *   LLMConfig.deleteLLM(id)
 *   LLMConfig.getActiveLocal()
 *   LLMConfig.getActiveId()
 *   LLMConfig.clearLocal()
 *
 * Backend:
 *
 *   /api/v1/llm
 *
 * Seguridad:
 *
 * - NO guarda API keys reales en localStorage.
 * - Solo conserva masked_key.
 * - La API key debe permanecer en backend.
 * ============================================================
 */

'use strict';


// ============================================================
// CONFIGURATION
// ============================================================

const LLM_API = '/api/v1/llm';

const LS_KEY = 'llm_configs';

const LS_ACTIVE = 'llm_active';


// ============================================================
// LOGGER
// ============================================================

const LOG_PREFIX =
    '[LLMConfig]';


function log(...args) {

    console.log(
        LOG_PREFIX,
        ...args
    );
}


function warn(...args) {

    console.warn(
        LOG_PREFIX,
        ...args
    );
}


function error(...args) {

    console.error(
        LOG_PREFIX,
        ...args
    );
}


// ============================================================
// LOCAL STORAGE
// ============================================================

function lsGet(
    key,
    fallback = null
) {

    try {

        const value =
            localStorage.getItem(
                key
            );


        if (
            value === null ||
            value === undefined ||
            value === ''
        ) {

            return fallback;
        }


        return JSON.parse(
            value
        );

    } catch (err) {

        warn(
            'localStorage read failed:',
            key,
            err
        );


        return fallback;
    }
}


function lsSet(
    key,
    value
) {

    try {

        localStorage.setItem(
            key,
            JSON.stringify(value)
        );

        return true;

    } catch (err) {

        warn(
            'localStorage write failed:',
            key,
            err
        );


        return false;
    }
}


function lsGetStr(key) {

    try {

        return localStorage.getItem(
            key
        );

    } catch (_) {

        return null;
    }
}


function lsSetStr(
    key,
    value
) {

    try {

        if (
            value === null ||
            value === undefined ||
            value === ''
        ) {

            localStorage.removeItem(
                key
            );

        } else {

            localStorage.setItem(
                key,
                String(value)
            );
        }


        return true;

    } catch (err) {

        warn(
            'localStorage string write failed:',
            key,
            err
        );


        return false;
    }
}


// ============================================================
// SAFE JSON
// ============================================================

async function parseResponse(
    response
) {

    if (
        response.status ===
        204
    ) {

        return null;
    }


    const text =
        await response.text();


    if (!text) {

        return null;
    }


    try {

        return JSON.parse(
            text
        );

    } catch (_) {

        return text;
    }
}


// ============================================================
// API FETCH
// ============================================================

async function apiFetch(
    url,
    options = {}
) {

    const config = {

        method:
            options.method ||
            'GET',

        ...options,

        headers: {

            Accept:
                'application/json',

            ...(options.body
                ? {
                    'Content-Type':
                        'application/json'
                }
                : {}),

            ...(options.headers || {})
        }
    };


    let response;


    try {

        response =
            await fetch(
                url,
                config
            );

    } catch (err) {

        const networkError =
            new Error(
                `No se pudo conectar con el backend LLM: ${err.message}`
            );


        networkError.code =
            'NETWORK_ERROR';


        throw networkError;
    }


    const data =
        await parseResponse(
            response
        );


    if (!response.ok) {

        let message =
            `HTTP ${response.status}`;


        if (
            typeof data ===
            'string' &&
            data.trim()
        ) {

            message =
                data;

        } else if (
            data?.detail
        ) {

            message =
                typeof data.detail ===
                'string'
                    ? data.detail
                    : JSON.stringify(
                        data.detail
                    );

        } else if (
            data?.message
        ) {

            message =
                data.message;
        }


        const err =
            new Error(
                message
            );


        err.status =
            response.status;


        err.data =
            data;


        throw err;
    }


    return data;
}


// ============================================================
// NORMALIZE LLM
// ============================================================

function normalizeLLM(
    item
) {

    if (!item) {

        return null;
    }


    return {

        id:
            item.id ||
            item.llm_id ||
            null,

        provider:
            item.provider ||
            '',

        name:
            item.name ||
            item.display_name ||
            item.provider ||
            'LLM',

        model:
            item.model ||
            '',

        base_url:
            item.base_url ||
            '',

        temperature:
            item.temperature ??
            0.7,

        max_tokens:
            item.max_tokens ??
            2048,

        timeout:
            item.timeout ??
            30000,

        masked_key:
            item.masked_key ||
            item.api_key_masked ||
            '',

        is_active:
            Boolean(
                item.is_active
            )
    };
}


// ============================================================
// SAFE LOCAL RECORD
// ============================================================
//
// IMPORTANTE:
// Nunca guardar:
//
//   api_key
//   authorization
//   bearer token
//   secret
//
// Solo metadata.
//

function toSafeLocal(
    item
) {

    const normalized =
        normalizeLLM(
            item
        );


    if (!normalized) {

        return null;
    }


    return {

        id:
            normalized.id,

        provider:
            normalized.provider,

        name:
            normalized.name,

        model:
            normalized.model,

        base_url:
            normalized.base_url,

        temperature:
            normalized.temperature,

        max_tokens:
            normalized.max_tokens,

        timeout:
            normalized.timeout,

        masked_key:
            normalized.masked_key,

        is_active:
            normalized.is_active
    };
}


// ============================================================
// SAVE SAFE LOCAL CONFIG
// ============================================================

function saveLocalConfig(
    item
) {

    const safe =
        toSafeLocal(
            item
        );


    if (
        !safe ||
        !safe.id
    ) {

        return;
    }


    const list =
        lsGet(
            LS_KEY,
            []
        );


    const index =
        list.findIndex(
            item =>
                String(item.id) ===
                String(safe.id)
        );


    if (index >= 0) {

        list[index] =
            {
                ...list[index],
                ...safe
            };

    } else {

        list.push(
            safe
        );
    }


    lsSet(
        LS_KEY,
        list
    );


    if (
        safe.is_active
    ) {

        lsSetStr(
            LS_ACTIVE,
            safe.id
        );
    }
}


// ============================================================
// FETCH LLM CONFIGURATIONS
// ============================================================

async function fetchLLMs() {

    try {

        const response =
            await apiFetch(
                `${LLM_API}/config`
            );


        const list =
            Array.isArray(response)

                ? response

                : (
                    response?.items ||
                    response?.configs ||
                    response?.data ||
                    []
                );


        const normalized =
            list
                .map(
                    normalizeLLM
                )
                .filter(
                    item =>
                        item &&
                        item.id
                );


        // Replace local metadata with backend state.
        const safe =
            normalized.map(
                toSafeLocal
            );


        lsSet(
            LS_KEY,
            safe
        );


        const active =
            normalized.find(
                item =>
                    item.is_active
            );


        if (active) {

            lsSetStr(
                LS_ACTIVE,
                active.id
            );
        }


        log(
            'LLM configurations loaded:',
            normalized.length
        );


        return normalized;

    } catch (err) {

        warn(
            'Backend unavailable. Using local metadata.',
            err.message
        );


        return lsGet(
            LS_KEY,
            []
        );
    }
}


// ============================================================
// SAVE LLM
// ============================================================

async function saveLLM(
    payload
) {

    if (!payload) {

        throw new Error(
            'Payload LLM requerido'
        );
    }


    const provider =
        String(
            payload.provider ||
            ''
        ).trim();


    const model =
        String(
            payload.model ||
            ''
        ).trim();


    const apiKey =
        String(
            payload.api_key ||
            ''
        ).trim();


    if (!provider) {

        throw new Error(
            'Provider requerido'
        );
    }


    if (!model) {

        throw new Error(
            'Model requerido'
        );
    }


    if (
        apiKey &&
        apiKey.length < 8
    ) {

        throw new Error(
            'API Key inválida (mínimo 8 caracteres)'
        );
    }


    /*
     * La API key se envía SOLO al backend.
     *
     * NO se escribe en localStorage.
     */

    try {

        const saved =
            await apiFetch(
                `${LLM_API}/config`,
                {
                    method:
                        'POST',

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        const normalized =
            normalizeLLM(
                saved
            );


        if (
            normalized
        ) {

            saveLocalConfig(
                normalized
            );
        }


        log(
            'LLM saved:',
            normalized?.id
        );


        return saved;

    } catch (err) {

        /*
         * NO hacemos fallback guardando
         * la API key en localStorage.
         */

        error(
            'No se pudo guardar LLM en backend:',
            err
        );


        throw err;
    }
}


// ============================================================
// TEST LLM
// ============================================================

async function testLLM(
    payload
) {

    if (!payload) {

        throw new Error(
            'Payload requerido'
        );
    }


    return apiFetch(
        `${LLM_API}/test`,
        {
            method:
                'POST',

            body:
                JSON.stringify(
                    payload
                )
        }
    );
}


// ============================================================
// ACTIVATE LLM
// ============================================================

async function activateLLM(
    id
) {

    if (!id) {

        throw new Error(
            'id requerido'
        );
    }


    try {

        const response =
            await apiFetch(
                `${LLM_API}/config/${encodeURIComponent(id)}/activate`,
                {
                    method:
                        'POST'
                }
            );


        const local =
            lsGet(
                LS_KEY,
                []
            );


        local.forEach(
            item => {

                item.is_active =
                    String(item.id) ===
                    String(id);
            }
        );


        lsSet(
            LS_KEY,
            local
        );


        lsSetStr(
            LS_ACTIVE,
            id
        );


        return response;

    } catch (err) {

        /*
         * Fallback solamente para metadata local.
         */

        warn(
            'Backend activate failed:',
            err.message
        );


        const local =
            lsGet(
                LS_KEY,
                []
            );


        const exists =
            local.some(
                item =>
                    String(item.id) ===
                    String(id)
            );


        if (!exists) {

            throw err;
        }


        local.forEach(
            item => {

                item.is_active =
                    String(item.id) ===
                    String(id);
            }
        );


        lsSet(
            LS_KEY,
            local
        );


        lsSetStr(
            LS_ACTIVE,
            id
        );


        return {

            id,

            activated:
                true,

            local:
                true
        };
    }
}


// ============================================================
// DELETE LLM
// ============================================================

async function deleteLLM(
    id
) {

    if (!id) {

        throw new Error(
            'id requerido'
        );
    }


    try {

        await apiFetch(
            `${LLM_API}/config/${encodeURIComponent(id)}`,
            {
                method:
                    'DELETE'
            }
        );

    } catch (err) {

        if (
            err.status !==
            404
        ) {

            throw err;
        }
    }


    const local =
        lsGet(
            LS_KEY,
            []
        ).filter(
            item =>
                String(item.id) !==
                String(id)
        );


    lsSet(
        LS_KEY,
        local
    );


    if (
        String(
            lsGetStr(
                LS_ACTIVE
            )
        ) ===
        String(id)
    ) {

        const next =
            local.find(
                item =>
                    item.is_active
            ) ||
            local[0] ||
            null;


        lsSetStr(
            LS_ACTIVE,
            next?.id ||
            null
        );
    }


    return {

        deleted:
            id
    };
}


// ============================================================
// ACTIVE LLM
// ============================================================

function getActiveId() {

    return lsGetStr(
        LS_ACTIVE
    );
}


function getActiveLocal() {

    const activeId =
        getActiveId();


    const list =
        lsGet(
            LS_KEY,
            []
        );


    return (
        list.find(
            item =>
                String(item.id) ===
                String(activeId)
        ) ||
        list.find(
            item =>
                item.is_active
        ) ||
        list[0] ||
        null
    );
}


// ============================================================
// CLEAR LOCAL CACHE
// ============================================================

function clearLocal() {

    try {

        localStorage.removeItem(
            LS_KEY
        );

        localStorage.removeItem(
            LS_ACTIVE
        );

    } catch (_) {}


    return {
        cleared:
            true
    };
}


// ============================================================
// PROVIDERS
// ============================================================

function getProviders() {

    return [

        {
            id:
                'openai',

            name:
                'OpenAI'
        },

        {
            id:
                'gemini',

            name:
                'Google Gemini'
        },

        {
            id:
                'openrouter',

            name:
                'OpenRouter'
        },

        {
            id:
                'ollama',

            name:
                'Ollama'
        },

        {
            id:
                'anthropic',

            name:
                'Anthropic'
        }
    ];
}


// ============================================================
// HEALTH
// ============================================================

async function health() {

    try {

        return await apiFetch(
            `${LLM_API}/health`
        );

    } catch (_) {

        return {

            status:
                'offline'
        };
    }
}


// ============================================================
// PUBLIC API
// ============================================================

const LLMConfig = {

    LLM_API,

    LS_KEY,

    LS_ACTIVE,

    fetchLLMs,

    saveLLM,

    testLLM,

    activateLLM,

    deleteLLM,

    getActiveLocal,

    getActiveId,

    getProviders,

    clearLocal,

    health
};


// ============================================================
// GLOBAL
// ============================================================

if (
    typeof window !==
    'undefined'
) {

    window.LLMConfig =
        LLMConfig;

    /*
     * Compatibilidad con código
     * existente.
     */

    window.fetchLLMs =
        fetchLLMs;

    window.saveLLM =
        saveLLM;

    window.testLLM =
        testLLM;

    window.activateLLM =
        activateLLM;

    window.deleteLLM =
        deleteLLM;

    window.getActiveLLM =
        getActiveLocal;


    log(
        'Loaded successfully'
    );
}


// ============================================================
// COMMONJS / NODE OPTIONAL
// ============================================================

if (
    typeof module !==
    'undefined' &&
    module.exports
) {

    module.exports =
        LLMConfig;
}
>>>>>>> ebbf022 (feat: complete Agent ReAct architecture)
