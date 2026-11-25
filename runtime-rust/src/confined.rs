//! Linux filesystem authority for the reference implementation.
//! The host-selected source directory is trusted authority. Relative child
//! components cannot traverse symlinks; all operations use opened directories.
//! This is not a sandbox against the host renaming granted directory objects,
//! modifying regular files or installing hard links/mounts in granted storage.
use crate::Result;
use std::{
    ffi::CString, fs::{File,OpenOptions}, io::{self,Read,Write},
    os::{fd::{AsRawFd,FromRawFd},unix::fs::OpenOptionsExt},
    path::Path, sync::atomic::{AtomicU64,Ordering},
};

pub(crate) fn source_directory(path:&Path)->&Path {
    path.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."))
}
pub(crate) fn safe_path(path:&str)->bool {
    !path.is_empty() && path.len()<=256 && path.is_ascii() &&
        path.split('/').all(|p|!p.is_empty() && p!="." && p!=".." &&
            p.bytes().all(|b|b.is_ascii_alphanumeric() || matches!(b,b'_'|b'-'|b'.')))
}
fn os_error(operation:&str)->String {format!("DOC filesystem {operation}: {}",io::Error::last_os_error())}
fn open_at(dir:&File,name:&CString,flags:libc::c_int,mode:libc::mode_t)->Result<File>{
    // SAFETY: name is NUL-terminated, directory FD remains owned throughout,
    // and only successful newly opened descriptors become owned Files.
    let fd=unsafe{libc::openat(dir.as_raw_fd(),name.as_ptr(),flags|libc::O_CLOEXEC,mode)};
    if fd<0 {return Err(os_error("openat"));}
    Ok(unsafe{File::from_raw_fd(fd)})
}
fn parent(base:&Path,relative:&str)->Result<(File,CString)>{
    if !safe_path(relative){return Err("DOC filesystem path not confined".into());}
    let mut dir=OpenOptions::new().read(true).custom_flags(libc::O_DIRECTORY|libc::O_CLOEXEC)
        .open(base).map_err(|e|format!("DOC source directory unavailable: {e}"))?;
    let mut parts=relative.split('/').peekable();
    while let Some(part)=parts.next(){
        let name=CString::new(part).map_err(|_|"invalid DOC path component")?;
        if parts.peek().is_none(){return Ok((dir,name));}
        dir=open_at(&dir,&name,libc::O_RDONLY|libc::O_DIRECTORY|libc::O_NOFOLLOW,0)?;
    }
    Err("DOC filesystem missing leaf".into())
}
fn bounded_text(file:File,limit:usize)->Result<String>{
    let meta=file.metadata().map_err(|e|format!("DOC file metadata: {e}"))?;
    if !meta.is_file(){return Err("DOC input must be a regular file".into());}
    if meta.len()>limit as u64{return Err("DOC input exceeds resource limit".into());}
    let mut bytes=Vec::new();
    file.take(limit as u64+1).read_to_end(&mut bytes)
        .map_err(|e|format!("DOC input read: {e}"))?;
    if bytes.len()>limit{return Err("DOC input exceeds resource limit".into());}
    String::from_utf8(bytes).map_err(|_|"DOC input must be UTF-8".into())
}
pub(crate) fn read_source(path:&Path,limit:usize)->Result<String>{
    // The explicitly named top-level source may be a host-approved symlink.
    // Nonblocking open + metadata on the opened object rejects FIFOs/devices.
    let file=OpenOptions::new().read(true).custom_flags(libc::O_NONBLOCK|libc::O_CLOEXEC)
        .open(path).map_err(|e|format!("DOC source open: {e}"))?;
    bounded_text(file,limit)
}
pub(crate) fn read(base:&Path,relative:&str,limit:usize)->Result<String>{
    let (dir,name)=parent(base,relative)?;
    bounded_text(open_at(&dir,&name,libc::O_RDONLY|libc::O_NOFOLLOW|libc::O_NONBLOCK,0)?,limit)
}
static TEMP_ID:AtomicU64=AtomicU64::new(0);
pub(crate) fn write(doc_file:&str,relative:&str,bytes:&[u8])->Result<()> {
    let (dir,name)=parent(source_directory(Path::new(doc_file)),relative)?;
    let id=TEMP_ID.fetch_add(1,Ordering::Relaxed);
    let temp=CString::new(format!(".doc-tmp-{}-{id}",std::process::id()))
        .map_err(|_|"invalid DOC temporary name")?;
    // If exclusive creation fails, never remove a file owned by another writer.
    let mut file=open_at(&dir,&temp,libc::O_WRONLY|libc::O_CREAT|libc::O_EXCL|libc::O_NOFOLLOW,0o600)?;
    let result=(||->Result<()> {
        file.write_all(bytes).map_err(|e|format!("DOC write: {e}"))?;
        file.sync_all().map_err(|e|format!("DOC sync: {e}"))?;
        drop(file);
        // SAFETY: both NUL-terminated names are relative to the same live FD.
        if unsafe{libc::renameat(dir.as_raw_fd(),temp.as_ptr(),dir.as_raw_fd(),name.as_ptr())}!=0 {
            return Err(os_error("renameat"));
        }
        Ok(())
    })();
    if result.is_err(){
        // SAFETY: remove only the name successfully created by this invocation.
        // The granted directory must not be controlled by an adversarial writer.
        unsafe{libc::unlinkat(dir.as_raw_fd(),temp.as_ptr(),0);}
    }
    result
}
