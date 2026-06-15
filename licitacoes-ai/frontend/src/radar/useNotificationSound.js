import { useCallback, useEffect, useRef } from "react";

/**
 * Som de notificação via Web Audio API (sem dependência de arquivo).
 * - Normal: 1 tom curto 660Hz
 * - Urgente: sequência de 3 tons 880-660-880Hz (mais alarmante)
 */
export default function useNotificationSound() {
  const ctxRef = useRef(null);

  // Lazy init do AudioContext (precisa user gesture na 1ª vez)
  const _ensureCtx = useCallback(() => {
    if (ctxRef.current) {
      // Resume se foi suspenso pelo browser
      if (ctxRef.current.state === "suspended") {
        ctxRef.current.resume().catch(() => {});
      }
      return ctxRef.current;
    }
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctxRef.current = new AC();
      return ctxRef.current;
    } catch {
      return null;
    }
  }, []);

  const _beep = useCallback((ctx, freq, durMs, gainVol = 0.25, delayMs = 0) => {
    if (!ctx) return;
    const t0 = ctx.currentTime + delayMs / 1000;
    const t1 = t0 + durMs / 1000;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(gainVol, t0 + 0.01);
    gain.gain.linearRampToValueAtTime(gainVol, t1 - 0.05);
    gain.gain.linearRampToValueAtTime(0, t1);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t0);
    osc.stop(t1 + 0.02);
  }, []);

  const tocar = useCallback((urgente = false) => {
    const ctx = _ensureCtx();
    if (!ctx) return;
    if (urgente) {
      // 3 tons rápidos alternando — chamativo
      _beep(ctx, 880, 150, 0.35, 0);
      _beep(ctx, 660, 150, 0.35, 200);
      _beep(ctx, 880, 200, 0.35, 400);
    } else {
      // 1 ping curto agradável
      _beep(ctx, 660, 180, 0.25, 0);
    }
  }, [_ensureCtx, _beep]);

  const parar = useCallback(() => {
    // Web Audio API: cada beep é descartável; não há nada pra parar
  }, []);

  useEffect(() => {
    return () => {
      if (ctxRef.current) {
        try { ctxRef.current.close(); } catch {}
      }
    };
  }, []);

  return { tocar, parar };
}
