import React from "react";
import jarvisVisualBody from "../../jarvis.html?raw";

export const JarvisHUD: React.FC = () => (
  <iframe
    className="hud-container"
    srcDoc={jarvisVisualBody}
    title="Jarvis HUD background"
    aria-hidden="true"
    tabIndex={-1}
  />
);
