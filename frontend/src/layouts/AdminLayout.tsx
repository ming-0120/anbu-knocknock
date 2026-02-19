import { Outlet } from "react-router-dom";

export default function AdminLayout() {
  return (
    <div>
      <h2>Admin Layout</h2>
      <Outlet />
    </div>
  );
}
