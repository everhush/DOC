// First independently implemented Goose DOC source evaluator slice.
// Scope: two boolean sources, one derived boolean, prefix eq/if, no effects.
// Not a full DOC graph scheduler, recurrence, or production runtime.
import std;
import os;

fn space(c: u8) -> bool { return c == ' ' || c == '\t' || c == '\r'; }
fn skip(s: u8[:], p: i64) -> i64 {
    var i = p;
    while i < s.len && space(s[i]) { i++; }
    return i;
}
fn expect(s: u8[:], p: i64, ch: u8) -> i64, bool {
    let i = skip(s, p);
    if i >= s.len || s[i] != ch { return i, false; }
    return i + 1, true;
}
// Evaluates DOC's pure total boolean expression syntax, not Goose expressions.
// Returns (value, next byte, syntax success); no unchecked indexing.
recursive fn expr(s: u8[:], p: i64, a: bool, b: bool, depth: i64) -> bool, i64, bool {
    if depth == 0 { return false, p, false; }
    let i = skip(s, p);
    var end = i;
    while end < s.len && ((s[end] >= 'a' && s[end] <= 'z') || s[end] == '_') {
        end++;
    }
    if end == i { return false, i, false; }
    let word = s[i..end];
    let after = skip(s, end);
    if word == "true" { return true, after, true; }
    if word == "false" { return false, after, true; }
    if word == "a" { return a, after, true; }
    if word == "b" { return b, after, true; }
    if word != "eq" && word != "if" { return false, after, false; }
    let open, ok = expect(s, after, '(');
    if !ok { return false, open, false; }
    let x, xend, xok = expr(s, open, a, b, depth - 1);
    if !xok { return false, xend, false; }
    let comma, cok = expect(s, xend, ',');
    if !cok { return false, comma, false; }
    let y, yend, yok = expr(s, comma, a, b, depth - 1);
    if !yok { return false, yend, false; }
    if word == "eq" {
        let close, done = expect(s, yend, ')');
        return x == y, close, done;
    }
    let comma2, cok2 = expect(s, yend, ',');
    if !cok2 { return false, comma2, false; }
    let z, zend, zok = expr(s, comma2, a, b, depth - 1);
    if !zok { return false, zend, false; }
    let close, done = expect(s, zend, ')');
    return if x { y } else { z }, close, done;
}
fn fail() { print("DOC_GOOSE_ERROR"); exit(1); }
fn main() {
    if arg_count() != 4 { fail(); }
    var path: u8[>..] = [];
    arg(1, path);
    var raw_a: u8[>..] = [];
    var raw_b: u8[>..] = [];
    arg(2, raw_a);
    arg(3, raw_b);
    if (raw_a != "true" && raw_a != "false") ||
       (raw_b != "true" && raw_b != "false") { fail(); }
    let a = raw_a == "true";
    let b = raw_b == "true";
    var source: u8[>..] = [];
    if !read_file(path, source) { fail(); }
    var count_a = 0;
    var count_b = 0;
    var count_derive = 0;
    var answer = false;
    for line in split(source, '\n') {
        let body = trim(line);
        if body.len == 0 || body[0] == '#' { continue; }
        if starts_with(body, "source a: bool = ") {
            if count_a != 0 { fail(); }
            let initial = trim(body[17..]);
            if initial != "true" && initial != "false" { fail(); }
            count_a++;
        } else if starts_with(body, "source b: bool = ") {
            if count_b != 0 { fail(); }
            let initial = trim(body[17..]);
            if initial != "true" && initial != "false" { fail(); }
            count_b++;
        } else if starts_with(body, "derive chosen: bool (a,b) = ") {
            if count_derive != 0 || count_a != 1 || count_b != 1 { fail(); }
            let expression = trim(body[28..]);
            let result, end, ok = expr(expression, 0, a, b, 128);
            if !ok || skip(expression, end) != expression.len { fail(); }
            answer = result;
            count_derive++;
        } else { fail(); }
    }
    if count_a != 1 || count_b != 1 || count_derive != 1 { fail(); }
    print("DOC_GOOSE_RESULT=", answer);
}
