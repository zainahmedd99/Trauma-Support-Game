// Simple countdown bar + callback
function startTimer(seconds, onTick, onDone) {
  let remaining = seconds;
  const id = setInterval(() => {
    remaining -= 1;
    if (onTick) onTick(remaining);
    if (remaining <= 0) { clearInterval(id); if (onDone) onDone(); }
  }, 1000);
  return () => clearInterval(id);
}
