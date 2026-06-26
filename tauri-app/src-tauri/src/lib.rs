use tauri_plugin_shell::ShellExt;
use tauri::Emitter;
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, Some(vec![])))
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            let app_handle = app.handle().clone();
            
            tauri::async_runtime::spawn(async move {
                let mut crash_count = 0;
                let max_restarts = 5;
                let healthy_uptime = std::time::Duration::from_secs(120);
                
                loop {
                    let exe_dir = std::env::current_exe().unwrap().parent().unwrap().to_path_buf();
                    let suffix = if cfg!(target_arch = "aarch64") {
                        "-aarch64-apple-darwin"
                    } else if cfg!(target_arch = "x86_64") {
                        "-x86_64-apple-darwin"
                    } else {
                        ""
                    };
                    
                    let tor_with_suffix = exe_dir.join(format!("tor{}", suffix));
                    let tor_path = if tor_with_suffix.exists() { tor_with_suffix } else { exe_dir.join("tor") };
                    
                    let privoxy_with_suffix = exe_dir.join(format!("privoxy{}", suffix));
                    let privoxy_path = if privoxy_with_suffix.exists() { privoxy_with_suffix } else { exe_dir.join("privoxy") };
                    
                    let sidecar_command = app_handle.shell().sidecar("python-backend").unwrap()
                        .env("TOR_PATH", tor_path.to_str().unwrap())
                        .env("PRIVOXY_PATH", privoxy_path.to_str().unwrap());
                    
                    let (mut rx, _child) = sidecar_command.spawn().expect("Failed to spawn sidecar");
                    
                    let start_time = std::time::Instant::now();
                    
                    while let Some(event) = rx.recv().await {
                        match event {
                            tauri_plugin_shell::process::CommandEvent::Terminated(_) | tauri_plugin_shell::process::CommandEvent::Error(_) => {
                                // If it lived longer than the healthy uptime, reset the crash counter
                                if start_time.elapsed() > healthy_uptime {
                                    crash_count = 0;
                                }
                                
                                crash_count += 1;
                                app_handle.emit("backend-crashed", crash_count).unwrap();
                                break;
                            },
                            _ => {}
                        }
                    }
                    
                    if crash_count >= max_restarts {
                        app_handle.emit("backend-fatal", ()).unwrap();
                        break; // Stop restarting, surface hard error to UI
                    }
                    tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
