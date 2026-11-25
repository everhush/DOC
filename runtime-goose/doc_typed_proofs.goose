// Scoped Goose conformance witnesses: owned pinned readers, graph replacement
// and pool compaction. These expensive four-reader demonstrations are NOT part
// of the regular DOC language evaluation kernel and are imported only by the
// CPU CLI that explicitly supports --snapshot-proof/--replace-pinned.
import std;
import os;
import .doc_typed_core;
namespace doc_typed;

// Independent owned snapshot proof using Goose's native share-nothing thread
// arguments. Each worker copies the stable valuation and both immutable
// allocation pools before the parent mutates/reclaims its current values.
// A ready/go handshake forces the readers to remain live over compaction.
struct SnapshotReady { worker:i64 }
struct SnapshotGo { proceed:bool }
struct SnapshotReply { worker:i64, original_digest:i64 }
fn snapshot_digest(values:Value[:],nats:u8[:],ints:i64[:],texts:u8[:]) -> i64 {
    var digest=0;
    for value in values {
        if value.kind==0 {
            digest+=if value.flag { 1 } else { 0 };
        } else if value.kind==1 {
            digest+=value.number;
        } else if value.kind==2 {
            for i in 0..value.length {
                digest+=nats[value.start+i] as i64;
            }
        } else if value.kind==3 {
            for i in 0..value.length {
                digest+=ints[value.start+i];
            }
        } else if value.kind==4 {
            if value.flag { digest+=value.number; }
        } else if value.kind==5 {
            for i in 0..value.length {
                digest+=texts[value.start+i] as i64;
            }
        }
    }
    return digest;
}
thread_fn snapshot_reader(worker:i64,
                          owned_values:Value[>..],
                          owned_nat:u8[>..],
                          owned_ints:i64[>..],
                          owned_text:u8[>..]) {
    qput(SnapshotReady { worker:worker });
    let proceed=qget<SnapshotGo>();
    if !proceed.proceed { fail(); }
    let digest=snapshot_digest(owned_values,owned_nat,owned_ints,owned_text);
    qput(SnapshotReply { worker:worker, original_digest:digest });
}
// Native Goose graph-replacement proof: four concurrent owned readers retain
// all types of prior immutable values while a replacement is fully evaluated
// and the parent reclaims/compacts nat, ints and UTF-8 pools. This witness is
// intentionally a scoped, single-authority graph-version operation, not an
// unproven distributed reclamation algorithm.
fn replace_pinned_proof(nodes:State[:],values:Value[:],
                        active:bool[:],path:u8[:]) {
    let _current=stabilize(nodes,values,active);
    let original=snapshot_digest(values,nat_pool,ints_pool,text_pool);
    print("DOC_GRAPH_GENERATION: 0");
    show(nodes,values);

    var owned_values:Value[>..]=[];
    owned_values.append(values);
    var ids:i64[>..]=[];
    for worker in 0..4 {
        ids.push(thread_spawn(snapshot_reader,worker,
            copy(owned_values),copy(nat_pool),copy(ints_pool),copy(text_pool)));
    }
    var ready:bool[>..]=[];
    ready.resize(4,false);
    for i in 0..4 {
        let response=qget<SnapshotReady>();
        if response.worker<0 || response.worker>=4 ||
           ready[response.worker] { fail(); }
        ready[response.worker]=true;
    }

    // Validate and evaluate the replacement in private mutable candidate
    // storage. Current published values are never modified during this step.
    var incoming:u8[>..]=[];
    if !read_file(path,incoming) { fail(); }
    var pending_nodes:State[>..]=[];
    var pending_values:Value[>..]=[];
    var pending_active:bool[>..]=[];
    load(incoming,pending_nodes,pending_values,pending_active,path);
    for i in 0..pending_nodes.len {
        if !pending_nodes[i].derived {
            let old=lookup(nodes,pending_nodes[i].name);
            if old>=0 && !nodes[old].derived &&
               nodes[old].kind==pending_nodes[i].kind {
                pending_values[i]=values[old];
            }
        }
    }
    let _stable=stabilize(pending_nodes,pending_values,pending_active);
    // Copy all candidate-owned roots before recycling the parent pool.
    // Detached reader copies are held independently until their barriers.
    var defaults:Value[>..]=[];
    var facts:EpochFact[>..]=[];
    compact_nat_roots(pending_values,defaults,facts);

    for i in 0..4 { qput(SnapshotGo {proceed:true}); }
    var verified:bool[>..]=[];
    verified.resize(4,false);
    for i in 0..4 {
        let reply=qget<SnapshotReply>();
        if reply.worker<0 || reply.worker>=4 ||
           verified[reply.worker] ||
           reply.original_digest!=original { fail(); }
        verified[reply.worker]=true;
    }
    for id in ids {
        if !thread_wait(id) { fail(); }
    }
    print("DOC_GOOSE_GRAPH_PINNED_REPLACE_PASS: 4 readers, full pool compaction");
    print("DOC_GRAPH_GENERATION: 1");
    show(pending_nodes,pending_values);
}

fn snapshot_proof(nodes:State[:],values:Value[:],active:bool[:]) {
    let _initial=stabilize(nodes,values,active);
    let original=snapshot_digest(values,nat_pool,ints_pool,text_pool);
    // Goose copy() consumes an owned value, not a borrowed slice.
    // Take an explicit owned root first and deep-copy it per worker.
    var owned_values:Value[>..]=[];
    owned_values.append(values);
    var ids:i64[>..]=[];
    for worker in 0..4 {
        ids.push(thread_spawn(snapshot_reader,worker,
                              copy(owned_values),copy(nat_pool),copy(ints_pool),
                              copy(text_pool)));
    }
    var ready:bool[>..]=[];ready.resize(4,false);
    for i in 0..4 {
        let response=qget<SnapshotReady>();
        if response.worker < 0 || response.worker >= 4 ||
           ready[response.worker] { fail(); }
        ready[response.worker]=true;
    }
    let nat_source=lookup(nodes,"n");
    let list_source=lookup(nodes,"items");
    if nat_source < 0 || list_source < 0 ||
       nodes[nat_source].kind != 2 || nodes[list_source].kind != 3 ||
       nodes[nat_source].derived || nodes[list_source].derived { fail(); }
    update(nodes,values,active,nat_source,
           nat_parse("12345678901234567890123456789012345678901234567890"));
    update(nodes,values,active,list_source,ints_parse("[11,13,17,19]"));
    let _updated=stabilize(nodes,values,active);
    var empty_defaults:Value[>..]=[];
    var empty_facts:EpochFact[>..]=[];
    compact_nat_roots(values,empty_defaults,empty_facts);
    for i in 0..4 {qput(SnapshotGo {proceed:true});}
    var verified:bool[>..]=[];verified.resize(4,false);
    for i in 0..4 {
        let result=qget<SnapshotReply>();
        if result.worker < 0 || result.worker >= 4 ||
           verified[result.worker] ||
           result.original_digest != original { fail(); }
        verified[result.worker]=true;
    }
    for id in ids {
        if !thread_wait(id) { fail(); }
    }
    print("DOC_GOOSE_PINNED_SNAPSHOT_PASS: 4 owned readers across pool compaction");
    show(nodes,values);
}
