#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde::Deserialize;
use std::io::{self, Read};
use tauri::{Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

#[derive(Deserialize)]
struct Launch { origin: String, access: String }
#[derive(Deserialize)]
struct Rect { x:f64, y:f64, width:f64, height:f64, rounded:bool }

#[cfg(windows)]
mod region {
    use super::Rect;
    use std::ffi::c_void;
    #[link(name="gdi32")]
    extern "system" {
        fn CreateRectRgn(a:i32,b:i32,c:i32,d:i32)->*mut c_void;
        fn CreateRoundRectRgn(a:i32,b:i32,c:i32,d:i32,e:i32,f:i32)->*mut c_void;
        fn CombineRgn(dest:*mut c_void,a:*mut c_void,b:*mut c_void,mode:i32)->i32;
        fn DeleteObject(object:*mut c_void)->i32;
    }
    #[link(name="user32")]
    extern "system" {fn SetWindowRgn(hwnd:*mut c_void,rgn:*mut c_void,redraw:i32)->i32;}
    pub fn apply(window:&tauri::WebviewWindow, rects:Vec<Rect>)->Result<(),String> {
        if rects.is_empty() || rects.len()>48 {return Err("invalid region count".into());}
        let scale=window.scale_factor().map_err(|_|"window unavailable")?;
        let size=window.inner_size().map_err(|_|"window unavailable")?;
        for r in &rects {
            if ![r.x,r.y,r.width,r.height].iter().all(|v|v.is_finite()) || r.width<=0.0 || r.height<=0.0
                || r.x<0.0 || r.y<0.0 || (r.x+r.width)*scale>size.width as f64+4.0
                || (r.y+r.height)*scale>size.height as f64+4.0 {return Err("invalid region bounds".into());}
        }
        let hwnd=window.hwnd().map_err(|_|"window unavailable")?.0 as *mut c_void;
        unsafe {
            let union=CreateRectRgn(0,0,0,0);
            if union.is_null(){return Err("region allocation failed".into());}
            for r in rects {
                let a=(r.x*scale).floor() as i32;let b=(r.y*scale).floor() as i32;
                let c=((r.x+r.width)*scale).ceil() as i32;let d=((r.y+r.height)*scale).ceil() as i32;
                let part=if r.rounded {CreateRoundRectRgn(a,b,c,d,(24.0*scale) as i32,(24.0*scale) as i32)} else {CreateRectRgn(a,b,c,d)};
                if part.is_null() || CombineRgn(union,union,part,2)==0 {
                    if !part.is_null(){DeleteObject(part);} DeleteObject(union);return Err("region merge failed".into());
                }
                DeleteObject(part);
            }
            if SetWindowRgn(hwnd,union,1)==0 {DeleteObject(union);return Err("window region failed".into());}
        }
        Ok(())
    }
}

#[tauri::command]
fn presence_regions(window:WebviewWindow,rects:Vec<Rect>)->Result<(),String>{
    #[cfg(windows)] region::apply(&window,rects)?;
    #[cfg(not(windows))] { let _=rects; return Err("native hit regions not implemented on this platform".into()); }
    window.show().map_err(|_|"window unavailable".into())
}
#[tauri::command]
fn presence_drag(window:WebviewWindow)->Result<(),String>{window.start_dragging().map_err(|_|"drag unavailable".into())}

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
    let width=(560.0*scale).min(size.width as f64) as u32;
    let height=(800.0*scale).min(size.height.saturating_sub(48) as f64) as u32;
    window.set_size(tauri::PhysicalSize::new(width,height))?;
    window.set_position(tauri::PhysicalPosition::new(point.x+size.width as i32-width as i32,point.y+size.height as i32-height as i32-40))?;
    Ok(())
}

fn main(){
    let mut input=String::new();if io::stdin().take(4097).read_to_string(&mut input).is_err(){return;}
    let cfg:Launch=match serde_json::from_str(&input){Ok(v)=>v,Err(_)=>return};
    let origin:tauri::Url=match cfg.origin.parse(){Ok(v)=>v,Err(_)=>return};
    if origin.scheme()!="http" || origin.host_str()!=Some("127.0.0.1") || origin.port().is_none()
        || origin.path()!="/" || origin.query().is_some() || origin.fragment().is_some()
        || !origin.username().is_empty() || origin.password().is_some()
        || !(32..=128).contains(&cfg.access.len()) || !cfg.access.chars().all(|c|c.is_ascii_alphanumeric()||c=='_'||c=='-'){return;}
    // UI-only single instance. It never acquires an executor or Host lock.
    #[cfg(windows)] unsafe {
        use std::ffi::c_void;
        #[link(name="kernel32")] extern "system" {
            fn CreateMutexW(a:*mut c_void,b:i32,c:*const u16)->*mut c_void;
            fn GetLastError()->u32;
        }
        let name:Vec<u16>=format!("Local\\Jarvis-Presence-v1-{}\0",origin.port().unwrap()).encode_utf16().collect();
        let handle=CreateMutexW(std::ptr::null_mut(),1,name.as_ptr());
        if handle.is_null()||GetLastError()==183{return;}
    }
    let expected=origin.origin();let mut url=origin.clone();url.set_path("/companion/native");url.set_fragment(Some(&format!("access={}",cfg.access)));
    let diagnostic_secret=cfg.access.clone();
    let result=tauri::Builder::default().manage(cfg)
        .invoke_handler(tauri::generate_handler![presence_regions,presence_drag,presence_workbench])
        .setup(move |app| {
            let window=WebviewWindowBuilder::new(app,"presence",WebviewUrl::External(url.clone()))
                .title("Jarvis 精灵").inner_size(560.0,800.0).decorations(false).transparent(true)
                .shadow(false).always_on_top(true).skip_taskbar(true).visible(cfg!(debug_assertions)).resizable(false)
                .on_page_load(|_,payload|eprintln!("presence page event: {:?}",payload.event()))
                .on_navigation(move |destination| destination.origin()==expected)
                .build()?;
            position(&window,0)?;
            use tauri::menu::{Menu,MenuItem};
            let show=MenuItem::with_id(app,"show","显示精灵",true,None::<&str>)?;
            let hide=MenuItem::with_id(app,"hide","隐藏精灵",true,None::<&str>)?;
            let full=MenuItem::with_id(app,"workbench","打开工作台",true,None::<&str>)?;
            let quit=MenuItem::with_id(app,"quit","退出精灵（后台任务继续）",true,None::<&str>)?;
            let menu=Menu::with_items(app,&[&show,&hide,&full])?;
            for (index,_) in window.available_monitors()?.iter().enumerate(){
                menu.append(&MenuItem::with_id(app,format!("screen-{index}"),format!("移到屏幕 {} 右侧",index+1),true,None::<&str>)?)?;
            }
            menu.append(&quit)?;
            let icon=tauri::image::Image::from_bytes(include_bytes!("../assets/icon.png"))?;
            tauri::tray::TrayIconBuilder::new().icon(icon).tooltip("Jarvis 精灵").menu(&menu)
                .on_menu_event(|app,event|{if let Some(window)=app.get_webview_window("presence"){
                    match event.id.as_ref(){"show"=>{let _=window.show();},"hide"=>{let _=window.hide();},
                        "workbench"=>{let _=open_workbench(&app.state::<Launch>());},"quit"=>app.exit(0),
                        id=>{if let Some(index)=id.strip_prefix("screen-").and_then(|n|n.parse::<usize>().ok()){let _=position(&window,index);}}
                    }
                }}).build(app)?;
            Ok(())
        }).run(tauri::generate_context!());
    if let Err(error)=result{eprintln!("Jarvis presence startup: {}",error.to_string().replace(&diagnostic_secret,"[redacted]"));}
}
