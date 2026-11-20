// Independent Goose implementation of a bounded, typed Boolean DOC DAG.
// Supports named sources, topologically ordered derived states, repeated
// premises, multiple ready definitions, atomic candidate evaluation,
// same-value cutoff and source-batch repair. Not a general-purpose runtime.
// Explicit prototype limits: Boolean values, 16 premises per definition,
// prior-declaration-only dependencies and no effects or recurrence.
import std;
import os;

struct Node {
    name_begin: i64, name_end: i64,
    expr_begin: i64, expr_end: i64,
    dependencies: i64[16], dep_count: i64,
    derived: bool, value: bool, candidate: bool,
    current: bool, active: bool, ready: bool, updated: bool
}

fn space(c: u8) -> bool { return c == ' ' || c == '\t' || c == '\r'; }
fn ident(c: u8) -> bool {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}
fn skip(s: u8[:], p: i64) -> i64 {
    var i = p;
    while i < s.len && space(s[i]) { i++; }
    return i;
}
fn word_end(s: u8[:], p: i64) -> i64 {
    var i = p;
    while i < s.len && ident(s[i]) { i++; }
    return i;
}
fn expect(s: u8[:], p: i64, ch: u8) -> i64, bool {
    let i = skip(s, p);
    if i >= s.len || s[i] != ch { return i, false; }
    return i + 1, true;
}
fn lookup(src: u8[:], ns: Node[:], name: u8[:]) -> i64 {
    var i = 0;
    while i < ns.len {
        if src[ns[i].name_begin..ns[i].name_end] == name { return i; }
        i++;
    }
    return -1;
}
fn allowed(deps: i64[:], id: i64) -> bool {
    for d in deps { if d == id { return true; } }
    return false;
}

// DOC expression evaluation reads ONLY the settled pre-frontier values.
// Lexical references must be declared in the ordered premise list.
recursive fn expr(s: u8[:], p: i64, src: u8[:], ns: Node[:],
                  deps: i64[:], depth: i64) -> bool, i64, bool {
    if depth == 0 { return false, p, false; }
    let begin = skip(s, p);
    let end = word_end(s, begin);
    if end == begin { return false, begin, false; }
    let token = s[begin..end];
    let after = skip(s, end);
    if token == "true" { return true, after, true; }
    if token == "false" { return false, after, true; }
    if token != "eq" && token != "if" {
        let id = lookup(src, ns, token);
        if id < 0 || !allowed(deps, id) || !ns[id].current || ns[id].active {
            return false, after, false;
        }
        return ns[id].value, after, true;
    }
    let open, ok = expect(s, after, '(');
    if !ok { return false, open, false; }
    let a, ae, ao = expr(s, open, src, ns, deps, depth - 1);
    if !ao { return false, ae, false; }
    let comma, co = expect(s, ae, ',');
    if !co { return false, comma, false; }
    let b, be, bo = expr(s, comma, src, ns, deps, depth - 1);
    if !bo { return false, be, false; }
    if token == "eq" {
        let close, done = expect(s, be, ')');
        return a == b, close, done;
    }
    let next, no = expect(s, be, ',');
    if !no { return false, next, false; }
    let c, ce, c_ok = expr(s, next, src, ns, deps, depth - 1);
    if !c_ok { return false, ce, false; }
    let close, done = expect(s, ce, ')');
    return if a { b } else { c }, close, done;
}
fn fail() { print("DOC_GOOSE_ERROR"); exit(1); }

fn main() {
    if arg_count() < 2 { fail(); }
    var path: u8[>..] = [];
    arg(1, path);
    var source: u8[>..] = [];
    if !read_file(path, source) { fail(); }
    var nodes: Node[>..] = [];
    var start = 0;
    while start < source.len {
        var line_end = start;
        while line_end < source.len && source[line_end] != '\n' { line_end++; }
        var body_end = line_end;
        var comment = start;
        while comment < line_end {
            if source[comment] == '#' { body_end = comment; break; }
            comment++;
        }
        let line = source[start..body_end];
        let first = skip(line, 0);
        if first < line.len {
            var derived = false;
            var cursor = first;
            if starts_with(line[first..], "source ") {
                cursor = first + 7;
            } else if starts_with(line[first..], "derive ") {
                derived = true;
                cursor = first + 7;
            } else { fail(); }
            let nb = skip(line, cursor);
            let ne = word_end(line, nb);
            if nb == ne || (line[nb] >= '0' && line[nb] <= '9') { fail(); }
            if lookup(source, nodes, line[nb..ne]) >= 0 { fail(); }
            let colon, colon_ok = expect(line, ne, ':');
            if !colon_ok { fail(); }
            let tb = skip(line, colon);
            if tb + 4 > line.len || line[tb..tb + 4] != "bool" { fail(); }
            cursor = tb + 4;
            var node = Node {
                name_begin: start + nb, name_end: start + ne,
                expr_begin: 0, expr_end: 0,
                dependencies: [0; 16], dep_count: 0,
                derived: derived, value: false, candidate: false,
                current: !derived, active: derived, ready: false,
                updated: false
            };
            if derived {
                let open, open_ok = expect(line, cursor, '(');
                if !open_ok { fail(); }
                cursor = open;
                while true {
                    cursor = skip(line, cursor);
                    if cursor >= line.len { fail(); }
                    if line[cursor] == ')' { cursor++; break; }
                    let pe = word_end(line, cursor);
                    if pe == cursor || node.dep_count >= 16 { fail(); }
                    let id = lookup(source, nodes, line[cursor..pe]);
                    if id < 0 { fail(); }
                    node.dependencies[node.dep_count] = id;
                    node.dep_count++;
                    cursor = skip(line, pe);
                    if cursor >= line.len { fail(); }
                    if line[cursor] == ')' { cursor++; break; }
                    if line[cursor] != ',' { fail(); }
                    cursor++;
                }
                let eq, eq_ok = expect(line, cursor, '=');
                if !eq_ok || skip(line, eq) == line.len { fail(); }
                node.expr_begin = start + eq;
                node.expr_end = body_end;
            } else {
                let eq, eq_ok = expect(line, cursor, '=');
                if !eq_ok { fail(); }
                let value = trim(line[eq..]);
                if value != "true" && value != "false" { fail(); }
                node.value = value == "true";
            }
            nodes.push(node);
        }
        start = line_end + 1;
    }
    if nodes.len == 0 { fail(); }

    // Validate the WHOLE source-update batch before changing any source.
    var update_arg = 2;
    while update_arg < arg_count() {
        var assignment: u8[>..] = [];
        arg(update_arg, assignment);
        var eq = 0;
        while eq < assignment.len && assignment[eq] != '=' { eq++; }
        if eq == 0 || eq >= assignment.len { fail(); }
        let id = lookup(source, nodes, assignment[..eq]);
        if id < 0 || nodes[id].derived || nodes[id].updated { fail(); }
        let value = assignment[eq + 1..];
        if value != "true" && value != "false" { fail(); }
        nodes[id].updated = true;
        nodes[id].candidate = value == "true";
        update_arg++;
    }
    var i = 0;
    while i < nodes.len {
        if !nodes[i].derived && nodes[i].updated {
            let changed = nodes[i].value != nodes[i].candidate;
            nodes[i].value = nodes[i].candidate;
            if changed {
                var j = 0;
                while j < nodes.len {
                    var k = 0;
                    while k < nodes[j].dep_count {
                        if nodes[j].dependencies[k] == i { nodes[j].active = true; }
                        k++;
                    }
                    j++;
                }
            }
        }
        i++;
    }

    // One private evaluation phase followed by one publication phase per
    // dependency-minimal frontier. Dependency order is not textual scheduling.
    while true {
        var active_count = 0;
        var ready_count = 0;
        i = 0;
        while i < nodes.len {
            nodes[i].ready = false;
            if nodes[i].derived && nodes[i].active {
                active_count++;
                var blocked = false;
                var k = 0;
                while k < nodes[i].dep_count {
                    if nodes[nodes[i].dependencies[k]].active { blocked = true; }
                    k++;
                }
                if !blocked { nodes[i].ready = true; ready_count++; }
            }
            i++;
        }
        if active_count == 0 { break; }
        if ready_count == 0 { fail(); }
        i = 0;
        while i < nodes.len {
            if nodes[i].ready {
                let expression = source[nodes[i].expr_begin..nodes[i].expr_end];
                let dependencies = nodes[i].dependencies[..nodes[i].dep_count];
                let candidate, end, ok = expr(expression, 0, source, nodes, dependencies, 128);
                if !ok || skip(expression, end) != expression.len { fail(); }
                nodes[i].candidate = candidate;
            }
            i++;
        }
        i = 0;
        while i < nodes.len {
            if nodes[i].ready {
                let changed = !nodes[i].current || nodes[i].value != nodes[i].candidate;
                nodes[i].value = nodes[i].candidate;
                nodes[i].current = true;
                nodes[i].active = false;
                nodes[i].ready = false;
                if changed {
                    var j = 0;
                    while j < nodes.len {
                        var k = 0;
                        while k < nodes[j].dep_count {
                            if nodes[j].dependencies[k] == i { nodes[j].active = true; }
                            k++;
                        }
                        j++;
                    }
                }
            }
            i++;
        }
    }
    i = 0;
    while i < nodes.len {
        if !nodes[i].current || nodes[i].active { fail(); }
        print(source[nodes[i].name_begin..nodes[i].name_end], ": ", nodes[i].value);
        i++;
    }
}
