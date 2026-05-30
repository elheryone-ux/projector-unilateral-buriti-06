import { useEffect } from "react";
import "@/App.css";
import "@/admin/admin.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AdminAuthProvider } from "@/admin/AuthContext";
import AdminLogin from "@/admin/AdminLogin";
import AdminLayout from "@/admin/AdminLayout";
import AdminDashboard from "@/admin/AdminDashboard";
import AdminInscriptions from "@/admin/AdminInscriptions";
import AdminUsers from "@/admin/AdminUsers";
import AdminSettings from "@/admin/AdminSettings";
import AdminPlaceholder from "@/admin/AdminPlaceholder";

// Componente que redireciona para o site estático (home.html) para qualquer rota
// que NÃO seja do painel administrativo.
function RedirectToStatic() {
  useEffect(() => {
    window.location.replace("/home.html");
  }, []);
  return null;
}

function App() {
  return (
    <BrowserRouter>
      <AdminAuthProvider>
        <Routes>
          {/* Painel administrativo */}
          <Route path="/donaspainel/login" element={<AdminLogin />} />
          <Route path="/donaspainel" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="inscricoes" element={<AdminInscriptions />} />
            <Route path="usuarios" element={<AdminUsers />} />
            <Route path="configuracoes" element={<AdminSettings />} />
          </Route>

          {/* Tudo que não for painel cai no site estático */}
          <Route path="*" element={<RedirectToStatic />} />
        </Routes>
      </AdminAuthProvider>
    </BrowserRouter>
  );
}

export default App;
