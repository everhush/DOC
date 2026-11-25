// DOC GPU execution on SDL3, completely owned by native Goose.
//
// GPU device, buffers, dispatch, readback and shaders all flow through
// Goose's upstream SDL3 gfx package. embed_shader compiles one small static
// operation kernel for the Linux SDL3 Vulkan backend. No DOC WGSL
// generator, Rust host, C/C++ DOC shim, or backend-specific source exists.
//
// The CPU oracle is the actual native Goose DOC evaluator imported as a
// module, not a second manually written DOC interpreter.
// Only explicitly matched, pure eligible definitions may use this kernel.
import std;
import os;
import gfx;
import .doc_typed_core;

struct Params { count: u32, operation: u32, pad 8 }

fn reject(reason: u8[:]) {
    print("DOC_GOOSE_SDL3_ERROR: ",reason);
    exit(1);
}
fn signed_word(value: i64) -> i32 {
    if value < -2147483648 || value > 2147483647 {
        reject("DOC i64 exceeds SDL3 portable shader i32");
    }
    return value as! i32;
}
fn pair(lane: i64, epoch: i64, boolean_mode: bool) -> i64, i64 {
    if boolean_mode {
        var a = if lane % 3 == 0 { 1 } else { 0 };
        var b = if lane % 5 < 2 { 1 } else { 0 };
        if epoch == 1 {
            if lane % 2 == 0 { a = 1-a; }
            if lane % 7 == 1 { b = 1-b; }
        }
        return a,b;
    }
    var a = if lane % 9 == 0 { -2147483648 }
        else if lane % 9 == 1 { 2147483647 }
        else if lane % 9 == 2 { -1 }
        else if lane % 9 == 3 { 0 }
        else if lane % 9 == 4 { 1 }
        else if lane % 9 == 5 { 5 }
        else if lane % 9 == 6 { -934 }
        else if lane % 9 == 7 { 65536 }
        else { -19000 };
    if epoch == 1 {
        if lane % 3 == 0 { a = 0; }
        else if lane % 3 == 2 {
            if a == -2147483648 { a = 2147483647; }
            else { a = -a; }
        }
    }
    let b = if lane % 4 == 0 { a }
        else if lane % 4 == 1 {
            if a == 2147483647 { -1 } else { a+1 }
        } else if lane % 4 == 2 {
            if a == -2147483648 { 1 } else { a-1 }
        } else {
            if a == -2147483648 { 2147483647 } else { -a }
        };
    return a,b;
}

// Source-program GPU evaluator. This is native Goose + SDL3: no Rust bridge.
// It accepts any finite pure DOC graph whose derived states have Boolean
// values expressible through premises, constants, eq, lt, le and if.
// The shader interprets the program-defined stack bytecode on the GPU; the
// host handles parsing, dependency ordering and typed i32 admission only.
struct GpuInstruction { opcode:i32, operand:i32 }
// One std430 ivec4 of metadata per independently computed GPU state.
struct GpuStage {offset:i32,length:i32,input_start:i32,kind:i32}
struct GpuCarry { source:i64, previous:i64 }
struct GpuEpochFact { epoch:i64, source:i64, value:doc_typed::Value }

fn gpu_reject(reason:u8[:]) {
    print("DOC_GOOSE_SELECTED_GPU_ERROR: ",reason);
    exit(1);
}

fn gpu_compile(node:doc_typed::State,nodes:doc_typed::State[:],
               code:GpuInstruction[>..]&) {
    let expression=node.expression[..];
    let start_code=code.len;
    var operator_stack:i32[>..]=[];
    var i=0;
    var depth=0;
    var height=0;
    var arithmetic_ops=0;
    var wide_literal=false;
    var oversized_nested_literal=false;
    while i<expression.len {
        let c=expression[i];
        if c==' ' || c=='\r' || c=='\t' || c==',' {
            i++;
            continue;
        }
        if c==')' {
            if operator_stack.len==0 || depth==0 {
                gpu_reject("unbalanced GPU expression");
            }
            let opcode=operator_stack[operator_stack.len-1];
            operator_stack.resize(operator_stack.len-1,0);
            if opcode==6 {
                if height<3 {gpu_reject("GPU conditional stack underflow");}
                height-=2;
            } else {
                if height<2 {gpu_reject("GPU comparison stack underflow");}
                height--;
            }
            code.push(GpuInstruction {opcode:opcode,operand:0});
            depth--;
            i++;
            continue;
        }
        var end=i;
        if expression[end]=='-' {end++;}
        while end<expression.len && doc_typed::ident(expression[end]) {end++;}
        if end==i {gpu_reject("GPU opcode syntax not eligible");}
        let word=expression[i..end];
        let after=doc_typed::skip(expression,end);
        if after<expression.len && expression[after]=='(' {
            let opcode:i32=if word=="eq" {3}
                else if word=="lt" {4}
                else if word=="le" {5}
                else if word=="if" {6}
                else if word=="add" {7}
                else if word=="sub" {8}
                else if word=="mul" {9}
                else {gpu_reject("unsupported GPU derived expression operation"); 0};
            if opcode>=7 && opcode<=9 {
                arithmetic_ops++;
                // 2..12 total operators with all integer leaves in [-4,4]
                // are bounded by 4^13 under +,-,*; no signed i32 overflow.
                // The host checks runtime premises before each dispatch.
                if arithmetic_ops>12 {
                    gpu_reject("GPU arithmetic exceeds proved operation bound");
                }
            }
            operator_stack.push(opcode);
            depth++;
            i=after+1;
            continue;
        }
        let opcode:i32;
        var operand:i32=0;
        if word=="true" {
            opcode=2;operand=1;
        } else if word=="false" {
            opcode=2;
        } else {
            let value,number=parse_int(word);
            if number {
                opcode=2;
                operand=signed_word(value);
                if value< -32767 || value>32767 {wide_literal=true;}
                if value< -4 || value>4 {oversized_nested_literal=true;}
            } else {
                opcode=1;
                var position=-1;
                for k in 0..node.count {
                    if nodes[node.premise[k]].name==word {position=k;}
                }
                if position<0 {gpu_reject("GPU premise not in declared dependencies");}
                operand=position as! i32;
            }
        }
        code.push(GpuInstruction {opcode:opcode,operand:operand});
        height++;
        // The stack/program cap belongs to ONE authored expression, not
        // the cumulative bytecode of an entire independent GPU frontier.
        if code.len-start_code>128 || height>128 {
            gpu_reject("GPU expression exceeds per-state stack limits");
        }
        i=end;
    }
    if depth!=0 || operator_stack.len!=0 || height!=1 || code.len==0 {
        gpu_reject("GPU expression cannot be lowered to one value");
    }
    if arithmetic_ops>0 && wide_literal {
        gpu_reject("GPU arithmetic literals must fit conservative signed range");
    }
    if arithmetic_ops>1 && oversized_nested_literal {
        gpu_reject("nested GPU arithmetic literals exceed proved small range");
    }
}

fn gpu_source_program() {
    var path:u8[>..]=[];
    arg(1,path);
    var backend:u8[>..]=[];
    var first_arg=2;
    // A bare FILE.doc, or FILE.doc source=value, must default to CPU.
    // Explicit --backend=gpu remains strict; no automatic GPU placement.
    if arg_count()>=3 {
        var selected:u8[>..]=[];
        arg(2,selected);
        if starts_with(selected,"--backend=") {
            backend.append(selected);
            first_arg=3;
        }
    }
    if backend.len==0 {backend.append("--backend=cpu");}
    if backend!="--backend=gpu" && backend!="--backend=cpu" {
        gpu_reject("expected --backend=cpu or --backend=gpu (no auto mode)");
    }
    var source:u8[>..]=[];
    if !read_file(path,source) {gpu_reject("DOC source cannot be read");}
    if backend=="--backend=gpu" {
        // Strict mode: reject potential effects BEFORE load() opens any files.
        // Library functions that have already been expanded are pure.
        for raw in split(source,'\n') {
            let line=trim(raw);
            if starts_with(line,"effect ") || starts_with(line,"import ") {
                gpu_reject("GPU source effects and imports are not supported");
            }
        }
    }
    var nodes:doc_typed::State[>..]=[];
    var values:doc_typed::Value[>..]=[];
    var active:bool[>..]=[];
    doc_typed::load(source,nodes,values,active,path);
    // The same DOC file may be run on either CPU or selected native GPU
    // through bounded stable epochs. CPU mode delegates to its independent
    // native recurrence evaluator; GPU mode dispatches ALL derived nodes on
    // SDL3 Vulkan for each epoch, with host-only source carry/fact transport.
    var recurrent=false;
    var end_epoch=0;
    var halt_id=-1;
    if arg_count()>first_arg {
        var mode:u8[>..]=[];
        arg(first_arg,mode);
        if starts_with(mode,"--through=") {
            let cap,ok=parse_int(mode[10..]);
            if !ok || cap<0 {gpu_reject("invalid GPU recurrence epoch limit");}
            recurrent=true;
            end_epoch=cap;
            first_arg++;
        } else if starts_with(mode,"--until=") {
            if arg_count()<=first_arg+1 {
                gpu_reject("GPU --until requires --max-epochs=N");
            }
            var raw_cap:u8[>..]=[];
            arg(first_arg+1,raw_cap);
            if !starts_with(raw_cap,"--max-epochs=") {
                gpu_reject("GPU --until requires --max-epochs=N");
            }
            let cap,ok=parse_int(raw_cap[13..]);
            halt_id=doc_typed::lookup(nodes,mode[8..]);
            if !ok || cap<0 || halt_id<0 || nodes[halt_id].kind!=0 {
                gpu_reject("invalid GPU recurrence halt predicate or epoch cap");
            }
            recurrent=true;
            end_epoch=cap;
            first_arg+=2;
        }
    }
    if recurrent && backend=="--backend=cpu" {
        doc_typed::run_recurrence(nodes,values,active,end_epoch,halt_id,first_arg);
        return;
    }
    var changes:doc_typed::Change[>..]=[];
    var gpu_carry:GpuCarry[>..]=[];
    var gpu_facts:GpuEpochFact[>..]=[];
    if recurrent {
        for i in first_arg..arg_count() {
            var raw:u8[>..]=[];
            arg(i,raw);
            if starts_with(raw,"--fact=") {
                let rest=raw[7..];
                let colon=find(rest,":");
                let equal=find(rest,"=");
                if colon<=0 || equal<=colon {
                    gpu_reject("GPU epoch fact requires --fact=EPOCH:name=value");
                }
                let epoch,ok=parse_int(rest[..colon]);
                if !ok || epoch<=0 || epoch>end_epoch {
                    gpu_reject("GPU epoch fact is outside the requested successor epochs");
                }
                let source=doc_typed::lookup(nodes,rest[colon+1..equal]);
                if source<0 || nodes[source].derived {
                    gpu_reject("GPU epoch fact cannot target a derived state");
                }
                let value=doc_typed::parse_value(rest[equal+1..],nodes[source].kind);
                for old in gpu_facts {
                    if old.epoch==epoch && old.source==source {
                        gpu_reject("duplicate GPU source fact in one epoch");
                    }
                }
                gpu_facts.push(GpuEpochFact {epoch:epoch,source:source,value:value});
            } else {
                let equal=find(raw,"=");
                if equal<=0 {
                    gpu_reject("GPU recurrence needs source=previous or epoch fact");
                }
                let source=doc_typed::lookup(nodes,raw[..equal]);
                let previous=doc_typed::lookup(nodes,raw[equal+1..]);
                if source<0 || previous<0 || nodes[source].derived ||
                   nodes[source].kind!=nodes[previous].kind {
                    gpu_reject("GPU carry requires source of previous state's type");
                }
                for old in gpu_carry {
                    if old.source==source {gpu_reject("duplicate GPU carry authority");}
                }
                gpu_carry.push(GpuCarry {source:source,previous:previous});
            }
        }
        for fact in gpu_facts {
            for carried in gpu_carry {
                if fact.source==carried.source {
                    gpu_reject("GPU epoch fact conflicts with carried source");
                }
            }
        }
    } else {
        for i in first_arg..arg_count() {
            var raw:u8[>..]=[];
            arg(i,raw);
            let delimiter=find(raw,"=");
            if delimiter<=0 {gpu_reject("GPU source assignment must use name=value");}
            let id=doc_typed::lookup(nodes,trim(raw[..delimiter]));
            if id<0 || nodes[id].derived {
                gpu_reject("GPU source assignment cannot target a derived value");
            }
            for change in changes {
                if change.id==id {gpu_reject("duplicate GPU source assignment");}
            }
            let value=doc_typed::parse_value(trim(raw[delimiter+1..]),nodes[id].kind);
            changes.push(doc_typed::Change {id:id,value:value,next:false});
        }
        for change in changes {
            doc_typed::update(nodes,values,active,change.id,change.value);
        }
    }
    if backend=="--backend=cpu" {
        let executed=doc_typed::stabilize(nodes,values,active);
        doc_typed::show(nodes,values);
        print("DOC_TYPED_EVALUATIONS=",executed);
        return;
    }
    // Validate EVERY derived expression, type and input domain before opening
    // GPU resources. Derived int, arbitrary-nat, text, lists, recurrence and
    // unsafe i64->i32 conversions never cause a silent CPU fallback.
    var all_code:GpuInstruction[>..]=[];
    var offsets:i64[>..]=[];
    var lengths:i64[>..]=[];
    var count=0;
    for i in 0..nodes.len {
        let node=nodes[i];
        offsets.push(all_code.len);
        if node.kind!=0 && node.kind!=1 {
            gpu_reject("GPU graph requires portable Boolean/integer nodes");
        }
        if node.derived {
            gpu_compile(node,nodes,all_code);
            count++;
        } else if node.kind==1 {
            let _admitted=signed_word(values[i].number);
        }
        lengths.push(all_code.len-offsets[i]);
    }
    // The executable intentionally does not manufacture a GPU success for a
    // graph containing only sources and no actual GPU work.
    if count==0 {gpu_reject("GPU graph has no derived computation to dispatch");}
    let shader=embed_shader("comp","""
        layout(local_size_x=64) in;
        layout(std430, set=0, binding=0) readonly buffer Inputs { int args[]; };
        layout(std430, set=0, binding=1) readonly buffer Program { ivec2 instructions[]; };
        layout(std430, set=0, binding=2) readonly buffer Stages { ivec4 stage_info[]; };
        layout(std430, set=1, binding=0) buffer Out { uint results[]; };
        layout(set=2, binding=0) uniform Params { uint count; uint operation; };
        void main() {
            uint lane=gl_GlobalInvocationID.x;
            if (lane>=count) return;
            ivec4 stage=stage_info[lane];
            int stack[128];
            int sp=0;
            for (int pc=0;pc<stage.y;pc++) {
                ivec2 inst=instructions[stage.x+pc];
                if (inst.x==1) stack[sp++]=args[stage.z+inst.y];
                else if (inst.x==2) stack[sp++]=inst.y;
                else if (inst.x==3) {
                    int b=stack[--sp];
                    int a=stack[--sp];
                    stack[sp++]=a==b ? 1 : 0;
                } else if (inst.x==4) {
                    int b=stack[--sp];
                    int a=stack[--sp];
                    stack[sp++]=a<b ? 1 : 0;
                } else if (inst.x==5) {
                    int b=stack[--sp];
                    int a=stack[--sp];
                    stack[sp++]=a<=b ? 1 : 0;
                } else if (inst.x==6) {
                    int no=stack[--sp];
                    int yes=stack[--sp];
                    int condition=stack[--sp];
                    stack[sp++]=condition!=0 ? yes : no;
                } else if (inst.x==7) {
                    int b=stack[--sp];
                    int a=stack[--sp];
                    stack[sp++]=a+b;
                } else if (inst.x==8) {
                    int b=stack[--sp];
                    int a=stack[--sp];
                    stack[sp++]=a-b;
                } else if (inst.x==9) {
                    int b=stack[--sp];
                    int a=stack[--sp];
                    stack[sp++]=a*b;
                }
            }
            // The host proves all operands for any one arithmetic operator
            // lie in [-32767,32767], so no signed i32 overflow is reachable.
            // For integer states return exact signed bits, not Booleanized.
            results[lane]=stage.w==1 ? uint(stack[0]) :
                (stack[0]!=0 ? 1u : 0u);
        }
        """);
    if !gfx::open_headless(16,16) {
        gpu_reject("no SDL3 Vulkan GPU device; no CPU fallback");
    }
    defer gfx::close();
    if gfx::driver()!="vulkan" {
        gpu_reject("initial Linux GPU backend requires Vulkan");
    }
    print("DOC_GOOSE_SELECTED_GPU_DEVICE: backend=",gfx::driver());
    let pipeline=gfx::compute_pipeline(shader);
    var candidate:doc_typed::Value[>..]=[];
    candidate.append(values);
    var epoch=0;
    loop {
        // Compute all simultaneously ready derived nodes in one SDL3 GPU
        // dispatch; dependencies from the same frontier cannot read peers.
        var done:bool[>..]=[];
        for node in nodes {done.push(!node.derived);}
        var remaining=count;
        while remaining>0 {
            var frontier:i64[>..]=[];
            for i in 0..nodes.len {
                if done[i] {continue;}
                var ready=true;
                for k in 0..nodes[i].count {
                    if !done[nodes[i].premise[k]] {ready=false;}
                }
                if ready {frontier.push(i);}
            }
            if frontier.len==0 {
                gpu_reject("no ready GPU frontier: cycle or missing premise");
            }
            // SDL3 gfx has no hardware max-workgroup query. Enforce the
            // portable Vulkan workgroup-X safety limit, not a DOC task cap.
            let groups=(frontier.len+63)/64;
            if groups>65535 {
                gpu_reject("frontier exceeds SDL3 portable workgroup limit");
            }
            var inputs:i32[>..]=[];
            var program:GpuInstruction[>..]=[];
            var stages:GpuStage[>..]=[];
            for id in frontier {
                var arithmetic_ops=0;
                for n in offsets[id]..offsets[id]+lengths[id] {
                    if all_code[n].opcode>=7 && all_code[n].opcode<=9 {
                        arithmetic_ops++;
                    }
                }
                let input_start=inputs.len;
                for k in 0..nodes[id].count {
                    let value=candidate[nodes[id].premise[k]];
                    if value.kind==0 {
                        inputs.push(if value.flag {1}else{0});
                    } else if value.kind==1 {
                        let bound=if arithmetic_ops>1 {4} else {32767};
                        if arithmetic_ops>0 &&
                           (value.number< -bound || value.number>bound) {
                            gpu_reject("GPU arithmetic premise exceeds proved signed range");
                        }
                        inputs.push(signed_word(value.number));
                    } else {
                        gpu_reject("GPU premise is not portable scalar");
                    }
                }
                if nodes[id].count==0 {inputs.push(0);}
                let start=program.len;
                for n in offsets[id]..offsets[id]+lengths[id] {
                    program.push(all_code[n]);
                }
                stages.push(GpuStage {
                    offset:start as! i32,
                    length:(program.len-start) as! i32,
                    input_start:input_start as! i32,
                    kind:nodes[id].kind as! i32,
                });
            }
            let input_buffer=gfx::buffer(gfx::BUFFER_COMPUTE_READ,bytes_of(inputs));
            let code_buffer=gfx::buffer(gfx::BUFFER_COMPUTE_READ,bytes_of(program));
            let stage_buffer=gfx::buffer(gfx::BUFFER_COMPUTE_READ,bytes_of(stages));
            let result_buffer=gfx::buffer(gfx::BUFFER_COMPUTE_WRITE,frontier.len*4,"");
            let results:gfx::Buffer[1]=[result_buffer];
            if !gfx::begin_compute(results) {
                gpu_reject("parallel GPU frontier could not begin");
            }
            gfx::bind(pipeline);
            gfx::bind_storage_buffer(gfx::COMPUTE,0,input_buffer);
            gfx::bind_storage_buffer(gfx::COMPUTE,1,code_buffer);
            gfx::bind_storage_buffer(gfx::COMPUTE,2,stage_buffer);
            gfx::uniforms(gfx::COMPUTE,0,Params {
                count:frontier.len as! u32,operation:0});
            gfx::dispatch(groups,1,1);
            gfx::end_compute();
            var output:u32[>..]=[];
            if !gfx::read_buffer(result_buffer,output,frontier.len) ||
                output.len!=frontier.len {
                gpu_reject("parallel GPU frontier readback incomplete");
            }
            // Validate every GPU result before advancing dependencies.
            var typed:doc_typed::Value[>..]=[];
            for pos in 0..frontier.len {
                let id=frontier[pos];
                if nodes[id].kind==0 {
                    if output[pos]>1 {gpu_reject("noncanonical GPU Boolean");}
                    typed.push(doc_typed::boolean(output[pos]==1));
                } else if nodes[id].kind==1 {
                    let signed:i32=output[pos] as! i32;
                    typed.push(doc_typed::integer(signed as i64));
                } else {
                    gpu_reject("unsupported GPU derived type");
                }
            }
            for pos in 0..frontier.len {
                let id=frontier[pos];
                candidate[id]=typed[pos];
                done[id]=true;
            }
            remaining-=frontier.len;
            gfx::release(input_buffer);
            gfx::release(code_buffer);
            gfx::release(stage_buffer);
            gfx::release(result_buffer);
            print("DOC_GOOSE_GPU_FRONTIER_DISPATCH: states=",frontier.len,
                  " workgroups=",groups);
        }
        // Every epoch's candidate is privately complete before publication.
        // A failing GPU stage cannot publish a partial current epoch.
        gfx::check();
        if recurrent {print("epoch: ",epoch);}
        doc_typed::show(nodes,candidate);
        print("DOC_TYPED_EVALUATIONS=",count);
        print("DOC_GOOSE_SELECTED_DOC_GPU_PASS: ",count," GPU-dispatched states");
        if !recurrent {break;}
        if halt_id>=0 && candidate[halt_id].flag {
            print("DOC_RECURRENCE_HALT: ",epoch);
            break;
        }
        if epoch>=end_epoch {
            if halt_id>=0 {
                gpu_reject("GPU recurrence did not halt within requested epoch cap");
            }
            break;
        }
        // Preserve previous complete GPU-derived values; default sources
        // are restored for the next epoch before applying typed carries and
        // local facts. The host never computes any derived DOC expression.
        var stable:doc_typed::Value[>..]=[];
        stable.append(candidate);
        for i in 0..nodes.len {candidate[i]=values[i];}
        for binding in gpu_carry {
            candidate[binding.source]=stable[binding.previous];
        }
        for fact in gpu_facts {
            if fact.epoch==epoch+1 {candidate[fact.source]=fact.value;}
        }
        epoch++;
    }
    gfx::release(pipeline);
    gfx::check();
}
fn main() {
    // The legacy bounded operation oracle syntax is FILE.doc eq|lt|le|bool|
    // staged LANES. A normal authored DOC invocation is selected by the
    // presence of a source assignment, a backend selector, or no arguments.
    if arg_count()==2 {
        gpu_source_program();
        return;
    }
    if arg_count()>=3 {
        var maybe_backend:u8[>..]=[];
        arg(2,maybe_backend);
        if starts_with(maybe_backend,"--backend=") ||
            find(maybe_backend,"=")>=0 {
            gpu_source_program();
            return;
        }
    }

    if arg_count() < 4 || arg_count() > 5 {
        reject("usage: doc_sdl3_gpu DOC_SOURCE eq|lt|le|bool|staged LANES [--inject-wide]");
    }
    var path:u8[>..]=[];
    var operation:u8[>..]=[];
    var raw_lanes:u8[>..]=[];
    arg(1,path);arg(2,operation);arg(3,raw_lanes);
    let lanes,valid=parse_int(raw_lanes);
    // SDL3 gfx does not provide a portable device-limit enumeration API.
    // Linux Vulkan guarantees 65535 dispatch groups in X; the embedded
    // kernel uses 64 threads per group. This is a hardware/API safety bound,
    // not a DOC worker-count cap. Reject before any per-lane allocation.
    if !valid || lanes<=0 || lanes>65535*64 {
        reject("SDL3 compute lanes exceed Vulkan portable dispatch limits");
    }
    var inject_wide=false;
    if arg_count()==5 {
        var extra:u8[>..]=[];
        arg(4,extra);
        if extra!="--inject-wide" { reject("unsupported SDL3 compute option"); }
        inject_wide=true;
    }
    let bool_mode=operation=="bool" || operation=="staged";
    let op: u32 = if operation=="eq" { 0 }
        else if operation=="lt" { 1 }
        else if operation=="le" { 2 }
        else if bool_mode { 3 }
        else { reject("not a supported pure SDL3 compute operation"); 0 };
    var source:u8[>..]=[];
    if !read_file(path,source) { reject("DOC input source not readable"); }
    var nodes:doc_typed::State[>..]=[];
    var values:doc_typed::Value[>..]=[];
    var active:bool[>..]=[];
    doc_typed::load(source,nodes,values,active,path);
    let aid=doc_typed::lookup(nodes,"a");
    let bid=doc_typed::lookup(nodes,"b");
    let state_name=if operation=="eq" { "equal" }
        else if operation=="lt" { "less" }
        else if operation=="le" { "less_or_equal" }
        else { "chosen" };
    let target=doc_typed::lookup(nodes,state_name);
    let verified=doc_typed::lookup(nodes,"verified");
    if aid<0 || bid<0 || target<0 ||
       nodes[target].kind!=0 || nodes[target].count!=2 ||
       nodes[target].premise[0]!=aid || nodes[target].premise[1]!=bid {
        reject("DOC graph is not an eligible two-source pure operation");
    }
    let expected_expression=if operation=="eq" { "eq(a,b)" }
        else if operation=="lt" { "lt(a,b)" }
        else if operation=="le" { "le(a,b)" }
        else { "if(eq(a,b),true,eq(a,false))" };
    if trim(nodes[target].expression[..])!=expected_expression {
        reject("DOC expression is outside SDL3 static kernel eligibility");
    }
    if bool_mode {
        if nodes[aid].kind!=0 || nodes[bid].kind!=0 {
            reject("SDL3 Boolean kernel requires Boolean DOC premises");
        }
    } else if nodes[aid].kind!=1 || nodes[bid].kind!=1 {
        reject("SDL3 signed kernel requires integer DOC premises");
    }
    if operation=="staged" &&
       (verified<0 || nodes[verified].kind!=0 ||
        nodes[verified].count!=2 || nodes[verified].premise[0]!=target ||
        nodes[verified].premise[1]!=bid ||
        trim(nodes[verified].expression[..])!="eq(chosen,b)") {
        reject("SDL3 staged dependency is not eligible");
    }
    // The compact GLSL kernels are ordinary Goose compile-time resources.
    // The compiler packages SPIR-V, MSL and HLSL for SDL3 GPU backend choice.
    let map_shader=embed_shader("comp", """
        layout(local_size_x = 64) in;
        layout(std430, set = 0, binding = 0) readonly buffer Left { int lhs[]; };
        layout(std430, set = 0, binding = 1) readonly buffer Right { int rhs[]; };
        layout(std430, set = 1, binding = 0) buffer Out { uint flags[]; };
        layout(set = 2, binding = 0) uniform Params { uint count; uint operation; };
        void main() {
            uint i = gl_GlobalInvocationID.x;
            if (i >= count) return;
            bool result = false;
            if (operation == 0u) result = lhs[i] == rhs[i];
            else if (operation == 1u) result = lhs[i] < rhs[i];
            else if (operation == 2u) result = lhs[i] <= rhs[i];
            else if (operation == 3u) result = lhs[i] == rhs[i] || lhs[i] == 0;
            flags[i] = result ? 1u : 0u;
        }
        """);
    let reduce_shader=embed_shader("comp", """
        layout(local_size_x = 1) in;
        layout(std430, set = 0, binding = 0) readonly buffer In { uint flags[]; };
        layout(std430, set = 1, binding = 0) buffer Totals { uint total[]; };
        layout(set = 2, binding = 0) uniform Params { uint count; uint operation; };
        void main() {
            uint n = 0u;
            for (uint i = 0u; i < count; i++) n += flags[i];
            total[0] = n;
        }
        """);
    // No CPU "fallback" is allowed to claim an SDL3 GPU pass. Lack of a
    // device is a hard error, not an environment-dependent test skip.
    if !gfx::open_headless(16,16) {
        print("DOC_GOOSE_SDL3_OPEN_ERROR: ",gfx::error());
        reject("SDL3 GPU unavailable: no silent CPU fallback");
    }
    defer gfx::close();
    print("DOC_GOOSE_SDL3_DEVICE: ",gfx::driver());
    let compare_pipeline=gfx::compute_pipeline(map_shader);
    let count_pipeline=gfx::compute_pipeline(reduce_shader);
    for epoch in 0..2 {
        var aa:i32[>..]=[];
        var bb:i32[>..]=[];
        var first_expected:u32[>..]=[];
        var final_expected:u32[>..]=[];
        for lane in 0..lanes {
            let a,b=pair(lane,epoch,bool_mode);
            if inject_wide && lane==0 {
                // Negative path must fail before allocating and submitting
                // any GPU candidate, and before printing a success marker.
                let invalid=signed_word(2147483648);
                aa.push(invalid);
            }
            let a32=signed_word(a);
            let b32=signed_word(b);
            aa.push(a32);
            bb.push(b32);
            if bool_mode {
                doc_typed::update(nodes,values,active,aid,doc_typed::boolean(a!=0));
                doc_typed::update(nodes,values,active,bid,doc_typed::boolean(b!=0));
            } else {
                doc_typed::update(nodes,values,active,aid,doc_typed::integer(a));
                doc_typed::update(nodes,values,active,bid,doc_typed::integer(b));
            }
            let _evaluated=doc_typed::stabilize(nodes,values,active);
            if values[target].kind!=0 {
                reject("DOC CPU target is not Boolean");
            }
            let first=if values[target].flag { 1 as u32 } else { 0 as u32 };
            first_expected.push(first);
            if operation=="staged" {
                if values[verified].kind!=0 {
                    reject("DOC CPU staged target is not Boolean");
                }
                final_expected.push(if values[verified].flag {1 as u32}else{0 as u32});
            } else {
                final_expected.push(first);
            }
        }
        let input_a=gfx::buffer(gfx::BUFFER_COMPUTE_READ,bytes_of(aa));
        let input_b=gfx::buffer(gfx::BUFFER_COMPUTE_READ,bytes_of(bb));
        let first_buffer=gfx::buffer(
            gfx::BUFFER_COMPUTE_READ | gfx::BUFFER_COMPUTE_WRITE,lanes*4,"");
        let first_outputs:gfx::Buffer[1]=[first_buffer];
        if !gfx::begin_compute(first_outputs) {
            reject("SDL3 GPU compute pass could not begin");
        }
        gfx::bind(compare_pipeline);
        gfx::bind_storage_buffer(gfx::COMPUTE,0,input_a);
        gfx::bind_storage_buffer(gfx::COMPUTE,1,input_b);
        gfx::uniforms(gfx::COMPUTE,0,Params {count:lanes as! u32,operation:op});
        gfx::dispatch((lanes+63)/64,1,1);
        gfx::end_compute();
        var first_observed:u32[>..]=[];
        if !gfx::read_buffer(first_buffer,first_observed,lanes) ||
           first_observed!=first_expected {
            reject("SDL3 first-pass GPU/CPU DOC differential mismatch");
        }
        var final_buffer=first_buffer;
        if operation=="staged" {
            let second_buffer=gfx::buffer(
                gfx::BUFFER_COMPUTE_READ | gfx::BUFFER_COMPUTE_WRITE,lanes*4,"");
            let second_outputs:gfx::Buffer[1]=[second_buffer];
            if !gfx::begin_compute(second_outputs) {
                reject("SDL3 dependent pass could not begin");
            }
            gfx::bind(compare_pipeline);
            gfx::bind_storage_buffer(gfx::COMPUTE,0,first_buffer);
            gfx::bind_storage_buffer(gfx::COMPUTE,1,input_b);
            gfx::uniforms(gfx::COMPUTE,0,Params {count:lanes as! u32,operation:0 as u32});
            gfx::dispatch((lanes+63)/64,1,1);
            gfx::end_compute();
            final_buffer=second_buffer;
        }
        var final_observed:u32[>..]=[];
        if !gfx::read_buffer(final_buffer,final_observed,lanes) ||
           final_observed!=final_expected {
            reject("SDL3 final GPU/CPU DOC differential mismatch");
        }
        let reduce_buffer=gfx::buffer(gfx::BUFFER_COMPUTE_WRITE,4,"");
        let rw_count:gfx::Buffer[1]=[reduce_buffer];
        if !gfx::begin_compute(rw_count) {
            reject("SDL3 dependent reduction pass could not begin");
        }
        gfx::bind(count_pipeline);
        gfx::bind_storage_buffer(gfx::COMPUTE,0,final_buffer);
        gfx::uniforms(gfx::COMPUTE,0,Params {count:lanes as! u32,operation:0 as u32});
        gfx::dispatch(1,1,1);
        gfx::end_compute();
        var count:u32[>..]=[];
        if !gfx::read_buffer(reduce_buffer,count,1) || count.len!=1 {
            reject("SDL3 dependent reduction readback failed");
        }
        var expected_count:u32=0;
        for bit in final_expected { expected_count+=bit; }
        if count[0]!=expected_count {
            reject("SDL3 dependent reduction does not equal DOC CPU count");
        }
        // Publication happens AFTER both passes and their independent native
        // CPU oracle comparison have succeeded, never after partial dispatch.
        print("DOC_GOOSE_SDL3_GPU_PASS: op=",operation,
              " epoch=",epoch," lanes=",lanes," count=",count[0],
              " backend=",gfx::driver());
        gfx::release(input_a);
        gfx::release(input_b);
        gfx::release(first_buffer);
        if operation=="staged" { gfx::release(final_buffer); }
        gfx::release(reduce_buffer);
    }
    gfx::release(compare_pipeline);
    gfx::release(count_pipeline);
    gfx::check();
}
