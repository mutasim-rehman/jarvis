import React from "react";
import { jarvisCoreVisualHtml } from "./jarvisCoreVisualHtml";

export const JarvisHUD: React.FC = () => (
  <iframe
    className="hud-container"
    srcDoc={jarvisCoreVisualHtml}
    title="Jarvis HUD visual"
    aria-hidden="true"
    tabIndex={-1}
  />
);
