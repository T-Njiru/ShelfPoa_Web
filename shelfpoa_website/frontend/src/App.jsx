import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./components/AppShell";
import Login from "./pages/Login";
import MerchandiserPerformance from "./pages/MerchandiserPerformance";
import Recommendations from "./pages/Recommendations";
import RecommendationMaker from "./pages/RecommendationMaker";
import StockoutAlerts from "./pages/StockoutAlerts";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<MerchandiserPerformance />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/recommendation-maker" element={<RecommendationMaker />} />
          <Route path="/stockouts" element={<StockoutAlerts />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
