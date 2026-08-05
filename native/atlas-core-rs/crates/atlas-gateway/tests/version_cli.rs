use serde_json::Value;
use std::process::Command;

#[test]
fn version_json_reports_compiled_identity() {
    let output = Command::new(env!("CARGO_BIN_EXE_atlas-gateway"))
        .args(["--version", "--json"])
        .output()
        .expect("gateway version command should run");
    assert!(output.status.success());
    let body: Value = serde_json::from_slice(&output.stdout).expect("valid version JSON");
    assert_eq!(body["service"], "atlas-gateway");
    assert_eq!(body["release_version"], atlas_gateway::RELEASE_VERSION);
    assert_eq!(body["component_version"], atlas_gateway::COMPONENT_VERSION);
    assert_eq!(body["build_sha"], atlas_gateway::BUILD_SHA);
}

#[test]
fn local_build_has_explicit_development_identity() {
    if option_env!("ATLAS_RELEASE_VERSION").is_none() {
        assert_eq!(
            atlas_gateway::RELEASE_VERSION,
            atlas_gateway::COMPONENT_VERSION
        );
    }
    if option_env!("ATLAS_BUILD_SHA").is_none() {
        assert_eq!(atlas_gateway::BUILD_SHA, "dev");
    }
}
