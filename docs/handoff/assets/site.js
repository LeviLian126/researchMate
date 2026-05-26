(function () {
  const root = document.documentElement;
  const button = document.querySelector("[data-theme-toggle]");
  const copyButton = document.querySelector("[data-copy-prompt]");
  const prompt = document.querySelector("[data-resume-prompt]");

  if (button) {
    button.addEventListener("click", () => {
      const nextMode = root.dataset.mode === "dark" ? "light" : "dark";
      root.dataset.mode = nextMode;
      button.textContent = nextMode === "dark" ? "浅色模式" : "深色模式";
    });
  }

  if (copyButton && prompt) {
    copyButton.addEventListener("click", async () => {
      await navigator.clipboard.writeText(prompt.textContent.trim());
      copyButton.textContent = "已复制";
      window.setTimeout(() => {
        copyButton.textContent = "复制提示词";
      }, 1200);
    });
  }
})();
