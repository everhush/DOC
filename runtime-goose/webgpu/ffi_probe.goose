// Standalone Goose FFI ABI/ownership probe. This program does not dispatch
// a GPU, claim device access or evaluate DOC on C. It must build and run
// without SDL3, Goose gfx or the Rust DOC evaluator.
import std;
extern "doc_gpu_ffi_probe" {
    fn doc_gpu_probe_abi_version() -> i32;
    fn doc_gpu_probe_copy(src:const i32&,dst:i32&,count:i32)->i32;
}
fn main() {
    if doc_gpu_probe_abi_version()!=1 {fail();}
    let original:i32[4]=[0,-1,2147483647,-2147483647];
    var result:i32[4]=[9,9,9,9];
    if doc_gpu_probe_copy(original[0],result[0],4)!=4 {fail();}
    for i in 0..4 {if result[i]!=original[i] {fail();}}
    let untouched:i32[4]=[23,23,23,23];
    for i in 0..4 {result[i]=untouched[i];}
    if doc_gpu_probe_copy(original[0],result[0],-1)!=-1 {fail();}
    for i in 0..4 {if result[i]!=23 {fail();}}
    print("DOC_GOOSE_WEBGPU_FFI_ABI_ONLY_PASS: 4 words, rejected invalid length");
}
