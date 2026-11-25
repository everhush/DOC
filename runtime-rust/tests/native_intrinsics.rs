use std::{fs,process::Command};

use doc_runtime::native_abi::NativeProgram;

#[test]
fn target_intrinsics_are_typed_total_and_fail_closed(){
    let source=concat!(
        "native intrinsic bit_count(i64) -> i64 = popcount\n",
        "native intrinsic leading(i64) -> i64 = leading_zeros\n",
        "native intrinsic trailing(i64) -> i64 = trailing_zeros\n",
        "source input: int = 0\n",
        "native call bits: int (input) = bit_count(input)\n",
        "native call lead: int (input,bits) = leading(input)\n",
        "native call tail: int (input,lead) = trailing(input)\n");
    let program=NativeProgram::parse(source,&[]).unwrap();
    let (c,h,ir)=program.emit("intrinsics").unwrap();
    assert!(ir.contains("intrinsic-call\t1\tbit_count\tbits\tint\t0\tpopcount\t0"));
    assert!(ir.contains("intrinsic-call\t2\tleading\tlead\tint\t0,1\tleading_zeros\t0"));
    assert!(ir.contains("intrinsic-call\t3\ttrailing\ttail\tint\t0,2\ttrailing_zeros\t0"));
    assert!(h.contains("int doc_export_intrinsics(int64_t in_input, struct doc_result_intrinsics *out);"));
    assert!(c.contains("__builtin_popcountll"));
    for invalid in [
        source.replace("= popcount","= unknown"),
        source.replace("bit_count(i64)","bit_count(i32)"),
        source.replace("leading(i64) -> i64","leading(i64) -> i32"),
        source.replace("native call bits: int (input) = bit_count(input)","native call bits: int (input) = missing(input)"),
        source.replace("native intrinsic trailing(i64) -> i64 = trailing_zeros\n",""),
        format!("{source}\nnative intrinsic bit_count(i64) -> i64 = popcount\n"),
    ]{assert!(NativeProgram::parse(&invalid,&[]).is_err(),"{invalid}");}
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn target_intrinsics_execute_without_external_symbols_and_preserve_output(){
    let source=concat!(
        "native intrinsic bit_count(i64) -> i64 = popcount\n",
        "native intrinsic leading(i64) -> i64 = leading_zeros\n",
        "native intrinsic trailing(i64) -> i64 = trailing_zeros\n",
        "source input: int = 0\n",
        "native call bits: int (input) = bit_count(input)\n",
        "native call lead: int (input,bits) = leading(input)\n",
        "native call tail: int (input,lead) = trailing(input)\n");
    let program=NativeProgram::parse(source,&[]).unwrap();
    let (c,h,_)=program.emit("intrinsics").unwrap();
    let root=std::env::temp_dir().join(format!("doc-intrinsic-{}",std::process::id()));
    let _=fs::remove_dir_all(&root);fs::create_dir(&root).unwrap();
    fs::write(root.join("intrinsics.c"),c).unwrap();
    fs::write(root.join("intrinsics.h"),h).unwrap();
    fs::write(root.join("check.c"),r#"
#include "intrinsics.h"
int main(void){
    struct doc_result_intrinsics r={0};
    if(!doc_export_intrinsics(0,&r)||r.s_bits!=0||r.s_lead!=64||r.s_tail!=64)return 1;
    if(!doc_export_intrinsics(-1,&r)||r.s_bits!=64||r.s_lead!=0||r.s_tail!=0)return 2;
    if(!doc_export_intrinsics(0x1001,&r)||r.s_bits!=2||r.s_lead!=51||r.s_tail!=0)return 3;
    return 0;
}
"#).unwrap();
    let out=Command::new("cc").current_dir(&root).args(["-std=c11","-O2","-Wall","-Wextra","intrinsics.c","check.c","-o","check"]).output().unwrap();
    assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));
    let undef=Command::new("nm").arg("-u").arg(root.join("check")).output().unwrap();
    assert!(undef.status.success());
    assert!(!String::from_utf8_lossy(&undef.stdout).contains("bit_count"));
    assert!(Command::new(root.join("check")).status().unwrap().success());
    let _=fs::remove_dir_all(&root);
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn external_target_intrinsic_uses_separate_authority_and_checked_typed_abi(){
    let source=concat!(
        "source input: int = 7\n",
        "source enabled: bool = true\n",
        "native intrinsic target_transform(u32,bool8) -> i32 = external(target_transform)\n",
        "native call transformed: int (input,enabled) = target_transform(input,enabled)\n",
    );
    let grant=vec!["target_transform".into()];
    let program=NativeProgram::parse_with_authority(source,&[],&[],&grant).unwrap();
    let (c,h,ir)=program.emit("external_intrinsic").unwrap();
    assert!(ir.contains("intrinsic-call\t2\ttarget_transform\ttransformed\tint\t0,1\texternal(target_transform)"));
    assert!(c.contains("doc_intrinsic_0")&&c.contains("__asm__(\"target_transform\")"));
    for invalid in [
        source.replace("external(target_transform)","external(ungranted)"),
        source.replace("target_transform(u32,bool8) -> i32","target_transform(i64) -> i32"),
        source.replace("target_transform(u32,bool8) -> i32","target_transform(u32,bool8) -> bool8"),
        source.replace("target_transform(input,enabled)","target_transform(enabled,input)"),
    ] { assert!(NativeProgram::parse_with_authority(&invalid,&[],&[],&grant).is_err(),"{invalid}"); }
    assert!(NativeProgram::parse(source,&[]).is_err());
    assert!(NativeProgram::parse(source,&grant).is_err());
    assert!(NativeProgram::parse_with_authority(source,&grant,&[],&grant).is_err());
    assert!(ir.contains("intrinsic\ttarget_transform\tu32,bool8\ti32\texternal(target_transform)\n"));
    let root=std::env::temp_dir().join(format!("doc-external-intrinsic-{}",std::process::id()));
    let _=fs::remove_dir_all(&root);fs::create_dir(&root).unwrap();
    fs::write(root.join("source.doc"),source).unwrap();
    let cli=Command::new(env!("CARGO_BIN_EXE_doc-compile"))
        .current_dir(&root)
        .args(["source.doc","--object","external_intrinsic","--emit-c","generated.c",
            "--emit-header","generated.h","--allow-native-intrinsic","target_transform","--out","generated.o"])
        .output().unwrap();
    assert!(cli.status.success(),"{}",String::from_utf8_lossy(&cli.stderr));
    assert!(root.join("generated.o").exists());
    let wrong=Command::new(env!("CARGO_BIN_EXE_doc-compile")).current_dir(&root)
        .args(["source.doc","--object","external_intrinsic","--emit-c","wrong.c","--emit-header","wrong.h","--allow-native-import","target_transform","--out","wrong.o"]).output().unwrap();
    assert!(!wrong.status.success());
    for file in ["wrong.c","wrong.h","wrong.o"]{assert!(!root.join(file).exists());}
    fs::write(root.join("external.c"),c).unwrap();
    fs::write(root.join("external.h"),h).unwrap();
    fs::write(root.join("check.c"),r#"
#include "external.h"
#include <stdint.h>
static int calls;
int32_t target_transform(uint32_t input, uint8_t enabled){ ++calls; return enabled ? (int32_t)(input + 3) : (int32_t)(input - 3); }
int main(void){
    struct doc_result_external_intrinsic r={0};
    if(!doc_export_external_intrinsic(7,1,&r)||r.s_transformed!=10||calls!=1)return 1;
    if(!doc_export_external_intrinsic(7,0,&r)||r.s_transformed!=4||calls!=2)return 2;
    if(doc_export_external_intrinsic(7,2,&r)||r.s_transformed!=4||calls!=2)return 3;
    if(doc_export_external_intrinsic(INT64_MAX,1,&r)||r.s_transformed!=4||calls!=2)return 4;
    return 0;
}
"#).unwrap();
    let out=Command::new("cc").current_dir(&root)
        .args(["-std=c11","-O2","-Wall","-Wextra","external.c","check.c","-o","check"])
        .output().unwrap();
    assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));
    assert!(Command::new(root.join("check")).status().unwrap().success());
    let _=fs::remove_dir_all(&root);
}


#[test]
fn external_intrinsic_authority_and_arity_are_checked_before_lowering(){
    let grants=vec!["target".to_owned()];
    let make=|arity:usize|{
        let types=vec!["i64";arity].join(",");
        let args=vec!["x";arity].join(",");
        format!("native intrinsic transform({types}) -> i64 = external(target)\nsource x: int = 1\nnative call result: int (x) = transform({args})\n")
    };
    let max=make(32);
    assert!(NativeProgram::parse_with_authority(&max,&[],&[],&grants).is_ok());
    let excessive=make(33);
    let error=NativeProgram::parse_with_authority(&excessive,&[],&[],&grants).unwrap_err();
    assert!(error.contains("argument resource bound"),"{error}");
    let import="native import target(i64) -> i64\nsource x: int = 1\nnative call result: int (x) = target(x)\n";
    assert!(NativeProgram::parse(import,&grants).is_ok());
    assert!(NativeProgram::parse_with_authority(import,&[],&[],&grants).is_err());
    let cleanup="native import acquire(i32) -> i32\nsource x: int = 1\nnative call acquired: int (x) = acquire(x)\nnative cleanup acquired = target\n";
    assert!(NativeProgram::parse_with_authority(cleanup,&["acquire".into()],&[],&grants).is_err());
    assert!(NativeProgram::parse_with_authority(&max,&[],&[],&["target".into(),"unused".into()]).is_err());
    assert!(NativeProgram::parse_with_authority(&max,&[],&[],&["target".into(),"target".into()]).is_err());
}
