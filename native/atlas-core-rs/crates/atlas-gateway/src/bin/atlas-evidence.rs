//! Versioned newline-delimited JSON protocol for atomic evidence persistence.

use atlas_gateway::evidence::{
    persist_full_result, FullResultRequest, ProtocolError, ProtocolResponse, PROTOCOL_VERSION,
};
use std::io::{self, BufRead};

fn main() {
    let mut failed = false;
    for line in io::stdin().lock().lines() {
        let response = match line {
            Ok(line) => match serde_json::from_str::<FullResultRequest>(&line) {
                Ok(request) => match persist_full_result(&request) {
                    Ok(reference) => ProtocolResponse {
                        protocol: PROTOCOL_VERSION.to_string(),
                        ok: true,
                        reference: Some(reference),
                        error: None,
                    },
                    Err(message) => {
                        failed = true;
                        ProtocolResponse {
                            protocol: PROTOCOL_VERSION.to_string(),
                            ok: false,
                            reference: None,
                            error: Some(ProtocolError {
                                code: "persistence_failed".to_string(),
                                message,
                            }),
                        }
                    }
                },
                Err(error) => {
                    failed = true;
                    ProtocolResponse {
                        protocol: PROTOCOL_VERSION.to_string(),
                        ok: false,
                        reference: None,
                        error: Some(ProtocolError {
                            code: "invalid_request".to_string(),
                            message: error.to_string(),
                        }),
                    }
                }
            },
            Err(error) => {
                failed = true;
                ProtocolResponse {
                    protocol: PROTOCOL_VERSION.to_string(),
                    ok: false,
                    reference: None,
                    error: Some(ProtocolError {
                        code: "stdin_failed".to_string(),
                        message: error.to_string(),
                    }),
                }
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
