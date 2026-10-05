<<<<<<< HEAD
/* Agent WebSocket client: reconnect + resume by persisted event sequence. */
export class AgentWebSocket {
  constructor({baseUrl='', onEvent=()=>{}, onDelta=()=>{}, onFinal=()=>{}, onError=()=>{}, onClose=()=>{}, maxRetries=8, retryBaseMs=500}={}) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${baseUrl || protocol + '//' + location.host}/api/v1/agent/ws`;
    this.onEvent = onEvent; this.onDelta = onDelta; this.onFinal = onFinal; this.onError = onError; this.onClose = onClose;
    this.ws = null; this.maxRetries = maxRetries; this.retryBaseMs = retryBaseMs;
    this.retryCount = 0; this.manualClose = false; this.pendingStart = null;
    this.runId = null; this.lastSequence = 0; this.connected = false; this.reconnecting = false;
  }
  connect() {
    this.manualClose = false;
    return new Promise((resolve,reject)=>{
      this.ws = new WebSocket(this.url);
      const timer = setTimeout(()=>reject(new Error('WebSocket connection timeout')), 10000);
      this.ws.onopen = () => { clearTimeout(timer); this.connected = true; this.retryCount = 0; this.reconnecting = false; resolve(); this._resumeOrStart(); };
      this.ws.onmessage = e => this._handle(e.data);
      this.ws.onerror = e => { clearTimeout(timer); this.onError(e); if(!this.connected) reject(e); };
      this.ws.onclose = e => { this.connected = false; this.onClose(e); if(!this.manualClose) this._scheduleReconnect(); };
    });
  }
  async _resumeOrStart() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    if (this.runId) {
      this.ws.send(JSON.stringify({type:'resume', run_id:this.runId, after:this.lastSequence}));
    } else if (this.pendingStart) {
      const payload = {...this.pendingStart, type:'start'};
      this.pendingStart = null;
      this.ws.send(JSON.stringify(payload));
    }
  }
  _handle(raw) {
    try {
      const event = JSON.parse(raw);
      if (event.run_id) this.runId = event.run_id;
      if (Number.isFinite(event.sequence) && event.sequence > this.lastSequence) this.lastSequence = event.sequence;
      this.onEvent(event);
      if (event.type === 'delta') this.onDelta(event.delta || '');
      if (event.type === 'final') this.onFinal(event);
      if (event.type === 'done' || event.type === 'cancelled' || event.type === 'error') {
        if (event.type !== 'error') this.pendingStart = null;
      }
    } catch (err) { this.onError(err); }
  }
  async send(payload) {
    if (payload.type === 'start' || !payload.type) { this.pendingStart = {...payload, type:'start'}; }
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) await this.connect();
    else await this._resumeOrStart();
  }
  async resume(runId=this.runId, after=this.lastSequence) {
    this.runId = runId; this.lastSequence = after;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) await this.connect();
    else this.ws.send(JSON.stringify({type:'resume', run_id:runId, after}));
  }
  cancel() {
    if (this.runId && this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({type:'cancel', run_id:this.runId}));
  }
  _scheduleReconnect() {
    if (this.reconnecting || this.manualClose || this.retryCount >= this.maxRetries) return;
    this.reconnecting = true;
    const delay = Math.min(15000, this.retryBaseMs * (2 ** this.retryCount)) + Math.round(Math.random()*250);
    this.retryCount++;
    setTimeout(()=>{ this.reconnecting=false; this.connect().catch(()=>{}); }, delay);
  }
  close() { this.manualClose = true; if (this.ws) this.ws.close(1000, 'client_close'); }
}
=======
/*
 * agent-ws.js
 * ============================================================
 * Cliente WebSocket AGENT-REACT
 *
 * Endpoint oficial:
 *
 *     /ws/langchain
 *
 * NO utilizar:
 *
 *     /api/v1/agent/ws
 *
 * Características:
 * - ws / wss automático
 * - reconexión
 * - backoff exponencial
 * - start
 * - resume
 * - cancel
 * - delta
 * - final
 * - done
 * - error
 * - cancelled
 * - protección contra doble conexión
 */

export class AgentWebSocket {

  constructor({
    baseUrl = "",
    wsPath = "/ws/langchain",
    onEvent = () => {},
    onDelta = () => {},
    onFinal = () => {},
    onError = () => {},
    onClose = () => {},
    onOpen = () => {},
    onReconnect = () => {},
    onResume = () => {},
    onDone = () => {},
    onCancelled = () => {},

    maxRetries = 8,
    retryBaseMs = 500,
    connectTimeoutMs = 10000

  } = {}) {

    this.baseUrl = baseUrl;
    this.wsPath = wsPath;

    this.onEvent = onEvent;
    this.onDelta = onDelta;
    this.onFinal = onFinal;
    this.onError = onError;
    this.onClose = onClose;
    this.onOpen = onOpen;
    this.onReconnect = onReconnect;
    this.onResume = onResume;
    this.onDone = onDone;
    this.onCancelled = onCancelled;

    this.maxRetries = maxRetries;
    this.retryBaseMs = retryBaseMs;
    this.connectTimeoutMs = connectTimeoutMs;

    this.ws = null;

    this.retryCount = 0;
    this.reconnecting = false;
    this.manualClose = false;
    this.connecting = null;

    this.pendingStart = null;

    this.runId = null;
    this.lastSequence = 0;

    this.connected = false;
  }


  // ==========================================================
  // URL
  // ==========================================================

  _buildUrl() {

    if (this.baseUrl) {

      if (
        this.baseUrl.startsWith("ws://") ||
        this.baseUrl.startsWith("wss://")
      ) {

        return this.baseUrl;
      }

      const protocol =
        location.protocol === "https:"
          ? "wss:"
          : "ws:";

      return `${protocol}//${this.baseUrl}${this.wsPath}`;
    }

    const protocol =
      location.protocol === "https:"
        ? "wss:"
        : "ws:";

    return `${protocol}//${location.host}${this.wsPath}`;
  }


  // ==========================================================
  // CONNECT
  // ==========================================================

  connect() {

    this.manualClose = false;

    // Ya conectado
    if (
      this.ws &&
      this.ws.readyState === WebSocket.OPEN
    ) {

      return Promise.resolve();
    }

    // Ya conectando
    if (this.connecting) {
      return this.connecting;
    }

    this.connecting = new Promise(
      (resolve, reject) => {

        const url = this._buildUrl();

        console.info(
          "[AgentWebSocket] conectando:",
          url
        );

        const ws = new WebSocket(url);

        this.ws = ws;

        let settled = false;

        const timer = setTimeout(() => {

          if (!settled) {

            settled = true;

            try {
              ws.close();
            } catch (_) {}

            const error =
              new Error(
                "WebSocket connection timeout"
              );

            this.onError(error);

            reject(error);
          }

        }, this.connectTimeoutMs);


        ws.onopen = () => {

          clearTimeout(timer);

          settled = true;

          this.connected = true;

          this.retryCount = 0;

          this.reconnecting = false;

          this.connecting = null;

          console.info(
            "[AgentWebSocket] conectado:",
            url
          );

          this.onOpen();

          resolve();

          // Continuar ejecución/resume
          this._resumeOrStart()
            .catch(error => {
              console.error(
                "[AgentWebSocket] start/resume:",
                error
              );

              this.onError(error);
            });
        };


        ws.onmessage = event => {

          this._handle(event.data);
        };


        ws.onerror = event => {

          console.error(
            "[AgentWebSocket] error:",
            event
          );

          this.onError(event);

          if (!settled) {

            clearTimeout(timer);

            settled = true;

            this.connecting = null;

            reject(
              new Error(
                "No se pudo conectar al WebSocket"
              )
            );
          }
        };


        ws.onclose = event => {

          clearTimeout(timer);

          this.connected = false;

          this.connecting = null;

          console.warn(
            "[AgentWebSocket] cerrado:",
            event.code,
            event.reason || ""
          );

          this.onClose(event);

          if (
            !this.manualClose
          ) {

            this._scheduleReconnect();
          }
        };

      }
    );

    return this.connecting;
  }


  // ==========================================================
  // START / RESUME
  // ==========================================================

  async _resumeOrStart() {

    if (
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {

      return;
    }


    // --------------------------------------------------------
    // RESUME
    // --------------------------------------------------------

    if (this.runId) {

      const payload = {
        type: "resume",
        run_id: this.runId,
        after: this.lastSequence
      };

      console.info(
        "[AgentWebSocket] resume:",
        payload
      );

      this.ws.send(
        JSON.stringify(payload)
      );

      this.onResume(payload);

      return;
    }


    // --------------------------------------------------------
    // START
    // --------------------------------------------------------

    if (this.pendingStart) {

      const payload = {
        ...this.pendingStart,
        type: "start"
      };

      this.pendingStart = null;

      console.info(
        "[AgentWebSocket] start:",
        payload
      );

      this.ws.send(
        JSON.stringify(payload)
      );
    }
  }


  // ==========================================================
  // MESSAGE HANDLER
  // ==========================================================

  _handle(raw) {

    try {

      const event =
        typeof raw === "string"
          ? JSON.parse(raw)
          : raw;


      if (!event || typeof event !== "object") {

        return;
      }


      // ------------------------------------------------------
      // RUN ID
      // ------------------------------------------------------

      if (event.run_id) {

        this.runId =
          event.run_id;
      }


      // ------------------------------------------------------
      // SEQUENCE
      // ------------------------------------------------------

      const sequence =
        Number(event.sequence);

      if (
        Number.isFinite(sequence) &&
        sequence > this.lastSequence
      ) {

        this.lastSequence =
          sequence;
      }


      // ------------------------------------------------------
      // EVENT GENERAL
      // ------------------------------------------------------

      this.onEvent(event);


      // ------------------------------------------------------
      // DELTA
      // ------------------------------------------------------

      if (event.type === "delta") {

        this.onDelta(
          event.delta || ""
        );
      }


      // ------------------------------------------------------
      // FINAL
      // ------------------------------------------------------

      if (event.type === "final") {

        this.onFinal(event);
      }


      // ------------------------------------------------------
      // DONE
      // ------------------------------------------------------

      if (event.type === "done") {

        this.pendingStart = null;

        this.onDone(event);
      }


      // ------------------------------------------------------
      // CANCELLED
      // ------------------------------------------------------

      if (
        event.type === "cancelled"
      ) {

        this.pendingStart = null;

        this.onCancelled(event);
      }


      // ------------------------------------------------------
      // ERROR
      // ------------------------------------------------------

      if (event.type === "error") {

        const error =
          new Error(
            event.message ||
            event.error ||
            "Error del agente"
          );

        error.event = event;

        this.onError(error);
      }

    } catch (error) {

      console.error(
        "[AgentWebSocket] JSON inválido:",
        raw,
        error
      );

      this.onError(error);
    }
  }


  // ==========================================================
  // SEND
  // ==========================================================

  async send(payload = {}) {

    if (
      !payload ||
      typeof payload !== "object"
    ) {

      throw new Error(
        "Payload WebSocket inválido"
      );
    }


    this.pendingStart = {
      ...payload,
      type: "start"
    };


    if (
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {

      await this.connect();

      return;
    }


    await this._resumeOrStart();
  }


  // ==========================================================
  // RESUME MANUAL
  // ==========================================================

  async resume(
    runId = this.runId,
    after = this.lastSequence
  ) {

    if (!runId) {

      throw new Error(
        "runId requerido para resume"
      );
    }

    this.runId = runId;

    this.lastSequence =
      Number.isFinite(Number(after))
        ? Number(after)
        : 0;


    if (
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {

      await this.connect();

      return;
    }


    this.ws.send(
      JSON.stringify({
        type: "resume",
        run_id: this.runId,
        after: this.lastSequence
      })
    );
  }


  // ==========================================================
  // CANCEL
  // ==========================================================

  cancel() {

    if (
      this.runId &&
      this.ws &&
      this.ws.readyState === WebSocket.OPEN
    ) {

      this.ws.send(
        JSON.stringify({
          type: "cancel",
          run_id: this.runId
        })
      );
    }
  }


  // ==========================================================
  // RECONNECT
  // ==========================================================

  _scheduleReconnect() {

    if (
      this.reconnecting ||
      this.manualClose ||
      this.retryCount >= this.maxRetries
    ) {

      return;
    }


    this.reconnecting = true;

    const delay =
      Math.min(
        15000,
        this.retryBaseMs *
          (2 ** this.retryCount)
      ) +
      Math.round(
        Math.random() * 250
      );


    this.retryCount++;


    console.info(
      `[AgentWebSocket] reconexión ${this.retryCount}/${this.maxRetries} en ${delay}ms`
    );


    this.onReconnect({
      attempt: this.retryCount,
      delay
    });


    setTimeout(
      () => {

        this.reconnecting = false;

        this.connect()
          .catch(error => {

            console.warn(
              "[AgentWebSocket] reconexión fallida:",
              error
            );

          });

      },
      delay
    );
  }


  // ==========================================================
  // CLOSE
  // ==========================================================

  close() {

    this.manualClose = true;

    this.pendingStart = null;

    this.connected = false;

    if (this.ws) {

      try {

        this.ws.close(
          1000,
          "client_close"
        );

      } catch (_) {}

    }

    this.ws = null;
  }
}
>>>>>>> ebbf022 (feat: complete Agent ReAct architecture)
