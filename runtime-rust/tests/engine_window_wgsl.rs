#[test]
fn coin_chase_window_wgsl_parses_and_validates(){
    let text=include_str!("../../engine/shaders/coin_chase.wgsl");
    let module=naga::front::wgsl::parse_str(text)
        .expect("DOC 2D presentation WGSL must parse");
    naga::valid::Validator::new(naga::valid::ValidationFlags::all(),
        naga::valid::Capabilities::all()).validate(&module)
        .expect("DOC 2D presentation WGSL must validate");
}
