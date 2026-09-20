/**
 * Wall-clock time for the people in the room.
 *
 * The stack records UTC; a responder reading the board is on Central European time,
 * so every timestamp shown to a person is rendered there. Machine payloads keep
 * their ISO strings untouched.
 */
export const DISPLAY_TIMEZONE = "Europe/Madrid";

export function localTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleTimeString("en-GB", { timeZone: DISPLAY_TIMEZONE });
}

export function localDateTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleString("en-GB", {
    timeZone: DISPLAY_TIMEZONE,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
