// One delegated interaction layer covers React-rendered actions and modal controls.
export function installEffects() {
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.addEventListener("pointermove", (event) => {
    if (event.pointerType !== "mouse" || reduced()) return;
    const target = (event.target as Element).closest<HTMLButtonElement>(
      "button",
    );
    if (!target || target.disabled || target.matches(".nav-item,.notice-row"))
      return;
    const box = target.getBoundingClientRect();
    target.style.setProperty(
      "--tilt-x",
      (0.5 - (event.clientY - box.top) / box.height) * 10 + "deg",
    );
    target.style.setProperty(
      "--tilt-y",
      ((event.clientX - box.left) / box.width - 0.5) * 12 + "deg",
    );
  });
  document.addEventListener("pointerout", (event) => {
    const target = (event.target as Element).closest<HTMLButtonElement>(
      "button",
    );
    if (target && !target.contains(event.relatedTarget as Node | null)) {
      target.style.removeProperty("--tilt-x");
      target.style.removeProperty("--tilt-y");
    }
  });
  document.addEventListener("click", (event) => {
    const target = (event.target as Element).closest<HTMLButtonElement>(
      "button",
    );
    if (
      !target ||
      target.disabled ||
      reduced() ||
      document.querySelectorAll(".lab-spark").length >= 60
    )
      return;
    const box = target.getBoundingClientRect(),
      x = event.detail ? event.clientX : box.left + box.width / 2,
      y = event.detail ? event.clientY : box.top + box.height / 2;
    const host = document.querySelector("dialog[open]") || document.body;
    for (let i = 0; i < 12; i++) {
      const spark = document.createElement("span"),
        angle = (i / 12) * Math.PI * 2,
        distance = 28 + Math.random() * 35;
      spark.className = "lab-spark";
      spark.setAttribute("aria-hidden", "true");
      spark.style.cssText = `left:${x}px;top:${y}px;--dx:${Math.cos(angle) * distance}px;--dy:${Math.sin(angle) * distance}px;--spark:${["#00aeec", "#fb7299", "#ac83e8", "#ffc857"][i % 4]}`;
      host.append(spark);
      setTimeout(() => spark.remove(), 700);
    }
  });
}
