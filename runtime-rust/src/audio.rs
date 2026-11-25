//! A narrow, optional AUDIO EFFECT: emit a real PCM WAV file for a
//! stable DOC-derived cue. No game rules, live sound device, mixer or GUI.
//! Audio is external I/O after DOC publication; output is atomic per file.

use crate::Result;

const SAMPLE_RATE: u32 = 44_100;
const MAX_DURATION_MS: u32 = 5_000;

/// Produce actual RIFF/WAVE PCM16 mono bytes. Bounds prevent oversized effects.
pub fn pcm16_tone(frequency_hz:u32,duration_ms:u32)->Result<Vec<u8>>{
    if !(20..=20_000).contains(&frequency_hz) ||
       !(1..=MAX_DURATION_MS).contains(&duration_ms) {
        return Err("DOC audio frequency/duration outside bounded PCM policy".into());
    }
    let samples=SAMPLE_RATE.checked_mul(duration_ms)
        .ok_or("DOC audio sample overflow")? / 1000;
    let data_bytes=samples.checked_mul(2).ok_or("DOC audio data size overflow")?;
    let chunk_bytes=data_bytes.checked_add(36).ok_or("DOC WAV RIFF size overflow")?;
    let mut out=Vec::with_capacity(44+data_bytes as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&chunk_bytes.to_le_bytes());
    out.extend_from_slice(b"WAVEfmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&SAMPLE_RATE.to_le_bytes());
    out.extend_from_slice(&(SAMPLE_RATE*2).to_le_bytes());
    out.extend_from_slice(&2u16.to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_bytes.to_le_bytes());
    for n in 0..samples {
        let radians=std::f64::consts::TAU * f64::from(frequency_hz) *
            f64::from(n) / f64::from(SAMPLE_RATE);
        let sample=(radians.sin()*7_200.0).round() as i16;
        out.extend_from_slice(&sample.to_le_bytes());
    }
    Ok(out)
}
/// Convert an already-authorized DOC audio cue into a confined, atomically
/// replaced WAV file. Directory creation and device output are NOT implicit.
pub fn write_tone_wav(
    doc_file:&str,relative:&str,frequency_hz:u32,duration_ms:u32
)->Result<()>{
    let bytes=pcm16_tone(frequency_hz,duration_ms)?;
    crate::confined::write(doc_file,relative,&bytes)
}
