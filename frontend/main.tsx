import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Console } from "./index";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Console />
  </StrictMode>,
);
