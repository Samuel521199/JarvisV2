const idle = {expression:'resting', pause:[3600, 9100], blinks:.68, doubles:.17};
const workStates = {
  idle,
  running:{expression:'focused', pause:[5300, 11500], blinks:.85, doubles:.05},
  unread:{expression:'attention', pause:[4100, 9600], blinks:.9, doubles:.1},
  unknown:{expression:'uncertain', pause:[7200, 13900], blinks:1, doubles:0},
};
const glances = [[-46, -16], [43, -21], [-38, 18], [36, 17]];
const jitter = ([min, max]) => min + Math.random() * (max - min);

export function mountCompanionFace(robot, status) {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const lids = robot.querySelector('.face-lids');
  const glanceLayer = robot.querySelector('.face-glance');
  let state = workStates[status.dataset.state] ?? idle;
  let allowed = false, moving = false, hovering = false, gaze = null, acknowledged = false;
  let ambientTimer, acknowledgeTimer, ambientAnimation;

  function paint() {
    const interactive = moving && (state === idle || state === workStates.running);
    robot.dataset.expression = interactive && acknowledged ? 'acknowledging'
      : interactive && hovering && state === idle ? 'curious' : state.expression;
    robot.dataset.gazeX = interactive && gaze ? gaze.x : '';
    robot.dataset.gazeY = interactive && gaze ? gaze.y : '';
  }

  function cancelAmbient() {
    clearTimeout(ambientTimer);
    ambientAnimation?.cancel();
    ambientAnimation = null;
  }

  function blink() {
    const double = !hovering && Math.random() < state.doubles;
    const frames = double ? [
      {transform:'scaleY(1)', offset:0}, {transform:'scaleY(.14)', offset:.14},
      {transform:'scaleY(1)', offset:.33}, {transform:'scaleY(1)', offset:.69},
      {transform:'scaleY(.17)', offset:.81}, {transform:'scaleY(1)', offset:1},
    ] : [
      {transform:'scaleY(1)'}, {transform:'scaleY(.13)', offset:.44}, {transform:'scaleY(1)'},
    ];
    ambientAnimation = lids.animate(frames, {duration:jitter(double ? [410, 510] : [145, 205]), easing:'ease-in-out'});
  }

  function glance() {
    const [x, y] = glances[Math.floor(Math.random() * glances.length)];
    const target = 'translate(' + x + 'px,' + y + 'px)';
    ambientAnimation = glanceLayer.animate([
      {transform:'none', offset:0, easing:'cubic-bezier(.16,.7,.29,1)'},
      {transform:target, offset:.18}, {transform:target, offset:.67, easing:'ease-in-out'},
      {transform:'none', offset:1},
    ], {duration:jitter([710, 1420])});
  }

  function schedule() {
    if (!moving || acknowledged) return;
    ambientTimer = setTimeout(() => {
      if (document.hidden) return;
      if (hovering || Math.random() < state.blinks) blink();
      else glance();
      schedule();
    }, jitter(state.pause));
  }

  function clearInteraction() {
    clearTimeout(acknowledgeTimer);
    acknowledged = false;
    hovering = false;
    gaze = null;
  }

  function syncMotion() {
    const next = allowed && !reduced.matches && !document.hidden;
    if (moving === next) return;
    moving = next;
    robot.toggleAttribute('data-face-motion', moving);
    cancelAmbient();
    clearInteraction();
    paint();
    schedule();
  }

  const observer = new MutationObserver(() => {
    const next = workStates[status.dataset.state] ?? idle;
    if (next === state) return;
    state = next;
    cancelAmbient();
    clearTimeout(acknowledgeTimer);
    acknowledged = false;
    paint();
    schedule();
  });
  observer.observe(status, {attributes:true, attributeFilter:['data-state']});

  robot.addEventListener('pointerenter', event => {
    if (!moving || event.pointerType === 'touch') return;
    hovering = true;
    cancelAmbient();
    paint();
    schedule();
  });
  robot.addEventListener('pointermove', event => {
    if (!hovering || event.buttons) return;
    const box = robot.getBoundingClientRect();
    function direction(value, origin, size, negative, positive) {
      const relative = (value - origin) / size;
      return relative < .34 ? negative : relative > .66 ? positive : '';
    }
    const x = direction(event.clientX, box.left, box.width, 'left', 'right');
    const y = direction(event.clientY, box.top, box.height, 'up', 'down');
    if (x === gaze?.x && y === gaze?.y) return;
    gaze = {x, y};
    paint();
  });
  function leave() {
    hovering = false;
    gaze = null;
    paint();
  }
  robot.addEventListener('pointerleave', leave);
  robot.addEventListener('pointercancel', leave);
  robot.addEventListener('click', () => {
    if (!moving || (state !== idle && state !== workStates.running)) return;
    cancelAmbient();
    clearTimeout(acknowledgeTimer);
    acknowledged = true;
    paint();
    acknowledgeTimer = setTimeout(() => {
      acknowledged = false;
      paint();
      schedule();
    }, 820);
  });
  document.addEventListener('visibilitychange', syncMotion);
  reduced.addEventListener('change', syncMotion);
  window.addEventListener('pagehide', () => {
    cancelAmbient();
    clearInteraction();
    observer.disconnect();
    document.removeEventListener('visibilitychange', syncMotion);
    reduced.removeEventListener('change', syncMotion);
  }, {once:true});
  paint();
  return value => {
    allowed = value;
    syncMotion();
  };
}
