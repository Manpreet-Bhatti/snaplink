export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// device_type is a fixed enum from the backend UA parser — stable slot order, never re-cycled
export const DEVICE_COLOR_VAR: Record<string, string> = {
  desktop: "--series-1",
  mobile: "--series-2",
  tablet: "--series-3",
  bot: "--series-4",
};

export const CATEGORICAL_SLOTS = ["--series-1", "--series-2", "--series-3", "--series-4"];
