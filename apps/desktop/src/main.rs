#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde::Deserialize;
use std::io::{self, Read};
use std::sync::atomic::{AtomicBool,Ordering};
use tauri::{Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
#[derive(Deserialize)]
struct Launch { protocol:u8, data_root:String, origin:String, access:String, #[serde(default)] diagnostics:bool }
#[derive(Deserialize)]
struct Rect { x:f64, y:f64, width:f64, height:f64, rounded:bool }
struct Presence { dock_ready:AtomicBool, robot_ready:AtomicBool, visible:AtomicBool }
impl Presence {
    fn new()->Self{Self{dock_ready:AtomicBool::new(false),robot_ready:AtomicBool::new(false),visible:AtomicBool::new(true)}}
    fn ready(&self,label:&str)->&AtomicBool {if label=="robot"{&self.robot_ready}else{&self.dock_ready}}
}
#[cfg(windows)] mod regions;
#[tauri::command]
fn presence_regions(window:WebviewWindow,rects:Vec<Rect>)->Result<(),String>{
    #[cfg(windows)] regions::apply(&window,&rects)?;
    #[cfg(not(windows))] { let _=rects; return Err("native hit regions not implemented on this platform".into()); }
    let state=window.state::<Presence>();state.ready(window.label()).store(true,Ordering::Release);
    if state.visible.load(Ordering::Acquire){window.show().map_err(|_|String::from("window unavailable"))?;}
    if window.state::<Launch>().diagnostics {
        #[cfg(windows)] if let Ok(report)=regions::inspect(&window,&rects){eprintln!("presence hit map [{}]: {}",window.label(),report);}
    }
    Ok(())
}
#[tauri::command]
fn presence_drag(window:WebviewWindow)->Result<(),String>{
    if window.label()!="robot"{return Err("only robot may be dragged".into());}
    window.start_dragging().map_err(|_|"drag unavailable".into())
}
#[tauri::command]
fn presence_toggle(window:WebviewWindow)->Result<(),String>{
    if window.label()!="robot"{return Err("only robot may toggle the dock".into());}
    let dock=window.app_handle().get_webview_window("presence").ok_or("dock unavailable")?;
    let state=window.state::<Presence>();state.visible.store(true,Ordering::Release);
    if state.dock_ready.load(Ordering::Acquire){dock.show().map_err(|_|"dock unavailable")?;}
    dock.eval("window.dispatchEvent(new Event('jarvis:native:toggle-chat'))").map_err(|_|"dock unavailable".into())
}
#[tauri::command]
fn presence_status(window:WebviewWindow,status:String)->Result<(),String>{
    if window.label()!="presence" || !["idle","running","unread","unknown"].contains(&status.as_str()){return Err("invalid presence status".into());}
    if let Some(robot)=window.app_handle().get_webview_window("robot") {
        robot.eval(format!("document.getElementById('presence-dot').dataset.state={}",serde_json::to_string(&status).unwrap())).map_err(|_|"robot unavailable")?;
    }
    Ok(())
}
fn open_workbench(cfg:&Launch)->Result<(),String>{
    #[cfg(windows)] {
        use std::ffi::c_void;
        #[link(name="shell32")] extern "system" {fn ShellExecuteW(a:*mut c_void,b:*const u16,c:*const u16,d:*const u16,e:*const u16,f:i32)->isize;}
        let verb:Vec<u16>="open\0".encode_utf16().collect();
        let url:Vec<u16>=format!("{}#access={}\0",cfg.origin,cfg.access).encode_utf16().collect();
        let value=unsafe{ShellExecuteW(std::ptr::null_mut(),verb.as_ptr(),url.as_ptr(),std::ptr::null(),std::ptr::null(),1)};
        if value<=32{return Err("browser unavailable".into());} Ok(())
    }
    #[cfg(not(windows))] {let _=cfg;Err("platform adapter unavailable".into())}
}
#[tauri::command]
fn presence_workbench(cfg:State<Launch>)->Result<(),String>{open_workbench(&cfg)}
fn position(window:&WebviewWindow,index:usize)->tauri::Result<()> {
    let monitors=window.available_monitors()?;
    let monitor=monitors.get(index).or_else(||monitors.first()).ok_or(tauri::Error::InvalidWindowHandle)?;
    let scale=monitor.scale_factor();let size=monitor.size();let point=monitor.position();
    let robot=window.label()=="robot";
    let width=((if robot{90.0}else{560.0})*scale).min(size.width as f64) as u32;
    let height=((if robot{90.0}else{800.0})*scale).min(size.height.saturating_sub(48) as f64) as u32;
    window.set_size(tauri::PhysicalSize::new(width,height))?;
    window.set_position(tauri::PhysicalPosition::new(point.x+size.width as i32-width as i32- if robot{14}else{0},point.y+size.height as i32-height as i32-40))?;
    Ok(())
}
fn create_window(app:&tauri::App,label:&str,origin:&tauri::Url,cfg:&Launch)->tauri::Result<WebviewWindow>{
    let mut url=origin.clone();url.set_path(if label=="robot"{"/companion/native-robot"}else{"/companion/native"});
    url.set_fragment(Some(&format!("access={}",cfg.access)));
    let expected=origin.origin();let diagnostics=cfg.diagnostics;
    let window=WebviewWindowBuilder::new(app,label,WebviewUrl::External(url))
        .data_directory(std::path::PathBuf::from(&cfg.data_root).join("optional/desktop-presence/webview"))
        .title(if label=="robot"{"Jarvis 精灵"}else{"Jarvis 标签与卡片"}).inner_size(560.0,800.0)
        .decorations(false).transparent(true).shadow(false).always_on_top(true).skip_taskbar(true).visible(false).resizable(false)
        .on_page_load(move |window,payload| {
            if diagnostics && payload.event()==tauri::webview::PageLoadEvent::Finished {
                let _=window.eval("setTimeout(()=>{document.title='Jarvis native probe:'+JSON.stringify({internals:typeof window.__TAURI_INTERNALS__,invoke:typeof window.__TAURI_INTERNALS__?.invoke,native:document.documentElement.classList.contains('native-presence'),error:document.documentElement.dataset.nativeError||'none'})},2000)");
            }
        })
        .on_document_title_changed(move |_,title|{if diagnostics&&title.starts_with("Jarvis native probe:")&&title.len()<400{eprintln!("{}",title);}})
        .on_navigation(move |destination|destination.origin()==expected).build()?;
    position(&window,0)?;Ok(window)
}
fn main(){
    let mut input=String::new();if io::stdin().take(4097).read_to_string(&mut input).is_err(){return;}
    let cfg:Launch=match serde_json::from_str(&input){Ok(v)=>v,Err(_)=>return};
    let origin:tauri::Url=match cfg.origin.parse(){Ok(v)=>v,Err(_)=>return};
    if cfg.protocol!=2 || !std::path::Path::new(&cfg.data_root).is_absolute() || !std::path::Path::new(&cfg.data_root).is_dir()
        || origin.scheme()!="http" || origin.host_str()!=Some("127.0.0.1") || origin.port().is_none()
        || origin.path()!="/" || origin.query().is_some() || origin.fragment().is_some()
        || !origin.username().is_empty() || origin.password().is_some()
        || !(32..=128).contains(&cfg.access.len()) || !cfg.access.chars().all(|c|c.is_ascii_alphanumeric()||c=='_'||c=='-'){return;}
    #[cfg(windows)] unsafe {
        use std::ffi::c_void;
        #[link(name="kernel32")] extern "system" {fn CreateMutexW(a:*mut c_void,b:i32,c:*const u16)->*mut c_void;fn GetLastError()->u32;}
        let name:Vec<u16>=format!("Local\\Jarvis-Presence-v1-{}\0",origin.port().unwrap()).encode_utf16().collect();
        let handle=CreateMutexW(std::ptr::null_mut(),1,name.as_ptr());if handle.is_null()||GetLastError()==183{return;}
    }
    let secret=cfg.access.clone();
    let result=tauri::Builder::default().manage(cfg).manage(Presence::new())
        .invoke_handler(tauri::generate_handler![presence_regions,presence_drag,presence_toggle,presence_status,presence_workbench])
        .setup(move |app| {
            let dock=create_window(app,"presence",&origin,&app.state::<Launch>())?;
            create_window(app,"robot",&origin,&app.state::<Launch>())?;
            use tauri::menu::{Menu,MenuItem};
            let show=MenuItem::with_id(app,"show","显示精灵与标签",true,None::<&str>)?;
            let hide=MenuItem::with_id(app,"hide","隐藏精灵与标签",true,None::<&str>)?;
            let recall=MenuItem::with_id(app,"recall","召回精灵到主屏",true,None::<&str>)?;
            let full=MenuItem::with_id(app,"workbench","打开工作台",true,None::<&str>)?;
            let quit=MenuItem::with_id(app,"quit","退出精灵（后台任务继续）",true,None::<&str>)?;
            let menu=Menu::with_items(app,&[&show,&hide,&recall,&full])?;
            for (index,_) in dock.available_monitors()?.iter().enumerate(){menu.append(&MenuItem::with_id(app,format!("screen-{index}"),format!("标签停靠到屏幕 {} 右侧",index+1),true,None::<&str>)?)?;}
            menu.append(&quit)?;
            let icon=tauri::image::Image::from_bytes(include_bytes!("../assets/icon.png"))?;
            tauri::tray::TrayIconBuilder::new().icon(icon).tooltip("Jarvis 精灵").menu(&menu)
                .on_menu_event(|app,event|{
                    let state=app.state::<Presence>();
                    match event.id.as_ref(){
                        "show"|"hide"=>{let show=event.id.as_ref()=="show";state.visible.store(show,Ordering::Release);
                            for label in ["presence","robot"] {if let Some(window)=app.get_webview_window(label){if show&&state.ready(label).load(Ordering::Acquire){let _=window.show();}else if !show{let _=window.hide();}}}},
                        "recall"=>{if let Some(robot)=app.get_webview_window("robot"){let _=position(&robot,0);if state.robot_ready.load(Ordering::Acquire){state.visible.store(true,Ordering::Release);let _=robot.show();}}},
                        "workbench"=>{let _=open_workbench(&app.state::<Launch>());},"quit"=>app.exit(0),
                        id=>{if let Some(index)=id.strip_prefix("screen-").and_then(|n|n.parse::<usize>().ok()){if let Some(dock)=app.get_webview_window("presence"){let _=position(&dock,index);}}}
                    }
                }).build(app)?;
            Ok(())
        }).run(tauri::generate_context!());
    if let Err(error)=result{eprintln!("Jarvis presence startup: {}",error.to_string().replace(&secret,"[redacted]"));}
}
