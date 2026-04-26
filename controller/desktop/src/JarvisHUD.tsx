import React, { useEffect, useRef } from "react";
import { jarvisCoreVisualHtml } from "./jarvisCoreVisualHtml";

type JarvisHUDProps = {
  speakModeOn: boolean;
  conversationHidden: boolean;
  isSpeaking: boolean;
};

export const JarvisHUD: React.FC<JarvisHUDProps> = ({ speakModeOn, conversationHidden, isSpeaking }) => {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const postModeToFrame = () => {
    const contentWindow = frameRef.current?.contentWindow;
    if (!contentWindow) return;
    contentWindow.postMessage({
      type: "jarvis-visual-mode",
      payload: { speakModeOn, conversationHidden, isSpeaking },
    }, "*");
  };

  useEffect(() => {
    postModeToFrame();
  }, [conversationHidden, isSpeaking, speakModeOn]);

  return (
    <iframe
      ref={frameRef}
      className="hud-container"
      srcDoc={jarvisCoreVisualHtml}
      onLoad={postModeToFrame}
      title="Jarvis HUD visual"
      aria-hidden="true"
      tabIndex={-1}
    />
  );
};
