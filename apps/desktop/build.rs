fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "presence_regions", "presence_drag", "presence_toggle", "presence_status", "presence_workbench",
        ]),
    )).expect("Native presence permission manifest");
}
