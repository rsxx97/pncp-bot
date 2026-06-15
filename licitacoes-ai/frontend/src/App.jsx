import { useState, useEffect } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import AppLayout from "./components/AppLayout";
import Home from "./components/Home";
import PncpSearch from "./components/PncpSearch";
import Perfil from "./components/Perfil";
import ConcorrentePanel from "./components/ConcorrentePanel";
import PregaoPanel from "./components/PregaoPanel";
import PlanilhaPanel from "./components/PlanilhaPanel";
import PipelinePage from "./components/PipelinePage";
import HabilitacaoPage from "./components/HabilitacaoPage";
import Login from "./components/Login";
import Landing from "./components/Landing";
import AdminPanel from "./components/AdminPanel";
import EmailConfirmBanner from "./components/EmailConfirmBanner";
import RadarRoot from "./radar/RadarRoot";

function pathToProduto(path) {
  const p = (path || "/").replace(/^\/+/, "").split("/")[0];
  const validas = new Set(["pipeline", "buscar", "radar", "pregoes", "planilhas", "habilitacao", "concorrentes", "perfil", "admin"]);
  if (validas.has(p)) return p;
  return "home";
}

function navegar(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function PageRouter() {
  const { tenant, isAdmin } = useAuth();
  const [path, setPath] = useState(() => window.location.pathname);
  const [period] = useState("90d");

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const produto = pathToProduto(path);

  const config = {
    home:         { tit: "Home",         sub: "Visão geral",            comp: <Home period={period} /> },
    pipeline:     { tit: "Pipeline",     sub: "Boletim de editais",     comp: <PipelinePage /> },
    buscar:       { tit: "Buscar PNCP",  sub: "Importar editais",       comp: <PncpSearch onImported={() => navegar("/pipeline")} /> },
    radar:        { tit: "Radar",        sub: "Monitoramento em tempo real", comp: <RadarRoot /> },
    pregoes:      { tit: "Disputa",      sub: "Lances + Robot",         comp: <PregaoPanel editais={[]} /> },
    planilhas:    { tit: "Proposta",     sub: "Planilhas e BDI",        comp: <PlanilhaPanel /> },
    habilitacao:  { tit: "Habilitação",  sub: "Documentos + CCT",       comp: <HabilitacaoPage /> },
    concorrentes: { tit: "BI",           sub: "Concorrentes e mercado", comp: <ConcorrentePanel /> },
    perfil:       { tit: "Empresa",      sub: "Cadastro e integrações", comp: <Perfil token={localStorage.getItem("token")} tenant={tenant} /> },
    admin:        { tit: "Admin",        sub: "Acesso restrito",        comp: isAdmin ? <AdminPanel /> : <div style={{ color: "#FF4D4D", fontFamily: "monospace", fontSize: 13 }}>Acesso negado.</div> },
  };

  const cfg = config[produto] || config.home;

  return (
    <AppLayout produto={produto} titulo={cfg.tit} subtitulo={cfg.sub}>
      <EmailConfirmBanner tenant={tenant} />
      {cfg.comp}
    </AppLayout>
  );
}

function MainApp() {
  const { tenant, loading, login } = useAuth();
  const [showLogin, setShowLogin] = useState(false);

  // Preview da Landing mesmo logado: acesse /landing
  if (window.location.pathname.replace(/\/+$/, "") === "/landing") {
    return <Landing onStart={() => navegar("/")} />;
  }

  if (loading) {
    return <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>Carregando…</div>;
  }
  if (tenant) return <PageRouter />;
  if (showLogin) return <Login onLogin={(t, tok) => login(t, tok)} />;
  return <Landing onStart={() => setShowLogin(true)} />;
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
