//! Real PCM output effects and confined failure boundaries; no speaker device required.
use doc_runtime::audio::{pcm16_tone,write_tone_wav};
use std::fs;

#[test]
fn wav_is_decodable_pcm16_mono_with_correct_sizes_and_nonzero_audio(){
    let bytes=pcm16_tone(880,120).unwrap();
    let total=44+44_100usize*120/1000*2;
    assert_eq!(bytes.len(),total);
    assert_eq!(&bytes[0..4],b"RIFF");
    assert_eq!(&bytes[8..12],b"WAVE");
    assert_eq!(&bytes[12..16],b"fmt ");
    assert_eq!(&bytes[36..40],b"data");
    assert_eq!(u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize,total-8);
    assert_eq!(u32::from_le_bytes(bytes[40..44].try_into().unwrap()) as usize,total-44);
    assert_eq!(u16::from_le_bytes(bytes[22..24].try_into().unwrap()),1);
    assert_eq!(u32::from_le_bytes(bytes[24..28].try_into().unwrap()),44_100);
    assert_eq!(u16::from_le_bytes(bytes[34..36].try_into().unwrap()),16);
    assert!(bytes[44..].iter().any(|&b|b!=0));
    for (hz,ms) in [(0,100),(19,100),(20_001,100),(880,0),(880,5_001)]{
        assert!(pcm16_tone(hz,ms).is_err());
    }
}
#[test]
fn audio_file_effect_is_confined_and_replaces_only_valid_full_file(){
    let root=std::env::temp_dir().join(format!("doc_audio_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("audio")).unwrap();
    let source=root.join("source.doc");
    fs::write(&source,"source cue: bool = true\n").unwrap();
    let src=source.to_str().unwrap();
    write_tone_wav(src,"audio/event.wav",440,100).unwrap();
    let original=fs::read(root.join("audio/event.wav")).unwrap();
    for bad in ["../escape.wav","audio/../escape.wav","/tmp/no.wav",
                "./audio/event.wav","audio\\event.wav","missing/event.wav"] {
        assert!(write_tone_wav(src,bad,880,100).is_err(),"{bad}");
    }
    assert!(write_tone_wav(src,"audio/event.wav",20_001,100).is_err());
    assert_eq!(fs::read(root.join("audio/event.wav")).unwrap(),original);
    write_tone_wav(src,"audio/event.wav",880,100).unwrap();
    let replaced=fs::read(root.join("audio/event.wav")).unwrap();
    assert_eq!(replaced.len(),original.len());
    assert_ne!(replaced,original);
    #[cfg(unix)]
    {
        use std::os::unix::fs::symlink;
        let foreign=std::env::temp_dir().join(format!("doc_audio_escape_{}",std::process::id()));
        let _=fs::remove_dir_all(&foreign);
        fs::create_dir_all(&foreign).unwrap();
        symlink(&foreign,root.join("outside")).unwrap();
        assert!(write_tone_wav(src,"outside/escape.wav",880,120).is_err());
        assert!(!foreign.join("escape.wav").exists());
        fs::remove_dir_all(foreign).unwrap();
    }
    fs::remove_dir_all(root).unwrap();
}
