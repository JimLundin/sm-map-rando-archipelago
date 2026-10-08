//! `smmr-engine`: Map Rando (our fork, ADR 0005) behind a JSON protocol.
//!
//! Usage: `smmr-engine --data <MapRandomizer checkout or data copy> <command>`
//! The request is a JSON object on stdin, the response a JSON object on a stdout line that starts with the byte 1E
//! (Map Rando prints progress to stdout too): `{"ok": <result>}`, or `{"error": "<message>"}` with exit code 1.
//! `serve` loads Map Rando's data once, then answers requests `{"command": ..., ...}`, one per line, until stdin ends.
//!
//! Commands:
//! - `info`: the item locations, items and version (stable facts the world is built from)
//! - `upgrade`: `{settings}` → `{settings}`, with presets applied and older formats upgraded
//! - `randomize`: `{settings, seed, maps_dir?}` → `{randomization, spoiler, seed_hash}`: Map Rando's own placement
//! - `world`: `{settings, seed, maps_dir?}` → `{world, seed_hash}`: everything but the item placement (`world.rs`)
//! - `reach`: `{settings, world, inventories: [{item: count}]}` → `[{locations, one_way, flags, beatable}]`: what each
//!   set of collected items (on top of the starting items) makes reachable
//! - `open`: `{settings, world}` → `{session}`, then `reach` with `{session, inventories}`: the world's logic set up
//!   once (in `serve`), for many queries
//! - `rom`: `{settings, randomization, rom, out}` or `{settings, world, item_placement, foreign_items, rom, out}` → `{}`;
//!   writes Map Rando's ROM to `out`
//!
//! Map Rando reads its data from paths relative to `<data>/rust`, so the engine changes directory there first. It is
//! its own process, so this doesn't affect the caller.

mod world;

use anyhow::{Context, Result, bail};
use maprando::customize::CustomizeSettings;
use maprando::customize::samus_sprite::{SamusSpriteCategory, SamusSpriteInfo};
use maprando::difficulty::{get_full_global, get_link_difficulty_length};
use maprando::map_repository::{MapRepository, MapSettings, OfflineMapRepository};
use maprando::patch::{Rom, make_rom};
use maprando::preset::PresetData;
use maprando::randomize::escape_timer::compute_escape_data;
use maprando::randomize::{
    DifficultyConfig, ForeignItem, Randomization, Randomizer, TraverserPair, assign_map_areas, filter_links,
    get_difficulty_tiers, get_objectives, make_locked_door_data, randomize_doors,
};
use maprando::settings::{RandomizerSettings, SaveAnimals, StartLocationMode, try_upgrade_settings};
use maprando::traverse::Traverser;
use maprando_game::{GameData, Item, LinksDataGroup, Map};
use maprando_logic::LocalState;
use rand::{Rng, RngCore, SeedableRng};
use world::World;
use serde_json::{Value, json};
use std::io::{BufRead, Read, Write};
use std::path::{Path, PathBuf};

const VERSION: usize = include!("../../MapRandomizer/rust/VERSION");
const MAX_ATTEMPTS: usize = 2000;
/// The map pool directory (and download name, see maprando's scripts/download_data.sh) of each map layout.
const MAP_POOLS: [(&str, &str); 3] = [
    ("Small", "v119-small-avro"),
    ("Standard", "v119-standard-avro"),
    ("Wild", "v119-wild-avro"),
];

struct Engine {
    game_data: GameData,
    preset_data: PresetData,
    sessions: std::cell::RefCell<Vec<Session>>,
}

/// A world's logic, set up once for many `reach` queries. Its data lives as long as the process (`serve` serves one
/// generation).
struct Session {
    world: &'static World,
    randomizer: Randomizer<'static>,
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
        Ok(Engine { game_data, preset_data, sessions: Default::default() })
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
        let p = &self.preset_data;
        let names = |presets: Vec<Option<String>>| presets.into_iter().flatten().collect::<Vec<_>>();
        Ok(json!({
            "version": VERSION,
            "items": self.game_data.item_isv.keys,
            "item_locations": locations,
            "map_pools": MAP_POOLS.iter().map(|(l, p)| (l.to_string(), json!(p))).collect::<serde_json::Map<_, _>>(),
            // Each settings category's preset names, in Map Rando's (website) order.
            "category_presets": {
                "skill_assumption_settings": names(p.skill_presets.iter().map(|x| x.preset.clone()).collect()),
                "item_progression_settings":
                    names(p.item_progression_presets.iter().map(|x| x.preset.clone()).collect()),
                "quality_of_life_settings":
                    names(p.quality_of_life_presets.iter().map(|x| x.preset.clone()).collect()),
                "objective_settings": names(p.objective_presets.iter().map(|x| x.preset.clone()).collect()),
                "doors_settings": names(p.doors_presets.iter().map(|x| x.preset.clone()).collect()),
            },
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
            for (layout, pool) in MAP_POOLS {
                if dir.join(pool).is_dir() && !pools.iter().any(|(l, _)| *l == layout) {
                    pools.push((layout, dir.join(pool)));
                }
            }
        }
        OfflineMapRepository::new(pools.iter().map(|(l, p)| (*l, p.as_path())).collect())
    }

    /// The settings' difficulty tiers and the links of their logic.
    fn rules(&self, settings: &RandomizerSettings) -> (Vec<DifficultyConfig>, LinksDataGroup) {
        let game_data = &self.game_data;
        let difficulty_tiers = get_difficulty_tiers(
            settings,
            &self.preset_data.difficulty_tiers,
            game_data,
            &self.preset_data.tech_by_difficulty["Implicit"],
            &self.preset_data.notables_by_difficulty["Implicit"],
        );
        let base_links = filter_links(&game_data.links, game_data, &difficulty_tiers[0]);
        let base_links_data = LinksDataGroup::new(base_links, game_data.vertex_isv.keys.len(), 0);
        (difficulty_tiers, base_links_data)
    }

    /// The website's randomization loop (maprando-web `handle_randomize_request`), with our seed and no timeout.
    fn randomize(&self, req: &Value) -> Result<Value> {
        let settings = parse_settings(req)?;
        let random_seed = req["seed"].as_u64().context("seed must be an unsigned integer")? as usize;
        let maps_dir = req["maps_dir"].as_str().map(PathBuf::from);
        let repository = self.map_repository(maps_dir.as_deref())?;
        let game_data = &self.game_data;

        let mut rng = seeded_rng(random_seed);
        let (difficulty_tiers, base_links_data) = self.rules(&settings);
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
                        // The hub: where the route from the start ends (or the start, if there's no route).
                        let hub = match spoiler.hub_obtain_route.last() {
                            Some(entry) => (entry.room_id, entry.to_node_id),
                            None => (randomization.start_location.room_id, randomization.start_location.node_id),
                        };
                        return Ok(json!({
                            "seed_hash": seed_hash(randomization.display_seed),
                            "randomization": randomization,
                            "spoiler": {
                                "summary": spoiler.summary,
                                "objectives": spoiler.objectives,
                                "start_location": spoiler.start_location,
                                "hub_location_name": spoiler.hub_location_name,
                                "hub": hub,
                            },
                        }));
                    }
                    Err(e) => last_error = e.to_string(),
                }
            }
        }
        bail!("randomization failed after {attempt_num} attempts (last: {last_error})")
    }

    /// The randomization loop up to the item placement: the map, the doors, the objectives and the start location,
    /// checked to be a world items can be placed in (`world::check`).
    fn world(&self, req: &Value) -> Result<Value> {
        let settings = parse_settings(req)?;
        let random_seed = req["seed"].as_u64().context("seed must be an unsigned integer")? as usize;
        let maps_dir = req["maps_dir"].as_str().map(PathBuf::from);
        let repository = self.map_repository(maps_dir.as_deref())?;
        let game_data = &self.game_data;
        let mut rng = seeded_rng(random_seed);
        let (difficulty_tiers, base_links_data) = self.rules(&settings);
        let mut map_settings = MapSettings::from_map_layout(&settings.map_layout)?;
        map_settings.area_assignment_base_order = settings.other_settings.area_assignment.base_order;
        let requires_area_assignment = repository.requires_area_assignment(map_settings);
        let attempts_per_map =
            if settings.start_location_settings.mode == StartLocationMode::Random { 10 } else { 1 };
        let start_attempts = if game_data.start_locations.len() > 1
            && settings.start_location_settings.mode != StartLocationMode::Custom
        {
            10
        } else {
            1
        };

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
                objectives.clone(),
                &settings,
                &difficulty_tiers,
                game_data,
                &base_links_data,
                &mut rng,
            );
            if settings.start_location_settings.mode == StartLocationMode::Escape {
                // Samus starts in the escape with every item: Map Rando places nothing (`dummy_randomize`).
                let (randomization, _) = match randomizer.dummy_randomize(random_seed, random_seed, &mut rng) {
                    Ok(x) => x,
                    Err(e) => {
                        last_error = format!("escape: {e}");
                        continue;
                    }
                };
                let start = randomization.start_location;
                let locations = world::locations(&randomizer);
                let world = World {
                    map: map.clone(),
                    locked_doors: locked_doors.locked_doors.clone(),
                    objectives: objectives.clone(),
                    hub: (start.room_id, start.node_id),
                    start_location: start,
                    save_animals: randomization.save_animals,
                    escape_time_seconds: randomization.escape_time_seconds,
                    toilet_intersections: randomizer.toilet_intersections.clone(),
                    seed: random_seed,
                    display_seed: random_seed,
                };
                return Ok(json!({
                    "world": world,
                    "seed_hash": seed_hash(random_seed),
                    "pool": { "Nothing": locations.len() },
                    "locations": locations,
                    "starting_items": {},
                    "escape": true,
                }));
            }
            for _ in 0..attempts_per_map {
                attempt_num += 1;
                // As Randomizer::randomize: traversers from the initial state, then the start location.
                let global = world::global_state(&randomizer, &[]);
                let local = LocalState::empty();
                let num_vertices = game_data.vertex_isv.keys.len();
                let mut traversers = TraverserPair {
                    forward: Traverser::new(num_vertices, false, local, &global),
                    reverse: Traverser::new(num_vertices, true, local, &global),
                };
                let start = match randomizer.determine_start_location(
                    attempt_num,
                    start_attempts,
                    &mut rng,
                    &mut traversers,
                ) {
                    Ok(start) => start,
                    Err(e) => {
                        last_error = e.to_string();
                        continue;
                    }
                };
                let save_animals = match settings.save_animals {
                    SaveAnimals::Random if rng.gen_bool(0.5) => SaveAnimals::Yes,
                    SaveAnimals::Random => SaveAnimals::No,
                    other => other,
                };
                let escape = match compute_escape_data(
                    game_data,
                    &map,
                    &settings,
                    save_animals != SaveAnimals::No,
                    &difficulty_tiers[0],
                ) {
                    Ok(escape) => escape,
                    Err(e) => {
                        last_error = format!("escape: {e}");
                        continue;
                    }
                };
                let world = World {
                    map: map.clone(),
                    locked_doors: locked_doors.locked_doors.clone(),
                    objectives: objectives.clone(),
                    start_location: start.start_location,
                    hub: (start.hub_location.room_id, start.hub_location.node_id),
                    save_animals,
                    escape_time_seconds: escape.final_time_seconds,
                    toilet_intersections: randomizer.toilet_intersections.clone(),
                    seed: random_seed,
                    display_seed: random_seed,
                };
                match world::check(&randomizer, &world) {
                    Ok(()) => {
                        let pool = world::pool(&randomizer);
                        return Ok(json!({
                            "world": world,
                            "seed_hash": seed_hash(random_seed),
                            // The items to place, and where: the item locations in the map's rooms.
                            "pool": pool.iter().map(|(item, count)| (format!("{item:?}"), json!(count)))
                                .collect::<serde_json::Map<_, _>>(),
                            "locations": world::locations(&randomizer),
                            "starting_items": randomizer.starting_items.iter()
                                .map(|x| (format!("{:?}", x.item), json!(x.count)))
                                .collect::<serde_json::Map<_, _>>(),
                            "escape": false,
                        }));
                    }
                    Err(e) => last_error = format!("[attempt {attempt_num}] {e}"),
                }
            }
        }
        bail!("no world found after {attempt_num} attempts (last: {last_error})")
    }

    /// Runs `f` with the Randomizer of `world` (which Map Rando's traversal works through).
    fn with_randomizer<T>(&self, settings: &RandomizerSettings, world: &World, f: impl FnOnce(&Randomizer) -> T) -> T {
        let (difficulty_tiers, base_links_data) = self.rules(settings);
        let locked_door_data = make_locked_door_data(world.locked_doors.clone(), &self.game_data);
        let randomizer = Randomizer::new(
            &world.map,
            &locked_door_data,
            world.objectives.clone(),
            settings,
            &difficulty_tiers,
            &self.game_data,
            &base_links_data,
            &mut seeded_rng(0),
        );
        f(&randomizer)
    }

    /// Sets up a world's logic for `reach {session, inventories}`.
    fn open(&'static self, req: &Value) -> Result<Value> {
        let settings: &'static RandomizerSettings = Box::leak(Box::new(parse_settings(req)?));
        let world: &'static World =
            Box::leak(Box::new(serde_json::from_value(req["world"].clone()).context("world")?));
        let (difficulty_tiers, base_links_data) = self.rules(settings);
        let difficulty_tiers: &'static [DifficultyConfig] = Box::leak(difficulty_tiers.into_boxed_slice());
        let base_links_data: &'static LinksDataGroup = Box::leak(Box::new(base_links_data));
        let locked_door_data = Box::leak(Box::new(make_locked_door_data(world.locked_doors.clone(), &self.game_data)));
        let randomizer = Randomizer::new(
            &world.map,
            locked_door_data,
            world.objectives.clone(),
            settings,
            difficulty_tiers,
            &self.game_data,
            base_links_data,
            &mut seeded_rng(0),
        );
        let mut sessions = self.sessions.borrow_mut();
        sessions.push(Session { world, randomizer });
        Ok(json!({ "session": sessions.len() - 1 }))
    }

    fn reach(&self, req: &Value) -> Result<Value> {
        let inventories = parse_inventories(req)?;
        if let Some(session) = req["session"].as_u64() {
            let sessions = self.sessions.borrow();
            let session = sessions.get(session as usize).context("no such session")?;
            return Ok(json!(
                inventories.iter().map(|x| world::reach(&session.randomizer, session.world, x)).collect::<Vec<_>>()
            ));
        }
        let settings = parse_settings(req)?;
        let world: World = serde_json::from_value(req["world"].clone()).context("world")?;
        let chain = req["chain"].as_bool().unwrap_or(false);
        self.with_randomizer(&settings, &world, |randomizer| {
            if chain {
                return Ok(json!(world::reach_chain(randomizer, &world, &inventories)));
            }
            Ok(json!(inventories.iter().map(|x| world::reach(randomizer, &world, x)).collect::<Vec<_>>()))
        })
    }

    fn rom(&self, req: &Value) -> Result<Value> {
        let settings = parse_settings(req)?;
        let randomization: Randomization = if req.get("world").is_some() {
            let world: World = serde_json::from_value(req["world"].clone()).context("world")?;
            let item_placement: Vec<Item> = serde_json::from_value(req["item_placement"].clone())?;
            let foreign_items: Vec<ForeignItem> = serde_json::from_value(req["foreign_items"].clone())?;
            world::randomization(world, item_placement, foreign_items)
        } else {
            serde_json::from_value(req["randomization"].clone())?
        };

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

/// `inventories`: a list of `{item: count}`.
fn parse_inventories(req: &Value) -> Result<Vec<Vec<(Item, usize)>>> {
    let inventories = req["inventories"].as_array().context("inventories must be a list")?;
    inventories
        .iter()
        .map(|inventory| {
            let items = inventory.as_object().context("an inventory is an object {item: count}")?;
            items
                .iter()
                .map(|(name, count)| {
                    let item = Item::try_from(name.as_str()).map_err(|_| anyhow::anyhow!("unknown item {name}"))?;
                    Ok((item, count.as_u64().context("an item count is an unsigned integer")? as usize))
                })
                .collect::<Result<Vec<_>>>()
        })
        .collect()
}

fn parse_settings(req: &Value) -> Result<RandomizerSettings> {
    serde_json::from_value(req["settings"].clone())
        .context("settings are not upgraded Map Rando settings (run `upgrade` first)")
}

fn seeded_rng(seed: usize) -> rand::rngs::StdRng {
    let mut rng_seed = [0u8; 32];
    rng_seed[..8].copy_from_slice(&seed.to_le_bytes());
    rand::rngs::StdRng::from_seed(rng_seed)
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

/// Responses are lines starting with this byte (ASCII record separator): Map Rando prints progress to stdout too.
const RESPONSE: char = '\u{1e}';

fn respond(result: Result<Value>) -> bool {
    let ok = result.is_ok();
    let response = match result {
        Ok(value) => json!({ "ok": value }),
        Err(e) => json!({ "error": format!("{e:#}") }),
    };
    let mut out = std::io::stdout().lock();
    let _ = writeln!(out, "{RESPONSE}{response}");
    let _ = out.flush();
    ok
}

fn dispatch(engine: &'static Engine, command: &str, req: &Value) -> Result<Value> {
    match command {
        "info" => engine.info(),
        "upgrade" => engine.upgrade(req),
        "randomize" => engine.randomize(req),
        "world" => engine.world(req),
        "reach" => engine.reach(req),
        "open" => engine.open(req),
        "rom" => engine.rom(req),
        _ => bail!("unknown command {command}"),
    }
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("warn")).init();
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (data, command) = match args.as_slice() {
        [flag, data, command] if flag == "--data" => (PathBuf::from(data), command.clone()),
        _ => {
            respond(Err(anyhow::anyhow!("usage: smmr-engine --data <dir> <info|upgrade|randomize|world|reach|rom|serve>")));
            std::process::exit(2);
        }
    };
    // Paths in requests are absolute (the caller resolves them), so changing directory doesn't affect them.
    let engine = std::env::set_current_dir(data.join("rust"))
        .with_context(|| format!("{} is not a Map Rando data directory", data.display()))
        .and_then(|_| Engine::load());
    let engine: &'static Engine = match engine {
        Ok(engine) => Box::leak(Box::new(engine)),
        Err(e) => {
            respond(Err(e));
            std::process::exit(1);
        }
    };
    if command == "serve" {
        // One request per line, `{"command": ..., ...}`; one response line each. Ends at the end of stdin.
        for line in std::io::stdin().lock().lines() {
            let Ok(line) = line else { break };
            let result = serde_json::from_str::<Value>(&line).map_err(anyhow::Error::from).and_then(|req| {
                let command = req["command"].as_str().unwrap_or_default().to_string();
                dispatch(engine, &command, &req)
            });
            respond(result);
        }
        return;
    }
    let mut input = String::new();
    let result = std::io::stdin()
        .read_to_string(&mut input)
        .map_err(anyhow::Error::from)
        .and_then(|_| Ok(if input.trim().is_empty() { json!({}) } else { serde_json::from_str(&input)? }))
        .and_then(|req| dispatch(engine, &command, &req));
    if !respond(result) {
        std::process::exit(1);
    }
}
