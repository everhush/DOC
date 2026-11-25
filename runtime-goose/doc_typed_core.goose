// Independent native-Goose interpreter for the typed, finite DOC graph subset.
// Supports bool/int, type-checked conditional/equality, checked i64 arithmetic,
// private ready-frontier evaluation, source updates and exact equality cutoffs.
// Also supports bounded-value forward carry with template defaults.
import std;
import os;
namespace doc_typed;

// Growable, append-only native Goose digit arena. DOC values hold stable
// offsets rather than raw pointers; an offset stays valid after pool growth.
// Physical compaction/reclamation across protected readers is a separate gate.
var nat_pool: u8[>..];
// Each immutable int collection is an offset/length into this independently
// managed Goose pool. No C allocator, mutable DOC alias or raw pointer escapes.
var ints_pool: i64[>..];
// Offset-backed immutable UTF-8 text, with bounded storage and raw byte length.
var text_pool:u8[>..];
fn text_zero()->Value {
    return Value {kind:5,number:0,flag:false,start:0,length:0};
}
// Native-Goose strict RFC 3629 scalar UTF-8 validation, no C decoder.
// Reject overlong encodings, surrogate values and out-of-range code points.
fn utf8_valid(bytes:u8[:])->bool {
    var i=0;
    while i<bytes.len {
        let lead=bytes[i] as i64;
        if lead<128 {i++;continue;}
        let size=if lead>=194 && lead<=223 {2}
            else if lead>=224 && lead<=239 {3}
            else if lead>=240 && lead<=244 {4}
            else {return false;};
        if i+size>bytes.len {return false;}
        for j in 1..size {
            let c=bytes[i+j];
            if c<128 || c>191 {return false;}
        }
        let second=bytes[i+1];
        if (lead==224 && second<160) ||
           (lead==237 && second>=160) ||
           (lead==240 && second<144) ||
           (lead==244 && second>=144) {return false;}
        i+=size;
    }
    return true;
}

fn text_store(raw:u8[:])->Value {
    if !utf8_valid(raw) {fail();}
    if raw.len==0 {return text_zero();}
    for c in raw {if c=='"' || c=='\\' || c=='\n' || c=='\r' {fail();}}
    let start=text_pool.len;
    text_pool.append(raw);
    return Value {kind:5,number:0,flag:false,start:start,length:raw.len};
}
fn text_bytes(v:Value)->u8[>..] {
    if v.kind!=5 {fail();}
    var out:u8[>..]=[];
    for i in 0..v.length {out.push(text_pool[v.start+i]);}
    return out;
}
fn text_equal(a:Value,b:Value)->bool {
    if a.length!=b.length {return false;}
    for i in 0..a.length {
        if text_pool[a.start+i]!=text_pool[b.start+i] {return false;}
    }
    return true;
}
fn text_concat(a:Value,b:Value)->Value {
    if a.kind!=5 || b.kind!=5 || a.length>9223372036854775807-b.length {fail();}
    var out:u8[>..]=[];
    for i in 0..a.length {out.push(text_pool[a.start+i]);}
    for i in 0..b.length {out.push(text_pool[b.start+i]);}
    return text_store(out);
}
fn text_starts_with(a:Value,prefix:Value)->bool {
    if a.kind!=5 || prefix.kind!=5 {fail();}
    if prefix.length>a.length {return false;}
    for i in 0..prefix.length {
        if text_pool[a.start+i]!=text_pool[prefix.start+i] {return false;}
    }
    return true;
}

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

fn ints_zero() -> Value {
    return Value { kind: 3, number: 0, flag: false, start: 0, length: 0 };
}
fn ints_at(xs: Value, index: i64) -> i64 {
    if xs.kind != 3 || index < 0 || index >= xs.length { fail(); }
    return ints_pool[xs.start+index];
}
fn ints_store(items: i64[:]) -> Value {
    if items.len == 0 { return ints_zero(); }
    let start = ints_pool.len;
    for value in items { ints_pool.push(value); }
    return Value { kind: 3, number: 0, flag: false,
                   start: start, length: items.len };
}
fn ints_parse(raw: u8[:]) -> Value {
    if raw.len < 2 || raw[0] != '[' || raw[raw.len-1] != ']' { fail(); }
    let inner = trim(raw[1..raw.len-1]);
    if inner.len == 0 { return ints_zero(); }
    var items: i64[>..] = [];
    for part in split(inner,',') {
        let parsed, ok = parse_int(trim(part));
        if !ok { fail(); }
        items.push(parsed);
    }
    return ints_store(items);
}
fn ints_printable(xs: Value) -> u8[>..] {
    var out: u8[>..] = [];
    out.push('[');
    for i in 0..xs.length {
        if i > 0 { out.push(','); }
        format_int(out,ints_at(xs,i),10,0,' ');
    }
    out.push(']');
    return out;
}
fn ints_append(xs: Value, value: i64) -> Value {
    if xs.kind != 3 { fail(); }
    var contents: i64[>..] = [];
    for i in 0..xs.length { contents.push(ints_at(xs,i)); }
    contents.push(value);
    return ints_store(contents);
}
fn ints_tail(xs: Value) -> Value {
    if xs.kind != 3 { fail(); }
    if xs.length == 0 { return ints_zero(); }
    var contents: i64[>..] = [];
    for i in 1..xs.length { contents.push(ints_at(xs,i)); }
    return ints_store(contents);
}
fn ints_equal(a: Value, b: Value) -> bool {
    if a.length != b.length { return false; }
    for i in 0..a.length { if ints_at(a,i) != ints_at(b,i) { return false; } }
    return true;
}


// Explicit, typed, immutable failure/absence data. A failed bounds probe
// stays in the value domain and can be handled by DOC conditional logic.
fn maybe_none() -> Value {
    return Value {kind:4,number:0,flag:false,start:0,length:0};
}
fn maybe_some(number:i64) -> Value {
    return Value {kind:4,number:number,flag:true,start:0,length:0};
}
fn maybe_text(v:Value) -> u8[>..] {
    var out:u8[>..]=[];
    if !v.flag {out.append("none");}
    else {
        out.append("some(");
        format_int(out,v.number,10,0,' ');
        out.push(')');
    }
    return out;
}

fn zero(k: i64) -> Value {
    return if k == 0 { boolean(false) } else if k == 1 { integer(0) }
           else if k == 2 { nat_zero() }
           else if k == 3 { ints_zero() }
           else if k == 4 { maybe_none() } else { text_zero() };
}
fn equal(a: Value, b: Value) -> bool {
    if a.kind != b.kind { return false; }
    if a.kind == 0 { return a.flag == b.flag; }
    if a.kind == 1 { return a.number == b.number; }
    if a.kind == 2 { return nat_compare(a,b) == 0; }
    if a.kind == 3 { return ints_equal(a,b); }
    if a.kind == 5 { return text_equal(a,b); }
    return a.flag == b.flag && (!a.flag || a.number == b.number);
}
fn type_name(t: u8[:]) -> i64 {
    if t == "bool" { return 0; }
    if t == "int" { return 1; }
    if t == "nat" { return 2; }
    if t == "ints" { return 3; }
    if t == "maybe_int" { return 4; }
    if t == "text" { return 5; }
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
    } else if kind == 3 {
        return ints_parse(raw);
    } else if kind == 5 {
        if raw.len>=2 && raw[0]=='"' && raw[raw.len-1]=='"' {
            return text_store(raw[1..raw.len-1]);
        }
    } else if kind == 4 {
        if raw == "none" {return maybe_none();}
        if raw.len >= 7 && starts_with(raw,"some(") &&
           raw[raw.len-1] == ')' {
            let num,ok=parse_int(trim(raw[5..raw.len-1]));
            if ok {return maybe_some(num);}
        }
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
    if word == "text" {
        let begin=expect(s,after,'(');
        let quote=skip(s,begin);
        if quote>=s.len || s[quote]!='"' {fail();}
        var last=quote+1;
        while last<s.len && s[last]!='"' {
            if s[last]=='\n' || s[last]=='\r' || s[last]=='\\' {fail();}
            last++;
        }
        if last>=s.len {fail();}
        let close=expect(s,last+1,')');
        let content=text_store(s[quote+1..last]);
        return if execute {content} else {text_zero()},close;
    }
    if word == "nat" {
        let begin = expect(s,after,'(');
        var end_lit = begin;
        while end_lit < s.len && s[end_lit] != ')' { end_lit++; }
        if end_lit >= s.len { fail(); }
        // Validate the literal even when only typechecking an inactive branch.
        let value = nat_parse(trim(s[begin..end_lit]));
        return if execute { value } else { nat_zero() }, end_lit + 1;
    }
    if word == "empty" || word == "none" {
        let close=expect(s,after,'(');
        return if word=="empty" {ints_zero()} else {maybe_none()},
            expect(s,close,')');
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
       word != "add" && word != "sub" && word != "mul" &&
       word != "append" && word != "get" &&
       word != "len" && word != "tail" &&
       word != "some" && word != "try_get" &&
       word != "unwrap_or" &&
       word != "concat" && word != "starts_with" { fail(); }
    let open = after + 1;
    let a, next = expression(s,open,nodes,values,premises,execute,depth - 1);
    if word == "some" {
        if a.kind != 1 { fail(); }
        let close=expect(s,next,')');
        return if execute {maybe_some(a.number)} else {maybe_none()},close;
    }
    if word == "len" || word == "tail" {
        if (a.kind!=3 && a.kind!=5) || (word=="tail" && a.kind!=3) {fail();}
        let close=expect(s,next,')');
        if !execute {return zero(if word=="len" {1}else{3}),close;}
        if word=="len" {return integer(a.length),close;}
        return ints_tail(a),close;
    }
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
    if word == "append" {
        if a.kind != 3 || b.kind != 1 { fail(); }
        if !execute { return ints_zero(), close; }
        return ints_append(a,b.number),close;
    }
    if word == "get" {
        if a.kind != 3 || b.kind != 1 { fail(); }
        if !execute { return integer(0), close; }
        return integer(ints_at(a,b.number)),close;
    }
    if word == "try_get" {
        if a.kind != 3 || b.kind != 1 { fail(); }
        if !execute || b.number < 0 || b.number >= a.length {
            return maybe_none(),close;
        }
        return maybe_some(ints_at(a,b.number)),close;
    }
    if word == "unwrap_or" {
        if a.kind != 4 || b.kind != 1 { fail(); }
        return integer(if execute && a.flag { a.number } else { b.number }),close;
    }
    if word=="concat" || word=="starts_with" {
        if a.kind!=5 || b.kind!=5 {fail();}
        if !execute {return zero(if word=="concat" {5}else{0}),close;}
        if word=="concat" {return text_concat(a,b),close;}
        return boolean(text_starts_with(a,b)),close;
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
           name == "empty" || name == "append" || name == "get" ||
           name == "len" || name == "tail" ||
           name == "none" || name == "some" ||
           name == "try_get" || name == "unwrap_or" ||
           name == "text" || name == "concat" ||
           name == "starts_with" ||
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

// Lexical portable path policy. Goose stdlib currently has no exposed
// canonical-path/symlink-check primitive: this is a strong lexical check,
// not an OS-level filesystem sandbox against preexisting symlinks.
fn safe_doc_path(path: u8[:]) -> bool {
    if path.len == 0 || path.len > 256 || path[0] == '/' { return false; }
    var component_start = 0;
    for i in 0..path.len {
        let c=path[i];
        if c == '/' {
            if i == component_start { return false; }
            let component=path[component_start..i];
            if component == "." || component == ".." { return false; }
            component_start=i+1;
        } else if !((c >= 'a' && c <= 'z') ||
                    (c >= 'A' && c <= 'Z') ||
                    (c >= '0' && c <= '9') ||
                    c == '-' || c == '_' || c == '.') {
            return false;
        }
    }
    let last=path[component_start..];
    return last.len > 0 && last != "." && last != "..";
}

fn load(source: u8[:], nodes: State[>..]&, values: Value[>..]&,
        active: bool[>..]&, origin: u8[:]) {
    if !utf8_valid(source) {fail();}
    var functions: UserFn[>..] = [];
    var effects = 0;
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
            if !safe_doc_path(relative) || relative.len < 5 ||
               relative[relative.len-4..] != ".doc" { fail(); }
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
            declare_user_function(line[3..],functions,nodes);        } else if starts_with(line,"effect ") {
            // Filesystem I/O is an explicitly declared, sampled source
            // boundary, never an operation inside a pure ready frontier.
            effects++;
            if effects > 64 { fail(); }
            let rest = line[7..];
            let colon = find(rest,":");
            let assign = find(rest,"=");
            if colon <= 0 || assign <= colon { fail(); }
            let name = trim(rest[..colon]);
            if !valid_name(name) || lookup(nodes,name) >= 0 ||
               function_index(functions,name) >= 0 { fail(); }
            let kind = type_name(trim(rest[colon+1..assign]));
            let command = trim(rest[assign+1..]);
            if command.len < 8 || !starts_with(command,"read(") ||
               command[command.len-1] != ')' { fail(); }
            let quoted = trim(command[5..command.len-1]);
            if quoted.len < 3 || quoted[0] != '"' ||
               quoted[quoted.len-1] != '"' { fail(); }
            let relative = quoted[1..quoted.len-1];
            if !safe_doc_path(relative) { fail(); }
            var prefix = 0;
            for i in 0..origin.len {
                if origin[i] == '/' { prefix = i+1; }
            }
            var file_path: u8[>..] = [];
            file_path.append(origin[..prefix]);
            file_path.append(relative);
            if file_path.len > 512 { fail(); }
            var text: u8[>..] = [];
            if !read_file(file_path,text) { fail(); }
            let value=if kind==5 {text_store(trim(text))}
                else{parse_value(trim(text),kind)};
            nodes.push(State {
                name: name, expression: "", premise: [0;16],
                count: 0, kind: kind, derived: false,
            });
            values.push(value);
            active.push(false);
        } else if starts_with(line,"source ") {
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

// Goose thread programs are isolated: only copied flat Boolean tasks cross
// typed queues. The main DOC worker remains the ONLY publisher. Restrict
// worker jobs to total pure Boolean expressions: no memory-pool use and no
// potentially overflowing arithmetic in a worker's native fail-stop path.
struct ScalarJob {
    position: i64,
    node: State,
    premises: State[16],
    inputs: Value[16],
}
// A Value with kind 0 (bool) or 1 (int) is self-contained and cannot
// reference any thread-local digit, list, or UTF-8 allocation arena.
struct ScalarReply { position: i64, value: Value }
// The expression parser has already validated every operator and type
// during load() via inspect(...,false). Scan actual operation tokens (not
// arbitrary substrings of legal state names): "national" is not "nat(...)"
// and "template" is not a pooled collection operation.
fn scalar_worker_total_syntax(body:u8[:]) -> bool {
    var p=0;
    while p<body.len {
        if body[p]=='"' {return false;}
        if !ident(body[p]) {p++;continue;}
        var end=p;
        while end<body.len && ident(body[end]) {end++;}
        let token=body[p..end];
        var next=end;
        while next<body.len &&
              (body[next]==' ' || body[next]=='\t') {next++;}
        if next<body.len && body[next]=='(' {
            if token!="if" && token!="eq" && token!="lt" &&
               token!="le" && token!="add" && token!="sub" &&
               token!="mul" {
                return false;
            }
        }
        p=end;
    }
    return true;
}
fn scalar_worker_eligible(nodes: State[:], frontier: i64[:]) -> bool {
    for id in frontier {
        if !nodes[id].derived ||
           (nodes[id].kind != 0 && nodes[id].kind != 1) {
            return false;
        }
        let body = nodes[id].expression[..];
        // Reject only actual pool/partial function calls; vetted literal
        // and variable tokens are safe, even when names contain "nat"/"len".
        if !scalar_worker_total_syntax(body) {return false;}
        // Only immediate int/bool scalar inputs are sent to isolated
        // workers. Nat/ints handles reference parent thread-owned pools and
        // MUST NOT cross queues without an explicit owning deep copy.
        for k in 0..nodes[id].count {
            let kind=nodes[nodes[id].premise[k]].kind;
            if kind != 0 && kind != 1 { return false; }
        }
    }
    return true;
}
thread_fn scalar_worker() {
    loop {
        let job = qget<ScalarJob>();
        if job.position < 0 { break; }
        var local_nodes: State[>..] = [];
        var local_values: Value[>..] = [];
        var derived = job.node;
        for k in 0..derived.count {
            local_nodes.push(job.premises[k]);
            local_values.push(job.inputs[k]);
            derived.premise[k] = k;
        }
        local_nodes.push(derived);
        local_values.push(boolean(false));
        let result = inspect(local_nodes,local_values,derived.count,true);
        if result.kind != derived.kind ||
           (result.kind != 0 && result.kind != 1) { fail(); }
        qput(ScalarReply { position: job.position, value: result });
    }
}
fn evaluate_ready_frontier(nodes: State[:], values: Value[:],
                           frontier: i64[:]) -> Value[>..] {
    var candidates: Value[>..] = [];
    var setting: u8[>..] = [];
    // Hardware resource budget, not an arbitrary 4/16-worker cap.
    // At least 32 independent tasks amortize each isolated worker.
    let hardware=max(1,hardware_threads());
    var workers=hardware;
    var explicit_workers=false;
    if env("DOC_GOOSE_WORKERS",setting) {
        explicit_workers=true;
        let requested,ok=parse_int(setting);
        if !ok || requested < 1 { fail(); }
        workers=min(requested,hardware);
    }
    if frontier.len<64 || !scalar_worker_eligible(nodes,frontier) {
        for id in frontier { candidates.push(inspect(nodes,values,id,true)); }
        return candidates;
    }
    if !explicit_workers {
        // Measured on a two-logical-core Linux CI runner: 512 trivial
        // eq(a,b) definitions were 2.35x slower with two newly spawned
        // Goose workers than serial. Estimate pure expression work, not
        // just graph width. Cheap automatic frontiers stay serial;
        // substantial ones use every profitable available worker.
        // Explicit DOC_GOOSE_WORKERS still exercises worker scaling.
        // Sampling a few distributed expressions avoids an O(frontier)
        // admission walk, which itself was measured to dominate the
        // evaluation of a cheap 512-node Boolean DAG.
        let samples=min(8,frontier.len);
        var sample_cost=0;
        for sample in 0..samples {
            let index=sample*(frontier.len-1)/max(1,samples-1);
            sample_cost+=max(1,nodes[frontier[index]].expression.len/8);
        }
        let mean_cost=max(1,(sample_cost+samples-1)/samples);
        if frontier.len<2048/mean_cost {
            let estimate=frontier.len*mean_cost;
            var message:u8[>..]=[];
            format(message,"DOC_GOOSE_AUTO_FRONTIER_SEQUENTIAL: estimate=",
                   estimate," candidates=",frontier.len,
                   " hardware=",hardware,"\n");
            write_stderr(message);
            for id in frontier {
                candidates.push(inspect(nodes,values,id,true));
            }
            return candidates;
        }
    }
    workers=min(workers,max(1,frontier.len/32));
    if workers<=1 {
        for id in frontier { candidates.push(inspect(nodes,values,id,true)); }
        return candidates;
    }
    candidates.resize(frontier.len,boolean(false));
    let blank = State {
        name: "", expression: "", premise: [0;16],
        count: 0, kind: 0, derived: false,
    };
    for position in 0..frontier.len {
        let id=frontier[position];
        var task = ScalarJob {
            position: position,
            node: nodes[id],
            premises: [blank;16],
            inputs: [boolean(false);16],
        };
        for k in 0..nodes[id].count {
            let original=nodes[id].premise[k];
            task.premises[k]=nodes[original];
            task.inputs[k]=values[original];
        }
        qput(task);
    }
    for i in 0..workers {
        qput(ScalarJob {
            position: -1, node: blank, premises: [blank;16],
            inputs: [boolean(false);16],
        });
    }
    var ids: i64[>..] = [];
    for i in 0..workers { ids.push(thread_spawn(scalar_worker)); }
    var seen: bool[>..] = [];
    seen.resize(frontier.len,false);
    for i in 0..frontier.len {
        let reply = qget<ScalarReply>();
        if reply.position < 0 || reply.position >= frontier.len ||
           seen[reply.position] { fail(); }
        seen[reply.position] = true;
        let expected_kind=nodes[frontier[reply.position]].kind;
        if reply.value.kind != expected_kind { fail(); }
        candidates[reply.position]=reply.value;
    }
    for id in ids { thread_wait(id); }
    var message: u8[>..] = [];
    format(message,"DOC_GOOSE_PARALLEL_FRONTIER: workers=",workers,
           " candidates=",frontier.len," hardware=",hardware,"\n");
    write_stderr(message);
    return candidates;
}

// A single ready-frontier and atomic-publication kernel handles both full
// and ancestor-closed demanded DOC evaluation. The needed mask is readonly;
// unneeded pending nodes stay inactive for this evaluation request.
fn stabilize_masked(nodes: State[:],values: Value[:],active: bool[:],
                    needed: bool[:]) -> i64 {
    if needed.len!=nodes.len {fail();}
    var evaluations=0;
    loop {
        var blocked:bool[>..]=[];
        var frontier:i64[>..]=[];
        for i in 0..nodes.len {
            var blocked_here=false;
            if nodes[i].derived {
                for k in 0..nodes[i].count {
                    let premise=nodes[i].premise[k];
                    if active[premise] || blocked[premise] {
                        blocked_here=true;
                    }
                }
            }
            blocked.push(blocked_here);
            if active[i] && needed[i] && !blocked_here {
                if !nodes[i].derived {fail();}
                frontier.push(i);
            }
        }
        if frontier.len==0 {
            for i in 0..nodes.len {
                if active[i] && needed[i] {fail();}
            }
            break;
        }
        let candidates=evaluate_ready_frontier(nodes,values,frontier);
        // Evaluate the entire eligible frontier before any publication;
        // exact equality cutoff and deterministic successor activation remain.
        for k in 0..frontier.len {
            let id=frontier[k];
            let candidate=candidates[k];
            active[id]=false;
            if !equal(candidate,values[id]) {
                values[id]=candidate;
                for user in id+1..nodes.len {
                    if nodes[user].derived && needed[user] &&
                       uses(nodes[user],id) {
                        active[user]=true;
                    }
                }
            }
        }
        evaluations+=frontier.len;
    }
    return evaluations;
}
fn stabilize(nodes: State[:],values: Value[:],active: bool[:]) -> i64 {
    var all:bool[>..]=[];
    all.resize(nodes.len,true);
    return stabilize_masked(nodes,values,active,all);
}
// Demand only the ancestor-closed requested subgraph. Other pending
// definitions and their failures remain out of this publication.
fn stabilize_demanded(nodes: State[:],values: Value[:],active: bool[:],
                      needed: bool[:]) -> i64 {
    return stabilize_masked(nodes,values,active,needed);
}

fn show(nodes: State[:], values: Value[:]) {
    for i in 0..nodes.len {
        if values[i].kind == 0 {
            print(nodes[i].name, ": ", values[i].flag);
        } else if values[i].kind == 1 {
            print(nodes[i].name, ": ", values[i].number);
        } else if values[i].kind == 2 {
            print(nodes[i].name, ": ", nat_text(values[i]));
        } else if values[i].kind == 3 {
            print(nodes[i].name, ": ", ints_printable(values[i]));
        } else if values[i].kind==4 {
            print(nodes[i].name, ": ", maybe_text(values[i]));
        } else {
            print(nodes[i].name, ": ", text_bytes(values[i]));
        }
    }
}
// Emit the pure Boolean subset after the normal DOC loader has checked types.
// The device inputs follow the definition's declared premise order.
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

// The old ints pool remains untouched until all roots have been copied.
// Relocating the current valuation, template defaults and scheduled facts
// also permits a future list to survive ordinary finite epoch turnover.
fn relocate_ints(value: Value, fresh: i64[>..]&) -> Value {
    if value.kind != 3 || value.length == 0 { return value; }
    var moved = value;
    moved.start = fresh.len;
    for i in 0..value.length {
        fresh.push(ints_pool[value.start+i]);
    }
    return moved;
}
// Safe compaction of all committed text roots.
fn relocate_text(value:Value,fresh:u8[>..]&)->Value{
    if value.kind!=5 || value.length==0 {return value;}
    var moved=value;
    moved.start=fresh.len;
    for i in 0..value.length {fresh.push(text_pool[value.start+i]);}
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
    var fresh_ints: i64[>..] = [];
    for &value in values { value = relocate_ints(value,fresh_ints); }
    for &value in defaults { value = relocate_ints(value,fresh_ints); }
    for &fact in facts { fact.value = relocate_ints(fact.value,fresh_ints); }
    ints_pool.resize(0,0);
    ints_pool.append(fresh_ints);
    var fresh_text:u8[>..]=[];
    for &value in values {value=relocate_text(value,fresh_text);}
    for &value in defaults {value=relocate_text(value,fresh_text);}
    for &fact in facts {fact.value=relocate_text(fact.value,fresh_text);}
    text_pool.resize(0,0);
    text_pool.append(fresh_text);
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

