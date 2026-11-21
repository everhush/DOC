//! Proof witness, not an alternate DOC grammar: arbitrary-natural two-counter
//! machine under finite demanded prefixes, implemented independently in Rust.
use std::{env,fs};
#[derive(Clone)]
struct Nat(Vec<u8>); // little-endian decimal, zero = empty
impl Nat {
    fn parse(s:&str)->Result<Self,String>{
        if s.is_empty()||!s.bytes().all(|c|c.is_ascii_digit()){
            return Err("invalid natural".into());
        }
        let mut v:Vec<u8>=s.bytes().rev().map(|c|c-b'0').collect();
        while v.last()==Some(&0){v.pop();}
        Ok(Self(v))
    }
    fn zero(&self)->bool{self.0.is_empty()}
    fn inc(&mut self){
        let mut i=0;
        while i<self.0.len()&&self.0[i]==9{self.0[i]=0;i+=1;}
        if i==self.0.len(){self.0.push(1);}else{self.0[i]+=1;}
    }
    fn dec(&mut self)->Result<(),String>{
        if self.zero(){return Err("underflow".into());}
        let mut i=0;
        while self.0[i]==0{self.0[i]=9;i+=1;}
        self.0[i]-=1;
        while self.0.last()==Some(&0){self.0.pop();}
        Ok(())
    }
}
impl std::fmt::Display for Nat{
    fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result{
        if self.zero(){return write!(f,"0");}
        for &d in self.0.iter().rev(){write!(f,"{d}")?;}
        Ok(())
    }
}
#[derive(Clone,Copy)]
enum Ins{Inc{r:usize,j:usize},Decz{r:usize,n:usize,z:usize},Halt}
fn reg(s:&str)->Result<usize,String>{
    match s{"a"=>Ok(0),"b"=>Ok(1),_=>Err("invalid register".into())}
}
fn parse(src:&str)->Result<Vec<Ins>,String>{
    let mut code=Vec::new();
    for original in src.lines(){
        let line=original.split('#').next().unwrap_or("").trim();
        if line.is_empty(){continue;}
        let p:Vec<_>=line.split_whitespace().collect();
        if p.len()<2||p[0].parse::<usize>().ok()!=Some(code.len()){
            return Err("bad instruction index".into());
        }
        let inst=match (p[1],p.len()){
            ("halt",2)=>Ins::Halt,
            ("inc",4)=>Ins::Inc{r:reg(p[2])?,j:p[3].parse().map_err(|_|"bad jump")?},
            ("decz",5)=>Ins::Decz{r:reg(p[2])?,
                n:p[3].parse().map_err(|_|"bad jump")?,
                z:p[4].parse().map_err(|_|"bad jump")?},
            _=>return Err("bad instruction".into())
        };
        code.push(inst);
    }
    if code.is_empty(){return Err("empty program".into());}
    for op in &code{
        match *op{
            Ins::Inc{j,..} if j>=code.len()=>return Err("bad jump".into()),
            Ins::Decz{n,z,..} if n>=code.len()||z>=code.len()=>return Err("bad jump".into()),
            _=>()
        }
    }
    Ok(code)
}
fn run()->Result<(),String>{
    let a:Vec<_>=env::args().collect();
    if a.len()!=5{return Err("usage: doc_counter FILE --prefix=N --a=NAT --b=NAT".into());}
    let program=parse(&fs::read_to_string(&a[1]).map_err(|e|e.to_string())?)?;
    let limit=a[2].strip_prefix("--prefix=").ok_or("missing --prefix")?
        .parse::<u64>().map_err(|_|"invalid prefix")?;
    let mut vals=[
        Nat::parse(a[3].strip_prefix("--a=").ok_or("missing --a")?)?,
        Nat::parse(a[4].strip_prefix("--b=").ok_or("missing --b")?)?
    ];
    let mut pc=0usize;let mut epoch=0u64;
    loop{
        println!("epoch: {epoch}\npc: {pc}\na: {}\nb: {}",vals[0],vals[1]);
        match program[pc]{
            Ins::Halt=>{println!("DOC_COUNTER_HALT: {epoch}");return Ok(());},
            _ if epoch==limit=>return Ok(()),
            Ins::Inc{r,j}=>{vals[r].inc();pc=j;}
            Ins::Decz{r,n,z}=>{
                if vals[r].zero(){pc=z;}else{vals[r].dec()?;pc=n;}
            }
        }
        epoch=epoch.checked_add(1).ok_or("epoch overflow")?;
    }
}
fn main(){
    if let Err(e)=run(){eprintln!("DOC_COUNTER_ERROR: {e}");std::process::exit(1);}
}
#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn arbitrary_precision_carry_borrow(){
        for n in [1,18,19,80,1000]{
            let s="9".repeat(n);let mut x=Nat::parse(&s).unwrap();
            x.inc();assert_eq!(x.to_string(),format!("1{}","0".repeat(n)));
            x.dec().unwrap();assert_eq!(x.to_string(),s);
        }
    }
    #[test]fn malformed_programs_are_rejected(){
        assert!(parse("0 inc a 10\n1 halt\n").is_err());
        assert!(parse("0 inc c 0\n").is_err());
        assert!(Nat::parse("-1").is_err());
        assert!(Nat::parse("0").unwrap().dec().is_err());
    }
}
