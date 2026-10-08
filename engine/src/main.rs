//! `smmr-engine`: upstream Map Rando, unmodified, behind a JSON protocol.
//!
//! Usage: `smmr-engine --data <MapRandomizer checkout or data copy> <command>`
//! The request is a JSON object on stdin. The response is the last line of stdout (Map Rando prints progress before
//! it), a JSON object: `{"ok": <result>}`, or `{"error": "<message>"}` with exit code 1.
//!
//! Commands:
//! - `info`: the item locations, items and version (stable facts the world is built from)
//! - `upgrade`: `{settings}` → `{settings}`, with presets applied and older formats upgraded
//! - `randomize`: `{settings, seed, maps_dir?}` → `{randomization, spoiler, seed_hash}`
//! - `rom`: `{settings, randomization, rom, out}` → `{}`; writes Map Rando's ROM to `out`
//!
//! Map Rando reads its data from paths relative to `<data>/rust`, so the engine changes directory there first. It is
//! its own process, so this doesn't affect the caller.

use anyhow::{Context, Result, bail};
use maprando::customize::CustomizeSettings;
use maprando::customize::samus_sprite::{SamusSpriteCategory, SamusSpriteInfo};
use maprando::difficulty::{get_full_global, get_link_difficulty_length};
use maprando::map_repository::{MapRepository, MapSettings, OfflineMapRepository};
use maprando::patch::{Rom, make_rom};
use maprando::preset::PresetData;
use maprando::randomize::{
    Randomization, Randomizer, assign_map_areas, filter_links, get_difficulty_tiers,
    get_objectives, randomize_doors,
};
use maprando::settings::{RandomizerSettings, StartLocationMode, try_upgrade_settings};
use maprando_game::{GameData, LinksDataGroup, Map};
use rand::{RngCore, SeedableRng};
use serde_json::{Value, json};
use std::io::Read;
use std::path::{Path, PathBuf};

const VERSION: usize = include!("../../MapRandomizer/rust/VERSION");
const MAX_ATTEMPTS: usize = 2000;

struct Engine {
    game_data: GameData,
    preset_data: PresetData,
}

impl Engine {
    fn load() -> Result<Self> {
        let mut game_data = GameData::load(Path::new(".")).context("loading Map Rando game data")?;
        let preset_data = PresetData::load(
            Path::new("data/tech_data.json"),
            Path::new("data/notable_data.json"),
            Path::new("data/presets"),
            &game_data,
        )
        .context("loading Map Rando presets")?;
        let global = get_full_global(&game_data);
        game_data.make_links_data(&|link, game_data| {
            get_link_difficulty_length(link, game_data, &preset_data, &global)
        });
        Ok(Engine { game_data, preset_data })
    }

    fn info(&self) -> Result<Value> {
        let locations: Vec<Value> = self
            .game_data
            .item_locations
            .iter()
            .enumerate()
            .map(|(index, &(room_id, node_id))| {
                let room = &self.game_data.room_json_map[&room_id];
                let node = &self.game_data.node_json_map[&(room_id, node_id)];
                let plm_ptr = self.game_data.node_ptr_map[&(room_id, node_id)];
                json!({
                    "index": index,
                    "room_id": room_id,
                    "node_id": node_id,
                    "room": room["name"].as_str(),
                    "node": node["name"].as_str(),
                    "area": self.game_data.room_full_area[&room_id],
                    "plm_addr": plm_ptr,
                })
            })
            .collect();
        Ok(json!({
            "version": VERSION,
            "items": self.game_data.item_isv.keys,
            "item_locations": locations,
        }))
    }

    fn upgrade(&self, req: &Value) -> Result<Value> {
        let (settings, _) = try_upgrade_settings(req["settings"].to_string(), &self.preset_data, true)?;
        Ok(json!({ "settings": serde_json::from_str::<Value>(&settings)? }))
    }

    /// The vanilla map, and the map pools found in `maps_dir` or `<data>/maps` (`tools/fetch_data.py --maps`).
    fn map_repository(&self, maps_dir: Option<&Path>) -> Result<OfflineMapRepository> {
        let mut pools: Vec<(&str, PathBuf)> = vec![("Vanilla", PathBuf::from("../maps/vanilla"))];
        let dirs = maps_dir.into_iter().chain([Path::new("../maps")]);
        for dir in dirs {
            for (layout, pool) in [
                ("Small", "v119-small-avro"),
                ("Standard", "v119-standard-avro"),
                ("Wild", "v119-wild-avro"),
            ] {
                if dir.join(pool).is_dir() && !pools.iter().any(|(l, _)| *l == layout) {
                    pools.push((layout, dir.join(pool)));
                }
            }
        }
        OfflineMapRepository::new(pools.iter().map(|(l, p)| (*l, p.as_path())).collect())
    }

    /// The website's randomization loop (maprando-web `handle_randomize_request`), with our seed and no timeout.
    fn randomize(&self, req: &Value) -> Result<Value> {
        let settings: RandomizerSettings = serde_json::from_value(req["settings"].clone())
            .context("settings are not upgraded Map Rando settings (run `upgrade` first)")?;
        let random_seed = req["seed"].as_u64().context("seed must be an unsigned integer")? as usize;
        let maps_dir = req["maps_dir"].as_str().map(PathBuf::from);
        let repository = self.map_repository(maps_dir.as_deref())?;
        let game_data = &self.game_data;

        let mut rng_seed = [0u8; 32];
        rng_seed[..8].copy_from_slice(&random_seed.to_le_bytes());
        let mut rng = rand::rngs::StdRng::from_seed(rng_seed);
        let difficulty_tiers = get_difficulty_tiers(
            &settings,
            &self.preset_data.difficulty_tiers,
            game_data,
            &self.preset_data.tech_by_difficulty["Implicit"],
            &self.preset_data.notables_by_difficulty["Implicit"],
        );
        let base_links = filter_links(&game_data.links, game_data, &difficulty_tiers[0]);
        let base_links_data = LinksDataGroup::new(base_links, game_data.vertex_isv.keys.len(), 0);
        let mut map_settings = MapSettings::from_map_layout(&settings.map_layout)?;
        map_settings.area_assignment_base_order = settings.other_settings.area_assignment.base_order;
        let requires_area_assignment = repository.requires_area_assignment(map_settings);
        let attempts_per_map =
            if settings.start_location_settings.mode == StartLocationMode::Random { 10 } else { 1 };

        let mut attempt_num = 0;
        let mut map_batch: Vec<Map> = vec![];
        let mut last_error = String::from("no attempt made");
        for _ in 0..MAX_ATTEMPTS / attempts_per_map {
            let map_seed = (rng.next_u64() & 0xFFFFFFFF) as usize;
            let door_seed = (rng.next_u64() & 0xFFFFFFFF) as usize;
            if map_batch.is_empty() {
                map_batch = repository.get_map_batch(map_seed, map_settings, game_data)?;
            }
            let mut map = map_batch.pop().context("empty map batch")?;
            if requires_area_assignment && !assign_map_areas(&mut map, &settings, map_seed, game_data) {
                continue;
            }
            let objectives = get_objectives(&settings, Some(&map), game_data, &mut rng);
            let locked_doors = randomize_doors(game_data, &map, &settings, &objectives, door_seed);
            let randomizer = Randomizer::new(
                &map,
                &locked_doors,
                objectives,
                &settings,
                &difficulty_tiers,
                game_data,
                &base_links_data,
                &mut rng,
            );
            for _ in 0..attempts_per_map {
                let item_seed = (rng.next_u64() & 0xFFFFFFFF) as usize;
                attempt_num += 1;
                match randomizer.randomize(attempt_num, item_seed, random_seed, true) {
                    Ok((randomization, spoiler)) => {
                        return Ok(json!({
                            "seed_hash": seed_hash(randomization.display_seed),
                            "randomization": randomization,
                            "spoiler": {
                                "summary": spoiler.summary,
                                "objectives": spoiler.objectives,
                                "start_location": spoiler.start_location,
                                "hub_location_name": spoiler.hub_location_name,
                            },
                        }));
                    }
                    Err(e) => last_error = e.to_string(),
                }
            }
        }
        bail!("randomization failed after {attempt_num} attempts (last: {last_error})")
    }

    fn rom(&self, req: &Value) -> Result<Value> {
        let settings: RandomizerSettings = serde_json::from_value(req["settings"].clone())?;
        let randomization: Randomization = serde_json::from_value(req["randomization"].clone())?;
        let rom_path = PathBuf::from(req["rom"].as_str().context("rom must be a path")?);
        let out_path = PathBuf::from(req["out"].as_str().context("out must be a path")?);
        let mut base_rom = Rom::load(&rom_path)?;
        base_rom.data.resize(0x400000, 0);
        let sprites = [SamusSpriteCategory {
            category_name: "default".to_string(),
            sprites: vec![SamusSpriteInfo {
                name: "samus_vanilla".to_string(),
                display_name: "Samus".to_string(),
                credits_name: None,
                authors: vec!["Nintendo".to_string()],
            }],
        }];
        let rom = make_rom(
            &base_rom,
            &settings,
            &CustomizeSettings::default(),
            &randomization,
            &self.game_data,
            &sprites,
            &[],
        )?;
        rom.save(&out_path)?;
        Ok(json!({}))
    }
}

/// The seed name shown on the title screen (maprando-web `get_seed_hash`).
fn seed_hash(display_seed: usize) -> String {
    const ENEMIES: [&str; 32] = [
        "GEEMER", "RIPPER", "ATOMIC", "POWAMP", "SCISER", "NAMIHE", "PUROMI", "ALCOON", "BEETOM",
        "OWTCH", "ZEBBO", "ZEELA", "HOLTZ", "VIOLA", "WAVER", "RINKA", "BOYON", "CHOOT", "KAGO",
        "SKREE", "COVERN", "EVIR", "TATORI", "OUM", "PUYO", "YARD", "ZOA", "FUNE", "GAMET",
        "GERUTA", "SOVA", "BULL",
    ];
    (display_seed as u32)
        .to_le_bytes()
        .iter()
        .map(|&i| ENEMIES[i as usize % 32])
        .collect::<Vec<_>>()
        .join(" ")
}

fn run(args: &[String]) -> Result<Value> {
    let (data, command) = match args {
        [flag, data, command] if flag == "--data" => (PathBuf::from(data), command.as_str()),
        _ => bail!("usage: smmr-engine --data <dir> <info|upgrade|randomize|rom>"),
    };
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input)?;
    let req: Value = if input.trim().is_empty() { json!({}) } else { serde_json::from_str(&input)? };
    // Paths in the request are resolved by the caller (absolute) before we change directory.
    std::env::set_current_dir(data.join("rust"))
        .with_context(|| format!("{} is not a Map Rando data directory", data.display()))?;
    let engine = Engine::load()?;
    match command {
        "info" => engine.info(),
        "upgrade" => engine.upgrade(&req),
        "randomize" => engine.randomize(&req),
        "rom" => engine.rom(&req),
        _ => bail!("unknown command {command}"),
    }
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("warn")).init();
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(result) => println!("{}", json!({ "ok": result })),
        Err(e) => {
            println!("{}", json!({ "error": format!("{e:#}") }));
            std::process::exit(1);
        }
    }
}
