// Timing and destinations belong to the face, independently of desktop position.
const idle = {expression:'resting', pause:[900, 2650], actions:['scan','scan','scan','blink','double','wink'], picks:[[67,-36],[-70,-31],[47,42],[-49,37],[0,-52]]};
const workStates = {
  idle,
  running:{expression:'focused', pause:[1450, 3350], actions:['read','read','blink'], picks:[[43,15],[-43,15],[45,-12],[-45,-12]]},
  queued:{expression:'waiting', pause:[2300, 4600], actions:['peek','peek','blink'], picks:[[0,30],[-32,18],[32,18]]},
  needs_input:{expression:'asking', pause:[1500, 3100], actions:['peek','peek','double','blink'], picks:[[0,-36],[-36,-24],[36,-24]]},
  unread:{expression:'attention', pause:[1450, 3000], actions:['perk','perk','blink','double'], picks:[[37,-34],[-37,-34],[0,-40]]},
  unknown:{expression:'uncertain', pause:[3300, 6100], actions:['blink','peek'], picks:[[-22,10],[25,10],[0,18]]},
};
const semanticState = status => Object.hasOwn(workStates, status) ? workStates[status] : workStates.unknown;
const jitter = ([min, max]) => min + Math.random() * (max - min);
const choose = list => list[Math.floor(Math.random() * list.length)];

export function mountCompanionFace(robot, status) {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const lids = robot.querySelector('.face-lids');
  const glanceLayer = robot.querySelector('.face-glance');
  const winkEyes = [...robot.querySelectorAll('.face-wink')];
  let state = semanticState(status.dataset.state), lastAction, lastPick;
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

  function blink(action) {
    const double = action === 'double';
    const eye = action === 'wink' ? choose(winkEyes) : lids;
    const frames = double ? [
      {transform:'scaleY(1)', offset:0}, {transform:'scaleY(.14)', offset:.14},
      {transform:'scaleY(1)', offset:.33}, {transform:'scaleY(1)', offset:.69},
      {transform:'scaleY(.17)', offset:.81}, {transform:'scaleY(1)', offset:1},
    ] : [
      {transform:'scaleY(1)'}, {transform:'scaleY(.13)', offset:.44}, {transform:'scaleY(1)'},
    ];
    const duration = jitter(double ? [410, 510] : action === 'wink' ? [230, 310] : [145, 205]);
    ambientAnimation = eye.animate(frames, {duration, easing:'ease-in-out'});
    return duration;
  }

  function glance(action) {
    const pick = choose(state.picks.filter(value => value !== lastPick));
    lastPick = pick;
    const [x, y] = pick;
    const shift = (a,b) => 'translate(' + a + 'px,' + b + 'px)';
    const settle = action === 'scan' ? shift(-x*.56, -y*.62)
      : action === 'read' ? shift(x*.28, y+10)
      : action === 'perk' ? shift(x*.52, y*.55) : shift(x, y);
    const duration = jitter(action === 'scan' ? [870, 1260] : [640, 990]);
    ambientAnimation = glanceLayer.animate([
      {transform:'none', offset:0, easing:'cubic-bezier(.16,.7,.29,1)'},
      {transform:shift(x,y), offset:.13}, {transform:shift(x,y), offset:.49},
      {transform:settle, offset:.6}, {transform:settle, offset:.82, easing:'ease-in-out'},
      {transform:'none', offset:1},
    ], {duration});
    return duration;
  }

  function schedule(previousDuration=0) {
    if (!moving || acknowledged) return;
    ambientTimer = setTimeout(() => {
      if (document.hidden) return;
      const airborne = document.documentElement.dataset.hopPose === 'launch';
      let action;
      if (hovering || airborne) {
        // Keep the deliberate pointer/flight gaze, but still blink.
        action = 'blink';
      } else if (!lastAction) {
        action = state.actions[0];
      } else {
        action = choose(state.actions.filter(value => value !== lastAction));
      }
      lastAction = action;
      const duration = ['blink','double','wink'].includes(action) ? blink(action) : glance(action);
      schedule(duration);
    }, previousDuration + jitter(hovering ? [2250, 4200] : state.pause));
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
    lastAction = lastPick = null;
    paint();
    schedule();
  }

  const observer = new MutationObserver(() => {
    const next = semanticState(status.dataset.state);
    if (next === state) return;
    state = next;
    lastAction = lastPick = null;
    cancelAmbient();
    clearTimeout(acknowledgeTimer);
    acknowledged = false;
    paint();
    schedule();
  });
  observer.observe(status, {attributes:true, attributeFilter:['data-state']});

  const flight = new MutationObserver(() => {
    if (document.documentElement.dataset.hopPose === 'launch' && ambientAnimation?.effect?.target === glanceLayer)
      ambientAnimation.cancel();
  });
  flight.observe(document.documentElement, {attributes:true, attributeFilter:['data-hop-pose']});

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
    flight.disconnect();
    document.removeEventListener('visibilitychange', syncMotion);
    reduced.removeEventListener('change', syncMotion);
  }, {once:true});
  paint();
  return value => {
    allowed = value;
    syncMotion();
  };
}
