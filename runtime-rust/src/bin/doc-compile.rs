//! Trusted Rust bootstrap driver; its generated applications do not link Rust.
use doc_runtime::{aot::{emit_c_options,emit_scalar_object}, typed_ir::emit_typed_ir_v1, native_abi::{NativeProgram,has_native_declarations}, Graph, Result};
use std::{env, fs::{self,OpenOptions}, io::Write, path::{Path,PathBuf}, process::{self,Command}};
fn create(path:&Path,bytes:&[u8])->Result<()> {
    let mut f=OpenOptions::new().write(true).create_new(true).open(path)
        .map_err(|e|format!("cannot create {}: {e}",path.display()))?;
    f.write_all(bytes).map_err(|e|e.to_string())
}
fn run()->Result<()>{
    let mut args=env::args().skip(1);
    let file=args.next().ok_or("usage: doc-compile FILE.doc --emit-c FILE.c --out EXE [--emit-ir FILE.ir] [--freeze-startup-assets] [--game] | --object SYMBOL --emit-header FILE.h [--allow-native-import SYMBOL ...] [--allow-native-intrinsic SYMBOL ...] [--allow-native-region NAME ...]")?;
    let(mut c,mut exe,mut ir)=(None,None,None);
    let mut freeze=false;
    let mut game=false;
    let mut object=None;let mut header=None;let mut grants=Vec::new();let mut regions=Vec::new();let mut intrinsics=Vec::new();
    while let Some(flag)=args.next(){
        if flag=="--game"{if game{return Err("duplicate game host flag".into());}game=true;continue;}
        if flag=="--freeze-startup-assets"{if freeze{return Err("duplicate asset flag".into());}freeze=true;continue;}
        if flag=="--allow-native-region"{
            regions.push(args.next().ok_or("missing native region grant")?);continue;
        }
        if flag=="--allow-native-import"{
            grants.push(args.next().ok_or("missing native symbol grant")?);continue;
        }
        if flag=="--allow-native-intrinsic"{
            intrinsics.push(args.next().ok_or("missing native intrinsic grant")?);continue;
        }
        if flag=="--object"{
            if object.is_some(){return Err("duplicate object export flag".into());}
            object=Some(args.next().ok_or("missing object export symbol")?);continue;
        }
        let slot=match flag.as_str(){"--emit-c"=>&mut c,"--out"=>&mut exe,"--emit-ir"=>&mut ir,"--emit-header"=>&mut header,_=>return Err(format!("unknown compiler flag {flag}"))};
        if slot.is_some(){return Err("duplicate compiler flag".into());}
        *slot=Some(PathBuf::from(args.next().ok_or("missing output path")?));
    }
    let c=c.ok_or("missing --emit-c")?;let exe=exe.ok_or("missing --out")?;
    if c==exe||ir.as_ref().is_some_and(|p|p==&c||p==&exe)||
       header.as_ref().is_some_and(|p|p==&c||p==&exe||Some(p)==ir.as_ref()){
        return Err("outputs must differ".into());
    }
    if object.is_some()!=(header.is_some())||object.is_some()&&(game||freeze){
        return Err("DOC_OBJECT: requires --emit-header; cannot use game or frozen assets".into());
    }
    let raw=Graph::read_source_file(&file)?;
    let native=has_native_declarations(&raw)||!grants.is_empty()||!regions.is_empty()||!intrinsics.is_empty();
    let (generated,abi,typed)=if native{
        let symbol=object.as_ref().ok_or("DOC_NATIVE: requires object profile")?;
        let program=NativeProgram::parse_with_authority(&raw,&grants,&regions,&intrinsics)?;
        let (c,h,ir)=program.emit(symbol)?;(c,Some(h),ir)
    }else{
        let (graph,assets)=Graph::parse_aot_snapshot(&file,&raw,freeze)?;
        if freeze{eprintln!("DOC_AOT_FROZEN_STARTUP_ASSETS: sampled build-time source facts");}
        if !assets.is_empty(){
            if ir.is_some(){return Err("DOC_AOT_UNSUPPORTED: IR/1 describes sampled facts, not deferred effects; omit --emit-ir or explicitly freeze startup assets".into());}
            eprintln!("DOC_AOT_DEFERRED_STARTUP_ASSETS: {} declared reads",assets.len());
        }
        let (c,h)=if let Some(symbol)=&object{
            if !assets.is_empty(){return Err("DOC_OBJECT_UNSUPPORTED: startup effects".into());}
            let (c,h)=emit_scalar_object(&graph,symbol)?;(c,Some(h))
        }else{(emit_c_options(&graph,&assets,game)?,None)};
        (c,h,emit_typed_ir_v1(&graph,&[])?)
    };
    if exe.exists(){return Err("native output already exists".into());}
    create(&c,generated.as_bytes())?;
    if let (Some(path),Some(abi))=(header,abi){create(&path,abi.as_bytes())?;}
    if let Some(path)=ir{create(&path,typed.as_bytes())?;}
    let c=fs::canonicalize(&c).map_err(|e|e.to_string())?;
    let output=env::current_dir().map_err(|e|e.to_string())?.join(exe);
    let cc=env::var_os("CC").unwrap_or_else(||"cc".into());
    let mut command=Command::new(cc);
    command.args(["-std=c11","-O2","-Wall","-Wextra"]);
    if object.is_some(){command.args(["-ffreestanding","-fno-builtin","-fno-stack-protector","-c"]);}
    else{command.arg("-pthread");}
    command.args(["-x","c"]).arg(&c).arg("-o").arg(&output);
    if game{command.arg("-lm");}
    let status=command.status().map_err(|e|format!("C toolchain launch: {e}"))?;
    if !status.success(){return Err("DOC_AOT_C_COMPILER_FAILED".into());}
    let bytes=fs::metadata(output).map_err(|e|e.to_string())?.len();
    if object.is_some(){println!("DOC_OBJECT_COMPILED: c_bytes={} object_bytes={bytes}",generated.len());}
    else{println!("DOC_AOT_COMPILED: c_bytes={} executable_bytes={bytes}",generated.len());}
    Ok(())
}
fn main(){if let Err(error)=run(){eprintln!("DOC_AOT: {error}");process::exit(1);}}
