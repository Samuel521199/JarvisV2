use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::Relaxed};

pub struct Motion {
    pub playful: AtomicBool,
    pub allowed: AtomicBool,
    pub idle: AtomicBool,
    pub panel_open: AtomicBool,
    revision: AtomicU64,
}

impl Motion {
    pub fn new(playful: bool) -> Self {
        Self {
            playful: AtomicBool::new(playful),
            allowed: AtomicBool::new(false),
            idle: AtomicBool::new(false),
            panel_open: AtomicBool::new(true),
            revision: AtomicU64::new(0),
        }
    }

    pub fn interrupt(&self) {
        self.revision.fetch_add(1, Relaxed);
    }
}

#[cfg(windows)]
mod windows {
    use super::Relaxed;
    use crate::Presence;
    use std::thread;
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
    use tauri::{Manager, WebviewWindow};

    const FRAME: Duration = Duration::from_millis(16);
    const REST_POLL: Duration = Duration::from_millis(120);
    const NO_ACTIVATION: u32 = 0x0001 | 0x0004 | 0x0010; // NOSIZE | NOZORDER | NOACTIVATE

    #[repr(C)]
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    struct Rect {
        left: i32,
        top: i32,
        right: i32,
        bottom: i32,
    }
    #[repr(C)]
    #[derive(Default)]
    struct Point {
        x: i32,
        y: i32,
    }
    #[repr(C)]
    struct MonitorInfo {
        size: u32,
        monitor: Rect,
        work: Rect,
        flags: u32,
    }
    #[link(name = "user32")]
    extern "system" {
        fn GetWindowRect(window: isize, rect: *mut Rect) -> i32;
        fn IsWindow(window: isize) -> i32;
        fn IsWindowVisible(window: isize) -> i32;
        fn GetCursorPos(point: *mut Point) -> i32;
        fn GetAsyncKeyState(key: i32) -> i16;
        fn MonitorFromWindow(window: isize, flags: u32) -> isize;
        fn GetMonitorInfoW(monitor: isize, info: *mut MonitorInfo) -> i32;
        fn SetWindowPos(
            window: isize,
            after: isize,
            x: i32,
            y: i32,
            w: i32,
            h: i32,
            flags: u32,
        ) -> i32;
    }

    impl Rect {
        fn near_pointer(self, padding: i32) -> bool {
            let mut p = Point::default();
            unsafe {
                GetCursorPos(&mut p) == 0
                    || (p.x >= self.left - padding
                        && p.x < self.right + padding
                        && p.y >= self.top - padding
                        && p.y < self.bottom + padding)
            }
        }
    }

    struct Field {
        start: Rect,
        work: Rect,
        scale: f64,
        left: i32,
        right: i32,
        ground: i32,
    }

    impl Field {
        fn new(start: Rect, work: Rect) -> Option<Self> {
            let width = start.right - start.left;
            let height = start.bottom - start.top;
            let scale = (f64::from(width) / 90.).clamp(0.75, 4.);
            let inset = (8. * scale).round() as i32;
            let left = work.left + inset;
            let right = work.right - width - inset;
            let ground = work.bottom - height - inset;
            (width > 0 && height > 0 && right > left && ground > work.top).then_some(Self {
                start,
                work,
                scale,
                left,
                right,
                ground,
            })
        }

        fn step(&self, end: i32, rise: i32, t: f64) -> Rect {
            let from_x = self.start.left.clamp(self.left, self.right);
            let from_y = self.start.top.clamp(self.work.top, self.ground);
            let distance = f64::from(end - from_x);
            let x = (f64::from(from_x) + distance * t * t * (3. - 2. * t)).round() as i32;
            let y = (f64::from(from_y) + f64::from(self.ground - from_y) * t
                - f64::from(rise) * 4. * t * (1. - t))
                .round() as i32;
            let y = y.clamp(self.work.top, self.ground);
            Rect {
                left: x,
                top: y,
                right: x + self.start.right - self.start.left,
                bottom: y + self.start.bottom - self.start.top,
            }
        }
    }

    #[derive(Clone, Copy)]
    enum Direction {
        Left,
        Right,
    }

    impl Direction {
        fn label(self) -> &'static str {
            match self {
                Self::Left => "left",
                Self::Right => "right",
            }
        }

        fn opposite(self) -> Self {
            match self {
                Self::Left => Self::Right,
                Self::Right => Self::Left,
            }
        }

        fn edge(self, field: &Field) -> i32 {
            match self {
                Self::Left => field.left,
                Self::Right => field.right,
            }
        }
    }

    fn next_hop(
        field: &Field,
        heading: Option<Direction>,
        rng: &mut Random,
    ) -> (Direction, i32, bool) {
        let x = field.start.left.clamp(field.left, field.right);
        // Start toward the farther edge, then keep a heading until the leg ends.
        let mut heading = heading.unwrap_or_else(|| {
            if x - field.left > field.right - x {
                Direction::Left
            } else {
                Direction::Right
            }
        });
        if heading.edge(field) == x {
            heading = heading.opposite();
        }
        let edge = heading.edge(field);
        let remaining = (edge - x).abs();
        let stride = (f64::from(field.right - field.left) * rng.next(13, 20) as f64 / 100.)
            .clamp(75. * field.scale, 290. * field.scale)
            .round() as i32;
        // Avoid a tiny last step at the edge; rest there and turn for the return trip.
        let at_edge = remaining <= stride + (30. * field.scale).round() as i32;
        let target = if at_edge {
            edge
        } else {
            x + (edge - x).signum() * stride
        };
        (heading, target, at_edge)
    }

    struct Random(u64);
    impl Random {
        fn next(&mut self, min: u64, max: u64) -> u64 {
            self.0 ^= self.0 << 13;
            self.0 ^= self.0 >> 7;
            self.0 ^= self.0 << 17;
            min + self.0 % (max - min + 1)
        }
    }

    fn read_work(hwnd: isize) -> Option<Rect> {
        let mut info = MonitorInfo {
            size: std::mem::size_of::<MonitorInfo>() as u32,
            monitor: Rect::default(),
            work: Rect::default(),
            flags: 0,
        };
        unsafe {
            (GetMonitorInfoW(MonitorFromWindow(hwnd, 2), &mut info) != 0).then_some(info.work)
        }
    }

    fn read_window(hwnd: isize) -> Option<Rect> {
        let mut rect = Rect::default();
        unsafe { (GetWindowRect(hwnd, &mut rect) != 0).then_some(rect) }
    }

    fn paint(robot: &WebviewWindow, pose: &str, direction: &str) {
        // Only internal constants reach this WebView; the position is native, not a screen overlay.
        let _ = robot.eval(format!("Object.assign(document.documentElement.dataset,{{hopPose:'{pose}',hopDirection:'{direction}'}})"));
    }

    pub fn run(robot: WebviewWindow, hwnd: isize) {
        thread::Builder::new()
            .name("jarvis-desktop-motion".into())
            .spawn(move || {
                let presence = robot.state::<Presence>();
                let motion = &presence.motion;
                let mut rng = Random(
                    SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .map_or(1, |value| value.as_nanos() as u64)
                        .max(1),
                );
                let mut due = Instant::now();
                let mut active = false;
                let mut observed = motion.revision.load(Relaxed);
                let can_move = || {
                    motion.playful.load(Relaxed)
                        && motion.allowed.load(Relaxed)
                        && motion.idle.load(Relaxed)
                        && presence.dock_ready.load(Relaxed)
                        && !motion.panel_open.load(Relaxed)
                        && presence.visible.load(Relaxed)
                        && presence.robot_ready.load(Relaxed)
                        && unsafe { IsWindowVisible(hwnd) != 0 && GetAsyncKeyState(1) >= 0 }
                };
                let mut heading = None;
                let mut last_work = None;
                loop {
                    if unsafe { IsWindow(hwnd) == 0 } {
                        break;
                    }
                    let revision = motion.revision.load(Relaxed);
                    if !can_move() || observed != revision {
                        if active {
                            paint(&robot, "", "");
                        }
                        active = false;
                        heading = None;
                        last_work = None;
                        observed = revision;
                        thread::sleep(REST_POLL);
                        continue;
                    }
                    if !active {
                        active = true;
                        due = Instant::now() + Duration::from_millis(rng.next(650, 1050));
                    }
                    if Instant::now() < due {
                        thread::sleep(REST_POLL);
                        continue;
                    }
                    let Some(field) = read_window(hwnd)
                        .zip(read_work(hwnd))
                        .and_then(|(w, m)| Field::new(w, m))
                    else {
                        thread::sleep(REST_POLL);
                        continue;
                    };
                    let padding = (34. * field.scale).round() as i32;
                    if field.start.near_pointer(padding) {
                        due = Instant::now() + Duration::from_millis(1150);
                        continue;
                    }
                    if last_work != Some(field.work) {
                        heading = None;
                        last_work = Some(field.work);
                    }
                    let (direction, target, at_edge) = next_hop(&field, heading, &mut rng);
                    let direction_label = direction.label();
                    let rise = (rng.next(35, 84) as f64 * field.scale).round() as i32;
                    let flight = Duration::from_millis(rng.next(390, 620));
                    paint(&robot, "launch", direction_label);
                    let start = Instant::now();
                    let landed = loop {
                        let t = (start.elapsed().as_secs_f64() / flight.as_secs_f64()).min(1.);
                        let next = field.step(target, rise, t);
                        if !can_move()
                            || motion.revision.load(Relaxed) != revision
                            || read_work(hwnd) != Some(field.work)
                            || next.near_pointer(padding)
                            || read_window(hwnd).is_none_or(|current| {
                                current.near_pointer(padding)
                                    || current.right - current.left
                                        != field.start.right - field.start.left
                                    || current.bottom - current.top
                                        != field.start.bottom - field.start.top
                            })
                        {
                            break false;
                        }
                        if unsafe {
                            SetWindowPos(hwnd, 0, next.left, next.top, 0, 0, NO_ACTIVATION)
                        } == 0
                        {
                            break false;
                        }
                        if t == 1. {
                            break true;
                        }
                        thread::sleep(FRAME);
                    };
                    paint(&robot, if landed { "land" } else { "" }, direction_label);
                    heading = Some(if landed && at_edge {
                        direction.opposite()
                    } else {
                        direction
                    });
                    let rest = if !landed {
                        1150
                    } else if at_edge {
                        rng.next(980, 1650)
                    } else if rng.next(0, 3) == 0 {
                        rng.next(680, 1000)
                    } else {
                        rng.next(260, 520)
                    };
                    due = Instant::now() + Duration::from_millis(rest);
                }
            })
            .ok();
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn hops_land_in_work_area_on_negative_coordinate_high_dpi_screen() {
            let work = Rect {
                left: -1800,
                top: -400,
                right: -80,
                bottom: 680,
            };
            let start = Rect {
                left: -330,
                top: 500,
                right: -150,
                bottom: 680,
            };
            let field = Field::new(start, work).unwrap();
            for target in [field.left, field.right] {
                for n in 0..=100 {
                    let p = field.step(target, 140, f64::from(n) / 100.);
                    assert!(
                        p.left >= work.left
                            && p.right <= work.right
                            && p.top >= work.top
                            && p.bottom <= work.bottom
                    );
                    if n == 50 {
                        assert!(p.top < field.ground);
                    }
                    if n == 100 {
                        assert_eq!((p.left, p.top), (target, field.ground));
                    }
                }
            }
        }

        #[test]
        fn cannot_hop_when_monitor_work_area_cannot_hold_the_window() {
            let area = Rect {
                left: 0,
                top: 0,
                right: 80,
                bottom: 1000,
            };
            let start = Rect {
                left: 0,
                top: 0,
                right: 90,
                bottom: 90,
            };
            assert!(Field::new(start, area).is_none());
        }
    }
}

#[cfg(windows)]
pub use windows::run;
