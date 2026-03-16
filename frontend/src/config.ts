// src/config.ts
export const API_BASE = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000' 
  : 'http://20.249.167.132'; // Azure 서버 IP

export const WS_BASE = window.location.hostname === 'localhost' 
  ? 'ws://localhost:8000' 
  : 'ws://20.249.167.132';