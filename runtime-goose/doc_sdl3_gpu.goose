// DOC GPU execution on SDL3, completely owned by native Goose.
//
// GPU device, buffers, dispatch, readback and shaders all flow through
// Goose's upstream SDL3 gfx package. embed_shader compiles one small static
// operation kernel for Vulkan, Metal and D3D12 at BUILD time. No DOC WGSL
// generator, Rust host, C/C++ DOC shim, or backend-specific source exists.
//
// The CPU oracle is the actual native Goose DOC evaluator imported as a
// module, not a second manually written DOC interpreter.
// Only explicitly matched, pure eligible definitions may use this kernel.
import std;
import os;
import gfx;
import .doc_typed;

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
fn main() {
    if arg_count() < 4 || arg_count() > 5 {
        reject("usage: doc_sdl3_gpu DOC_SOURCE eq|lt|le|bool|staged LANES [--inject-wide]");
    }
    var path:u8[>..]=[];
    var operation:u8[>..]=[];
    var raw_lanes:u8[>..]=[];
    arg(1,path);arg(2,operation);arg(3,raw_lanes);
    let lanes,valid=parse_int(raw_lanes);
    if !valid || lanes<=0 || lanes>4096 { reject("invalid SDL3 compute lane count"); }
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
