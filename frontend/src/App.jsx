import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./app/Layout";
import { routes } from "./app/routes";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          {routes.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
