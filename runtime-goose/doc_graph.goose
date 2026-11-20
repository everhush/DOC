// Native Goose prototype: finite Boolean dependency DAG and exact-cutoff repair.
// Uses topological declarations, dependency-minimal ready frontiers and batch publication.
// No recurrence, arbitrary types, concurrent execution, or physical GC claims.
import std;
import os;

struct Node {
    name: u8[..64],
    expression: u8[..512],
    premise: i64[16],
    count: i64,
    derived: bool,
}
fn fail() { print("DOC_GOOSE_GRAPH_ERROR"); exit(1); }
fn identifier_char(c: u8) -> bool {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}
fn valid_name(s: u8[:]) -> bool {
    if s.len == 0 || s.len > 64 { return false; }
    if s[0] >= '0' && s[0] <= '9' { return false; }
    for c in s { if !identifier_char(c) { return false; } }
    return s != "true" && s != "false" && s != "eq" && s != "if";
}
fn lookup(nodes: Node[:], name: u8[:]) -> i64 {
    for i in 0..nodes.len { if nodes[i].name == name { return i; } }
    return -1;
}
fn uses(node: Node&, id: i64) -> bool {
    for i in 0..node.count { if node.premise[i] == id { return true; } }
    return false;
}
fn skip(s: u8[:], p: i64) -> i64 {
    var i = p;
    while i < s.len && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r') { i++; }
    return i;
}
fn expect(s: u8[:], p: i64, c: u8) -> i64, bool {
    let i = skip(s, p);
    if i >= s.len || s[i] != c { return i, false; }
    return i + 1, true;
}
// All identifiers must appear in the definition's explicit premise sequence.
recursive fn expr(s: u8[:], p: i64, nodes: Node[:], values: bool[:],
                  premises: i64[:], depth: i64) -> bool, i64, bool {
    if depth == 0 { return false, p, false; }
    let i = skip(s, p);
    var end = i;
    while end < s.len && identifier_char(s[end]) { end++; }
    if end == i { return false, i, false; }
    let word = s[i..end];
    let after = skip(s, end);
    if word == "true" { return true, after, true; }
    if word == "false" { return false, after, true; }
    if word != "eq" && word != "if" {
        let id = lookup(nodes, word);
        if id < 0 { return false, after, false; }
        var allowed = false;
        for premise in premises { if premise == id { allowed = true; } }
        if !allowed { return false, after, false; }
        return values[id], after, true;
    }
    let open, ok = expect(s, after, '(');
    if !ok { return false, open, false; }
    let a, aend, aok = expr(s, open, nodes, values, premises, depth - 1);
    if !aok { return false, aend, false; }
    let comma, cok = expect(s, aend, ',');
    if !cok { return false, comma, false; }
    let b, bend, bok = expr(s, comma, nodes, values, premises, depth - 1);
    if !bok { return false, bend, false; }
    if word == "eq" {
        let close, done = expect(s, bend, ')');
        return a == b, close, done;
    }
    let comma2, cok2 = expect(s, bend, ',');
    if !cok2 { return false, comma2, false; }
    let c, cend, valid = expr(s, comma2, nodes, values, premises, depth - 1);
    if !valid { return false, cend, false; }
    let close, done = expect(s, cend, ')');
    return if a { b } else { c }, close, done;
}
fn evaluate(nodes: Node[:], values: bool[:], id: i64) -> bool {
    let s = nodes[id].expression[..];
    let deps = nodes[id].premise[..nodes[id].count];
    let result, end, ok = expr(s, 0, nodes, values, deps, 128);
    if !ok || skip(s, end) != s.len { fail(); }
    return result;
}
// Evaluate every dependency-minimal ready node privately against one settled
// pre-valuation, then publish the full frontier. Serial evaluation is a valid
// schedule here; independent worker execution remains a later implementation.
fn stabilize(nodes: Node[:], values: bool[:], active: bool[:]) -> i64 {
    var evaluations = 0;
    loop {
        // Because declarations are topological, predecessor ancestry is known
        // before inspecting a node, including active transitive ancestors whose
        // immediate children are presently inactive.
        var blocked: bool[>..] = [];
        var frontier: i64[>..] = [];
        for i in 0..nodes.len {
            var has_active_ancestor = false;
            if nodes[i].derived {
                for k in 0..nodes[i].count {
                    let premise = nodes[i].premise[k];
                    if active[premise] || blocked[premise] {
                        has_active_ancestor = true;
                    }
                }
            }
            blocked.push(has_active_ancestor);
            if active[i] && !has_active_ancestor {
                if !nodes[i].derived { fail(); }
                frontier.push(i);
            }
        }
        if frontier.len == 0 {
            // Do not silently report stability if an illegal active state
            // or dependency cycle somehow escaped validation.
            for v in active { if v { fail(); } }
            break;
        }
        var candidates: bool[>..] = [];
        for id in frontier {
            candidates.push(evaluate(nodes, values, id));
        }
        // All candidates succeeded; no new logical value was published above.
        for k in 0..frontier.len {
            let id = frontier[k];
            let candidate = candidates[k];
            active[id] = false;
            if candidate != values[id] {
                values[id] = candidate;
                for j in id + 1..nodes.len {
                    if nodes[j].derived && uses(nodes[j], id) {
                        active[j] = true;
                    }
                }
            }
        }
        evaluations += frontier.len;
    }
    return evaluations;
}
fn update(nodes: Node[:], values: bool[:], active: bool[:],
          name: u8[:], value: bool) {
    let id = lookup(nodes, name);
    if id < 0 || nodes[id].derived { fail(); }
    if values[id] == value { return; }
    values[id] = value;
    for j in 0..nodes.len {
        if nodes[j].derived && uses(nodes[j], id) { active[j] = true; }
    }
}
fn load(src: u8[:], nodes: Node[>..]&, values: bool[>..]&, active: bool[>..]&) {
    for original in split(src, '\n') {
        var comment = 0;
        while comment < original.len && original[comment] != '#' { comment++; }
        let line = trim(original[..comment]);
        if line.len == 0 { continue; }
        if starts_with(line, "source ") {
            let text = line[7..];
            let sep = find(text, ": bool = ");
            if sep <= 0 { fail(); }
            let name = trim(text[..sep]);
            let value = trim(text[sep + 9..]);
            if !valid_name(name) || lookup(nodes, name) >= 0 { fail(); }
            if value != "true" && value != "false" { fail(); }
            nodes.push(Node {
                name: name, expression: "", premise: [0; 16],
                count: 0, derived: false,
            });
            values.push(value == "true");
            active.push(false);
        } else if starts_with(line, "derive ") {
            let text = line[7..];
            let sep = find(text, ": bool (");
            if sep <= 0 { fail(); }
            let tail = text[sep + 8..];
            let close = find(tail, ") = ");
            if close < 0 { fail(); }
            let name = trim(text[..sep]);
            let parameters = trim(tail[..close]);
            let body = trim(tail[close + 4..]);
            if !valid_name(name) || lookup(nodes, name) >= 0 ||
               body.len == 0 || body.len > 512 { fail(); }
            var node = Node {
                name: name, expression: body, premise: [0; 16],
                count: 0, derived: true,
            };
            if parameters.len > 0 {
                for part in split(parameters, ',') {
                    let pname = trim(part);
                    let dep = lookup(nodes, pname);
                    if dep < 0 || node.count >= 16 { fail(); }
                    for k in 0..node.count {
                        if node.premise[k] == dep { fail(); }
                    }
                    node.premise[node.count] = dep;
                    node.count++;
                }
            }
            nodes.push(node);
            values.push(false);
            active.push(true);
        } else { fail(); }
    }
    if nodes.len == 0 { fail(); }
}
fn argument_boolean(i: i64) -> bool {
    var raw: u8[>..] = [];
    arg(i, raw);
    if raw != "true" && raw != "false" { fail(); }
    return raw == "true";
}
fn output(nodes: Node[:], values: bool[:]) {
    for i in 0..nodes.len { print(nodes[i].name, ": ", values[i]); }
}
fn main() {
    if arg_count() != 4 && arg_count() != 6 { fail(); }
    var path: u8[>..] = [];
    arg(1, path);
    let a = argument_boolean(2);
    let b = argument_boolean(3);
    var raw: u8[>..] = [];
    if !read_file(path, raw) { fail(); }
    var nodes: Node[>..] = [];
    var values: bool[>..] = [];
    var active: bool[>..] = [];
    load(raw, nodes, values, active);
    update(nodes, values, active, "a", a);
    update(nodes, values, active, "b", b);
    let first = stabilize(nodes, values, active);
    output(nodes, values);
    print("DOC_GOOSE_EVALUATIONS=", first);
    if arg_count() == 6 {
        let next_a = argument_boolean(4);
        let next_b = argument_boolean(5);
        update(nodes, values, active, "a", next_a);
        update(nodes, values, active, "b", next_b);
        let second = stabilize(nodes, values, active);
        print("DOC_GOOSE_NEXT");
        output(nodes, values);
        print("DOC_GOOSE_EVALUATIONS=", second);
    }
}
