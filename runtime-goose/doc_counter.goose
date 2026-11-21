// Native-Goose arbitrary-natural two-counter recurrence proof witness.
// Instruction-table files are proof inputs, NOT a separate DOC frontend.
import std;
import os;
struct Op { kind: i64, reg: i64, next: i64, alt: i64 }
fn fail(){print("DOC_COUNTER_ERROR");exit(1);}
fn nat(raw:u8[:])->u8[>..]{
    if raw.len==0{fail();}
    var v:u8[>..]=[];
    for c in raw{if c<'0'||c>'9'{fail();}}
    var i=raw.len;
    while i>0{i--;v.push(raw[i]-'0');}
    while v.len>0&&v[v.len-1]==0{v.pop();}
    return v;
}
fn text_nat(v:u8[:])->u8[>..]{
    var out:u8[>..]=[];
    if v.len==0{out.push('0');return out;}
    var i=v.len;while i>0{i--;out.push(v[i]+'0');}
    return out;
}
fn inc(v:u8[>..]&){
    var i=0;
    while i<v.len&&v[i]==9{v[i]=0;i++;}
    if i==v.len{v.push(1);}else{v[i]++;}
}
fn dec(v:u8[>..]&){
    if v.len==0{fail();}
    var i=0;while v[i]==0{v[i]=9;i++;}
    v[i]--;
    while v.len>0&&v[v.len-1]==0{v.pop();}
}
fn register(raw:u8[:])->i64{
    if raw=="a"{return 0;}
    if raw=="b"{return 1;}
    fail();return -1;
}
fn parse(raw:u8[:],code:Op[>..]&){
    for original in split(raw,'\n'){
        var end=0;
        while end<original.len&&original[end]!='#'{end++;}
        let line=trim(original[..end]);
        if line.len==0{continue;}
        var parts:u8[..64][>..]=[];
        for fragment in split(line,' '){
            let word=trim(fragment);
            if word.len>0{parts.push(word);}
        }
        if parts.len<2{fail();}
        let id,valid=parse_int(parts[0]);
        if !valid||id!=code.len{fail();}
        if parts[1]=="halt"&&parts.len==2{
            code.push(Op{kind:2,reg:0,next:0,alt:0});
        }else if parts[1]=="inc"&&parts.len==4{
            let j,ok=parse_int(parts[3]);
            if !ok||j<0{fail();}
            code.push(Op{kind:0,reg:register(parts[2]),next:j,alt:0});
        }else if parts[1]=="decz"&&parts.len==5{
            let j,jok=parse_int(parts[3]);
            let alt,aok=parse_int(parts[4]);
            if !jok||!aok||j<0||alt<0{fail();}
            code.push(Op{kind:1,reg:register(parts[2]),next:j,alt:alt});
        }else{fail();}
    }
    if code.len==0{fail();}
    for op in code{
        if op.kind!=2&&op.next>=code.len{fail();}
        if op.kind==1&&op.alt>=code.len{fail();}
    }
}
fn main(){
    if arg_count()!=5{fail();}
    var path:u8[>..]=[];var raw_prefix:u8[>..]=[];
    var raw_a:u8[>..]=[];var raw_b:u8[>..]=[];
    arg(1,path);arg(2,raw_prefix);arg(3,raw_a);arg(4,raw_b);
    if !starts_with(raw_prefix,"--prefix=")||
       !starts_with(raw_a,"--a=")||!starts_with(raw_b,"--b="){fail();}
    let limit,ok=parse_int(raw_prefix[9..]);
    if !ok||limit<0{fail();}
    var a=nat(raw_a[4..]);var b=nat(raw_b[4..]);
    var bytes:u8[>..]=[];
    if !read_file(path,bytes){fail();}
    var code:Op[>..]=[];parse(bytes,code);
    var pc=0;var epoch=0;
    loop{
        print("epoch: ",epoch);
        print("pc: ",pc);
        print("a: ",text_nat(a));
        print("b: ",text_nat(b));
        let op=code[pc];
        if op.kind==2{print("DOC_COUNTER_HALT: ",epoch);return;}
        if epoch==limit{return;}
        if op.kind==0{
            if op.reg==0{inc(a);}else{inc(b);}
            pc=op.next;
        }else{
            let nonzero=if op.reg==0{a.len>0}else{b.len>0};
            if nonzero{
                if op.reg==0{dec(a);}else{dec(b);}
                pc=op.next;
            }else{pc=op.alt;}
        }
        epoch++;
    }
}
