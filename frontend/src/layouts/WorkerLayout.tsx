import { Outlet } from "react-router-dom";

export default function WorkerLayout() {
  return (
    <div>
      <h2>Worker Layout</h2>
      <Outlet />
    </div>
  );
}
