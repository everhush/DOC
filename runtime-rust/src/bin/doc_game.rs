//! DOC Coin Chase host: only ordered input facts, recurrence ticks and presentation.
//! Gameplay/collisions/scoring/pause/win/scene boundaries are authored in DOC.
use doc_runtime::{audio::write_tone_wav,checkpoint::{load_checkpoint,save_checkpoint},recurrence::Recurrence, Graph, Value};
use std::{env, io::{self,BufRead}, process, time::Instant};

const CARRIES: &[(&str,&str)] = &[
    ("frame","next_frame"), ("player_x","next_x"), ("player_y","next_y"),
    ("coin_x","next_coin_x"), ("coin_y","next_coin_y"),
    ("score","next_score"), ("paused","next_paused"), ("won","next_won"),
    ("animation_phase","next_animation_phase"),
];
const SHOWCASE_CARRIES:&[(&str,&str)]=&[
    ("entity_ids","next_entity_ids"),("entity_xs","next_entity_xs"),
    ("entity_ys","next_entity_ys"),("next_entity_id","next_next_entity_id"),
    ("issued_high_water","next_issued_high_water"),
    ("prefab_template_xs","template_next_xs"),
    ("prefab_template_ys","template_next_ys"),
];
fn field(game:&Recurrence,graph:&Graph,name:&str)->Result<Value,String>{
    game.value(graph.id(name).ok_or_else(||format!("Missing DOC scene field {name}"))?)
        .ok_or_else(||format!("Missing stable DOC value {name}"))
}
fn int(game:&Recurrence,graph:&Graph,name:&str)->Result<i64,String>{
    match field(game,graph,name)? {
        Value::Int(x)=>Ok(x), _=>Err(format!("DOC scene field {name} must be int"))
    }
}
fn boolean(game:&Recurrence,graph:&Graph,name:&str)->Result<bool,String>{
    match field(game,graph,name)? {
        Value::Bool(x)=>Ok(x), _=>Err(format!("DOC scene field {name} must be bool"))
    }
}
fn input(c:char)->Result<Option<i64>,String>{
    match c {
        'w'=>Ok(Some(1)), 's'=>Ok(Some(2)), 'a'=>Ok(Some(3)),
        'd'=>Ok(Some(4)), 'p'=>Ok(Some(5)), 'r'=>Ok(Some(6)),
        'e'=>Ok(Some(7)), 'x'=>Ok(Some(8)),
        '.'=>Ok(Some(0)), 'q'=>Ok(None),
        _=>Err(format!("Unknown input {c:?}; use w/a/s/d/p/r/e/x/./q"))
    }
}
fn present(game:&Recurrence,graph:&Graph,headless:bool)->Result<(),String>{
    let frame=int(game,graph,"next_frame")?;
    let x=int(game,graph,"next_x")?;
    let y=int(game,graph,"next_y")?;
    let cx=int(game,graph,"next_coin_x")?;
    let cy=int(game,graph,"next_coin_y")?;
    let score=int(game,graph,"next_score")?;
    let won=boolean(game,graph,"next_won")?;
    let paused=boolean(game,graph,"next_paused")?;
    let width=int(game,graph,"width")?;
    let height=int(game,graph,"height")?;
    let wx=int(game,graph,"wall_x")?;
    let wy=int(game,graph,"wall_y")?;
    if !(1..=200).contains(&width)||!(1..=200).contains(&height) {
        return Err("DOC screen dimensions exceed terminal presentation budget".into());
    }
    println!("DOC_GAME_FRAME: tick={frame} player=({x},{y}) score={score} paused={paused} won={won} coin=({cx},{cy})");
    let (obstacles,ids)=if let (Some(xs),Some(ys),Some(ids))=(
        graph.id("next_entity_xs"),graph.id("next_entity_ys"),
        graph.id("next_entity_ids")){
        match (game.value(xs),game.value(ys),game.value(ids)){
            (Some(Value::Ints(xs)),Some(Value::Ints(ys)),Some(Value::Ints(ids)))=>{
                if xs.len()!=ys.len()||xs.len()!=ids.len(){
                    return Err("DOC showcase components lost column alignment".into());
                }
                (xs.into_iter().zip(ys).collect::<Vec<_>>(),ids)
            },
            _=>return Err("DOC showcase expects typed entity component columns".into())
        }
    }else{(Vec::new(),Vec::new())};
    if !ids.is_empty()||graph.id("next_entity_ids").is_some(){
        println!("DOC_GAME_ENTITIES: count={} ids={ids:?} hazards={obstacles:?}",ids.len());
    }
    if graph.id("radar_player_cell").is_some(){
        println!("DOC_GAME_RADAR: pre_action_player_cell={} pre_action_coin_cell={}",
            int(game,graph,"radar_player_cell")?,int(game,graph,"radar_coin_cell")?);
    }
    if !headless {
        for row in 0..height{
            let mut line=String::with_capacity(width as usize);
            for col in 0..width{
                line.push(if (col,row)==(x,y){'@'}
                    else if (col,row)==(wx,wy){'#'}
                    else if obstacles.contains(&(col,row)){'X'}
                    else if (col,row)==(cx,cy)&&!won{'*'}
                    else {'.'});
            }
            println!("{line}");
        }
        if won {println!("GOAL REACHED — press r to restart or q to quit");}
    }
    Ok(())
}
/// Optional OS/audio effect. Cue parameters and triggering are computed in DOC.
/// No mock speaker success, live audio device, or audio mixer is implied.
fn emit_audio(game:&Recurrence,graph:&Graph,doc_file:&str,dir:&str)->Result<(),String>{
    let hz=int(game,graph,"audio_hz")?;
    let ms=int(game,graph,"audio_ms")?;
    if hz==0 && ms==0{return Ok(());}
    let frequency=u32::try_from(hz).map_err(|_|"Invalid DOC audio frequency")?;
    let duration=u32::try_from(ms).map_err(|_|"Invalid DOC audio duration")?;
    let output=format!("{dir}/cue_{}.wav",game.epoch());
    write_tone_wav(doc_file,&output,frequency,duration)?;
    println!("DOC_GAME_AUDIO_WAV: epoch={} path={output}",game.epoch());
    Ok(())
}
fn print_measurement(samples:&mut Vec<u128>,gpu_used:bool){
    samples.sort_unstable();
    let n=samples.len();
    let p50=if n==0{0}else{samples[(n*50-1)/100]};
    let p95=if n==0{0}else{samples[(n*95-1)/100]};
    let peak=std::fs::read_to_string("/proc/self/status").ok()
        .and_then(|s|s.lines().find_map(|line|
            line.strip_prefix("VmHWM:").and_then(|v|v.split_whitespace().next())
                .and_then(|s|s.parse::<u64>().ok())))
        .map(|n|n.to_string()).unwrap_or_else(||"unavailable".into());
    let label=if gpu_used{"DOC_GAME_AUTO_MIXED_MEASURED"}else{"DOC_GAME_CPU_MEASURED"};
    println!("{label}: steps={n} p50_us={p50} p95_us={p95} process_peak_rss_kib={peak} measurement=DOC_recurrence_advance_only");
}
fn play()->Result<(),String>{
    let mut args=env::args().skip(1);
    let file=args.next().ok_or("usage: doc-game FILE.doc [--replay=wasdpr.] [--headless] [--workers=N] [--load=relative.chk] [--save=relative.chk] [--audio-dir=existing/dir] [--measure]")?;
    let mut replay=None;
    let mut headless=false;
    let mut save=None;
    let mut load=None;
    let mut audio_dir=None;
    let mut measure=false;
    let mut samples=Vec::new();
    let mut workers=std::thread::available_parallelism().map(|n|n.get()).unwrap_or(1);
    for arg in args {
        if let Some(raw)=arg.strip_prefix("--replay="){
            if replay.replace(raw.to_string()).is_some(){return Err("Duplicate replay".into());}
        }else if let Some(raw)=arg.strip_prefix("--workers="){
            workers=raw.parse().map_err(|_|"Invalid workers")?;
            if !(1..=256).contains(&workers){return Err("Worker count out of range".into());}
        }else if let Some(raw)=arg.strip_prefix("--save="){
            if save.replace(raw.to_string()).is_some(){return Err("Duplicate save".into());}
        }else if let Some(raw)=arg.strip_prefix("--load="){
            if load.replace(raw.to_string()).is_some(){return Err("Duplicate load".into());}
        }else if let Some(raw)=arg.strip_prefix("--audio-dir="){
            if audio_dir.replace(raw.to_string()).is_some(){return Err("Duplicate audio directory".into());}
        }else if arg=="--measure"{measure=true;}
        else if arg=="--headless"{headless=true;}
        else{return Err(format!("Unknown option {arg}"));}
    }
    let graph=Graph::parse_file(&file)?;
    let mut carry=Vec::with_capacity(CARRIES.len());
    for &(source,derived) in CARRIES {
        carry.push((graph.id(source).ok_or("Missing DOC carry source")?,
                    graph.id(derived).ok_or("Missing DOC carried derivation")?));
    }
    for &(source,result) in SHOWCASE_CARRIES{
        match (graph.id(source),graph.id(result)){
            (Some(a),Some(b))=>carry.push((a,b)),
            (None,None)=>{},
            _=>return Err(format!("incomplete DOC showcase carry {source} -> {result}")),
        }
    }
    let action=graph.id("action").ok_or("Missing DOC action source")?;
    let mut game=if let Some(relative)=load {
        let mut loaded=load_checkpoint(&file,&relative,graph.clone(),carry,workers,2)?;
        loaded.recurrence.enable_automatic();
        println!("DOC_GAME_RESTORED: saved_epoch={} new_epoch=0",loaded.saved_epoch);
        loaded.recurrence
    }else{
        Recurrence::new_automatic_with_retention(graph.clone(),carry,&[],workers,2)?
    };
    present(&game,&graph,headless)?;
    if let Some(replay)=replay {
        for c in replay.chars(){
            let Some(action_code)=input(c)? else {break};
            let started=Instant::now();
            game.advance(&[(action,Value::Int(action_code))])?;
            if measure{samples.push(started.elapsed().as_micros());}
            if let Some(dir)=&audio_dir{emit_audio(&game,&graph,&file,dir)?;}
            present(&game,&graph,headless)?;
        }
    }else{
        println!("Controls: w/a/s/d move, p pause, r restart, e spawn, x despawn, . idle, q quit. Press Enter after input.");
        'commands: for line in io::stdin().lock().lines(){
            let line=line.map_err(|e|format!("Input effect failed: {e}"))?;
            for c in line.trim().chars(){
                let Some(action_code)=input(c)? else {break 'commands};
                let started=Instant::now();
                game.advance(&[(action,Value::Int(action_code))])?;
                if measure{samples.push(started.elapsed().as_micros());}
                if let Some(dir)=&audio_dir{emit_audio(&game,&graph,&file,dir)?;}
                present(&game,&graph,headless)?;
            }
        }
    }
    if let Some(relative)=save {
        save_checkpoint(&file,&relative,&game)?;
        println!("DOC_GAME_CHECKPOINT_SAVED: epoch={}",game.epoch());
    }
    if measure{let used_gpu=game.automatic_stats().is_some_and(|s|s.gpu_nodes>0);
        print_measurement(&mut samples,used_gpu);}
    if let Some(report)=game.automatic_report(){eprintln!("{report}");}
    Ok(())
}
fn main(){
    if let Err(e)=play(){eprintln!("DOC_GAME_ERROR: {e}");process::exit(1);}
}
