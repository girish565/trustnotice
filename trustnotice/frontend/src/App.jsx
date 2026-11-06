import { Routes, Route, Navigate } from "react-router-dom"; import { useAuth } from "./context/AuthContext"; import { Layout } from "./components/ui";
import Landing from "./pages/Landing"; import Verify from "./pages/Verify"; import AdminLogin from "./pages/AdminLogin"; import Dashboard from "./pages/Dashboard"; import NoticeForm from "./pages/NoticeForm";
import StudentDashboard from "./pages/StudentDashboard"; import EmergencyForm from "./pages/EmergencyForm";
function Guard({ children, role = "admin" }) { const { user, ready } = useAuth(); if (!ready) return null; return user?.role === role ? children : <Navigate to={role === "student" ? "/student/login" : "/admin/login"} replace />; }
export default function App() {
  return <Layout><Routes>
    <Route path="/" element={<Landing />} /><Route path="/verify" element={<Verify />} /><Route path="/verify/:noticeId" element={<Verify />} />
    <Route path="/admin/login" element={<AdminLogin />} />
    <Route path="/admin" element={<Guard><Dashboard /></Guard>} /><Route path="/admin/new" element={<Guard><NoticeForm /></Guard>} />
    <Route path="/admin/emergency" element={<Guard><EmergencyForm /></Guard>} />
    <Route path="/admin/notices/:id/new-version" element={<Guard><NoticeForm /></Guard>} /><Route path="*" element={<Navigate to="/" />} />
    <Route path="/student/login" element={<AdminLogin student />} />
    <Route path="/student" element={<Guard role="student"><StudentDashboard /></Guard>} />
  </Routes></Layout>;
}
