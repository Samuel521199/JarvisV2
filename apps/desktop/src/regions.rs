//! Native window geometry only; no input injection or access to other apps.
use super::Rect;
use std::ffi::c_void;
type Handle = *mut c_void;
#[repr(C)] struct Point { x:i32, y:i32 }
#[link(name="gdi32")]
extern "system" {
    fn CreateRectRgn(a:i32,b:i32,c:i32,d:i32)->Handle;
    fn CreateRoundRectRgn(a:i32,b:i32,c:i32,d:i32,e:i32,f:i32)->Handle;
    fn CombineRgn(dest:Handle,a:Handle,b:Handle,mode:i32)->i32;
    fn DeleteObject(object:Handle)->i32;
    fn PtInRegion(region:Handle,x:i32,y:i32)->i32;
}
#[link(name="user32")]
extern "system" {
    fn SetWindowRgn(hwnd:Handle,rgn:Handle,redraw:i32)->i32;
    fn GetWindowRgn(hwnd:Handle,rgn:Handle)->i32;
    fn ClientToScreen(hwnd:Handle,point:*mut Point)->i32;
    fn WindowFromPoint(point:Point)->Handle;
    fn GetAncestor(hwnd:Handle,flags:u32)->Handle;
}
struct Region(Handle);
impl Drop for Region {fn drop(&mut self){if !self.0.is_null(){unsafe{DeleteObject(self.0);}}}}

fn create(rects:&[Rect],scale:f64,width:u32,height:u32)->Result<Region,String> {
    if rects.is_empty() || rects.len()>48 || !scale.is_finite() || scale<=0.0 || width==0 || height==0 {
        return Err("invalid region count or scale".into());
    }
    for r in rects {
        if ![r.x,r.y,r.width,r.height].iter().all(|v|v.is_finite()) || r.width<=0.0 || r.height<=0.0
            || r.x<0.0 || r.y<0.0 || (r.x+r.width)*scale>width as f64+4.0
            || (r.y+r.height)*scale>height as f64+4.0 {return Err("invalid region bounds".into());}
    }
    unsafe {
        let union=Region(CreateRectRgn(0,0,0,0));
        if union.0.is_null(){return Err("region allocation failed".into());}
        for r in rects {
            let a=(r.x*scale).floor() as i32;let b=(r.y*scale).floor() as i32;
            let c=((r.x+r.width)*scale).ceil() as i32;let d=((r.y+r.height)*scale).ceil() as i32;
            let part=Region(if r.rounded {CreateRoundRectRgn(a,b,c,d,(24.0*scale) as i32,(24.0*scale) as i32)} else {CreateRectRgn(a,b,c,d)});
            if part.0.is_null() || CombineRgn(union.0,union.0,part.0,2)==0 {return Err("region merge failed".into());}
        }
        Ok(union)
    }
}

pub fn apply(window:&tauri::WebviewWindow,rects:&[Rect])->Result<(),String> {
    let scale=window.scale_factor().map_err(|_|"window unavailable")?;
    let size=window.inner_size().map_err(|_|"window unavailable")?;
    let mut region=create(rects,scale,size.width,size.height)?;
    let hwnd=window.hwnd().map_err(|_|"window unavailable")?.0 as Handle;
    if unsafe{SetWindowRgn(hwnd,region.0,1)}==0 {return Err("window region failed".into());}
    region.0=std::ptr::null_mut(); // The OS owns it after successful SetWindowRgn.
    Ok(())
}

/// Read-only inspection of this window's OS hit map. Does not click or inspect
/// the content/title/process of an underlying window; not a user-input test.
pub fn inspect(window:&tauri::WebviewWindow,rects:&[Rect])->Result<serde_json::Value,String> {
    let scale=window.scale_factor().map_err(|_|"window unavailable")?;
    let size=window.inner_size().map_err(|_|"window unavailable")?;
    let hwnd=window.hwnd().map_err(|_|"window unavailable")?.0 as Handle;
    let mask=Region(unsafe{CreateRectRgn(0,0,0,0)});
    if mask.0.is_null() || unsafe{GetWindowRgn(hwnd,mask.0)}==0{return Err("native mask missing".into());}
    let mut controls=0;let mut control_hits=0;let mut blank=0;let mut blank_hits=0;
    for r in rects {
        let mut point=Point{x:((r.x+r.width/2.0)*scale) as i32,y:((r.y+r.height/2.0)*scale) as i32};
        if unsafe{PtInRegion(mask.0,point.x,point.y)}==0{return Err("control center excluded".into());}
        controls+=1;
        if unsafe{ClientToScreen(hwnd,&mut point)}==0{return Err("window unavailable".into());}
        if unsafe{GetAncestor(WindowFromPoint(point),2)}==hwnd{control_hits+=1;}
    }
    for x in (8..size.width).step_by(47) {for y in (8..size.height).step_by(47) {
        if unsafe{PtInRegion(mask.0,x as i32,y as i32)}!=0{continue;}
        let mut point=Point{x:x as i32,y:y as i32};blank+=1;
        if unsafe{ClientToScreen(hwnd,&mut point)}==0{return Err("window unavailable".into());}
        if unsafe{GetAncestor(WindowFromPoint(point),2)}==hwnd{blank_hits+=1;}
    }}
    Ok(serde_json::json!({"controls":controls,"control_os_hits":control_hits,"blank_samples":blank,
        "blank_os_hits":blank_hits,"passed":controls>0&&controls==control_hits&&blank>0&&blank_hits==0,
        "scope":"this window OS hit map, no input injection"}))
}

#[cfg(test)] mod tests {
    use super::*;
    fn rect(x:f64,y:f64,w:f64,h:f64)->Rect{Rect{x,y,width:w,height:h,rounded:false}}
    #[test] fn islands_and_blank_gap_at_multiple_dpi(){
        for scale in [1.0,1.25,1.5,2.0] {
            let mask=create(&[rect(5.0,10.0,30.0,20.0),rect(80.0,60.0,20.0,20.0)],scale,220,180).unwrap();
            assert_ne!(unsafe{PtInRegion(mask.0,(15.0*scale) as i32,(15.0*scale) as i32)},0);
            assert_ne!(unsafe{PtInRegion(mask.0,(90.0*scale) as i32,(70.0*scale) as i32)},0);
            assert_eq!(unsafe{PtInRegion(mask.0,(50.0*scale) as i32,(45.0*scale) as i32)},0);
        }
    }
    #[test] fn rounded_corner_is_not_a_solid_rectangle(){
        let mask=create(&[Rect{rounded:true,..rect(10.0,10.0,74.0,74.0)}],1.0,100,100).unwrap();
        assert_eq!(unsafe{PtInRegion(mask.0,10,10)},0);assert_ne!(unsafe{PtInRegion(mask.0,47,47)},0);
    }
    #[test] fn invalid_geometry_fails_before_creating_window_mask(){
        for r in [rect(-1.0,0.0,10.0,10.0),rect(0.0,0.0,0.0,10.0),rect(0.0,0.0,f64::INFINITY,1.0),rect(0.0,0.0,200.0,1.0)] {
            assert!(create(&[r],1.0,100,100).is_err());
        }
        assert!(create(&[],1.0,100,100).is_err());assert!(create(&[rect(0.0,0.0,1.0,1.0)],f64::NAN,100,100).is_err());
        let many:Vec<_>=(0..49).map(|_|rect(0.0,0.0,1.0,1.0)).collect();assert!(create(&many,1.0,100,100).is_err());
    }
}
