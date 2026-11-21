// Native Goose DOC CLI; imports the same namespaced native DOC CPU core
// used by SDL3 without a duplicate executable main entrypoint.
import std;
import os;
import .doc_typed_core;
namespace doc_typed;

fn run_doc_cli() {
    if arg_count() < 2 { fail(); }
    var path: u8[>..] = [];
    arg(1,path);
    var source: u8[>..] = [];
    if !read_file(path,source) { fail(); }
    var nodes: State[>..] = [];
    var values: Value[>..] = [];
    var active: bool[>..] = [];
    load(source,nodes,values,active,path);
    if arg_count() >= 3 {
        var mode: u8[>..] = [];
        arg(2,mode);
        if starts_with(mode,"--emit=") {
            if arg_count()!=3 { fail(); }
            let target_spec=mode[7..];
            let colon=find(target_spec,":");
            if colon <= 0 { fail(); }
            let id=lookup(nodes,target_spec[..colon]);
            let relative=target_spec[colon+1..];
            if id < 0 || !safe_doc_path(relative) { fail(); }
            var prefix=0;
            for i in 0..path.len {
                if path[i]=='/' { prefix=i+1; }
            }
            var output_path:u8[>..]=[];
            output_path.append(path[..prefix]);
            output_path.append(relative);
            if output_path.len > 512 { fail(); }
            let _ready=stabilize(nodes,values,active);
            var contents:u8[>..]=[];
            let result=values[id];
            if result.kind==0 {
                contents.append(if result.flag { "true" } else { "false" });
            } else if result.kind==1 {
                format_int(contents,result.number,10,0,' ');
            } else if result.kind==2 {
                contents.append(nat_text(result));
            } else if result.kind==3 {
                contents.append(ints_printable(result));
            } else if result.kind==4 {
                contents.append(maybe_text(result));
            } else {
                contents.append(text_bytes(result));
            }
            contents.push('\n');
            if !write_file_atomic(output_path,contents) { fail(); }
            print("DOC_EFFECT_WRITE_PASS: ",nodes[id].name);
            return;
        }
        if mode=="--snapshot-proof" {
            if arg_count()!=3 { fail(); }
            snapshot_proof(nodes,values,active);
            return;
        }
        if starts_with(mode,"--demand=") {
            let target = lookup(nodes,mode[9..]);
            if target < 0 { fail(); }
            var changes: Change[>..] = [];
            for i in 3..arg_count() {
                var raw: u8[>..] = [];
                arg(i,raw);
                let eq = find(raw,"=");
                if eq <= 0 { fail(); }
                let id = lookup(nodes,raw[..eq]);
                if id < 0 || nodes[id].derived { fail(); }
                let value = parse_value(raw[eq + 1..],nodes[id].kind);
                for old in changes {
                    if old.id == id { fail(); }
                }
                changes.push(Change { id: id, value: value, next: false });
            }
            for entry in changes {
                update(nodes,values,active,entry.id,entry.value);
            }
            var needed: bool[>..] = [];
            for i in 0..nodes.len { needed.push(false); }
            needed[target] = true;
            var cursor = nodes.len;
            while cursor > 0 {
                cursor--;
                if needed[cursor] && nodes[cursor].derived {
                    for p in 0..nodes[cursor].count {
                        needed[nodes[cursor].premise[p]] = true;
                    }
                }
            }
            let _performed = stabilize_demanded(nodes,values,active,needed);
            if values[target].kind == 0 {
                print(nodes[target].name, ": ", values[target].flag);
            } else if values[target].kind == 1 {
                print(nodes[target].name, ": ", values[target].number);
            } else if values[target].kind == 2 {
                print(nodes[target].name, ": ", nat_text(values[target]));
            } else if values[target].kind == 3 {
                print(nodes[target].name, ": ", ints_printable(values[target]));
            } else if values[target].kind==4 {
                print(nodes[target].name, ": ", maybe_text(values[target]));
            } else {
                print(nodes[target].name, ": ", text_bytes(values[target]));
            }
            return;
        }
        if starts_with(mode,"--through=") {
            let limit, ok = parse_int(mode[10..]);
            if !ok || limit < 0 { fail(); }
            run_recurrence(nodes,values,active,limit,-1,3);
            return;
        }
        if starts_with(mode,"--until=") {
            if arg_count() < 4 { fail(); }
            var raw_cap: u8[>..] = [];
            arg(3,raw_cap);
            if !starts_with(raw_cap,"--max-epochs=") { fail(); }
            let cap, ok = parse_int(raw_cap[13..]);
            let halt = lookup(nodes,mode[8..]);
            if !ok || cap < 0 || halt < 0 || nodes[halt].kind != 0 { fail(); }
            run_recurrence(nodes,values,active,cap,halt,4);
            return;
        }
        if starts_with(mode,"--replace-pinned=") {
            if arg_count()!=3 { fail(); }
            let next_path=mode[17..];
            if next_path.len==0 || !safe_doc_path(next_path) { fail(); }
            replace_pinned_proof(nodes,values,active,next_path);
            return;
        }
        if starts_with(mode,"--replace=") {
            if arg_count()!=3 { fail(); }
            let next_path=mode[10..];
            if next_path.len==0 { fail(); }
            // Complete the old frontier before any candidate is constructed.
            let _old=stabilize(nodes,values,active);
            print("DOC_GRAPH_GENERATION: 0");
            show(nodes,values);
            var incoming: u8[>..] = [];
            if !read_file(next_path,incoming) { fail(); }
            var pending_nodes: State[>..] = [];
            var pending_values: Value[>..] = [];
            var pending_active: bool[>..] = [];
            load(incoming,pending_nodes,pending_values,pending_active,next_path);
            for i in 0..pending_nodes.len {
                if !pending_nodes[i].derived {
                    let previous=lookup(nodes,pending_nodes[i].name);
                    if previous >= 0 && !nodes[previous].derived &&
                       nodes[previous].kind == pending_nodes[i].kind {
                        pending_values[i]=values[previous];
                    }
                }
            }
            let _computed=stabilize(pending_nodes,pending_values,pending_active);
            // The pending graph, sources and derived values form a complete,
            // independently owned next observation before the generation
            // marker is released. No prior materialization is modified.
            print("DOC_GRAPH_GENERATION: 1");
            show(pending_nodes,pending_values);
            return;
        }
    }
    // Validate the full command line before applying any source batch.
    var changes: Change[>..] = [];
    var next = false;
    for i in 2..arg_count() {
        var raw: u8[>..] = [];
        arg(i,raw);
        if raw == "--next" {
            if next { fail(); }
            next = true;
            continue;
        }
        let equal_mark = find(raw,"=");
        if equal_mark <= 0 { fail(); }
        let id = lookup(nodes,trim(raw[..equal_mark]));
        if id < 0 || nodes[id].derived { fail(); }
        let value = parse_value(trim(raw[equal_mark + 1..]),nodes[id].kind);
        for old in changes {
            if old.id == id && old.next == next { fail(); }
        }
        changes.push(Change { id: id, value: value, next: next });
    }
    for change in changes {
        if !change.next {
            update(nodes,values,active,change.id,change.value);
        }
    }
    let first = stabilize(nodes,values,active);
    show(nodes,values);
    print("DOC_TYPED_EVALUATIONS=",first);
    if next {
        for change in changes {
            if change.next {
                update(nodes,values,active,change.id,change.value);
            }
        }
        let second = stabilize(nodes,values,active);
        print("DOC_TYPED_NEXT");
        show(nodes,values);
        print("DOC_TYPED_EVALUATIONS=",second);
    }
}

fn ::main() { doc_typed::run_doc_cli(); }
