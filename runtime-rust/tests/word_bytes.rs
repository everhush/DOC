use doc_runtime::{Cutoff,Graph,Runtime,Value};
const SOURCE:&str=include_str!("../examples/byte_token.doc");
#[test]
fn actual_text_token_and_byte_roundtrip(){
    for workers in [1,2,4,8]{
        let g=Graph::parse(SOURCE).unwrap();let input=g.id("input").unwrap();let number=g.id("number").unwrap();let output=g.id("output").unwrap();
        let mut r=Runtime::new(g,workers,Cutoff::Exact);
        for (s,n) in [("123",123),("",0),("0042",42),("9223372036854775807",i64::MAX)]{
            r.update(&[(input,Value::Text(s.into()))]).unwrap();r.stabilize().unwrap();
            assert_eq!(r.value(number),Some(Value::Int(n)));assert_eq!(r.value(output),Some(Value::Text(s.into())));
        }
        for s in ["12a","é","9223372036854775808"]{
            r.update(&[(input,Value::Text(s.into()))]).unwrap();assert!(r.stabilize().is_err());
            assert_eq!(r.value(number),Some(Value::Int(i64::MAX)));
        }
    }
}
#[test]
fn utf8_and_word_boundaries(){
    let source="source text_in: text = \"é🙂\"\nderive bytes: ints (text_in) = utf8_bytes(text_in)\nderive result: text (bytes) = utf8_text(bytes)\n";
    let g=Graph::parse(source).unwrap();let bytes=g.id("bytes").unwrap();let result=g.id("result").unwrap();let mut r=Runtime::new(g,2,Cutoff::Exact);
    r.stabilize().unwrap();assert_eq!(r.value(bytes),Some(Value::Ints(vec![195,169,240,159,153,130])));assert_eq!(r.value(result),Some(Value::Text("é🙂".into())));
    for s in ["[-1]","[256]","[192,128]","[237,160,128]","[240,159]"]{
        let g=Graph::parse(&format!("source xs: ints = {s}\nderive out: text (xs) = utf8_text(xs)\n")).unwrap();
        let mut r=Runtime::new(g,1,Cutoff::Exact);let before=r.snapshot();assert!(r.stabilize().is_err());assert_eq!(r.snapshot(),before);
    }
    // Use a named dummy source rather than assuming zero-premise syntax.
    let eval=|expr:&str|{let g=Graph::parse(&format!("source unused: int = 0\nderive result: int (unused) = {expr}\n")).unwrap();let mut r=Runtime::new(g,1,Cutoff::Exact);r.stabilize()?;Ok::<_,String>(r.value(1).unwrap())};
    for (e,n) in [("quot(-7,3)",-2),("rem(-7,3)",-1),("bit_and(-1,255)",255),("bit_or(4,1)",5),("bit_xor(7,3)",4),("bit_not(0)",-1),("shift_left(1,63)",i64::MIN),("shift_right(-1,1)",i64::MAX),("shift_right(-1,0)",-1)]{
        assert_eq!(eval(e).unwrap(),Value::Int(n));
    }
    for e in ["quot(1,0)","rem(-9223372036854775808,-1)","quot(-9223372036854775808,-1)","shift_left(1,64)","shift_right(1,-1)"]{assert!(eval(e).is_err());}
}
