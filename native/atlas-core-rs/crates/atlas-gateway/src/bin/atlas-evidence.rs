//! Versioned newline-delimited JSON protocol for atomic evidence persistence.

use atlas_gateway::evidence::{
    persist_change_set, persist_change_set_aggregation, persist_full_result,
    AggregateChangeSetsRequest, ChangeSetRequest, FullResultRequest, ProtocolError,
    ProtocolResponse, PROTOCOL_VERSION,
};
use std::io::{self, BufRead};

fn error_response(code: &str, message: String) -> ProtocolResponse {
    ProtocolResponse {
        protocol: PROTOCOL_VERSION.to_string(),
        ok: false,
        reference: None,
        change_set: None,
        aggregation: None,
        error: Some(ProtocolError {
            code: code.to_string(),
            message,
        }),
    }
}

fn dispatch(line: &str) -> ProtocolResponse {
    let value: serde_json::Value = match serde_json::from_str(line) {
        Ok(value) => value,
        Err(error) => return error_response("invalid_request", error.to_string()),
    };
    if value.get("kind").and_then(serde_json::Value::as_str) == Some("aggregate_change_sets") {
        let request: AggregateChangeSetsRequest = match serde_json::from_value(value) {
            Ok(request) => request,
            Err(error) => return error_response("invalid_request", error.to_string()),
        };
        return persist_change_set_aggregation(&request)
            .map(|aggregation| ProtocolResponse {
                protocol: PROTOCOL_VERSION.to_string(),
                ok: true,
                reference: None,
                change_set: None,
                aggregation: Some(aggregation),
                error: None,
            })
            .unwrap_or_else(|message| error_response("persistence_failed", message));
    }
    if value.get("kind").and_then(serde_json::Value::as_str) == Some("change_set") {
        let request: ChangeSetRequest = match serde_json::from_value(value) {
            Ok(request) => request,
            Err(error) => return error_response("invalid_request", error.to_string()),
        };
        return persist_change_set(&request)
            .map(|change_set| ProtocolResponse {
                protocol: PROTOCOL_VERSION.to_string(),
                ok: true,
                reference: None,
                change_set: Some(change_set),
                aggregation: None,
                error: None,
            })
            .unwrap_or_else(|message| error_response("persistence_failed", message));
    }
    let request: FullResultRequest = match serde_json::from_value(value) {
        Ok(request) => request,
        Err(error) => return error_response("invalid_request", error.to_string()),
    };
    persist_full_result(&request)
        .map(|reference| ProtocolResponse {
            protocol: PROTOCOL_VERSION.to_string(),
            ok: true,
            reference: Some(reference),
            change_set: None,
            aggregation: None,
            error: None,
        })
        .unwrap_or_else(|message| error_response("persistence_failed", message))
}

fn main() {
    let mut failed = false;
    for line in io::stdin().lock().lines() {
        let response = match line {
            Ok(line) => {
                let response = dispatch(&line);
                if !response.ok {
                    failed = true;
                }
                response
            }
            Err(error) => {
                failed = true;
                error_response("stdin_failed", error.to_string())
            }
        };
        println!(
            "{}",
            serde_json::to_string(&response).expect("protocol response serializes")
        );
    }
    if failed {
        std::process::exit(1);
    }
}
