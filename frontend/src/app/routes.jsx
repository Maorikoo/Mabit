import InstagramDashboard from "../features/instagram/pages/Dashboard";
import InstagramUsernames from "../features/instagram/pages/Usernames";

export const routes = [
  { path: "/", element: <InstagramDashboard /> },
  { path: "/instagram/dashboard", element: <InstagramDashboard /> },
  { path: "/instagram/usernames", element: <InstagramUsernames /> },
];
