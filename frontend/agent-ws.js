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
