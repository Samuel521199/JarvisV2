fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "presence_regions", "presence_drag", "presence_toggle", "presence_status", "presence_workbench",
            "presence_motion_policy", "presence_panel_state",
        ]),
    )).expect("Native presence permission manifest");
}
