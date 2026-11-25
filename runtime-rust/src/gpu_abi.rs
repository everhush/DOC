//! Rust-owned compiler for the documented DOC GPU ABI v1 stack contract.
//! CPU host code typechecks and validates only; selected-GPU execution
//! remains an independent wgpu shader (never a hidden CPU fallback).
use crate::{Expr,Graph,Result,StateId,Value,Type,wgsl};

#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Instruction {
    pub opcode:i32,
    pub operand:i32,
}
impl Instruction {
    fn new(opcode:i32,operand:i32)->Self{Self{opcode,operand}}
}
fn append(expr:&Expr,out:&mut Vec<Instruction>)->Result<()> {
    use Expr::*;
    match expr {
        Lit(Value::Bool(value))=>out.push(Instruction::new(2,i32::from(*value))),
        Lit(Value::Int(value))=>{
            let narrow=i32::try_from(*value)
                .map_err(|_|"DOC_GPU_UNSUPPORTED: ABI i64 literal exceeds i32")?;
            out.push(Instruction::new(2,narrow));
        }
        Arg(index)=>{
            let index=i32::try_from(*index)
                .map_err(|_|"DOC_GPU_UNSUPPORTED: ABI premise offset overflow")?;
            out.push(Instruction::new(1,index));
        }
        If(condition,yes,no)=>{
            append(condition,out)?;
            append(yes,out)?;
            append(no,out)?;
            out.push(Instruction::new(6,0));
        }
        Eq(a,b)|Lt(a,b)|Le(a,b)|Add(a,b)|Sub(a,b)|Mul(a,b)=>{
            append(a,out)?;
            append(b,out)?;
            let opcode=match expr {
                Eq(_,_)=>3,Lt(_,_)=>4,Le(_,_)=>5,
                Add(_,_)=>7,Sub(_,_)=>8,Mul(_,_)=>9,
                _=>unreachable!(),
            };
            out.push(Instruction::new(opcode,0));
        }
        _=>return Err("DOC_GPU_UNSUPPORTED: ABI scalar expression only".into()),
    }
    if out.len()>128 {
        return Err("DOC_GPU_UNSUPPORTED: ABI exceeds verified 128-instruction stack".into());
    }
    Ok(())
}
pub fn encode_derived(graph:&Graph,state_id:StateId)->Result<Vec<Instruction>> {
    // This shares a Rust parser/type admission proof with its own current
    // generated-WGSL path, not with Goose's independent frontend/encoder.
    wgsl::validate_gpu_derived(graph,state_id)?;
    let state=graph.states.get(state_id).ok_or("unknown ABI state")?;
    if !matches!(state.kind,Type::Bool|Type::Int){
        return Err("DOC_GPU_UNSUPPORTED: ABI scalar output kind required".into());
    }
    let definition=state.definition.as_ref().ok_or("ABI requires a derived state")?;
    let mut out=Vec::new();
    append(&definition.expr,&mut out)?;
    let mut height:usize=0;
    for instruction in &out {
        match instruction.opcode {
            1|2=>height=height.checked_add(1)
                .ok_or("DOC_GPU_UNSUPPORTED: ABI stack depth overflow")?,
            6 if height>=3=>height-=2,
            3..=5|7..=9 if height>=2=>height-=1,
            _=>return Err("DOC_GPU_UNSUPPORTED: ABI bad stack program".into()),
        }
        if height>128 {
            return Err("DOC_GPU_UNSUPPORTED: ABI stack depth beyond 128".into());
        }
    }
    if height!=1 {return Err("DOC_GPU_UNSUPPORTED: ABI invalid final stack".into());}
    Ok(out)
}
pub fn encode_bytes_le(instructions:&[Instruction])->Vec<u8>{
    let mut bytes=Vec::with_capacity(instructions.len().saturating_mul(8));
    for op in instructions {
        bytes.extend_from_slice(&op.opcode.to_le_bytes());
        bytes.extend_from_slice(&op.operand.to_le_bytes());
    }
    bytes
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn independently_encoded_stage_matches_versioned_pure_scalar_contract(){
        let graph=Graph::parse(concat!(
            "source choice: bool = true\n",
            "source a: int = 3\n",
            "source b: int = 1\n",
            "derive selected: int (choice,a,b) = if(choice,add(a,b),sub(a,b))\n"
        )).unwrap();
        let code=encode_derived(&graph,graph.id("selected").unwrap()).unwrap();
        let expected=[
            Instruction::new(1,0),
            Instruction::new(1,1),Instruction::new(1,2),
            Instruction::new(7,0),
            Instruction::new(1,1),Instruction::new(1,2),
            Instruction::new(8,0),Instruction::new(6,0),
        ];
        assert_eq!(code,expected);
        let packed=encode_bytes_le(&code);
        assert_eq!(packed.len(),64);
        assert_eq!(&packed[..8],&[1,0,0,0,0,0,0,0]);
        assert_eq!(&packed[24..32],&[7,0,0,0,0,0,0,0]);
    }
    #[test]
    fn abi_compiler_rejects_non_scalar_and_unproved_programs(){
        let graph=Graph::parse(concat!(
            "source a: int = 2\n",
            "derive sum: int (a) = mul(a,100000)\n"
        )).unwrap();
        assert!(encode_derived(&graph,graph.id("sum").unwrap()).is_err());
        let graph=Graph::parse(concat!(
            "source text_a: text = \"hello\"\n",
            "derive found: bool (text_a) = starts_with(text_a,text(\"he\"))\n"
        )).unwrap();
        assert!(encode_derived(&graph,graph.id("found").unwrap()).is_err());
    }
}
