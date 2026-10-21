//! Read-only file inspection, except explicit snapshot recording / new-file extraction.
use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap, HashSet},
    fs::{self, File, OpenOptions},
    io::{self, Read, Seek, SeekFrom},
    os::unix::{
        ffi::OsStrExt,
        fs::{MetadataExt, OpenOptionsExt},
    },
    path::{Path, PathBuf},
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};
use walkdir::WalkDir;
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
const BLOCK: usize = 65536;

#[derive(Parser)]
#[command(
    version,
    about = "File tools: JSON reports; inspected files are never executed"
)]
struct Args {
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
    /// Find byte-verified duplicates, ignoring symlinks and duplicate hardlinks.
    Dupes {
        root: PathBuf,
        #[arg(long, default_value_t = 1024)]
        min_size: u64,
    },
    /// Compare directory sizes to the previous scan; records a private local baseline.
    Growth {
        root: PathBuf,
        #[arg(long)]
        no_save: bool,
    },
    /// Inspect file format, SHA-256 and extension/signature consistency.
    Kind { file: PathBuf },
    /// Compare bytes, strings, ELF section listings and entropy without executing files.
    Bindiff { first: PathBuf, second: PathBuf },
    /// Find candidate embedded objects, or copy an explicitly selected byte range.
    Carve {
        file: PathBuf,
        #[arg(long, value_parser=number)]
        offset: Option<u64>,
        #[arg(long, value_parser=number)]
        length: Option<u64>,
        #[arg(long)]
        out: Option<PathBuf>,
    },
}
fn number(s: &str) -> std::result::Result<u64, String> {
    if let Some(v) = s.strip_prefix("0x") {
        u64::from_str_radix(v, 16)
    } else {
        s.parse()
    }
    .map_err(|e| e.to_string())
}
fn regular(path: &Path) -> Result<File> {
    let f = File::open(path)?;
    if !f.metadata()?.is_file() {
        return Err("Expected a regular file".into());
    }
    Ok(f)
}
fn identity(m: &fs::Metadata) -> (u64, u64, u64, i64, i64, i64, i64) {
    (
        m.dev(),
        m.ino(),
        m.len(),
        m.mtime(),
        m.mtime_nsec(),
        m.ctime(),
        m.ctime_nsec(),
    )
}
fn sha(path: &Path) -> Result<String> {
    let mut f = regular(path)?;
    let before = identity(&f.metadata()?);
    let mut hash = Sha256::new();
    let mut buf = [0; BLOCK];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hash.update(&buf[..n]);
    }
    if before != identity(&f.metadata()?) {
        return Err("File changed while hashing".into());
    }
    Ok(format!("{:x}", hash.finalize()))
}
fn paths(root: &Path) -> Result<(Vec<PathBuf>, Vec<String>)> {
    if !root.is_dir() {
        return Err("Expected a directory".into());
    }
    let mut files = Vec::new();
    let mut errors = Vec::new();
    for entry in WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| {
            e.depth() == 0
                || ![".git", ".cache", "node_modules", "target"]
                    .contains(&e.file_name().to_string_lossy().as_ref())
        })
    {
        match entry {
            Ok(e) if e.file_type().is_file() => files.push(e.into_path()),
            Ok(_) => {}
            Err(e) => errors.push(e.to_string()),
        }
    }
    Ok((files, errors))
}
fn same_bytes(a: &Path, b: &Path) -> Result<bool> {
    let mut a = regular(a)?;
    let mut b = regular(b)?;
    let ma = a.metadata()?;
    let mb = b.metadata()?;
    let ia = identity(&ma);
    let ib = identity(&mb);
    if ma.len() != mb.len() {
        return Ok(false);
    }
    let mut aa = [0; BLOCK];
    let mut bb = [0; BLOCK];
    let mut remaining = ma.len();
    while remaining > 0 {
        let n = remaining.min(BLOCK as u64) as usize;
        a.read_exact(&mut aa[..n])?;
        b.read_exact(&mut bb[..n])?;
        if aa[..n] != bb[..n] {
            return Ok(false);
        }
        remaining -= n as u64;
    }
    if ia != identity(&a.metadata()?) || ib != identity(&b.metadata()?) {
        return Err("File changed while comparing".into());
    }
    Ok(true)
}
fn dupes(root: &Path, min_size: u64) -> Result<Value> {
    let (files, mut errors) = paths(root)?;
    let mut sizes: BTreeMap<u64, Vec<PathBuf>> = BTreeMap::new();
    let mut inodes = HashSet::new();
    for path in files {
        match fs::symlink_metadata(&path) {
            Ok(m) => {
                if m.is_file() && m.len() >= min_size && inodes.insert((m.dev(), m.ino())) {
                    sizes.entry(m.len()).or_default().push(path);
                }
            }
            Err(e) => errors.push(format!("{}: {e}", path.display())),
        }
    }
    let mut groups = Vec::new();
    let mut saving = 0u64;
    for (size, files) in sizes {
        if files.len() < 2 {
            continue;
        }
        let mut hashes: HashMap<String, Vec<PathBuf>> = HashMap::new();
        for p in files {
            match sha(&p) {
                Ok(h) => hashes.entry(h).or_default().push(p),
                Err(e) => errors.push(format!("{}: {e}", p.display())),
            }
        }
        for (hash, mut bucket) in hashes {
            if bucket.len() < 2 {
                continue;
            }
            bucket.sort();
            let mut verified = vec![bucket[0].clone()];
            for p in &bucket[1..] {
                match same_bytes(&bucket[0], p) {
                    Ok(true) => verified.push(p.clone()),
                    Ok(false) => errors.push(format!("Changed/colliding file: {}", p.display())),
                    Err(e) => errors.push(e.to_string()),
                }
            }
            if verified.len() > 1 {
                if sha(&verified[0]).ok().as_ref() != Some(&hash) {
                    errors.push(format!(
                        "File changed after comparison: {}",
                        verified[0].display()
                    ));
                    continue;
                }
                let extra = size.saturating_mul(verified.len() as u64 - 1);
                saving = saving.saturating_add(extra);
                groups.push(
                    json!({"size":size,"sha256":hash,"files":verified,"possible_saving":extra}),
                );
            }
        }
    }
    groups.sort_by_key(|g| std::cmp::Reverse(g["possible_saving"].as_u64().unwrap_or(0)));
    Ok(
        json!({"root":root,"groups":groups,"possible_saving":saving,"errors":errors,"note":"Potential logical bytes; Btrfs sharing/compression may reduce actual savings. No files deleted."}),
    )
}
#[derive(Serialize, Deserialize, Default)]
struct Snapshot {
    time: u64,
    files: BTreeMap<PathBuf, (u64, u64)>,
}
fn state_root() -> PathBuf {
    std::env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".local/state")
        })
        .join("workstation-tools")
}
fn growth(root: &Path, no_save: bool) -> Result<Value> {
    let root = fs::canonicalize(root)?;
    let (files, mut errors) = paths(&root)?;
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    let state_dir = state_root().join("growth");
    let name = format!("{:x}.json", Sha256::digest(root.as_os_str().as_bytes()));
    let target = state_dir.join(name);
    let mut current = Snapshot {
        time: now,
        ..Default::default()
    };
    for path in files {
        if path.starts_with(state_root()) {
            continue;
        }
        match fs::symlink_metadata(&path) {
            Ok(m) => {
                current.files.insert(
                    path.strip_prefix(&root)?.to_owned(),
                    (m.len(), m.blocks() * 512),
                );
            }
            Err(e) => errors.push(e.to_string()),
        }
    }
    let previous: Option<Snapshot> = match fs::read(&target) {
        Ok(data) => Some(serde_json::from_slice(&data)?),
        Err(e) if e.kind() == io::ErrorKind::NotFound => None,
        Err(e) => return Err(e.into()),
    };
    let mut changes = Vec::new();
    let mut folders: BTreeMap<PathBuf, i128> = BTreeMap::new();
    if let Some(old) = &previous {
        let all: BTreeSet<_> = old.files.keys().chain(current.files.keys()).collect();
        for p in all {
            let a = old.files.get(p).copied().unwrap_or_default();
            let b = current.files.get(p).copied().unwrap_or_default();
            if a != b || old.files.contains_key(p) != current.files.contains_key(p) {
                let delta = b.0 as i128 - a.0 as i128;
                let folder = p.parent().unwrap_or(Path::new(""));
                *folders.entry(folder.to_path_buf()).or_default() += delta;
                changes.push(json!({"path":p,"delta":delta as i64,"allocated_delta":(b.1 as i128-a.1 as i128) as i64,"before":a.0,"after":b.0,
                "state":if !old.files.contains_key(p){"added"}else if !current.files.contains_key(p){"removed"}else{"changed"}}));
            }
        }
    }
    changes.sort_by_key(|v| std::cmp::Reverse(v["delta"].as_i64().unwrap_or(0).unsigned_abs()));
    let total: u64 = current.files.values().map(|v| v.0).sum();
    let allocated: u64 = current.files.values().map(|v| v.1).sum();
    let before = previous
        .as_ref()
        .map(|s| s.files.values().map(|v| v.0).sum::<u64>());
    // Never replace a usable baseline with an incomplete traversal.
    let saved = !no_save && errors.is_empty();
    if saved {
        fs::create_dir_all(&state_dir)?;
        let tmp = state_dir.join(format!(".scan-{}-{now}.tmp", std::process::id()));
        let mut f = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&tmp)?;
        serde_json::to_writer(&mut f, &current)?;
        f.sync_all()?;
        fs::rename(tmp, &target)?;
    }
    let folder_rows: Vec<_> = folders
        .into_iter()
        .map(|(p, d)| json!({"path":p,"delta":d as i64}))
        .collect();
    Ok(
        json!({"root":root,"baseline_created":previous.is_none()&&saved,"previous_time":previous.as_ref().map(|s|s.time),"time":now,"saved":saved,
        "total":total,"allocated":allocated,"before":before,"delta":before.map(|v|total as i128-v as i128),"changes":changes,"folders":folder_rows,"errors":errors,
        "note":"Sizes are logical / per-file allocated bytes, not unique Btrfs physical usage. Incomplete scans do not overwrite baseline."}),
    )
}
fn at(f: &mut File, pos: u64, len: usize) -> Result<Vec<u8>> {
    f.seek(SeekFrom::Start(pos))?;
    let mut out = vec![0; len];
    f.read_exact(&mut out)?;
    Ok(out)
}
fn identify(data: &[u8]) -> Option<(&'static str, &'static [&'static str])> {
    if data.starts_with(b"\x7fELF") {
        Some(("ELF", &["elf", "so", "o", "bin", "run"]))
    } else if data.starts_with(b"MZ") {
        Some(("DOS/PE candidate", &["exe", "dll", "sys", "scr", "com"]))
    } else if data.starts_with(b"\x89PNG\r\n\x1a\n") {
        Some(("PNG", &["png"]))
    } else if data.starts_with(b"\xff\xd8\xff") {
        Some(("JPEG", &["jpg", "jpeg"]))
    } else if data.starts_with(b"%PDF-") {
        Some(("PDF", &["pdf"]))
    } else if data.starts_with(b"PK\x03\x04") {
        Some((
            "ZIP",
            &["zip", "jar", "apk", "docx", "xlsx", "pptx", "odt", "epub"],
        ))
    } else if data.starts_with(b"\x1f\x8b\x08") {
        Some(("GZIP", &["gz", "tgz"]))
    } else if data.starts_with(b"7z\xbc\xaf\x27\x1c") {
        Some(("7z", &["7z"]))
    } else if data.starts_with(b"\xfd7zXZ\x00") {
        Some(("XZ", &["xz", "txz"]))
    } else {
        None
    }
}
fn external(program: &str, args: &[&str], path: &Path) -> Value {
    match Command::new("timeout")
        .args(["--signal=TERM", "--kill-after=2s", "15s", program])
        .args(args)
        .arg("--")
        .arg(path)
        .env("LC_ALL", "C")
        .output()
    {
        Ok(r) => {
            json!({"ok":r.status.success(),"text":String::from_utf8_lossy(&r.stdout).trim(),"error":String::from_utf8_lossy(&r.stderr).trim()})
        }
        Err(e) => json!({"ok":false,"error":e.to_string()}),
    }
}
fn kind(path: &Path) -> Result<Value> {
    let mut f = regular(path)?;
    let mut data = [0; 512];
    let n = f.read(&mut data)?;
    let sig = identify(&data[..n]);
    let extension = path
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();
    Ok(
        json!({"file":path,"size":f.metadata()?.len(),"sha256":sha(path)?,"extension":extension,"signature":sig.map(|v|v.0),
        "extension_mismatch":sig.map(|(_,ext)|!extension.is_empty()&&!ext.contains(&extension.as_str())),
        "description":external("file",&["-b"],path),"mime":external("file",&["-b","--mime-type"],path),
        "note":"Signature/extension mismatch is not a malware verdict; MZ alone does not validate a PE image. A missing signature is inconclusive."}),
    )
}
fn entropy(counts: &[u64; 256], n: u64) -> f64 {
    if n == 0 {
        return 0.;
    }
    counts
        .iter()
        .filter(|&&v| v > 0)
        .map(|&v| {
            let p = v as f64 / n as f64;
            -p * p.log2()
        })
        .sum()
}
fn binary_stats(path: &Path) -> Result<Value> {
    let mut f = regular(path)?;
    let initial = identity(&f.metadata()?);
    let mut counts = [0u64; 256];
    let mut total = 0u64;
    let mut windows = Vec::new();
    let mut buf = [0; BLOCK];
    let mut set = BTreeSet::new();
    let mut text = Vec::new();
    let mut examined = 0usize;
    let mut strings_capped = false;
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        let mut window = [0u64; 256];
        for &b in &buf[..n] {
            counts[b as usize] += 1;
            window[b as usize] += 1;
            if examined < 16 * 1024 * 1024 {
                if (32..=126).contains(&b) {
                    if text.len() < 4096 {
                        text.push(b);
                    }
                } else {
                    if text.len() >= 6 {
                        if set.len() < 20000 {
                            set.insert(String::from_utf8_lossy(&text).to_string());
                        } else {
                            strings_capped = true;
                        }
                    }
                    text.clear();
                }
                examined += 1;
            }
        }
        if windows.len() < 4096 {
            windows.push(json!({"offset":total,"length":n,"entropy":entropy(&window,n as u64)}));
        }
        total += n as u64;
    }
    if text.len() >= 6 && set.len() < 20000 {
        set.insert(String::from_utf8_lossy(&text).to_string());
    }
    if initial != identity(&f.metadata()?) {
        return Err("File changed while reading statistics".into());
    }
    Ok(
        json!({"entropy":entropy(&counts,total),"entropy_windows":windows,"entropy_windows_truncated":total>4096*BLOCK as u64,
        "strings":set,"strings_prefix_limit":16*1024*1024,"strings_capped":strings_capped||total>16*1024*1024}),
    )
}
fn ranges(a: &Path, b: &Path) -> Result<Value> {
    let mut a = regular(a)?;
    let mut b = regular(b)?;
    let am = a.metadata()?;
    let bm = b.metadata()?;
    let ia = identity(&am);
    let ib = identity(&bm);
    let size = am.len().max(bm.len());
    let mut offset = 0;
    let mut changed = 0u64;
    let mut start = None;
    let mut result = Vec::new();
    let mut total_ranges = 0;
    let mut aa = [0; BLOCK];
    let mut bb = [0; BLOCK];
    while offset < size {
        let n = (size - offset).min(BLOCK as u64) as usize;
        let na = am.len().saturating_sub(offset).min(n as u64) as usize;
        let nb = bm.len().saturating_sub(offset).min(n as u64) as usize;
        a.read_exact(&mut aa[..na])?;
        b.read_exact(&mut bb[..nb])?;
        for i in 0..n {
            let diff = i >= na || i >= nb || aa[i] != bb[i];
            let pos = offset + i as u64;
            if diff {
                changed += 1;
                if start.is_none() {
                    start = Some(pos);
                }
            } else if let Some(s) = start.take() {
                total_ranges += 1;
                if result.len() < 200 {
                    result.push(json!({"start":s,"end":pos,"length":pos-s}));
                }
            }
        }
        offset += n as u64;
    }
    if let Some(s) = start {
        total_ranges += 1;
        if result.len() < 200 {
            result.push(json!({"start":s,"end":size,"length":size-s}));
        }
    }
    if ia != identity(&a.metadata()?) || ib != identity(&b.metadata()?) {
        return Err("File changed while comparing".into());
    }
    Ok(
        json!({"changed_bytes":changed,"ranges":result,"total_ranges":total_ranges,"ranges_truncated":total_ranges>200,"offsets":"zero-based, end exclusive"}),
    )
}
fn section_summary(path: &Path, listing: &Value) -> Result<BTreeMap<String, Value>> {
    let mut sections = BTreeMap::new();
    if listing["ok"] != true {
        return Ok(sections);
    }
    let mut file = regular(path)?;
    let file_size = file.metadata()?.len();
    let mut budget = 64 * 1024 * 1024u64;
    let mut occurrences = HashMap::new();
    for line in listing["text"].as_str().unwrap_or("").lines() {
        let line = line.trim();
        if !line.starts_with('[') {
            continue;
        }
        let Some((index, rest)) = line.split_once(']') else {
            continue;
        };
        let Ok(index) = index.trim_start_matches('[').trim().parse::<usize>() else {
            continue;
        };
        if index == 0 {
            continue;
        }
        let fields: Vec<_> = rest.split_whitespace().collect();
        if fields.len() < 6 {
            continue;
        }
        let (Ok(offset), Ok(size)) = (
            u64::from_str_radix(fields[3], 16),
            u64::from_str_radix(fields[4], 16),
        ) else {
            continue;
        };
        let count = occurrences.entry(fields[0].to_owned()).or_insert(0usize);
        *count += 1;
        let key = if *count == 1 {
            fields[0].to_owned()
        } else {
            format!("{}#{}", fields[0], count)
        };
        let mut hash = None;
        let has_data = fields[1] != "NOBITS";
        if has_data
            && size <= budget
            && offset.checked_add(size).is_some_and(|end| end <= file_size)
        {
            file.seek(SeekFrom::Start(offset))?;
            let mut remaining = size;
            let mut digest = Sha256::new();
            let mut buf = [0; BLOCK];
            while remaining > 0 {
                let n = remaining.min(BLOCK as u64) as usize;
                file.read_exact(&mut buf[..n])?;
                digest.update(&buf[..n]);
                remaining -= n as u64;
            }
            hash = Some(format!("{:x}", digest.finalize()));
            budget -= size;
        }
        sections.insert(
            key,
            json!({"type":fields[1],"address":fields[2],"offset":offset,"size":size,
            "entry_size":fields[5],"attributes":fields[6..].join(" "),"sha256":hash,
            "content_checked":hash.is_some(),"has_file_data":has_data}),
        );
    }
    Ok(sections)
}
fn bindiff(a: &Path, b: &Path) -> Result<Value> {
    let ha = sha(a)?;
    let hb = sha(b)?;
    let mut sa = binary_stats(a)?;
    let mut sb = binary_stats(b)?;
    let aa: BTreeSet<String> = serde_json::from_value(sa["strings"].take())?;
    let bb: BTreeSet<String> = serde_json::from_value(sb["strings"].take())?;
    let added: Vec<_> = bb.difference(&aa).take(100).collect();
    let removed: Vec<_> = aa.difference(&bb).take(100).collect();
    let diff = ranges(a, b)?;
    let first_sections = external("readelf", &["-SW"], a);
    let second_sections = external("readelf", &["-SW"], b);
    let first_summary = section_summary(a, &first_sections)?;
    let second_summary = section_summary(b, &second_sections)?;
    let names: BTreeSet<_> = first_summary.keys().chain(second_summary.keys()).collect();
    let section_changes: Vec<_> = names.into_iter().filter(|name|first_summary.get(*name)!=second_summary.get(*name))
        .map(|name|json!({"name":name,"before":first_summary.get(name),"after":second_summary.get(name)})).collect();
    if sha(a)? != ha || sha(b)? != hb {
        return Err("Input changed during comparison".into());
    }
    Ok(
        json!({"first":a,"second":b,"first_sha256":ha,"second_sha256":hb,"bytes":diff,"first_stats":sa,"second_stats":sb,
        "strings_added":added,"strings_removed":removed,"strings_difference_limit":100,"first_elf_sections":first_sections,"second_elf_sections":second_sections,
        "section_changes":section_changes,"section_hash_budget_per_file":64*1024*1024,
        "note":"Byte ranges compare equal offsets, not semantic instructions. Entropy is not a malware verdict. Strings: ASCII, first 16 MiB, max 20,000 unique; output max 100 per direction."}),
    )
}
fn integer(data: &[u8], little: bool) -> u64 {
    if little {
        data.iter()
            .enumerate()
            .map(|(i, &b)| (b as u64) << (i * 8))
            .sum()
    } else {
        data.iter().fold(0, |n, &b| (n << 8) | b as u64)
    }
}
fn elf_length(f: &mut File, offset: u64, size: u64) -> Result<u64> {
    let h = at(f, offset, 64)?;
    if !h.starts_with(b"\x7fELF") || ![1, 2].contains(&h[4]) || ![1, 2].contains(&h[5]) {
        return Err("Invalid ELF identification".into());
    }
    let is64 = h[4] == 2;
    let little = h[5] == 1;
    let read = |s: usize, n: usize| integer(&h[s..s + n], little);
    let (phoff, shoff, eh, phsize, phnum, shsize, shnum) = if is64 {
        (
            read(32, 8),
            read(40, 8),
            read(52, 2),
            read(54, 2),
            read(56, 2),
            read(58, 2),
            read(60, 2),
        )
    } else {
        (
            read(28, 4),
            read(32, 4),
            read(40, 2),
            read(42, 2),
            read(44, 2),
            read(46, 2),
            read(48, 2),
        )
    };
    if eh < if is64 { 64 } else { 52 } || phnum == 65535 || (shnum == 0 && shoff != 0) {
        return Err("Unsupported/truncated ELF header or extended numbering".into());
    }
    let available = size.checked_sub(offset).ok_or("Offset past EOF")?;
    let mut end = eh;
    for (table, entry_size, count, is_ph) in
        [(phoff, phsize, phnum, true), (shoff, shsize, shnum, false)]
    {
        if count == 0 {
            continue;
        }
        let minimum = if is_ph {
            if is64 {
                56
            } else {
                32
            }
        } else if is64 {
            64
        } else {
            40
        };
        if entry_size < minimum || entry_size > 4096 {
            return Err("Invalid ELF table entry size".into());
        }
        let table_end = table
            .checked_add(entry_size.checked_mul(count).ok_or("ELF overflow")?)
            .ok_or("ELF overflow")?;
        if table_end > available {
            return Err("ELF table beyond EOF".into());
        }
        end = end.max(table_end);
        for i in 0..count {
            let row = at(f, offset + table + i * entry_size, minimum as usize)?;
            let n = |s: usize, l: usize| integer(&row[s..s + l], little);
            let (start, len) = if is_ph {
                if is64 {
                    (n(8, 8), n(32, 8))
                } else {
                    (n(4, 4), n(16, 4))
                }
            } else {
                if n(4, 4) == 8 {
                    continue;
                }
                if is64 {
                    (n(24, 8), n(32, 8))
                } else {
                    (n(16, 4), n(20, 4))
                }
            };
            if len == 0 {
                continue;
            }
            let item_end = start.checked_add(len).ok_or("ELF overflow")?;
            if item_end > available {
                return Err("ELF data beyond EOF".into());
            }
            end = end.max(item_end);
        }
    }
    Ok(end)
}
fn png_length(f: &mut File, offset: u64, size: u64) -> Result<u64> {
    let mut p = offset.checked_add(8).ok_or("Overflow")?;
    let mut chunks = 0;
    while p.checked_add(12).is_some_and(|n| n <= size) && chunks < 100000 {
        let h = at(f, p, 8)?;
        let len = integer(&h[..4], false);
        let kind = &h[4..];
        if chunks == 0 && (kind != b"IHDR" || len != 13) {
            return Err("Invalid PNG header".into());
        }
        p = p.checked_add(12 + len).ok_or("PNG overflow")?;
        if p > size {
            return Err("PNG chunk beyond EOF".into());
        }
        chunks += 1;
        if kind == b"IEND" {
            if len != 0 {
                return Err("Invalid PNG end".into());
            }
            return Ok(p - offset);
        }
    }
    Err("Incomplete PNG / too many chunks".into())
}
fn scan(path: &Path) -> Result<Value> {
    let mut f = regular(path)?;
    let before = identity(&f.metadata()?);
    let size = f.metadata()?.len();
    let signatures: &[(&[u8], &str)] = &[
        (b"\x7fELF", "ELF"),
        (b"MZ", "MZ"),
        (b"\x89PNG\r\n\x1a\n", "PNG"),
        (b"\xff\xd8\xff", "JPEG"),
        (b"%PDF-", "PDF"),
        (b"PK\x03\x04", "ZIP"),
        (b"\x1f\x8b\x08", "GZIP"),
        (b"7z\xbc\xaf\x27\x1c", "7z"),
        (b"\xfd7zXZ\x00", "XZ"),
    ];
    let mut buffer = vec![0; BLOCK + 8];
    let mut carry = 0;
    let mut base = 0u64;
    let mut candidates = Vec::new();
    let mut seen = HashSet::new();
    let mut capped = false;
    'scan: loop {
        let n = f.read(&mut buffer[carry..])?;
        if n == 0 {
            break;
        }
        let valid = carry + n;
        for i in 0..valid {
            for &(sig, kind) in signatures {
                if i + sig.len() <= valid && &buffer[i..i + sig.len()] == sig {
                    let pos = base + i as u64;
                    if seen.insert((pos, kind)) {
                        candidates.push((pos, kind));
                        if candidates.len() >= 2000 {
                            capped = true;
                            break 'scan;
                        }
                    }
                }
            }
        }
        carry = valid.min(7);
        buffer.copy_within(valid - carry..valid, 0);
        base += (valid - carry) as u64;
    }
    candidates.sort_by_key(|c| c.0);
    let mut results = Vec::new();
    for (offset, kind) in candidates {
        let measured = match kind {
            "ELF" => elf_length(&mut f, offset, size),
            "PNG" => png_length(&mut f, offset, size),
            _ => Err("Length must be selected manually".into()),
        };
        let (length, reason) = match measured {
            Ok(n) => (Some(n), None),
            Err(e) => (None, Some(e.to_string())),
        };
        results.push(json!({"offset":offset,"hex_offset":format!("0x{offset:x}"),"kind":kind,"suggested_length":length,"note":reason}));
    }
    if before != identity(&f.metadata()?) {
        return Err("File changed during scan".into());
    }
    Ok(
        json!({"file":path,"size":size,"candidates":results,"truncated":capped,"note":"Signatures are candidates, not proof of a valid object. PNG length uses chunk bounds, no CRC verification; ELF length uses bounded tables, excludes overlays. Other formats require an explicit length."}),
    )
}
fn extract(path: &Path, offset: u64, length: u64, out: &Path) -> Result<Value> {
    let mut source = regular(path)?;
    let before = identity(&source.metadata()?);
    let size = source.metadata()?.len();
    if length == 0 || offset.checked_add(length).is_none_or(|end| end > size) {
        return Err("Extraction range is empty or beyond EOF".into());
    }
    source.seek(SeekFrom::Start(offset))?;
    let mut target = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(out)?;
    let result = (|| -> Result<()> {
        let copied = io::copy(&mut Read::by_ref(&mut source).take(length), &mut target)?;
        if copied != length {
            return Err("Source was truncated during extraction".into());
        }
        if before != identity(&source.metadata()?) {
            return Err("Source changed during extraction".into());
        }
        target.sync_all()?;
        Ok(())
    })();
    if let Err(error) = result {
        drop(target);
        let _ = fs::remove_file(out);
        return Err(error);
    }
    Ok(json!({"source":path,"offset":offset,"length":length,"output":out,"sha256":sha(out)?}))
}
fn execute(args: Args) -> Result<Value> {
    match args.command {
        Action::Dupes { root, min_size } => dupes(&root, min_size),
        Action::Growth { root, no_save } => growth(&root, no_save),
        Action::Kind { file } => kind(&file),
        Action::Bindiff { first, second } => bindiff(&first, &second),
        Action::Carve {
            file,
            offset,
            length,
            out,
        } => match (offset, length, out) {
            (None, None, None) => scan(&file),
            (Some(o), Some(l), Some(p)) => extract(&file, o, l, &p),
            _ => Err("Extraction requires --offset, --length and --out together".into()),
        },
    }
}
fn main() {
    match execute(Args::parse()) {
        Ok(v) => {
            let stdout = io::stdout();
            if let Err(e) = serde_json::to_writer_pretty(stdout.lock(), &v) {
                eprintln!("{e}");
                std::process::exit(1);
            }
            println!();
        }
        Err(e) => {
            eprintln!("workstation-files: {e}");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn temporary() -> PathBuf {
        let d = std::env::temp_dir().join(format!(
            "workstation-files-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&d).unwrap();
        d
    }
    #[test]
    fn byte_ranges_include_eof_changes() {
        let d = temporary();
        fs::write(d.join("a"), b"abcdef").unwrap();
        fs::write(d.join("b"), b"axcdZZ++").unwrap();
        let v = ranges(&d.join("a"), &d.join("b")).unwrap();
        assert_eq!(v["changed_bytes"], 5);
        assert_eq!(v["ranges"][0]["start"], 1);
        assert_eq!(v["ranges"][1]["end"], 8);
        fs::remove_dir_all(d).unwrap();
    }
    #[test]
    fn duplicates_ignore_hardlinks_and_symlinks() {
        let d = temporary();
        let b = vec![7u8; 2048];
        fs::write(d.join("a"), &b).unwrap();
        fs::write(d.join("b"), &b).unwrap();
        fs::hard_link(d.join("a"), d.join("hard")).unwrap();
        std::os::unix::fs::symlink(d.join("a"), d.join("link")).unwrap();
        let v = dupes(&d, 1).unwrap();
        assert_eq!(v["groups"].as_array().unwrap().len(), 1);
        assert_eq!(v["groups"][0]["files"].as_array().unwrap().len(), 2);
        assert_eq!(v["possible_saving"], 2048);
        fs::remove_dir_all(d).unwrap();
    }
    #[test]
    fn extension_mismatch_and_sha_known_vector() {
        let d = temporary();
        let p = d.join("fake.jpg");
        fs::write(&p, b"\x7fELFxxx").unwrap();
        assert_eq!(kind(&p).unwrap()["extension_mismatch"], true);
        fs::write(&p, b"abc").unwrap();
        assert_eq!(
            sha(&p).unwrap(),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        fs::remove_dir_all(d).unwrap();
    }
    #[test]
    fn extraction_refuses_overwrite_and_out_of_bounds() {
        let d = temporary();
        let p = d.join("in");
        let out = d.join("out");
        fs::write(&p, b"0123456789").unwrap();
        assert!(extract(&p, 9, 2, &out).is_err());
        assert!(!out.exists());
        extract(&p, 2, 4, &out).unwrap();
        assert_eq!(fs::read(&out).unwrap(), b"2345");
        assert!(extract(&p, 0, 1, &out).is_err());
        assert_eq!(fs::read(&out).unwrap(), b"2345");
        fs::remove_dir_all(d).unwrap();
    }
    #[test]
    fn signature_across_chunk_boundary() {
        let d = temporary();
        let p = d.join("in");
        let mut data = vec![0u8; BLOCK + 20];
        data[BLOCK + 6..BLOCK + 10].copy_from_slice(b"\x7fELF");
        fs::write(&p, data).unwrap();
        let v = scan(&p).unwrap();
        assert_eq!(v["candidates"][0]["offset"], BLOCK + 6);
        assert!(v["candidates"][0]["suggested_length"].is_null());
        fs::remove_dir_all(d).unwrap();
    }
    #[test]
    fn elf_extraction_extent_accepts_real_executable() {
        let p = std::env::current_exe().unwrap();
        let mut f = regular(&p).unwrap();
        let n = f.metadata().unwrap().len();
        let extent = elf_length(&mut f, 0, n).unwrap();
        assert!(extent > 64 && extent <= n);
    }
}
