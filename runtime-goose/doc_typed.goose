// Independent native-Goose interpreter for the typed, finite DOC graph subset.
// Supports bool/int, type-checked conditional/equality, checked i64 arithmetic,
// private ready-frontier evaluation, source updates and exact equality cutoffs.
// It does not yet implement recurrence, I/O effects, threads or physical GC.
import std;
import os;

struct Value { kind: i64, number: i64, flag: bool }
struct State {
    name: u8[..64],
    expression: u8[..512],
    premise: i64[16],
    count: i64,
    kind: i64,
    derived: bool,
}
struct Change { id: i64, value: Value, next: bool }

fn fail() { print("DOC_TYPED_ERROR"); exit(1); }
fn boolean(v: bool) -> Value { return Value { kind: 0, number: 0, flag: v }; }
fn integer(v: i64) -> Value { return Value { kind: 1, number: v, flag: false }; }
fn zero(k: i64) -> Value {
    return if k == 0 { boolean(false) } else { integer(0) };
}
fn equal(a: Value, b: Value) -> bool {
    if a.kind != b.kind { return false; }
    return if a.kind == 0 { a.flag == b.flag } else { a.number == b.number };
}
fn type_name(t: u8[:]) -> i64 {
    if t == "bool" { return 0; }
    if t == "int" { return 1; }
    fail();
    return -1;
}
fn parse_value(raw: u8[:], kind: i64) -> Value {
    if kind == 0 {
        if raw == "true" { return boolean(true); }
        if raw == "false" { return boolean(false); }
    } else {
        let number, ok = parse_int(raw);
        if ok { return integer(number); }
    }
    fail();
    return zero(kind);
}
fn ident(c: u8) -> bool {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}
fn valid_name(s: u8[:]) -> bool {
    if s.len == 0 || s.len > 64 { return false; }
    if s[0] >= '0' && s[0] <= '9' { return false; }
    for c in s { if !ident(c) { return false; } }
    return s != "true" && s != "false" && s != "add" &&
           s != "sub" && s != "mul" && s != "eq" && s != "if";
}
fn lookup(nodes: State[:], name: u8[:]) -> i64 {
    for i in 0..nodes.len { if nodes[i].name == name { return i; } }
    return -1;
}
fn uses(node: State&, id: i64) -> bool {
    for k in 0..node.count { if node.premise[k] == id { return true; } }
    return false;
}
fn skip(s: u8[:], p: i64) -> i64 {
    var i = p;
    while i < s.len && (s[i] == ' ' || s[i] == '\r' || s[i] == '\t') { i++; }
    return i;
}
fn expect(s: u8[:], p: i64, ch: u8) -> i64 {
    let i = skip(s, p);
    if i >= s.len || s[i] != ch { fail(); }
    return i + 1;
}
fn arithmetic(op: u8[:], a: i64, b: i64) -> i64 {
    let hi = 9223372036854775807;
    let lo = -9223372036854775807 - 1;
    if op == "add" {
        if (b > 0 && a > hi - b) || (b < 0 && a < lo - b) { fail(); }
        return a + b;
    }
    if op == "sub" {
        if (b > 0 && a < lo + b) || (b < 0 && a > hi + b) { fail(); }
        return a - b;
    }
    if op == "mul" {
        if a == 0 || b == 0 { return 0; }
        if a > 0 {
            if (b > 0 && a > hi / b) || (b < 0 && b < lo / a) { fail(); }
        } else {
            if (b > 0 && a < lo / b) || (b < 0 && a < hi / b) { fail(); }
        }
        return a * b;
    }
    fail();
    return 0;
}
// execute=false checks types in every expression without evaluating operations,
// including the unselected branch of a conditional.
recursive fn expression(s: u8[:], p: i64, nodes: State[:],
                        values: Value[:], premises: i64[:],
                        execute: bool, depth: i64) -> Value, i64 {
    if depth == 0 { fail(); }
    let i = skip(s, p);
    var end = i;
    if end < s.len && s[end] == '-' { end++; }
    while end < s.len && ident(s[end]) { end++; }
    if end == i { fail(); }
    let word = s[i..end];
    let after = skip(s,end);
    if word == "true" { return boolean(execute), after; }
    if word == "false" { return boolean(false), after; }
    let n, is_number = parse_int(word);
    if is_number { return integer(if execute { n } else { 0 }), after; }
    if word != "if" && word != "eq" &&
       word != "add" && word != "sub" && word != "mul" {
        let id = lookup(nodes,word);
        if id < 0 { fail(); }
        var allowed = false;
        for premise in premises { if premise == id { allowed = true; } }
        if !allowed { fail(); }
        return if execute { values[id] } else { zero(nodes[id].kind) }, after;
    }
    let open = expect(s,after,'(');
    let a, next = expression(s,open,nodes,values,premises,execute,depth - 1);
    let comma = expect(s,next,',');
    if word == "if" {
        if a.kind != 0 { fail(); }
        let yes, after_yes = expression(s,comma,nodes,values,premises,
                                        execute && a.flag,depth - 1);
        let comma2 = expect(s,after_yes,',');
        let no, after_no = expression(s,comma2,nodes,values,premises,
                                      execute && !a.flag,depth - 1);
        let close = expect(s,after_no,')');
        if yes.kind != no.kind { fail(); }
        if !execute { return zero(yes.kind), close; }
        return if a.flag { yes } else { no }, close;
    }
    let b, after_b = expression(s,comma,nodes,values,premises,execute,depth - 1);
    let close = expect(s,after_b,')');
    if word == "eq" {
        if a.kind != b.kind { fail(); }
        return boolean(execute && equal(a,b)), close;
    }
    if a.kind != 1 || b.kind != 1 { fail(); }
    if !execute { return integer(0), close; }
    return integer(arithmetic(word,a.number,b.number)), close;
}
fn inspect(nodes: State[:], values: Value[:], id: i64, execute: bool) -> Value {
    let node = nodes[id];
    let premises = node.premise[..node.count];
    let body = node.expression[..];
    let value, end = expression(body,0,nodes,values,premises,execute,128);
    if skip(body,end) != body.len || value.kind != node.kind { fail(); }
    return value;
}
fn load(source: u8[:], nodes: State[>..]&, values: Value[>..]&,
        active: bool[>..]&) {
    for original in split(source,'\n') {
        var n = 0;
        while n < original.len && original[n] != '#' { n++; }
        let line = trim(original[..n]);
        if line.len == 0 { continue; }
        if starts_with(line,"source ") {
            let rest = line[7..];
            let colon = find(rest,":");
            let assign = find(rest," = ");
            if colon <= 0 || assign <= colon { fail(); }
            let name = trim(rest[..colon]);
            if !valid_name(name) || lookup(nodes,name) >= 0 { fail(); }
            let kind = type_name(trim(rest[colon + 1..assign]));
            let value = parse_value(trim(rest[assign + 3..]),kind);
            nodes.push(State {
                name: name, expression: "", premise: [0;16],
                count: 0, kind: kind, derived: false,
            });
            values.push(value);
            active.push(false);
        } else if starts_with(line,"derive ") {
            let rest = line[7..];
            let colon = find(rest,":");
            let open = find(rest,"(");
            let close = find(rest,") = ");
            if colon <= 0 || open <= colon || close < open { fail(); }
            let name = trim(rest[..colon]);
            if !valid_name(name) || lookup(nodes,name) >= 0 { fail(); }
            let kind = type_name(trim(rest[colon + 1..open]));
            let body = trim(rest[close + 4..]);
            if body.len == 0 || body.len > 512 { fail(); }
            var node = State {
                name: name, expression: body, premise: [0;16],
                count: 0, kind: kind, derived: true,
            };
            let names = trim(rest[open + 1..close]);
            if names.len > 0 {
                for part in split(names,',') {
                    let pname = trim(part);
                    let id = lookup(nodes,pname);
                    if id < 0 || node.count >= 16 { fail(); }
                    for k in 0..node.count {
                        if node.premise[k] == id { fail(); }
                    }
                    node.premise[node.count] = id;
                    node.count++;
                }
            }
            nodes.push(node);
            values.push(zero(kind));
            active.push(true);
            let id = nodes.len - 1;
            let _checked = inspect(nodes,values,id,false);
        } else { fail(); }
    }
    if nodes.len == 0 { fail(); }
}
fn update(nodes: State[:], values: Value[:], active: bool[:],
          id: i64, value: Value) {
    if id < 0 || id >= nodes.len || nodes[id].derived ||
       value.kind != nodes[id].kind { fail(); }
    if equal(values[id],value) { return; }
    values[id] = value;
    for j in 0..nodes.len {
        if nodes[j].derived && uses(nodes[j],id) { active[j] = true; }
    }
}
fn stabilize(nodes: State[:], values: Value[:], active: bool[:]) -> i64 {
    var evaluations = 0;
    loop {
        var blocked: bool[>..] = [];
        var frontier: i64[>..] = [];
        for i in 0..nodes.len {
            var blocked_here = false;
            if nodes[i].derived {
                for k in 0..nodes[i].count {
                    let premise = nodes[i].premise[k];
                    if active[premise] || blocked[premise] {
                        blocked_here = true;
                    }
                }
            }
            blocked.push(blocked_here);
            if active[i] && !blocked_here {
                if !nodes[i].derived { fail(); }
                frontier.push(i);
            }
        }
        if frontier.len == 0 {
            for a in active { if a { fail(); } }
            break;
        }
        var candidates: Value[>..] = [];
        for id in frontier { candidates.push(inspect(nodes,values,id,true)); }
        // Complete frontier candidate evaluation precedes publication.
        for k in 0..frontier.len {
            let id = frontier[k];
            let candidate = candidates[k];
            active[id] = false;
            if !equal(candidate,values[id]) {
                values[id] = candidate;
                for user in id + 1..nodes.len {
                    if nodes[user].derived && uses(nodes[user],id) {
                        active[user] = true;
                    }
                }
            }
        }
        evaluations += frontier.len;
    }
    return evaluations;
}
fn show(nodes: State[:], values: Value[:]) {
    for i in 0..nodes.len {
        if values[i].kind == 0 {
            print(nodes[i].name, ": ", values[i].flag);
        } else {
            print(nodes[i].name, ": ", values[i].number);
        }
    }
}
fn main() {
    if arg_count() < 2 { fail(); }
    var path: u8[>..] = [];
    arg(1,path);
    var source: u8[>..] = [];
    if !read_file(path,source) { fail(); }
    var nodes: State[>..] = [];
    var values: Value[>..] = [];
    var active: bool[>..] = [];
    load(source,nodes,values,active);
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
