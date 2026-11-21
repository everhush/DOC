//! Canonical, arbitrarily extensible nonnegative naturals for DOC.
//! Stored decimal form is deliberately simple and deterministic across hosts.
//! Resource use remains subject to the surrounding runtime's limits.
use crate::Result;
pub fn canonical(raw:&str)->Result<String>{
    if raw.is_empty() || !raw.bytes().all(|c|c.is_ascii_digit()){
        return Err("natural literal must have decimal digits".into());
    }
    let stripped=raw.trim_start_matches('0');
    Ok(if stripped.is_empty(){"0".into()}else{stripped.into()})
}
pub fn add(a:&str,b:&str)->String{
    let ab=a.as_bytes();let bb=b.as_bytes();
    let mut out=Vec::with_capacity(ab.len().max(bb.len())+1);
    let mut carry:u16=0;
    for i in 0..ab.len().max(bb.len()){
        let x=ab.len().checked_sub(i+1).map_or(0,|p|(ab[p]-b'0') as u16);
        let y=bb.len().checked_sub(i+1).map_or(0,|p|(bb[p]-b'0') as u16);
        let sum=x+y+carry;
        out.push(b'0'+(sum%10) as u8);
        carry=sum/10;
    }
    if carry>0{out.push(b'0'+carry as u8);}
    out.reverse();
    String::from_utf8(out).expect("all digits are ASCII")
}
pub fn sub(a:&str,b:&str)->Result<String>{
    if a.len()<b.len() || (a.len()==b.len()&&a<b){
        return Err("natural-number underflow; no DOC publication".into());
    }
    let ab=a.as_bytes();let bb=b.as_bytes();
    let mut out=Vec::with_capacity(ab.len());let mut borrow:i16=0;
    for i in 0..ab.len(){
        let x=(ab[ab.len()-1-i]-b'0') as i16;
        let y=bb.len().checked_sub(i+1).map_or(0,|p|(bb[p]-b'0') as i16);
        let mut digit=x-y-borrow;
        if digit<0{digit+=10;borrow=1;}else{borrow=0;}
        out.push(b'0'+digit as u8);
    }
    debug_assert_eq!(borrow,0);
    while out.len()>1&&out.last()==Some(&b'0'){out.pop();}
    out.reverse();
    Ok(String::from_utf8(out).expect("all digits are ASCII"))
}
pub fn mul(a:&str,b:&str)->String{
    if a=="0"||b=="0"{return "0".into();}
    let x:Vec<_>=a.bytes().rev().map(|c|c-b'0').collect();
    let y:Vec<_>=b.bytes().rev().map(|c|c-b'0').collect();
    let mut out=vec![0u16;x.len()+y.len()];
    for (i,&xi) in x.iter().enumerate(){
        let mut carry=0u16;
        for (j,&yj) in y.iter().enumerate(){
            let t=out[i+j]+xi as u16*yj as u16+carry;
            out[i+j]=t%10;carry=t/10;
        }
        out[i+y.len()]+=carry;
    }
    while out.last()==Some(&0){out.pop();}
    out.into_iter().rev().map(|v|(b'0'+v as u8) as char).collect()
}
#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn decimal_canonical_and_edges(){
        assert_eq!(canonical("0000").unwrap(),"0");
        assert_eq!(canonical("000123").unwrap(),"123");
        assert!(canonical("-1").is_err());
        assert!(canonical("0x13").is_err());
        assert_eq!(add("999","1"),"1000");
        assert_eq!(sub("1000","1").unwrap(),"999");
        assert!(sub("0","1").is_err());
        assert_eq!(mul("123","456"),"56088");
        assert_eq!(mul("0","987654321"),"0");
    }
    #[test]fn arbitrary_decimal_exceeds_i64_without_overflow(){
        let huge="9".repeat(1000);
        let next=add(&huge,"1");
        assert_eq!(next,format!("1{}","0".repeat(1000)));
        assert_eq!(sub(&next,"1").unwrap(),huge);
        assert_eq!(mul(&next,"10"),format!("1{}","0".repeat(1001)));
    }
}
