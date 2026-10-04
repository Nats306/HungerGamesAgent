import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Landing from "./components/Landing";
import { initAuth } from "./auth/keycloak";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root")!);

initAuth()
  .then((authenticated) => {
    root.render(<React.StrictMode>{authenticated ? <App /> : <Landing />}</React.StrictMode>);
  })
  .catch(() => {
    root.render(
      <Landing error="Could not connect to the authentication server. Please try again later." />,
    );
  });
