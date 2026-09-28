import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ApprovalsPage } from './pages/ApprovalsPage'
import { EvaluationPage } from './pages/EvaluationPage'
import { IncidentPage } from './pages/IncidentPage'
import { IncidentsPage } from './pages/IncidentsPage'
import { MemoryPage } from './pages/MemoryPage'
import { OverviewPage } from './pages/OverviewPage'
import { UploadPage } from './pages/UploadPage'

export default function App() {
  return <Routes><Route element={<Layout />}><Route index element={<OverviewPage />} /><Route path="incidents" element={<IncidentsPage />} /><Route path="incidents/:id" element={<IncidentPage />} /><Route path="memory" element={<MemoryPage />} /><Route path="memory/upload" element={<UploadPage />} /><Route path="approvals" element={<ApprovalsPage />} /><Route path="evaluation" element={<EvaluationPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes>
}
