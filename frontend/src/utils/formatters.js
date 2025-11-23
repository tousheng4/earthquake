import dayjs from "dayjs";

export function getColorByMagnitude(mag) {
  if (mag < 3.0) return "#4caf50"; // Green
  if (mag < 4.5) return "#ffeb3b"; // Yellow
  if (mag < 6.0) return "#ff9800"; // Orange
  return "#f44336";               // Red
}

export function formatTime(timeStr) {
  return dayjs(timeStr).format("MM-DD HH:mm");
}

export function formatCoordinate(lon, lat) {
  const lonStr = Math.abs(lon).toFixed(2) + "°" + (lon >= 0 ? "E" : "W");
  const latStr = Math.abs(lat).toFixed(2) + "°" + (lat >= 0 ? "N" : "S");
  return `${latStr}, ${lonStr}`;
}
