//! Exact signed 64-bit arithmetic and 64-bit bit patterns, plus explicit
//! lossless UTF-8/byte-list conversion. No implicit native memory access.
use crate::{Result,Value};
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum WordOp{Quot,Rem,And,Or,Xor,Shl,Shr}
impl WordOp{
    pub fn parse(name:&str)->Option<Self>{Some(match name{
        "quot"=>Self::Quot,"rem"=>Self::Rem,"bit_and"=>Self::And,"bit_or"=>Self::Or,
        "bit_xor"=>Self::Xor,"shift_left"=>Self::Shl,"shift_right"=>Self::Shr,_=>return None,
    })}
    pub fn name(self)->&'static str{match self{
        Self::Quot=>"quot",Self::Rem=>"rem",Self::And=>"bit_and",Self::Or=>"bit_or",
        Self::Xor=>"bit_xor",Self::Shl=>"shift_left",Self::Shr=>"shift_right",
    }}
    pub fn eval(self,x:i64,y:i64)->Result<i64>{
        match self{
            Self::Quot=>x.checked_div(y).ok_or_else(||"DOC_WORD: invalid signed quotient".into()),
            Self::Rem=>x.checked_rem(y).ok_or_else(||"DOC_WORD: invalid signed remainder".into()),
            Self::And=>Ok(x&y),Self::Or=>Ok(x|y),Self::Xor=>Ok(x^y),
            Self::Shl|Self::Shr=>{
                if !(0..64).contains(&y){return Err("DOC_WORD: shift count outside 0..63".into());}
                Ok(if self==Self::Shl{((x as u64)<<(y as u32)) as i64}else{((x as u64)>>(y as u32)) as i64})
            }
        }
    }
}
pub const MAX_BYTES:usize=65536;
pub(crate) fn utf8_bytes(v:Value)->Result<Value>{
    let Value::Text(s)=v else{return Err("DOC_BYTES: text required".into())};
    if s.len()>MAX_BYTES{return Err("DOC_BYTES: byte resource bound".into());}
    Ok(Value::Ints(s.bytes().map(i64::from).collect()))
}
pub(crate) fn utf8_text(v:Value)->Result<Value>{
    let Value::Ints(xs)=v else{return Err("DOC_BYTES: ints required".into())};
    if xs.len()>MAX_BYTES{return Err("DOC_BYTES: byte resource bound".into());}
    let bytes=xs.into_iter().map(|n|u8::try_from(n).map_err(|_|"DOC_BYTES: value outside 0..255".to_owned())).collect::<Result<Vec<_>>>()?;
    String::from_utf8(bytes).map(Value::Text).map_err(|_|"DOC_BYTES: invalid UTF-8".into())
}
