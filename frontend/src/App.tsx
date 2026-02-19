import { BrowserRouter, Routes, Route } from "react-router-dom";
import AdminLayout from "./layouts/AdminLayout";
import WorkerLayout from "./layouts/WorkerLayout";
import Dashboard from "./pages/admin/Dashboard";
import WorkerHome from "./pages/worker/WorkerHome";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/dashboard" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
        </Route>

        <Route path="/worker" element={<WorkerLayout />}>
          <Route index element={<WorkerHome />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
