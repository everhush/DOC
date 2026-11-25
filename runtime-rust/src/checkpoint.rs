//! Versioned, bounded, fail-closed durable checkpoints for stable DOC source facts.
//! Checkpoints are not arbitrary code and are never evaluated while parsing.
//! The restored recurrence starts at epoch zero; saved_epoch is provenance only.
//! FNV-1a checksums detect accidental damage, NOT malicious modification.
//! The schema fingerprint is bound to the v1 Rust typed Graph representation.

use std::{collections::HashSet, path::Path};

use crate::{recurrence::Recurrence, Graph, Result, StateId, Type, Value, write_doc_output};

const MAX_BYTES: usize = 8 * 1024 * 1024;
const MAGIC: &str = "DOC-CHECKPOINT/1";
const FNV_START: u64 = 0xcbf29ce484222325;
const FNV_PRIME: u64 = 0x100000001b3;

pub struct LoadedCheckpoint {
    /// Independently evaluated DOC graph with its saved sources at new epoch 0.
    pub recurrence: Recurrence,
    /// Original epoch index for diagnostics; no unavailable history is recreated.
    pub saved_epoch: u64,
}

fn checksum(bytes: &[u8]) -> u64 {
    bytes.iter().fold(FNV_START, |acc, byte| (acc ^ u64::from(*byte)).wrapping_mul(FNV_PRIME))
}
fn hex_encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len().saturating_mul(2));
    for byte in bytes { out.push_str(&format!("{byte:02x}")); }
    out
}
fn hex_decode(raw: &str) -> Result<Vec<u8>> {
    if raw.len() % 2 != 0 || raw.len() > MAX_BYTES * 2 {
        return Err("checkpoint invalid hex length".into());
    }
    let mut out = Vec::with_capacity(raw.len() / 2);
    for pair in raw.as_bytes().chunks_exact(2) {
        let hex = std::str::from_utf8(pair).map_err(|_| "checkpoint hex must be ASCII")?;
        let byte = u8::from_str_radix(hex,16).map_err(|_| "checkpoint invalid hex value")?;
        out.push(byte);
    }
    if hex_encode(&out) != raw { return Err("checkpoint hex not canonical".into()); }
    Ok(out)
}
fn type_name(t: Type) -> &'static str {
    match t {
        Type::Int => "int",
        Type::Bool => "bool",
        Type::Nat => "nat",
        Type::Ints => "ints",
        Type::MaybeInt => "maybe_int",
        Type::Text => "text",
    }
}
fn fingerprint(graph: &Graph, carry: &[(StateId,StateId)]) -> u64 {
    // The schema is explicitly tied to the graph's typed reference IR v1:
    // names, types, source defaults, ordered typed expressions, carry authority.
    let mut text = String::from("DOC-RUST-TYPED-IR/1\n");
    for state in &graph.states {
        text.push_str(&format!("state\t{:?}\n", state));
    }
    for &(from, to) in carry {
        text.push_str(&format!("carry\t{from}\t{to}\n"));
    }
    checksum(text.as_bytes())
}
fn serialized_value(value: &Value) -> String {
    match value {
        Value::Text(text) => text.clone(),
        other => other.to_string(),
    }
}
fn decoded_value(kind: Type, bytes: &[u8]) -> Result<Value> {
    let value=std::str::from_utf8(bytes).map_err(|_| "checkpoint invalid UTF-8")?;
    if kind == Type::Text { return Ok(Value::Text(value.to_owned())); }
    let typed = Value::parse_for_type(value,kind)?;
    if serialized_value(&typed) != value {
        return Err("checkpoint value not canonical".into());
    }
    Ok(typed)
}

/// Store the latest fully stable typed source facts as an atomic same-directory file
/// replacement using the existing explicit confined DOC output boundary.
pub fn save_checkpoint(doc_file: &str, relative: &str, recurrence: &Recurrence) -> Result<()> {
    let facts = recurrence.current_source_facts()?;
    let graph=recurrence.graph();
    let mut body=format!("{MAGIC}\nschema\t{:016x}\nepoch\t{}\ncount\t{}\n",
        fingerprint(graph,recurrence.carries()),recurrence.epoch(),facts.len());
    for (id, value) in facts {
        let state=graph.states.get(id).ok_or("checkpoint source id invalid")?;
        if state.definition.is_some() || state.kind != value.kind() {
            return Err("checkpoint source type mismatch".into());
        }
        body.push_str(&format!("fact\t{}\t{}\t{}\n",
            state.name,type_name(state.kind),hex_encode(serialized_value(&value).as_bytes())));
        if body.len() > MAX_BYTES.saturating_sub(64) {
            return Err("checkpoint exceeds resource limit".into());
        }
    }
    let encoded=format!("{body}checksum\t{:016x}",checksum(body.as_bytes()));
    write_doc_output(doc_file,relative,&Value::Text(encoded))
}

/// Load a snapshot from a confined file and validate it BEFORE constructing a
/// candidate DOC epoch. Never mutate an existing recurrence on parse failure.
pub fn load_checkpoint(
    doc_file: &str, relative: &str,
    graph: Graph, carry: Vec<(StateId,StateId)>,
    workers: usize, retention: usize,
) -> Result<LoadedCheckpoint> {
    let text=crate::confined::read(crate::confined::source_directory(Path::new(doc_file)),relative,MAX_BYTES)?;
    let text=text.strip_suffix('\n').ok_or("checkpoint missing final newline")?;
    let (head, reported)=text.rsplit_once("\nchecksum\t")
        .ok_or("checkpoint missing checksum")?;
    if reported.len()!=16 || !reported.bytes().all(|c|c.is_ascii_hexdigit()) {
        return Err("checkpoint malformed checksum".into());
    }
    let expected=u64::from_str_radix(reported,16)
        .map_err(|_| "checkpoint malformed checksum")?;
    let body=format!("{head}\n");
    if checksum(body.as_bytes())!=expected || format!("{expected:016x}")!=reported {
        return Err("checkpoint checksum mismatch".into());
    }
    let mut lines=body.lines();
    if lines.next()!=Some(MAGIC) { return Err("checkpoint version unsupported".into()); }
    let schema=lines.next().and_then(|s|s.strip_prefix("schema\t"))
        .ok_or("checkpoint missing schema")?;
    if schema!=format!("{:016x}",fingerprint(&graph,&carry)) {
        return Err("checkpoint schema, source or carry mismatch".into());
    }
    let epoch=lines.next().and_then(|s|s.strip_prefix("epoch\t"))
        .ok_or("checkpoint missing epoch")?;
    let saved_epoch=epoch.parse::<u64>().map_err(|_| "checkpoint invalid epoch")?;
    if saved_epoch.to_string()!=epoch { return Err("checkpoint noncanonical epoch".into()); }
    let count=lines.next().and_then(|s|s.strip_prefix("count\t"))
        .ok_or("checkpoint missing source count")?;
    let count=count.parse::<usize>().map_err(|_| "checkpoint invalid source count")?;
    let expected_count=graph.states.iter().filter(|s|s.definition.is_none()).count();
    if count!=expected_count { return Err("checkpoint source count mismatch".into()); }
    let mut seen=HashSet::new();
    let mut facts=Vec::with_capacity(count);
    for _ in 0..count {
        let line=lines.next().ok_or("checkpoint truncated facts")?;
        let mut fields=line.split('\t');
        if fields.next()!=Some("fact") { return Err("checkpoint malformed fact row".into()); }
        let name=fields.next().ok_or("checkpoint missing source name")?;
        let ty=fields.next().ok_or("checkpoint missing source type")?;
        let raw=fields.next().ok_or("checkpoint missing source value")?;
        if fields.next().is_some() { return Err("checkpoint extra fact fields".into()); }
        let id=graph.id(name).ok_or("checkpoint unknown state")?;
        let state=&graph.states[id];
        if state.definition.is_some() || type_name(state.kind)!=ty || !seen.insert(id) {
            return Err("checkpoint duplicate, derived or mistyped source".into());
        }
        let bytes=hex_decode(raw)?;
        let value=decoded_value(state.kind,&bytes)?;
        facts.push((id,value));
    }
    if lines.next().is_some() { return Err("checkpoint trailing data".into()); }
    let recurrence=Recurrence::new_with_retention(graph,carry,&facts,workers,retention)?;
    Ok(LoadedCheckpoint{recurrence,saved_epoch})
}
