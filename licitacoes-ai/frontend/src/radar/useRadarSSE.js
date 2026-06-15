import { useEffect, useRef, useState } from "react";

export default function useRadarSSE(onEvent) {
  const [status, setStatus] = useState("connecting");
  const esRef = useRef(null);
  const reconnectRef = useRef(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setStatus("nao_autenticado");
      return;
    }

    let cancelled = false;

    const conectar = () => {
      if (cancelled) return;
      const url = `/api/radar/stream?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("open", () => setStatus("conectado"));

      es.addEventListener("hello", () => setStatus("conectado"));

      es.addEventListener("radar", (e) => {
        try {
          const data = JSON.parse(e.data);
          onEvent?.(data);
        } catch (err) {
          console.error("Erro parse SSE", err);
        }
      });

      es.addEventListener("ping", () => {});

      es.addEventListener("error", () => {
        setStatus("desconectado");
        es.close();
        if (!cancelled) {
          reconnectRef.current = setTimeout(conectar, 3000);
        }
      });
    };

    conectar();

    return () => {
      cancelled = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      esRef.current?.close();
    };
  }, [onEvent]);

  return { status };
}
