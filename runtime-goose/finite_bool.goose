// Goose host-toolchain smoke only. This does NOT implement a DOC runtime.
// The DOC user language is independent of Goose syntax and this smoke never
// counts towards DOC paper-parity or general-purpose acceptance.
fn derived_equal(a: bool, b: bool) -> bool {
    a == b
}
fn main() {
    let source_a = true;
    let source_b = false;
    let result = derived_equal(source_a, source_b);
    if result {
        print("DOC_GOOSE_SMOKE=unexpected");
    } else {
        print("DOC_GOOSE_SMOKE=ok");
    }
}
