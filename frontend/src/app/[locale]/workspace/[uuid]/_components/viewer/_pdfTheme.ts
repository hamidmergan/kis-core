// The viewer colours in both themes, values from the house styling, change both files together.
export const PDF_THEME_COLORS = {
  light: {
    accent: {
      primary:           "#004261", // --kb
      primaryHover:      "#003350", // --kb-dark
      primaryActive:     "#00293d", // --kb-darker
      primaryLight:      "#EBEDF0", // --surface-dim (text-selection background)
      primaryForeground: "#ffffff",
    },
    background: {
      app:        "#F3F4F6", // --surface
      surface:    "#ffffff", // --background (toolbars, panels)
      surfaceAlt: "#EBEDF0", // --surface-dim
      elevated:   "#ffffff",
      input:      "#ffffff",
    },
    foreground: {
      primary:   "#0D1F2D", // --foreground
      secondary: "#2F4D5C", // --foreground-soft
      muted:     "#668DA0", // --muted
      disabled:  "#8FAEC0", // --muted-soft
      onAccent:  "#ffffff",
    },
    border: {
      default: "#B8CDD5", // --border
      subtle:  "#D9E2E6", // --border-soft
      strong:  "#8FAEC0", // --muted-soft
    },
    interactive: {
      hover:    "#F3F4F6", // --surface
      active:   "#EBEDF0", // --surface-dim
      selected: "#EBEDF0", // --surface-dim
      focus:    "#004261", // --kb
    },
    state: {
      error:        "#DC2626", errorLight:   "#FEF2F2",
      warning:      "#D97706", warningLight: "#FFFBEB",
      success:      "#16A34A", successLight: "#F0FDF4",
      info:         "#2563EB", infoLight:    "#EFF6FF",
    },
    scrollbar: { track: "transparent", thumb: "#d8d8d8", thumbHover: "#bbb" },
  },
  dark: {
    accent: {
      primary:           "#5BA3CE", // --kb (dark)
      primaryHover:      "#7BBDE5", // --kb-dark (dark)
      primaryActive:     "#9BD2F0", // --kb-darker (dark)
      primaryLight:      "#1C2A33", // --kb20 (dark)
      primaryForeground: "#0A0B0D", // text on lifted accent
    },
    background: {
      app:        "#0A0B0D", // --background (dark)
      surface:    "#141519", // --surface (dark)
      surfaceAlt: "#1C1D22", // --surface-dim (dark)
      elevated:   "#141519",
      input:      "#1C1D22",
    },
    foreground: {
      primary:   "#F5F5F7", // --foreground (dark)
      secondary: "#C8CACF", // --foreground-soft (dark)
      muted:     "#8B8E97", // --muted (dark)
      disabled:  "#6E7079", // --muted-soft (dark)
      onAccent:  "#0A0B0D",
    },
    border: {
      default: "#2A2C32", // --border (dark)
      subtle:  "#23252B", // --border-soft (dark)
      strong:  "#3A3C42",
    },
    interactive: {
      hover:    "#1C1D22", // --surface-dim (dark)
      active:   "#23252B",
      selected: "#23252B",
      focus:    "#5BA3CE", // --kb (dark)
    },
    state: {
      error:        "#F87171", errorLight:   "#2A1414",
      warning:      "#FBBF24", warningLight: "#2A1F0A",
      success:      "#4ADE80", successLight: "#0F2818",
      info:         "#60A5FA", infoLight:    "#0F1A2E",
    },
    scrollbar: { track: "transparent", thumb: "#3A3C42", thumbHover: "#52545C" },
  },
};
