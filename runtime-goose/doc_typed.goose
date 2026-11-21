// Independent native-Goose interpreter for the typed, finite DOC graph subset.
// Supports bool/int, type-checked conditional/equality, checked i64 arithmetic,
// private ready-frontier evaluation, source updates and exact equality cutoffs.
// Also supports bounded-value forward carry with template defaults.
import std;
import os;

// Growable, append-only native Goose digit arena. DOC values hold stable
// offsets rather than raw pointers; an offset stays valid after pool growth.
// Physical compaction/reclamation across protected readers is a separate gate.
var nat_pool: u8[>..];
struct Value { kind: i64, number: i64, flag: bool, start: i64, length: i64 }
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

fn nat_zero() -> Value {
    return Value { kind: 2, number: 0, flag: false, start: 0, length: 0 };
}
fn nat_digit(v: Value, index: i64) -> i64 {
    return if index >= 0 && index < v.length {
        nat_pool[v.start + index] as i64
    } else { 0 };
}
fn nat_store(digits: u8[:]) -> Value {
    var count = digits.len;
    while count > 0 && digits[count - 1] == 0 { count--; }
    if count == 0 { return nat_zero(); }
    let start = nat_pool.len;
    for i in 0..count {
        if digits[i] > 9 { fail(); }
        nat_pool.push(digits[i]);
    }
    return Value { kind: 2, number: 0, flag: false, start: start, length: count };
}
fn nat_parse(raw: u8[:]) -> Value {
    if raw.len == 0 { fail(); }
    var digits: u8[>..] = [];
    for c in raw {
        if c < '0' || c > '9' { fail(); }
    }
    var i = raw.len;
    while i > 0 {
        i--;
        digits.push(raw[i] - '0');
    }
    return nat_store(digits);
}
fn nat_text(v: Value) -> u8[>..] {
    var out: u8[>..] = [];
    if v.length == 0 { out.push('0'); return out; }
    var i = v.length;
    while i > 0 {
        i--;
        out.push((nat_digit(v, i) as! u8) + '0');
    }
    return out;
}
fn nat_compare(a: Value, b: Value) -> i64 {
    if a.length < b.length { return -1; }
    if a.length > b.length { return 1; }
    var i = a.length;
    while i > 0 {
        i--;
        let ad = nat_digit(a, i);
        let bd = nat_digit(b, i);
        if ad < bd { return -1; }
        if ad > bd { return 1; }
    }
    return 0;
}
fn nat_add(a: Value, b: Value) -> Value {
    var digits: u8[>..] = [];
    var carry = 0;
    for i in 0..max(a.length, b.length) {
        let sum = nat_digit(a,i) + nat_digit(b,i) + carry;
        digits.push((sum % 10) as! u8);
        carry = sum / 10;
    }
    if carry > 0 { digits.push(carry as! u8); }
    return nat_store(digits);
}
fn nat_sub(a: Value, b: Value) -> Value {
    if nat_compare(a,b) < 0 { fail(); }
    var digits: u8[>..] = [];
    var borrow = 0;
    for i in 0..a.length {
        var delta = nat_digit(a,i) - nat_digit(b,i) - borrow;
        if delta < 0 { delta += 10; borrow = 1; }
        else { borrow = 0; }
        digits.push(delta as! u8);
    }
    if borrow != 0 { fail(); }
    return nat_store(digits);
}
fn nat_mul(a: Value, b: Value) -> Value {
    if a.length == 0 || b.length == 0 { return nat_zero(); }
    var digits: u8[>..] = [];
    digits.resize(a.length + b.length, 0);
    for i in 0..a.length {
        var carry = 0;
        for j in 0..b.length {
            let total = digits[i+j] as i64 +
                nat_digit(a,i) * nat_digit(b,j) + carry;
            digits[i+j] = (total % 10) as! u8;
            carry = total / 10;
        }
        let total = digits[i+b.length] as i64 + carry;
        digits[i+b.length] = total as! u8;
    }
    return nat_store(digits);
}

fn boolean(v: bool) -> Value { return Value { kind: 0, number: 0, flag: v, start: 0, length: 0 }; }
fn integer(v: i64) -> Value { return Value { kind: 1, number: v, flag: false, start: 0, length: 0 }; }
fn zero(k: i64) -> Value {
    return if k == 0 { boolean(false) } else if k == 1 { integer(0) } else { nat_zero() };
}
fn equal(a: Value, b: Value) -> bool {
    if a.kind != b.kind { return false; }
    if a.kind == 0 { return a.flag == b.flag; }
    if a.kind == 1 { return a.number == b.number; }
    return nat_compare(a,b) == 0;
}
fn type_name(t: u8[:]) -> i64 {
    if t == "bool" { return 0; }
    if t == "int" { return 1; }
    if t == "nat" { return 2; }
    fail();
    return -1;
}
fn parse_value(raw: u8[:], kind: i64) -> Value {
    if kind == 0 {
        if raw == "true" { return boolean(true); }
        if raw == "false" { return boolean(false); }
    } else if kind == 1 {
        let number, ok = parse_int(raw);
        if ok { return integer(number); }
    } else if kind == 2 {
        return nat_parse(raw);
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
    return s != "true" && s != "false";
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
    if word == "nat" {
        let begin = expect(s,after,'(');
        var end_lit = begin;
        while end_lit < s.len && s[end_lit] != ')' { end_lit++; }
        if end_lit >= s.len { fail(); }
        // Validate the literal even when only typechecking an inactive branch.
        let value = nat_parse(trim(s[begin..end_lit]));
        return if execute { value } else { nat_zero() }, end_lit + 1;
    }
    if after >= s.len || s[after] != '(' {
        let id = lookup(nodes,word);
        if id < 0 { fail(); }
        var allowed = false;
        for premise in premises { if premise == id { allowed = true; } }
        if !allowed { fail(); }
        return if execute { values[id] } else { zero(nodes[id].kind) }, after;
    }
    if word != "if" && word != "eq" && word != "lt" && word != "le" &&
       word != "add" && word != "sub" && word != "mul" { fail(); }
    let open = after + 1;
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
    if word == "lt" || word == "le" {
        if a.kind != b.kind || (a.kind != 1 && a.kind != 2) { fail(); }
        if !execute { return boolean(false), close; }
        let ordering = if a.kind == 1 {
            if a.number < b.number { -1 }
            else if a.number > b.number { 1 }
            else { 0 }
        } else { nat_compare(a,b) };
        return boolean(ordering < 0 || (word == "le" && ordering == 0)), close;
    }
    if a.kind != b.kind || (a.kind != 1 && a.kind != 2) { fail(); }
    if !execute { return zero(a.kind), close; }
    if a.kind == 2 {
        let result = if word == "add" { nat_add(a,b) }
            else if word == "sub" { nat_sub(a,b) }
            else { nat_mul(a,b) };
        return result, close;
    }
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
// Independent Goose frontend expansion of bounded, pure reusable DOC
// functions. Expansion happens before existing type-check/evaluation.
// No separate compiler, FFI call or cross-runtime dependency is involved.
struct UserFn {
    name: u8[..64],
    formals: u8[..256],
    body: u8[..512],
    count: i64,
}
fn function_index(functions: UserFn[:], name: u8[:]) -> i64 {
    for i in 0..functions.len {
        if functions[i].name == name { return i; }
    }
    return -1;
}
fn function_reserved(name: u8[:]) -> bool {
    return name == "add" || name == "sub" || name == "mul" ||
           name == "eq" || name == "lt" || name == "le" ||
           name == "nat" || name == "if" || name == "fn" ||
           name == "source" || name == "derive";
}
// Iterative expansion is required by Goose's strict scope checks: no
// growable arrays remain live across a recursive call. Each pass lowers the
// outermost user call; nested calls are expanded in subsequent passes.
// A nonterminating function cycle is rejected after a bounded number of
// passes, before source execution or publication.
fn expand_function_pass(source: u8[:], functions: UserFn[:])
    -> u8[>..], bool {
    var output: u8[>..] = [];
    var changed = false;
    var i = 0;
    while i < source.len {
        if (source[i] >= 'a' && source[i] <= 'z') ||
           (source[i] >= 'A' && source[i] <= 'Z') ||
           source[i] == '_' {
            var end = i+1;
            while end < source.len && ident(source[end]) { end++; }
            let word = source[i..end];
            let target = function_index(functions,word);
            let open = skip(source,end);
            if target >= 0 && open < source.len && source[open] == '(' {
                var arguments: u8[..512][>..] = [];
                var cursor = open+1;
                var begin = cursor;
                var nesting = 0;
                loop {
                    if cursor >= source.len { fail(); }
                    let ch = source[cursor];
                    if ch == '(' {
                        nesting++;
                    } else if ch == ')' {
                        if nesting > 0 { nesting--; }
                        else {
                            if cursor > begin {
                                let argument = trim(source[begin..cursor]);
                                if argument.len == 0 { fail(); }
                                arguments.push(argument);
                            } else if arguments.len > 0 { fail(); }
                            cursor++;
                            break;
                        }
                    } else if ch == ',' && nesting == 0 {
                        let argument = trim(source[begin..cursor]);
                        if argument.len == 0 { fail(); }
                        arguments.push(argument);
                        begin = cursor+1;
                    }
                    cursor++;
                }
                let user_function = functions[target];
                if arguments.len != user_function.count { fail(); }
                let body = user_function.body[..];
                var p = 0;
                while p < body.len {
                    if (body[p] >= 'a' && body[p] <= 'z') ||
                       (body[p] >= 'A' && body[p] <= 'Z') ||
                       body[p] == '_' {
                        var next = p+1;
                        while next < body.len && ident(body[next]) { next++; }
                        let name = body[p..next];
                        var matched = false;
                        var idx = 0;
                        if user_function.count > 0 {
                            for formal in split(user_function.formals[..],',') {
                                if trim(formal) == name {
                                    output.append(arguments[idx]);
                                    matched = true;
                                    break;
                                }
                                idx++;
                            }
                        }
                        if !matched { output.append(name); }
                        p = next;
                    } else {
                        output.push(body[p]);
                        p++;
                    }
                }
                i = cursor;
                changed = true;
            } else {
                output.append(word);
                i = end;
            }
        } else {
            output.push(source[i]);
            i++;
        }
        if output.len > 512 { fail(); }
    }
    return output, changed;
}
fn expand_function_calls(source: u8[:],functions: UserFn[:],
                         depth: i64) -> u8[>..] {
    if depth != 0 || source.len > 512 { fail(); }
    var current: u8[>..] = [];
    current.append(source);
    for pass in 0..33 {
        let next, changed = expand_function_pass(current,functions);
        if !changed { return next; }
        current.resize(0,0);
        current.append(next);
    }
    fail();
    return current;
}

// Pure function module registration; import is a compile-time filesystem
// operation, not an effect inside dependency computation.
fn declare_user_function(rest: u8[:],functions: UserFn[>..]&,
                         nodes: State[:]) {
    let assign = find(rest,"=");
    if assign < 0 || functions.len >= 64 { fail(); }
    let signature = trim(rest[..assign]);
    let open = find(signature,"(");
    if open <= 0 || signature[signature.len-1] != ')' { fail(); }
    let name = trim(signature[..open]);
    if !valid_name(name) || function_reserved(name) ||
       lookup(nodes,name) >= 0 || function_index(functions,name) >= 0 {
        fail();
    }
    let formals = trim(signature[open+1..signature.len-1]);
    if formals.len > 256 { fail(); }
    var count = 0;
    if formals.len > 0 {
        for part in split(formals,',') {
            let formal = trim(part);
            if !valid_name(formal) || function_reserved(formal) ||
               count >= 4 { fail(); }
            var i = 0;
            for previous in split(formals,',') {
                if i >= count { break; }
                if trim(previous) == formal { fail(); }
                i++;
            }
            count++;
        }
    }
    let body = trim(rest[assign+1..]);
    if body.len == 0 || body.len > 512 { fail(); }
    functions.push(UserFn {
        name: name, formals: formals, body: body, count: count,
    });
}

fn load(source: u8[:], nodes: State[>..]&, values: Value[>..]&,
        active: bool[>..]&, origin: u8[:]) {
    var functions: UserFn[>..] = [];
    for original in split(source,'\n') {
        var n = 0;
        while n < original.len && original[n] != '#' { n++; }
        let line = trim(original[..n]);
        if line.len == 0 { continue; }
        if starts_with(line,"import ") {
            // Single-level, function-only module imports relative to this
            // source file. We reject transitive imports and side-effectful
            // module declarations instead of silently changing semantics.
            let relative = trim(line[7..]);
            if relative.len < 5 || relative.len > 256 ||
               relative[0] == '/' ||
               relative[relative.len-4..] != ".doc" { fail(); }
            for c in relative {
                if c == ' ' || c == '\t' || c == '\r' { fail(); }
            }
            var prefix = 0;
            for i in 0..origin.len {
                if origin[i] == '/' { prefix = i+1; }
            }
            var module_path: u8[>..] = [];
            module_path.append(origin[..prefix]);
            module_path.append(relative);
            if module_path.len > 512 { fail(); }
            var module_source: u8[>..] = [];
            if !read_file(module_path,module_source) ||
               module_source.len > 65536 { fail(); }
            for original_module in split(module_source,'\n') {
                var last = 0;
                while last < original_module.len &&
                      original_module[last] != '#' { last++; }
                let declaration = trim(original_module[..last]);
                if declaration.len == 0 { continue; }
                if !starts_with(declaration,"fn ") { fail(); }
                declare_user_function(declaration[3..],functions,nodes);
            }
        } else if starts_with(line,"fn ") {
            declare_user_function(line[3..],functions,nodes);        } else if starts_with(line,"source ") {
            let rest = line[7..];
            let colon = find(rest,":");
            let assign = find(rest,"=");
            if colon <= 0 || assign <= colon { fail(); }
            let name = trim(rest[..colon]);
            if !valid_name(name) || lookup(nodes,name) >= 0 ||
               function_index(functions,name) >= 0 { fail(); }
            let kind = type_name(trim(rest[colon + 1..assign]));
            let value = parse_value(trim(rest[assign + 1..]),kind);
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
            let assign = find(rest,"=");
            if colon <= 0 || open <= colon || assign <= open { fail(); }
            let signature = trim_end(rest[..assign]);
            if signature[signature.len - 1] != ')' { fail(); }
            let close = signature.len - 1;
            let name = trim(rest[..colon]);
            if !valid_name(name) || lookup(nodes,name) >= 0 ||
               function_index(functions,name) >= 0 { fail(); }
            let kind = type_name(trim(rest[colon + 1..open]));
            let body = trim(rest[assign + 1..]);
            if body.len == 0 || body.len > 512 { fail(); }
            let expanded = expand_function_calls(body,functions,0);
            var node = State {
                name: name, expression: expanded, premise: [0;16],
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
// Evaluate only the ancestor-closed subgraph selected by `needed`.
// Unrelated pending values and even unrelated overflowing definitions stay
// unmaterialized. This is a legal subset schedule of the finite DOC kernel.
fn stabilize_demanded(nodes: State[:], values: Value[:], active: bool[:],
                      needed: bool[:]) -> i64 {
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
            if active[i] && needed[i] && !blocked_here {
                if !nodes[i].derived { fail(); }
                frontier.push(i);
            }
        }
        if frontier.len == 0 {
            for i in 0..nodes.len { if active[i] && needed[i] { fail(); } }
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
                    if nodes[user].derived && needed[user] && uses(nodes[user],id) {
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
        } else if values[i].kind == 1 {
            print(nodes[i].name, ": ", values[i].number);
        } else {
            print(nodes[i].name, ": ", nat_text(values[i]));
        }
    }
}
// Emit the pure Boolean subset after the normal DOC loader has checked types.
// The device inputs follow the definition's declared premise order.
fn shader_index(out: u8[>..]&, index: i64) {
    format_int(out,index,10,0,' ');
}
fn shader_ref(out: u8[>..]&, index: i64) {
    out.append("t");
    shader_index(out,index);
}
fn shader_let(out: u8[>..]&, index: i64) {
    out.append("  let ");
    shader_ref(out,index);
    out.append(": bool = ");
}
recursive fn shader_expr(s: u8[:], p: i64, nodes: State[:], premises: i64[:],
                         out: u8[>..]&, depth: i64) -> i64 {
    if depth == 0 { fail(); }
    let start = skip(s,p);
    var end = start;
    while end < s.len && ident(s[end]) { end++; }
    if end == start { fail(); }
    let word = s[start..end];
    let after = skip(s,end);
    if after >= s.len || s[after] != '(' {
        shader_let(out,start);
        if word == "true" || word == "false" {
            out.append(word);
            out.append(";\n");
            return after;
        }
        for i in 0..premises.len {
            if nodes[premises[i]].name == word {
                out.append("a");
                shader_index(out,i);
                out.append(";\n");
                return after;
            }
        }
        fail();
    }
    if word != "eq" && word != "if" { fail(); }
    let first = skip(s,after + 1);
    let first_end = shader_expr(s,first,nodes,premises,out,depth - 1);
    let second = skip(s,expect(s,first_end,','));
    let second_end = shader_expr(s,second,nodes,premises,out,depth - 1);
    if word == "eq" {
        shader_let(out,start);
        shader_ref(out,first);
        out.append(" == ");
        shader_ref(out,second);
        out.append(";\n");
        return expect(s,second_end,')');
    }
    let third = skip(s,expect(s,second_end,','));
    let third_end = shader_expr(s,third,nodes,premises,out,depth - 1);
    shader_let(out,start);
    out.append("select(");
    shader_ref(out,third);
    out.append(", ");
    shader_ref(out,second);
    out.append(", ");
    shader_ref(out,first);
    out.append(");\n");
    return expect(s,third_end,')');
}
// The only eligible signed-DOC-i64 GPU operation is equality between two
// host-validated i32 premises. A CPU/transport boundary must reject every
// source outside the i32 range; arbitrary i64 arithmetic remains CPU-only.
fn emit_signed_equality(nodes: State[:], node: State, path: u8[:]) {
    if node.count != 2 { fail(); }
    let lhs = node.premise[0];
    let rhs = node.premise[1];
    if nodes[lhs].kind != 1 || nodes[rhs].kind != 1 { fail(); }
    let raw = trim(node.expression[..]);
    if raw.len < 6 || raw[raw.len - 1] != ')' { fail(); }
    let comparator = if starts_with(raw,"eq(") { "==" }
        else if starts_with(raw,"lt(") { "<" }
        else if starts_with(raw,"le(") { "<=" }
        else { fail(); "==" };
    let operands = raw[3..raw.len - 1];
    let comma = find(operands,",");
    if comma <= 0 { fail(); }
    let a = trim(operands[..comma]);
    let b = trim(operands[comma + 1..]);
    // Reject nested/partial arithmetic and unknown identifiers. Equality is
    // symmetric, but premises retain their authored order in the bindings.
    let forwards = a == nodes[lhs].name && b == nodes[rhs].name;
    let reversed = a == nodes[rhs].name && b == nodes[lhs].name;
    if !forwards && !reversed { fail(); }
    var out: u8[>..] = [];
    out.append("struct Storage { data: array<u32>, }\n");
    out.append("@group(0) @binding(0) var<storage, read> input_0: Storage;\n");
    out.append("@group(0) @binding(1) var<storage, read> input_1: Storage;\n");
    out.append("@group(0) @binding(2) var<storage, read_write> result: Storage;\n");
    out.append("@compute @workgroup_size(64)\n");
    out.append("fn main(@builtin(global_invocation_id) gid: vec3<u32>) {\n");
    out.append("  let idx: u32 = gid.x;\n");
    out.append("  if (idx >= arrayLength(&result.data)) { return; }\n");
    out.append("  if (idx >= arrayLength(&input_0.data)) { return; }\n");
    out.append("  if (idx >= arrayLength(&input_1.data)) { return; }\n");
    out.append("  let a0: i32 = bitcast<i32>(input_0.data[idx]);\n");
    out.append("  let a1: i32 = bitcast<i32>(input_1.data[idx]);\n");
    out.append("  result.data[idx] = select(0u, 1u, ");
    if reversed && !forwards { out.append("a1 "); }
    else { out.append("a0 "); }
    out.append(comparator);
    if reversed && !forwards { out.append(" a0);\n}\n"); }
    else { out.append(" a1);\n}\n"); }
    if !write_file_atomic(path,out) { fail(); }
}

fn emit_shader(nodes: State[:], target: u8[:], path: u8[:]) {
    let id = lookup(nodes,target);
    if id < 0 { fail(); }
    let node = nodes[id];
    if !node.derived || node.kind != 0 || node.count > 4 { fail(); }
    if node.count == 2 && nodes[node.premise[0]].kind == 1 &&
       nodes[node.premise[1]].kind == 1 {
        emit_signed_equality(nodes,node,path);
        return;
    }
    let premises = node.premise[..node.count];
    var out: u8[>..] = [];
    out.append("struct Storage { data: array<u32>, }\n");
    for i in 0..node.count {
        if nodes[premises[i]].kind != 0 { fail(); }
        out.append("@group(0) @binding(");
        shader_index(out,i);
        out.append(") var<storage, read> input_");
        shader_index(out,i);
        out.append(": Storage;\n");
    }
    out.append("@group(0) @binding(");
    shader_index(out,node.count);
    out.append(") var<storage, read_write> result: Storage;\n");
    out.append("@compute @workgroup_size(64)\n");
    out.append("fn main(@builtin(global_invocation_id) gid: vec3<u32>) {\n");
    out.append("  let idx: u32 = gid.x;\n");
    out.append("  if (idx >= arrayLength(&result.data)) { return; }\n");
    for i in 0..node.count {
        out.append("  if (idx >= arrayLength(&input_");
        shader_index(out,i);
        out.append(".data)) { return; }\n  let a");
        shader_index(out,i);
        out.append(": bool = input_");
        shader_index(out,i);
        out.append(".data[idx] != 0u;\n");
    }
    let body = node.expression[..];
    let end = shader_expr(body,0,nodes,premises,out,128);
    if skip(body,end) != body.len { fail(); }
    out.append("  result.data[idx] = select(0u, 1u, ");
    shader_ref(out,skip(body,0));
    out.append(");\n}\n");
    if !write_file_atomic(path,out) { fail(); }
}

struct Carry { source: i64, previous: i64 }
struct EpochFact { epoch: i64, source: i64, value: Value }

// Compact the Goose digit arena after each completed epoch. These are the
// only roots of the printed/forward-carry recurrence path: the committed
// valuation, immutable source defaults and future epoch-local facts.
// Copy all live digits first; overwrite/release the previous arena only
// after every root has been relocated. No GC, RC or C runtime is involved.
// Candidate scratch is reset from defaults before its next use.
fn relocate_nat(value: Value, fresh: u8[>..]&) -> Value {
    if value.kind != 2 || value.length == 0 { return value; }
    var moved = value;
    moved.start = fresh.len;
    for i in 0..value.length {
        fresh.push(nat_pool[value.start + i]);
    }
    return moved;
}
fn compact_nat_roots(values: Value[:], defaults: Value[:],
                     facts: EpochFact[:]) {
    var fresh: u8[>..] = [];
    for &value in values { value = relocate_nat(value, fresh); }
    for &value in defaults { value = relocate_nat(value, fresh); }
    for &fact in facts { fact.value = relocate_nat(fact.value, fresh); }
    // A Goose growable array lives on its own data stack. Shrinking its
    // logical extent and copying the packed roots reclaims obsolete digits.
    nat_pool.resize(0, 0);
    nat_pool.append(fresh);
}

fn run_recurrence(nodes: State[:], values: Value[:], active: bool[:],
                  limit: i64, halt: i64, first_binding_arg: i64) {
    var carry: Carry[>..] = [];
    var facts: EpochFact[>..] = [];
    if halt >= 0 && (halt >= nodes.len || nodes[halt].kind != 0) { fail(); }
    for i in first_binding_arg..arg_count() {
        var raw: u8[>..] = [];
        arg(i,raw);
        if starts_with(raw,"--fact=") {
            let rest = raw[7..];
            let colon = find(rest,":");
            let assign = find(rest,"=");
            if colon <= 0 || assign <= colon { fail(); }
            let epoch, ok = parse_int(rest[..colon]);
            if !ok || epoch <= 0 || epoch > limit { fail(); }
            let source = lookup(nodes,rest[colon + 1..assign]);
            if source < 0 || nodes[source].derived { fail(); }
            let value = parse_value(rest[assign + 1..],nodes[source].kind);
            for old in facts {
                if old.epoch == epoch && old.source == source { fail(); }
            }
            facts.push(EpochFact { epoch: epoch, source: source, value: value });
        } else {
            let assign = find(raw,"=");
            if assign <= 0 { fail(); }
            let source = lookup(nodes,raw[..assign]);
            let previous = lookup(nodes,raw[assign + 1..]);
            if source < 0 || previous < 0 || nodes[source].derived ||
               nodes[source].kind != nodes[previous].kind { fail(); }
            for old in carry { if old.source == source { fail(); } }
            carry.push(Carry { source: source, previous: previous });
        }
    }
    for fact in facts {
        for binding in carry {
            if fact.source == binding.source { fail(); }
        }
    }
    var defaults: Value[>..] = [];
    defaults.append(values);
    var candidate: Value[>..] = [];
    candidate.append(defaults);
    let _initial = stabilize(nodes,values,active);
    var epoch = 0;
    loop {
        print("epoch: ",epoch);
        show(nodes,values);
        if halt >= 0 && values[halt].flag {
            print("DOC_RECURRENCE_HALT: ", epoch);
            return;
        }
        if epoch == limit {
            if halt >= 0 { fail(); }
            return;
        }
        for i in 0..nodes.len {
            candidate[i] = defaults[i];
            active[i] = nodes[i].derived;
        }
        for binding in carry { candidate[binding.source] = values[binding.previous]; }
        for fact in facts {
            if fact.epoch == epoch + 1 { candidate[fact.source] = fact.value; }
        }
        let _checked = stabilize(nodes,candidate,active);
        for i in 0..nodes.len { values[i] = candidate[i]; }
        compact_nat_roots(values, defaults, facts);
        epoch++;
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
    load(source,nodes,values,active,path);
    if arg_count() >= 3 {
        var mode: u8[>..] = [];
        arg(2,mode);
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
            } else {
                print(nodes[target].name, ": ", nat_text(values[target]));
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
        if mode == "--emit-wgsl" {
            if arg_count() != 5 { fail(); }
            var target: u8[>..] = [];
            var output: u8[>..] = [];
            arg(3,target);
            arg(4,output);
            emit_shader(nodes,target,output);
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
