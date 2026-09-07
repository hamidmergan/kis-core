import type { PopoverDOM } from "driver.js";

/** Phosphor X in bold, the icon of the app, driver.js only offers a text times sign. */
export const SCHLIESSEN_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" aria-hidden="true"><path d="M208.49,191.51a12,12,0,0,1-17,17L128,145,64.49,208.49a12,12,0,0,1-17-17L111,128,47.51,64.49a12,12,0,0,1,17-17L128,111l63.51-63.52a12,12,0,0,1,17,17L145,128Z" /></svg>`;

/** driver.js builds its own buttons, this hands them the app classes, shared by both tours. */
export function knoepfeAngleichen(popover: PopoverDOM, schliessenLabel: string) {
  popover.nextButton.classList.remove("driver-popover-footer-btn");
  popover.nextButton.classList.add("btn-primary", "text-sm", "rounded-lg", "px-4", "py-2");
  popover.previousButton.classList.remove("driver-popover-footer-btn");
  popover.previousButton.classList.add(
    "btn-ghost", "text-sm", "rounded-lg", "px-4", "py-2",
    "text-foreground-soft", "border", "border-border", "transition-colors",
  );
  popover.closeButton.classList.add(
    "w-7", "h-7", "flex", "items-center", "justify-center",
    "rounded-full", "btn-icon", "flex-shrink-0", "text-[var(--kb)]",
  );
  popover.closeButton.style.backgroundColor = "rgba(var(--kb-rgb),0.10)";
  // driver.js sets display as an inline style, which beats the flex class and
  // pushes the icon out of the middle. "none" means the step hides the button.
  if (popover.closeButton.style.display !== "none") popover.closeButton.style.display = "flex";
  popover.closeButton.setAttribute("aria-label", schliessenLabel);
  popover.closeButton.innerHTML = SCHLIESSEN_ICON;
}
